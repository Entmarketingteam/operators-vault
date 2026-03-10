"""
Hydrate speaker_profiles from people table.
For each person not already in speaker_profiles:
  - Fetch their insight/video mentions from DB
  - Generate bio + company via claude-haiku-4-5
  - Insert into speaker_profiles

Usage:
    doppler run --project ent-agency-automation --config dev -- python3 scripts/hydrate_speakers.py
"""
from __future__ import annotations

import os
import re
import sys
import time

import anthropic
import psycopg2


def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def _get_person_context(cur, person_id: str, name: str) -> str:
    """Gather context about a person from their video appearances and insights."""
    lines: list[str] = []

    # Videos they appeared in
    cur.execute(
        """
        SELECT v.title, v.podcast
        FROM videos v
        JOIN video_people vp ON vp.video_id = v.video_id
        WHERE vp.person_id = %s
        ORDER BY v.published_at DESC NULLS LAST
        LIMIT 10
        """,
        (person_id,),
    )
    for title, podcast in cur.fetchall():
        lines.append(f"- Appeared on: {title} ({podcast})")

    # Insights linked to them (quotes, frameworks)
    cur.execute(
        """
        SELECT i.category, i.title, i.description
        FROM insights i
        JOIN insight_people ip ON ip.insight_id = i.id
        WHERE ip.person_id = %s
        ORDER BY i.created_at DESC
        LIMIT 10
        """,
        (person_id,),
    )
    for category, title, desc in cur.fetchall():
        snippet = (desc or "")[:200].replace("\n", " ")
        lines.append(f"- [{category}] {title}: {snippet}")

    return "\n".join(lines) if lines else f"Speaker: {name}"


def _build_profile_with_haiku(client: anthropic.Anthropic, name: str, context: str) -> dict:
    """Call Claude Haiku to generate bio + company/title for the speaker."""
    prompt = (
        f"You are building a speaker directory for Operators Vault, a DTC (direct-to-consumer) "
        f"operator knowledge base.\n\n"
        f"Speaker name: {name}\n\n"
        f"Context from their vault appearances:\n{context}\n\n"
        f"Based on this context, produce a JSON object with exactly these fields:\n"
        f'  "bio": a 2-3 sentence professional bio\n'
        f'  "company": their primary company or employer (string or null)\n'
        f'  "title": their professional title (string or null)\n'
        f'  "twitter_handle": best-guess Twitter/X handle without @ (string or null)\n\n'
        f"Return ONLY valid JSON. No markdown fences, no explanation."
    )

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        import json
        data = json.loads(raw)
        return {
            "bio": data.get("bio") or None,
            "company": data.get("company") or None,
            "title": data.get("title") or None,
            "twitter_handle": data.get("twitter_handle") or None,
        }
    except Exception as e:
        print(f"    [WARN] Haiku failed for {name}: {e}", flush=True)
        return {"bio": None, "company": None, "title": None, "twitter_handle": None}


def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not db_url:
        print("[ERROR] DATABASE_URL not set", flush=True)
        sys.exit(1)
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY not set", flush=True)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            # Ensure speaker_profiles table exists
            sql_path = os.path.join(os.path.dirname(__file__), "..", "sql", "add_speaker_profiles.sql")
            sql_path = os.path.abspath(sql_path)
            if os.path.exists(sql_path):
                with open(sql_path) as f:
                    migration_sql = f.read()
                for stmt in migration_sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        cur.execute(stmt)
                conn.commit()
                print("[INFO] Migration applied (or already exists)", flush=True)

            # Fetch all people
            cur.execute("SELECT id, name, slug FROM people ORDER BY name")
            all_people = cur.fetchall()
            print(f"[INFO] Found {len(all_people)} people in vault", flush=True)

            # Fetch slugs that already have a bio (non-null)
            cur.execute("SELECT slug FROM speaker_profiles WHERE bio IS NOT NULL AND bio != ''")
            existing_slugs = {r[0] for r in cur.fetchall()}
            print(f"[INFO] {len(existing_slugs)} already hydrated with bios", flush=True)

        hydrated = 0
        skipped = 0

        for person_id, name, person_slug in all_people:
            slug = person_slug or _slugify(name)
            if not slug:
                print(f"  [SKIP] Cannot slugify name: {name!r}", flush=True)
                skipped += 1
                continue

            if slug in existing_slugs:
                print(f"  [SKIP] Already hydrated: {name} ({slug})", flush=True)
                skipped += 1
                continue

            print(f"  [HYDRATE] {name} ({slug}) ...", flush=True)

            with conn.cursor() as cur:
                context = _get_person_context(cur, str(person_id), name)

            profile = _build_profile_with_haiku(client, name, context)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO speaker_profiles (slug, name, bio, twitter_handle, company, title, source)
                    VALUES (%s, %s, %s, %s, %s, %s, 'auto')
                    ON CONFLICT (slug) DO UPDATE SET
                        bio = EXCLUDED.bio,
                        twitter_handle = EXCLUDED.twitter_handle,
                        company = EXCLUDED.company,
                        title = EXCLUDED.title,
                        source = EXCLUDED.source,
                        updated_at = NOW()
                    """,
                    (
                        slug,
                        name,
                        profile["bio"],
                        profile["twitter_handle"],
                        profile["company"],
                        profile["title"],
                    ),
                )
                conn.commit()

            existing_slugs.add(slug)
            hydrated += 1
            print(f"    -> bio={bool(profile['bio'])} company={profile['company']!r}", flush=True)

            # Rate limit: 0.5s between each
            time.sleep(0.5)

        print(
            f"\n[DONE] Hydrated: {hydrated} | Skipped: {skipped} | Total: {len(all_people)}",
            flush=True,
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
