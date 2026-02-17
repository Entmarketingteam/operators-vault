"""
Extract companies/brands from insights and transcripts using LLM.
"""
from __future__ import annotations

import os
import re
from typing import Any


def _slugify(name: str) -> str:
    """Convert company name to URL slug."""
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[-\s]+", "-", s)
    return s.strip("-")


def _anthropic_message(system: str, user: str, model: str = "claude-sonnet-4-5-20250929") -> str:
    try:
        import anthropic
    except ImportError:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    c = anthropic.Anthropic(api_key=api_key)
    r = c.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if r.content and len(r.content) > 0 and hasattr(r.content[0], "text"):
        return r.content[0].text
    return ""


def extract_companies_from_text(text: str) -> list[dict[str, str]]:
    """
    Extract company/brand names from text using LLM.
    Returns list of {name, type} where type is 'brand', 'saas', or 'other'.
    """
    system = (
        "Extract company and brand names mentioned in the text. "
        "Output as JSON array: [{\"name\": \"Company Name\", \"type\": \"brand\"|\"saas\"|\"other\"}]. "
        "Only include actual company/brand names, not generic terms. Output only JSON, no other text."
    )
    user = f"Text:\n{text[:4000]}"
    raw = _anthropic_message(system, user)
    # Parse JSON array
    try:
        import json
        # Extract JSON from markdown code blocks if present
        m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
        companies = json.loads(raw)
        if isinstance(companies, list):
            return [{"name": c.get("name", "").strip(), "type": c.get("type", "other")} for c in companies if c.get("name")]
    except Exception:
        pass
    return []


def ensure_companies(cursor, companies: list[dict[str, str]]) -> dict[str, str]:
    """
    Ensure companies exist in DB. Returns {company_name: company_id}.
    Creates records if missing, generates slugs.
    """
    name_to_id: dict[str, str] = {}
    for comp in companies:
        name = comp.get("name", "").strip()
        if not name or len(name) < 2:
            continue
        comp_type = comp.get("type", "other")
        slug = _slugify(name)
        # Find or create
        cursor.execute("SELECT id FROM companies WHERE name = %s", (name,))
        row = cursor.fetchone()
        if row:
            company_id = str(row[0])
        else:
            cursor.execute(
                "INSERT INTO companies (name, type, slug) VALUES (%s, %s, %s) RETURNING id",
                (name, comp_type, slug),
            )
            company_id = str(cursor.fetchone()[0])
        name_to_id[name] = company_id
    return name_to_id


def link_insights_to_companies(cursor, insight_id: str, companies: list[dict[str, str]]) -> None:
    """Link an insight to companies."""
    name_to_id = ensure_companies(cursor, companies)
    for name, comp_id in name_to_id.items():
        cursor.execute(
            """
            INSERT INTO insight_companies (insight_id, company_id)
            VALUES (%s, %s)
            ON CONFLICT (insight_id, company_id) DO NOTHING
            """,
            (insight_id, comp_id),
        )


def link_video_to_companies(cursor, video_id: str, companies: list[dict[str, str]]) -> None:
    """Link a video to companies."""
    name_to_id = ensure_companies(cursor, companies)
    for name, comp_id in name_to_id.items():
        cursor.execute(
            """
            INSERT INTO video_companies (video_id, company_id)
            VALUES (%s, %s)
            ON CONFLICT (video_id, company_id) DO NOTHING
            """,
            (video_id, comp_id),
        )
