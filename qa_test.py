#!/usr/bin/env python3
"""
Comprehensive QA test for Operators Vault.
Tests: data quality, search, RAG chat, edge cases, performance.
"""
import os
import sys
import time
import json
import random
import re
import requests
from pathlib import Path
from urllib.parse import quote

# Load .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import psycopg2

import db_utils

# Route to the working Supabase pooler port (6543 transaction pooler drops SSL;
# 5432 session pooler is healthy). See db_utils.resolve_db_url.
DB_URL = db_utils.resolve_db_url() or os.environ["DATABASE_URL"]
BASE_URL = "https://superb-smile-production.up.railway.app"
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndiZHdubHpiZ3VnZXd0bXZhaHdnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5Mzc0MzIsImV4cCI6MjA4NDUxMzQzMn0.8cW9UoDzsCzv8_JHU0imeY8NpOdF5e2XAE_Gxq6O_cs"
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

results = {}

print("=" * 70)
print("OPERATORS VAULT — QA TEST SUITE")
print("=" * 70)

# ============================================================
# AUTH — get JWT token
# ============================================================
print("\n[AUTH] Getting Supabase JWT token...")
TOKEN = None
# Try service role key first (it's a JWT we can use directly)
if SERVICE_ROLE_KEY:
    TOKEN = SERVICE_ROLE_KEY
    print(f"  Using service role key as bearer token")

# ============================================================
# SECTION 1: DATA QUALITY
# ============================================================
print("\n" + "=" * 70)
print("SECTION 1: DATA QUALITY (DB Direct)")
print("=" * 70)

conn = db_utils.connect(DB_URL, connect_timeout=15)
cur = conn.cursor()

# 1a. Total video coverage
cur.execute("SELECT COUNT(*) FROM videos")
total_videos = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT video_id) FROM insights
""")
videos_with_insights = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM insights")
total_insights = cur.fetchone()[0]

coverage_pct = (videos_with_insights / total_videos * 100) if total_videos else 0
print(f"\n[1a] Coverage:")
print(f"  Total videos: {total_videos}")
print(f"  Videos with insights: {videos_with_insights}")
print(f"  Coverage: {coverage_pct:.1f}%")
print(f"  Total insights: {total_insights}")
results["coverage_pct"] = coverage_pct
results["total_videos"] = total_videos
results["videos_with_insights"] = videos_with_insights
results["total_insights"] = total_insights

# 1b. Insight quality sample — 20 random
cur.execute("""
    SELECT id, title, description, category, video_id
    FROM insights
    ORDER BY RANDOM()
    LIMIT 20
""")
sample = cur.fetchall()

GARBAGE_PATTERNS = [
    "let me categorize",
    "extraction_process",
    "as an ai",
    "i cannot",
    "i don't have",
    "i'm sorry",
    "<no insight>",
    "no insight",
    "n/a",
    "[",  # JSON leakage
    "```",  # code fence leakage
]

print(f"\n[1b] Insight Quality Sample (20 random):")
quality_issues = []
for row in sample:
    ins_id, title, desc, cat, vid = row
    issues = []
    if not title or len(title.strip()) == 0:
        issues.append("EMPTY_TITLE")
    elif len(title.strip()) < 5:
        issues.append(f"SHORT_TITLE({len(title.strip())})")
    elif len(title.strip()) > 100:
        issues.append(f"LONG_TITLE({len(title.strip())})")

    if not desc or len(desc.strip()) == 0:
        issues.append("EMPTY_DESC")
    elif len(desc.strip()) < 20:
        issues.append(f"SHORT_DESC({len(desc.strip())})")
    elif len(desc.strip()) > 500:
        issues.append(f"LONG_DESC({len(desc.strip())})")  # warn, not fail

    check_text = ((title or "") + " " + (desc or "")).lower()
    for pat in GARBAGE_PATTERNS:
        if pat in check_text:
            issues.append(f"GARBAGE:{pat}")

    if issues:
        quality_issues.append({"id": str(ins_id), "title": title[:60] if title else None, "issues": issues})
        print(f"  WARN id={ins_id}: {issues}")
    else:
        print(f"  OK   id={ins_id}: '{str(title)[:50]}' | desc len={len(desc or '')} | cat={cat}")

results["sample_quality_issues"] = quality_issues
results["sample_quality_issue_count"] = len(quality_issues)

# 1c. Category distribution
cur.execute("""
    SELECT category, COUNT(*) as cnt
    FROM insights
    GROUP BY category
    ORDER BY cnt DESC
