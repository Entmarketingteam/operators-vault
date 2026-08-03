"""
CTC (commonthreadco.com) long-form article ingestion for Operators Vault.

Why this exists
---------------
`taylor_holiday` is the weakest source in the vault per issue — 130 issues / 728
insights (5.6 per issue) against Chase Dimond's 18.9 and Nik Sharma's 38.8, with an
average body of 3,856 chars. That is not a pipeline failure: his *emails* are short
sales copy that drive to the site. The substance — four-quarter accounting, OPEX
floor, unit economics — is published as articles on commonthreadco.com and had never
been ingested.

Articles land in the SAME `newsletters` / `newsletter_insights` tables under the same
`taylor_holiday` slug, distinguished by `newsletters.medium`. Everything downstream
(the weighted `fts` index, rank normalization, the guide/chat source quota, the
InsightModal sibling loader, the speaker-page fallback) already understands
newsletter_insights; a separate `articles` table would mean re-doing all of it for a
document of identical shape.

Probe findings this file encodes (2026-08-02, verified against the live site)
---------------------------------------------------------------------------
1. Enumeration: `sitemap_blogs_1.xml` → 722 article URLs across 13 blog handles.
2. ⚠️ Generic extractors DO NOT work here. `defuddle parse <url> --md` returned 892
   bytes of nav chrome and zero body, and there is NO JSON-LD on any page (0
   `application/ld+json` blocks on both templates). Two hand-written selectors
   resolved 99/99 sampled pages. Do not swap this for a readability library.
3. ⚠️ The `.atom` feed is a SYNC path, never a BACKFILL path: it caps at 30 entries
   and silently ignores pagination — `?page=1`, `?page=2` and `?page=8` returned
   byte-identical 356,076-byte responses. Backfill must walk the sitemap.
4. Article pages carry NO publish date — no `<time>`, no `datetime=`, no
   `article:published_time`. Dates come from the atom feeds where available (true
   publish time, ~30 newest per blog) and fall back to sitemap `<lastmod>`, which is
   an *update* time. See `build_date_index()`.
5. Half the corpus is the CTC podcast archive (`ecommerce-playbook`, `dtc-hotline`)
   at ~1,122 chars of show notes. Those are classified `shownotes` and never stored —
   307+ thin rows would dilute the source without adding operator substance.
"""
from __future__ import annotations

import gzip
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITEMAP_URL = "https://commonthreadco.com/sitemap_blogs_1.xml"
SITE_HOST = "commonthreadco.com"

# Articles merge into Taylor's existing source so the two media meet on his speaker
# page and in per-source counts. `medium` carries the distinction where it matters.
SOURCE_SLUG = "taylor_holiday"
SOURCE_AUTHOR = "Taylor Holiday / CTC"

MEDIUM_EMAIL = "email"
MEDIUM_ARTICLE = "article"
MEDIUM_ARTICLE_NEWS = "article_news"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Template detection is the real gate — podcast show notes are excluded by template,
# not by length, so this floor exists only to catch extraction FAILURE.
#
# It was 1000 and that was wrong: CTC's older coachs-corner posts are genuinely short
# (`marginal-frontier` 848 chars, `can-you-say-dpa` 772) and `marginal-frontier` is
# exactly the Taylor material this whole job exists to capture. A length floor tuned
# to exclude show notes silently deletes his short posts.
MIN_ARTICLE_CHARS = 400

# An article-template page yielding less than this almost certainly means the selectors
# missed, not that the post is short. Those are QUARANTINED and surfaced in the run
# handoff — never silently skipped (traps.md T4: quarantine what you can't classify).
EXTRACTION_FAILURE_CHARS = 250


class RateLimited(Exception):
    """CTC returned 429. Burst-based: the site tolerates a low steady rate and blocks
    bursts (measured 2026-08-02 — 6 concurrent requests tripped it, and it escalates
    from 429 to refusing connections entirely). Callers must back off, not retry hot."""