""")
cat_rows = cur.fetchall()
print(f"\n[1c] Category Distribution:")
valid_categories = {
    "Paid Media", "Email & SMS", "Finance & Ops", "Brand & Creative",
    "Sourcing & Supply Chain", "Retention & Loyalty", "Growth Strategy"
}
invalid_cats = []
for cat, cnt in cat_rows:
    marker = "OK" if cat in valid_categories else "INVALID"
    print(f"  {marker}: {cat} — {cnt}")
    if cat not in valid_categories:
        invalid_cats.append({"category": cat, "count": cnt})
results["invalid_categories"] = invalid_cats
results["category_count"] = len(cat_rows)

# 1d. Duplicates (video_id + title)
cur.execute("""
    SELECT video_id, title, COUNT(*) as cnt
    FROM insights
    GROUP BY video_id, title
    HAVING COUNT(*) > 1
    LIMIT 20
""")
dupes = cur.fetchall()
print(f"\n[1d] Duplicate (video_id + title) pairs: {len(dupes)}")
for d in dupes[:5]:
    print(f"  video={d[0]}, title='{str(d[1])[:50]}', count={d[2]}")
results["duplicate_count"] = len(dupes)

# 1e. Empty descriptions
cur.execute("""
    SELECT COUNT(*) FROM insights
    WHERE description IS NULL OR description = ''
""")
empty_desc = cur.fetchone()[0]
print(f"\n[1e] Insights with empty description: {empty_desc}")
results["empty_desc_count"] = empty_desc

# 1f. FTS coverage
cur.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(fts) as has_fts,
        ROUND(COUNT(fts)::decimal / NULLIF(COUNT(*), 0) * 100, 1) as pct
    FROM insights
""")
fts_row = cur.fetchone()
print(f"\n[1f] FTS Coverage:")
print(f"  Total insights: {fts_row[0]}")
print(f"  Has FTS: {fts_row[1]}")
print(f"  Coverage: {fts_row[2]}%")
results["fts_coverage_pct"] = float(fts_row[2]) if fts_row[2] else 0

# 1g. Short/junk insights
cur.execute("""
    SELECT COUNT(*) FROM insights
    WHERE LENGTH(TRIM(COALESCE(title, ''))) < 5
       OR LENGTH(TRIM(COALESCE(description, ''))) < 10
""")
junk_count = cur.fetchone()[0]
print(f"\n[1g] Junk insights (title<5 or desc<10): {junk_count}")
results["junk_count"] = junk_count

# Also check newsletter insights
cur.execute("SELECT COUNT(*) FROM newsletter_insights")
nl_total = cur.fetchone()[0]
cur.execute("""
    SELECT COUNT(DISTINCT newsletter_id) FROM newsletter_insights
""")
nl_newsletters = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM newsletters")
nl_all = cur.fetchone()[0]
print(f"\n[1h] Newsletter Coverage:")
print(f"  Total newsletters: {nl_all}")
print(f"  Newsletters with insights: {nl_newsletters}")
print(f"  Total newsletter insights: {nl_total}")
results["newsletter_total"] = nl_total
results["newsletter_count"] = nl_all

cur.close()
conn.close()

# ============================================================
# SECTION 2: SEARCH QUALITY (DB Direct)
# ============================================================
print("\n" + "=" * 70)
print("SECTION 2: SEARCH QUALITY (DB Direct via _search_postgres)")
print("=" * 70)

sys.path.insert(0, str(Path(__file__).parent))

# Inline the search function directly
def db_search(q, limit=10):
    """Direct DB search replicating _search_postgres for insights."""
    import psycopg2
    hits = []
    if not q or not q.strip():
        return {"query": q, "total": 0, "hits": []}

    conn2 = db_utils.connect(DB_URL, connect_timeout=10)
    cur2 = conn2.cursor()
    try:
        cur2.execute("""
            SELECT id, video_id, podcast, category, title, description,
                   ts_rank(fts, plainto_tsquery('english', %s)) AS rank
            FROM insights
            WHERE fts @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
        """, (q.strip(), q.strip(), limit))
        for row in cur2.fetchall():
            hits.append({
                "type": "insight",
                "id": str(row[0]),
                "video_id": row[1],
                "podcast": row[2],
                "category": row[3],
                "title": row[4],
                "description": row[5],
                "rank": float(row[6]) if row[6] else 0,
            })
        # Also search newsletters
        cur2.execute("""
            SELECT ni.id, ni.source, ni.category, ni.title, ni.description,
                   ts_rank(to_tsvector('english', coalesce(ni.title,'') || ' ' || coalesce(ni.description,'')), plainto_tsquery('english', %s)) AS rank
            FROM newsletter_insights ni
            WHERE to_tsvector('english', coalesce(ni.title,'') || ' ' || coalesce(ni.description,'')) @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC
            LIMIT %s
        """, (q.strip(), q.strip(), limit))
        for row in cur2.fetchall():
            hits.append({
                "type": "newsletter_insight",
                "id": str(row[0]),
                "source": row[1],
                "category": row[2],
                "title": row[3],
                "description": row[4],
                "rank": float(row[5]) if row[5] else 0,
            })
    finally:
        cur2.close()
        conn2.close()

    hits.sort(key=lambda h: h.get("rank", 0), reverse=True)
    return {"query": q, "total": len(hits), "hits": hits[:limit]}


test_queries = [
    ("BFCM Black Friday strategy", "Black Friday / BFCM prep"),
    ("email marketing list building", "email list growth"),
    ("meta ads creative testing", "Meta/Facebook ad creative testing"),
    ("contribution margin profitability", "financial metrics / margins"),
    ("influencer gifting strategy", "influencer / creator gifting"),
    ("inventory management cash flow", "inventory & cash flow ops"),
    ("customer acquisition cost CAC", "CAC / unit economics"),
    ("subscription retention", "subscription business retention"),
    ("DTC brand building community", "brand building & community"),
    ("Amazon marketplace strategy", "Amazon selling strategy"),
]

search_results = []
for q, expected_topic in test_queries:
    t0 = time.time()
    res = db_search(q)
    elapsed = time.time() - t0
    total_hits = res["total"]
    top3 = res["hits"][:3]

    relevance_issues = []
    for h in top3:
        title = h.get("title", "") or ""
        desc = h.get("description", "") or ""
        if not title and not desc:
            relevance_issues.append("empty result")

    status = "OK" if total_hits >= 3 else ("WARN" if total_hits > 0 else "FAIL")
    print(f"\n  [{status}] Q: '{q}' — {total_hits} hits ({elapsed:.2f}s)")
    for i, h in enumerate(top3):
        title = h.get("title", "")[:70]
        cat = h.get("category", h.get("source", ""))
        print(f"    #{i+1} [{h['type']}] [{cat}] {title}")

    search_results.append({
        "query": q,
        "expected": expected_topic,
        "hits": total_hits,
        "status": status,
        "elapsed": elapsed,
        "top3": [{"title": h.get("title", "")[:80], "type": h["type"]} for h in top3],
    })