# ── Fetch ──────────────────────────────────────────────────────────────────────

def fetch(url: str, timeout: int = 45) -> str:
    """GET a URL as text. Raises so the caller's retry policy can classify the failure.

    429 is raised as `RateLimited` specifically: it is not a per-item fault (the next
    URL fails identically), so a caller must slow the whole run down rather than
    quarantine the item.
    """
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(f"429 on {url}") from e
        raise
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


# Full-jitter backoff, per escalation.md. CTC sends no Retry-After header, so the
# schedule is ours to pick — and it escalates from 429 to refusing connections
# outright, so the first wait is deliberately long rather than the usual 2s.
_BACKOFF_BASE, _BACKOFF_CAP, _BACKOFF_ATTEMPTS = 8, 300, 5


def fetch_polite(url: str, attempts: int = _BACKOFF_ATTEMPTS, timeout: int = 45) -> str:
    """`fetch` with backoff on 429 only.

    429 here is a whole-run condition, not a per-item fault: while it is firing every
    URL fails identically, so retrying the same URL IS the correct behaviour and
    quarantining the item would be wrong. Non-429 errors are raised immediately so the
    caller can classify them per item.
    """
    import random
    import time

    last: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch(url, timeout=timeout)
        except RateLimited as e:
            last = e
            if attempt == attempts - 1:
                break
            wait = min(_BACKOFF_CAP, _BACKOFF_BASE * (2 ** attempt) * (0.5 + random.random()))
            time.sleep(wait)
    assert last is not None
    raise last


# ── Enumeration ────────────────────────────────────────────────────────────────

def enumerate_articles() -> list[dict]:
    """All article URLs from the blog sitemap.

    Returns [{url, blog, handle, lastmod}]. Sitemap entries with fewer than two path
    segments after /blogs/ are blog index pages, not articles, and are dropped.
    """
    xml = fetch_polite(SITEMAP_URL, timeout=90)
    out = []
    for m in re.finditer(r"<url>(.*?)</url>", xml, re.S):
        block = m.group(1)
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        if not loc:
            continue
        url = loc.group(1).strip()
        if "/blogs/" not in url:
            continue
        parts = url.split("/blogs/", 1)[1].split("/")
        if len(parts) < 2 or not parts[1]:
            continue
        lastmod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        out.append({
            "url": url,
            "blog": parts[0],
            "handle": parts[1],
            "lastmod": lastmod.group(1).strip() if lastmod else None,
        })
    return out


def build_date_index(blogs: list[str]) -> dict[str, str]:
    """URL -> true published timestamp, from each blog's atom feed.

    The feeds carry only the ~30 newest entries per blog and ignore pagination, so
    this covers recent articles only. Everything older falls back to sitemap
    `<lastmod>`, which is an UPDATE time — a 2020 article edited in 2026 will sort as
    2026. Accepted: the alternative is no date at all, and the newest articles (the
    ones that sort to the top) are exactly the ones this resolves correctly.
    """
    index: dict[str, str] = {}
    for blog in blogs:
        try:
            xml = fetch_polite(f"https://{SITE_HOST}/blogs/{blog}.atom", timeout=45)
        except Exception:
            continue
        for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
            link = re.search(r'<link[^>]*href="([^"]+)"', entry)
            pub = re.search(r"<published>([^<]+)</published>", entry)
            if link and pub:
                index[link.group(1).strip()] = pub.group(1).strip()
    return index


# ── Body extraction ────────────────────────────────────────────────────────────

# Ordered by specificity. `bc-content` wraps long-form articles; `description` wraps
# podcast episode show notes. Both were confirmed on 99/99 sampled pages.
_BODY_WRAPPERS = ("bc-content", "description", "rte", "article-body")