results["search_results"] = search_results
zero_result_queries = [r for r in search_results if r["hits"] == 0]
print(f"\n  Zero-result queries: {len(zero_result_queries)}/{len(test_queries)}")
results["zero_result_queries"] = len(zero_result_queries)


# ============================================================
# SECTION 3: RAG CHAT QUALITY
# ============================================================
print("\n" + "=" * 70)
print("SECTION 3: RAG CHAT QUALITY (/chat endpoint)")
print("=" * 70)

CHAT_URL = f"{BASE_URL}/chat"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

chat_questions = [
    "What's the best framework for setting MER targets?",
    "How do 8-figure brands approach BFCM prep?",
    "What do operators say about Meta creative fatigue?",
    "How should I think about email vs SMS for DTC?",
    "What's the right way to measure influencer ROI?",
]

chat_results = []
for q in chat_questions:
    print(f"\n  Q: {q[:70]}")
    t0 = time.time()
    try:
        r = requests.post(CHAT_URL, json={"message": q}, headers=headers, timeout=90)
        elapsed = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            answer = data.get("answer", data.get("response", str(data)))
            # Quality checks
            issues = []
            if len(answer) < 50:
                issues.append("TOO_SHORT")
            hallucination_markers = ["as an ai", "i don't have access", "i cannot", "i'm not able", "i apologize"]
            if any(m in answer.lower() for m in hallucination_markers):
                issues.append("REFUSAL_OR_HEDGE")
            # Check for source citations
            has_source = any(w in answer.lower() for w in ["operator", "episode", "according", "mentioned", "said", "source", "from"])

            print(f"  Status: {r.status_code} | Time: {elapsed:.1f}s | Len: {len(answer)} chars")
            print(f"  Has sources: {has_source} | Issues: {issues or 'None'}")
            print(f"  Preview: {answer[:200]}...")

            chat_results.append({
                "question": q,
                "status": "PASS" if not issues else "WARN",
                "elapsed": elapsed,
                "answer_len": len(answer),
                "has_source": has_source,
                "issues": issues,
                "preview": answer[:300],
            })
        else:
            print(f"  FAIL: HTTP {r.status_code} — {r.text[:200]}")
            chat_results.append({
                "question": q,
                "status": "FAIL",
                "http_status": r.status_code,
                "error": r.text[:300],
            })
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ERROR: {e} ({elapsed:.1f}s)")
        chat_results.append({"question": q, "status": "ERROR", "error": str(e), "elapsed": elapsed})

results["chat_results"] = chat_results


# ============================================================
# SECTION 4: EDGE CASES
# ============================================================
print("\n" + "=" * 70)
print("SECTION 4: EDGE CASES")
print("=" * 70)

edge_cases = []

# 4a. Empty search query
print("\n[4a] Empty search query (q='')")
res = db_search("")
print(f"  Result: total={res['total']} — {'OK (returns 0)' if res['total'] == 0 else 'WARN (returned results)'}")
edge_cases.append({"test": "empty_query", "status": "PASS" if res["total"] == 0 else "WARN", "detail": f"total={res['total']}"})

# 4b. Very long query (500 chars)
long_q = "email marketing strategy for DTC brands " * 12  # ~500 chars
long_q = long_q[:500]
print(f"\n[4b] Very long query ({len(long_q)} chars)")
try:
    res = db_search(long_q)
    print(f"  Result: total={res['total']} — OK (no crash)")
    edge_cases.append({"test": "long_query", "status": "PASS", "detail": f"total={res['total']}"})
except Exception as e:
    print(f"  ERROR: {e}")
    edge_cases.append({"test": "long_query", "status": "FAIL", "detail": str(e)})

# 4c. Chat with empty message
print(f"\n[4c] Chat with empty message")
try:
    r = requests.post(CHAT_URL, json={"message": ""}, headers=headers, timeout=30)
    print(f"  Status: {r.status_code}")
    if r.status_code in (400, 422):
        print(f"  OK — properly rejected empty message")
        edge_cases.append({"test": "empty_chat", "status": "PASS", "detail": f"HTTP {r.status_code}"})
    elif r.status_code == 200:
        data = r.json()
        print(f"  WARN — 200 returned for empty message: {str(data)[:200]}")
        edge_cases.append({"test": "empty_chat", "status": "WARN", "detail": "200 for empty message"})
    else:
        print(f"  FAIL: HTTP {r.status_code}")
        edge_cases.append({"test": "empty_chat", "status": "FAIL", "detail": f"HTTP {r.status_code}"})
except Exception as e:
    print(f"  ERROR: {e}")
    edge_cases.append({"test": "empty_chat", "status": "ERROR", "detail": str(e)})

# 4d. Off-topic chat question
print(f"\n[4d] Off-topic chat question (capital of France)")
try:
    r = requests.post(CHAT_URL, json={"message": "What is the capital of France?"}, headers=headers, timeout=60)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        answer = data.get("answer", data.get("response", str(data)))
        print(f"  Answer preview: {answer[:300]}")
        # Check if it declines or answers
        declines = any(w in answer.lower() for w in ["not", "outside", "can't", "cannot", "focus", "dtc", "operator"])
        print(f"  Declines/scopes: {declines}")
        edge_cases.append({"test": "off_topic_chat", "status": "PASS" if declines else "WARN",
                           "detail": answer[:200]})
    else:
        edge_cases.append({"test": "off_topic_chat", "status": "FAIL", "detail": f"HTTP {r.status_code}"})
except Exception as e:
    print(f"  ERROR: {e}")
    edge_cases.append({"test": "off_topic_chat", "status": "ERROR", "detail": str(e)})

# 4e. Very obscure search term
print(f"\n[4e] Very obscure search term")
res = db_search("xyzzy_ultraspecific_nonexistent_term_2345")
print(f"  Result: total={res['total']} — {'OK (0 results)' if res['total'] == 0 else 'SUSPICIOUS'}")
edge_cases.append({"test": "obscure_term", "status": "PASS" if res["total"] == 0 else "WARN",
                   "detail": f"total={res['total']}"})

results["edge_cases"] = edge_cases


# ============================================================
# SECTION 5: PERFORMANCE
# ============================================================
print("\n" + "=" * 70)
print("SECTION 5: PERFORMANCE")
print("=" * 70)

perf_results = []

# 5a. /search endpoint
print(f"\n[5a] /search endpoint via HTTP")
try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/search?q=email+marketing+strategy&limit=10",
                     headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
    elapsed = time.time() - t0
    status = "PASS" if elapsed < 2 else ("WARN" if elapsed < 5 else "FAIL")
    print(f"  HTTP {r.status_code} | Time: {elapsed:.2f}s | Status: {status}")
    perf_results.append({"endpoint": "/search", "elapsed": elapsed, "status": status})
except Exception as e:
    print(f"  ERROR: {e}")
    perf_results.append({"endpoint": "/search", "status": "ERROR", "error": str(e)})

# 5b. /episodes endpoint
print(f"\n[5b] /episodes endpoint via HTTP")
try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/episodes", timeout=30)
    elapsed = time.time() - t0
    status = "PASS" if elapsed < 2 else ("WARN" if elapsed < 5 else "FAIL")
    print(f"  HTTP {r.status_code} | Time: {elapsed:.2f}s | Status: {status}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Episodes returned: {data.get('total', '?')}")
    perf_results.append({"endpoint": "/episodes", "elapsed": elapsed, "status": status,
                          "http_status": r.status_code})
except Exception as e:
    print(f"  ERROR: {e}")
    perf_results.append({"endpoint": "/episodes", "status": "ERROR", "error": str(e)})