def _scan_div(html_text: str, start: int) -> str:
    """Return the inner HTML of the div opening at `start`, matching nesting depth."""
    depth = 1
    for m in re.finditer(r"<(/?)div\b", html_text[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html_text[start:start + m.start()]
    return html_text[start:]


def _to_text(fragment: str) -> str:
    """HTML fragment -> readable text, preserving paragraph breaks."""
    import html as _html

    fragment = re.sub(r"<(style|script)[^>]*>[\s\S]*?</\1>", "", fragment, flags=re.I)
    fragment = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = _html.unescape(fragment)
    fragment = re.sub(r"[ \t]+", " ", fragment)
    fragment = re.sub(r"\n{3,}", "\n\n", fragment)
    return fragment.strip()


def detect_template(html_text: str) -> str:
    """'podcast' | 'article'. Read off the theme's own body class."""
    m = re.search(r'class="blog-article-bg ([^"]*)"', html_text)
    return "podcast" if (m and "podcast" in m.group(1)) else "article"


def extract_title(html_text: str) -> str:
    import html as _html

    m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html_text)
    if not m:
        m = re.search(r'<meta[^>]*content="([^"]*)"[^>]*property="og:title"', html_text)
    if not m:
        m = re.search(r"<title>(.*?)</title>", html_text, re.S)
    return _html.unescape(m.group(1)).strip() if m else ""


def extract_body(html_text: str) -> str:
    """Longest text block across the known wrappers. Empty string if none match."""
    best = ""
    for wrapper in _BODY_WRAPPERS:
        pattern = r'<div[^>]*class="[^"]*\b' + re.escape(wrapper) + r'\b[^"]*"[^>]*>'
        for m in re.finditer(pattern, html_text):
            text = _to_text(_scan_div(html_text, m.end()))
            if len(text) > len(best):
                best = text
    return best


# ── Classification gate ────────────────────────────────────────────────────────

# Title shapes that only ever appear on the AI-written platform-news roundups
# ("This Week in Ad Platforms: Snapchat Opens to AI Agents…"). ~13-25% of recent
# coachs-corner. These are not dropped — they are stored as `article_news` so search
# can down-weight them, because a few carry real operator relevance
# (e.g. "Google's July 2026 Demand Gen Drop: Checkout Links, tROAS Upgrades").
_NEWS_MARKERS = (
    "this week in ad platforms",
    "what ecommerce brands need to know",
    "new terms of service",
    "is live:",
    " announces ",
    " launches ",
    " opens to ",
    " rolls out ",
    "summit recap",
    "what the ",
)


def classify_article(title: str, body: str, template: str) -> str:
    """'shownotes' | 'extraction_failed' | 'thin' | 'article_news' | 'substantive'.

    Runs BEFORE extraction, mirroring `newsletter_ingestor.is_promo_only()`. A
    zero-insight extraction result is not an acceptable substitute: it costs a full
    multi-chunk Claude pass per item and cannot distinguish "thin" from "extraction
    failed", so the two get conflated in coverage metrics — the exact silent failure
    the newsletter layer spent three months in. Those two outcomes are separate
    verdicts here for that reason: `thin` is a real short post, `extraction_failed`
    means the selectors missed and a human should look.
    """
    if template == "podcast":
        return "shownotes"
    if len(body) < EXTRACTION_FAILURE_CHARS:
        return "extraction_failed"
    if len(body) < MIN_ARTICLE_CHARS:
        return "thin"

    blob = f"{title}\n{body[:2000]}".lower()
    if not any(marker in blob for marker in _NEWS_MARKERS):
        return "substantive"

    # A marker fired — ask the model, because these titles overlap with genuinely
    # useful platform-change explainers. Fail OPEN to substantive: mislabelling a
    # real article as news costs it search rank, which is worse than the reverse.
    try:
        from insight_extractor import _anthropic_message

        system = "You classify ecommerce industry content. Answer with exactly one word."
        user = (
            "Is this article a NEWS roundup — reporting what a platform announced, "
            "recapping an event, or summarising this week's updates — or is it an "
            "EVERGREEN operator piece: a framework, unit-economics teardown, case "
            "study, or point of view that stays useful months from now?\n\n"
            "Answer NEWS or EVERGREEN.\n\n"
            "An article that explains what a platform change MEANS for how operators "
            "should act is EVERGREEN. Pure 'here is what was announced' is NEWS.\n\n"
            f"TITLE: {title}\n\nBODY:\n{body[:4000]}"
        )
        verdict = (_anthropic_message(system, user) or "").strip().upper()
    except Exception:
        return "substantive"
    return "article_news" if verdict.startswith("NEWS") else "substantive"


# ── Single-article pipeline ────────────────────────────────────────────────────

def parse_article(url: str, html_text: str, published_at: str | None = None) -> dict:
    """HTML -> the row shape `/ingest-article` and the backfill both store."""
    template = detect_template(html_text)
    title = extract_title(html_text)
    body = extract_body(html_text)
    kind = classify_article(title, body, template)
    return {
        "url": url,
        "title": title,
        "body_text": body,
        "template": template,
        "kind": kind,
        "chars": len(body),
        "published_at": published_at,
        "medium": MEDIUM_ARTICLE_NEWS if kind == "article_news" else MEDIUM_ARTICLE,
        "source": SOURCE_SLUG,
        "author": SOURCE_AUTHOR,
    }


def extract_article_insights(text: str, title: str = "") -> list[dict[str, str]]:
    """Extract insights with the article's provenance stated up front.

    Reuses the newsletters prompt rather than forking it — but that prompt opens by
    naming five newsletter authors and asks for "quotes from the author", and a CTC
    article carries no From header to tell the model who wrote it. Run unframed, it
    invents attributions: a real 2026-08-02 test on "26 Predictions for Commerce"
    produced quote titles reading "(Operators Newsletter author)", "Author", and
    "Newsletter author, on nearshoring to Mexico". Naming the publication and author
    in the content itself fixes it without duplicating a 98-line prompt that would
    then drift out of sync.
    """
    from insight_extractor import (
        _anthropic_message, _load_prompt, parse_extract_insights_output,
    )

    tpl = _load_prompt("extract_insights_system", prompt_set="newsletters")
    if not tpl:
        return []
    framed = (
        "[SOURCE: a long-form article published by Common Thread Collective (CTC) at "
        "commonthreadco.com — not an email newsletter. The author is Taylor Holiday / "
        "CTC unless the text names someone else. Attribute quotes to the person the "
        "text names, or to Taylor Holiday when unattributed. Never attribute anything "
        "to a 'newsletter author' or to another newsletter's author.]\n\n"
        f"ARTICLE TITLE: {title}\n\n{text}"
    )
    user = tpl.replace("{transcript}", framed)
    system = "You are an expert DTC and eCommerce operator analyst. Follow the instructions exactly."
    raw = _anthropic_message(system, user, model="claude-haiku-4-5-20251001")
    return parse_extract_insights_output(raw)


def source_from_url(url: str) -> str | None:
    """Derive the source slug from the URL host — never from a caller-supplied field.

    Caller-supplied attribution is what filed every newsletter from 2026-05-09 on as
    `nik_sharma` (CLAUDE.md defect #2). Same rule applies here from day one.
    """
    m = re.match(r"https?://(?:www\.)?([^/]+)/", url)
    if not m:
        return None
    return SOURCE_SLUG if m.group(1).lower() == SITE_HOST else None


def fetch_and_parse(url: str, published_at: str | None = None) -> dict:
    return parse_article(url, fetch_polite(url), published_at)


# ── Sync path (atom feeds) ─────────────────────────────────────────────────────

def fetch_recent(blog: str) -> list[dict]:
    """Newest entries for one blog, with full body straight from the atom feed.

    The feed's `<content type="html">` is the complete article, so the daily sync
    never needs to fetch the page itself. 30 entries max, pagination ignored.
    """
    import html as _html

    xml = fetch_polite(f"https://{SITE_HOST}/blogs/{blog}.atom", timeout=45)
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        link = re.search(r'<link[^>]*href="([^"]+)"', entry)
        pub = re.search(r"<published>([^<]+)</published>", entry)
        title = re.search(r"<title>(.*?)</title>", entry, re.S)
        content = re.search(r"<content[^>]*>(.*?)</content>", entry, re.S)
        if not (link and content):
            continue
        raw = content.group(1)
        cdata = re.search(r"<!\[CDATA\[(.*?)\]\]>", raw, re.S)
        body_html = cdata.group(1) if cdata else _html.unescape(raw)
        body = _to_text(body_html)
        name = _html.unescape(title.group(1)).strip() if title else ""
        kind = classify_article(name, body, "article")
        out.append({
            "url": link.group(1).strip(),
            "title": name,
            "body_text": body,
            "template": "article",
            "kind": kind,
            "chars": len(body),
            "published_at": pub.group(1).strip() if pub else None,
            "medium": MEDIUM_ARTICLE_NEWS if kind == "article_news" else MEDIUM_ARTICLE,
            "source": SOURCE_SLUG,
            "author": SOURCE_AUTHOR,
            "blog": blog,
        })
    return out


# ── Storage ────────────────────────────────────────────────────────────────────

def upsert_article(row: dict) -> tuple[str, bool]:
    """Insert/refresh one article. Returns (newsletter_id, needs_extraction).

    `newsletters.email_id` is UNIQUE, so the canonical URL goes there and carries
    idempotency for free — re-running the backfill cannot duplicate a row.
    """
    import uuid

    from newsletter_ingestor import _db_conn

    conn = _db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, processed, length(body_text) FROM newsletters WHERE email_id = %s",
                (row["url"],),
            )
            existing = cur.fetchone()
            if existing:
                nl_id, processed, body_len = str(existing[0]), existing[1], (existing[2] or 0)
                # Only rewrite when the article genuinely grew (CTC edits posts).
                if len(row["body_text"]) > body_len * 1.5 and len(row["body_text"]) > 500:
                    cur.execute(
                        "UPDATE newsletters SET body_text = %s, processed = FALSE, medium = %s "
                        "WHERE id = %s",
                        (row["body_text"], row["medium"], nl_id),
                    )
                    conn.commit()
                    return nl_id, True
                return nl_id, not processed

            nl_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO newsletters
                    (id, email_id, source, author, subject, published_at, body_text,
                     processed, medium, url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                ON CONFLICT (email_id) DO NOTHING
                """,
                (
                    nl_id, row["url"], row["source"], row["author"], row["title"],
                    row.get("published_at"), row["body_text"], row["medium"], row["url"],
                ),
            )
            conn.commit()
            return nl_id, True
    finally:
        conn.close()


def ingest_article(url: str, row: dict | None = None) -> dict:
    """Full path for one article: fetch -> classify -> store -> extract.

    Show notes are never stored. Everything else lands and is extracted with the same
    chunker and prompt the newsletters use.
    """
    from newsletter_ingestor import chunk_text, store_newsletter_insights

    if row is None:
        row = fetch_and_parse(url)

    if row["kind"] in ("shownotes", "thin", "extraction_failed"):
        return {"url": url, "status": f"skipped_{row['kind']}", "kind": row["kind"],
                "chars": row["chars"], "insights_count": 0}

    nl_id, needs_extraction = upsert_article(row)
    if not needs_extraction:
        return {"url": url, "newsletter_id": nl_id, "status": "duplicate",
                "insights_count": 0}

    all_insights: list[dict] = []
    for chunk in chunk_text(row["body_text"]):
        chunk_insights = extract_article_insights(chunk, row.get("title", ""))
        for ins in chunk_insights:
            ins["source_chunk"] = chunk[:500]
        all_insights.extend(chunk_insights)

    count = store_newsletter_insights(nl_id, row["source"], all_insights)
    return {
        "url": url,
        "newsletter_id": nl_id,
        "status": "processed",
        "kind": row["kind"],
        "medium": row["medium"],
        "chars": row["chars"],
        "insights_count": count,
    }


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