# 5c. /health endpoint
print(f"\n[5c] /health endpoint via HTTP")
try:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/health", timeout=15)
    elapsed = time.time() - t0
    status = "PASS" if r.status_code == 200 and elapsed < 2 else "FAIL"
    print(f"  HTTP {r.status_code} | Time: {elapsed:.2f}s | Status: {status}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Health data: {json.dumps(data, indent=2)[:500]}")
    perf_results.append({"endpoint": "/health", "elapsed": elapsed, "status": status,
                          "http_status": r.status_code})
except Exception as e:
    print(f"  ERROR: {e}")
    perf_results.append({"endpoint": "/health", "status": "ERROR", "error": str(e)})

# 5d. DB search latency (direct)
print(f"\n[5d] DB search latency (direct)")
t0 = time.time()
db_search("email marketing strategy")
elapsed = time.time() - t0
status = "PASS" if elapsed < 1 else ("WARN" if elapsed < 2 else "FAIL")
print(f"  Direct DB search: {elapsed:.3f}s | Status: {status}")
perf_results.append({"endpoint": "db_direct_search", "elapsed": elapsed, "status": status})

results["perf_results"] = perf_results


# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("FINAL QA REPORT")
print("=" * 70)

def grade_section(name, checks):
    fails = sum(1 for c in checks if c.get("status") == "FAIL")
    warns = sum(1 for c in checks if c.get("status") in ("WARN", "ERROR"))
    if fails > 0:
        return f"FAIL ({fails} failures, {warns} warnings)"
    elif warns > 0:
        return f"WARN ({warns} warnings)"
    return "PASS"

# Data Quality Summary
dq_checks = [
    {"status": "PASS" if coverage_pct >= 80 else ("WARN" if coverage_pct >= 50 else "FAIL"), "name": "coverage"},
    {"status": "PASS" if results["sample_quality_issue_count"] <= 3 else "WARN", "name": "sample_quality"},
    {"status": "PASS" if not invalid_cats else "WARN", "name": "categories"},
    {"status": "PASS" if results["duplicate_count"] == 0 else "WARN", "name": "duplicates"},
    {"status": "PASS" if empty_desc == 0 else "WARN", "name": "empty_desc"},
    {"status": "PASS" if results["fts_coverage_pct"] >= 95 else "WARN", "name": "fts_coverage"},
    {"status": "PASS" if junk_count == 0 else "WARN", "name": "junk_insights"},
]

print(f"\n1. DATA QUALITY: {grade_section('dq', dq_checks)}")
print(f"   - Video coverage: {coverage_pct:.1f}% ({videos_with_insights}/{total_videos})")
print(f"   - Total insights: {total_insights}")
print(f"   - Newsletter insights: {nl_total}")
print(f"   - Sample issues: {results['sample_quality_issue_count']}/20")
print(f"   - Invalid categories: {len(invalid_cats)}")
print(f"   - Duplicates: {results['duplicate_count']}")
print(f"   - Empty descriptions: {empty_desc}")
print(f"   - FTS coverage: {results['fts_coverage_pct']}%")
print(f"   - Junk insights: {junk_count}")

print(f"\n2. SEARCH QUALITY: {'PASS' if zero_result_queries == 0 else 'WARN'}")
print(f"   - Zero-result queries: {zero_result_queries}/{len(test_queries)}")
for sr in search_results:
    print(f"   - '{sr['query'][:45]}...' → {sr['hits']} hits [{sr['status']}]")

chat_passes = sum(1 for c in chat_results if c.get("status") in ("PASS", "WARN"))
chat_fails = sum(1 for c in chat_results if c.get("status") in ("FAIL", "ERROR"))
print(f"\n3. RAG CHAT QUALITY: {'PASS' if chat_fails == 0 else 'FAIL'}")
for c in chat_results:
    q_short = c['question'][:50]
    status = c.get('status', '?')
    elapsed = c.get('elapsed', 0)
    issues = c.get('issues', [])
    print(f"   - [{status}] '{q_short}' | {elapsed:.1f}s | {c.get('answer_len','?')}chars | issues={issues}")

edge_statuses = [e["status"] for e in edge_cases]
print(f"\n4. EDGE CASES: {'PASS' if 'FAIL' not in edge_statuses else 'FAIL'}")
for e in edge_cases:
    print(f"   - [{e['status']}] {e['test']}: {e['detail'][:80] if isinstance(e.get('detail'), str) else e.get('detail','')}")

perf_statuses = [p["status"] for p in perf_results]
print(f"\n5. PERFORMANCE: {'PASS' if 'FAIL' not in perf_statuses else 'WARN'}")
for p in perf_results:
    print(f"   - [{p['status']}] {p['endpoint']}: {p.get('elapsed', '?'):.2f}s")

# Overall score
fail_count = sum([
    1 if coverage_pct < 50 else 0,
    1 if results["sample_quality_issue_count"] > 5 else 0,
    1 if len(invalid_cats) > 2 else 0,
    1 if results["fts_coverage_pct"] < 80 else 0,
    1 if len(zero_result_queries) > 5 else 0,
    1 if chat_fails > 2 else 0,
    1 if "FAIL" in edge_statuses else 0,
    1 if "FAIL" in perf_statuses else 0,
])
warn_count = sum([
    1 if coverage_pct < 80 else 0,
    1 if results["sample_quality_issue_count"] > 0 else 0,
    1 if invalid_cats else 0,
    1 if results["duplicate_count"] > 0 else 0,
    1 if empty_desc > 0 else 0,
    1 if junk_count > 0 else 0,
    1 if len(zero_result_queries) > 0 else 0,
    1 if "WARN" in perf_statuses else 0,
    1 if "WARN" in edge_statuses else 0,
])

score = max(1, 10 - (fail_count * 2) - (warn_count * 0.5))
score = min(10, score)

print(f"\n{'=' * 70}")
print(f"OVERALL READINESS SCORE: {score:.1f}/10")
print(f"Failures: {fail_count} | Warnings: {warn_count}")
print(f"{'=' * 70}")

# Top 3 issues
print(f"\nTOP 3 ISSUES TO FIX BEFORE EXTERNAL SHARING:")
issues_to_report = []

if coverage_pct < 80:
    issues_to_report.append(f"1. LOW VIDEO COVERAGE: Only {coverage_pct:.1f}% of {total_videos} videos have insights extracted. "
                             f"{total_videos - videos_with_insights} videos unprocessed.")
if invalid_cats:
    cat_str = ", ".join([f"'{c['category']}' ({c['count']})" for c in invalid_cats[:3]])
    issues_to_report.append(f"2. INVALID CATEGORIES: {len(invalid_cats)} non-standard categories found: {cat_str}")
if len(zero_result_queries) > 0:
    zero_qs = [r['query'] for r in search_results if r['hits'] == 0]
    issues_to_report.append(f"3. SEARCH GAPS: {len(zero_result_queries)} queries return 0 results: {zero_qs}")
if results["fts_coverage_pct"] < 95:
    issues_to_report.append(f"4. FTS GAPS: {100-results['fts_coverage_pct']:.1f}% of insights lack FTS index (not searchable)")
if junk_count > 0:
    issues_to_report.append(f"5. JUNK INSIGHTS: {junk_count} insights with near-empty title or description")
if results["duplicate_count"] > 0:
    issues_to_report.append(f"6. DUPLICATES: {results['duplicate_count']} duplicate (video_id, title) pairs")

for i, issue in enumerate(issues_to_report[:3], 1):
    print(f"  {issue}")

if not issues_to_report:
    print("  No critical issues found! Good to share.")

# Save results JSON
out_path = Path(__file__).parent / "qa_results.json"
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nDetailed results saved to: {out_path}")
