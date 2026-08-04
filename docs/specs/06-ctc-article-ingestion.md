# Spec 06 — CTC long-form article ingestion (`taylor_holiday` depth fix)

Status: **BUILT AND DEPLOYED 2026-08-03.** Backfill of the ~400-article history is
queued but not yet run. Probed 2026-08-02 against the live site and the live DB.

Decisions taken (Ethan: "do what you think is best"):
1. **Same slug.** Articles merge into `taylor_holiday`, separated by `newsletters.medium`.
2. **Podcast show notes excluded** — 307+ URLs at ~1,100 chars, dropped by template
   detection so they never cost a fetch or an extraction pass.
3. **News roundups tagged, not dropped** — stored as `medium='article_news'` so search
   can down-weight them while keeping the useful platform-change explainers.

Shipped:
- `ctc_article_ingestor.py` — enumeration, two-selector extraction, classification gate
- `sql/add_newsletter_medium.sql` — `medium` + `url` columns (applied, self-applying)
- `POST /sync-ctc-articles` — server-side atom walk, backgrounded, paced
- `scripts/backfill_ctc_articles.py` — harnessed historical backfill (self-check 10/10)
- n8n `WEH4lUoSawN0J78f` — daily trigger, two nodes, no Code node
- **Bonus fix:** the startup migration runner, which had been silently skipping the
  first statement of three of five migration files. See CLAUDE.md.

## Why

`taylor_holiday` is the weakest source in the vault per issue, and it is the one operator
whose material Ethan actually asks for (OPEX floor, four-quarter accounting, unit economics).

| source | issues | insights | insights/issue | avg body chars |
|---|---:|---:|---:|---:|
| chase_dimond | 1,013 | 19,168 | 18.9 | — |
| nik_sharma | 191 | 7,419 | 38.8 | — |
| matt_bertulli | 249 | 5,183 | 20.8 | — |
| operators_newsletter | 113 | 3,225 | 28.5 | — |
| chew_on_this | 104 | 2,670 | 25.7 | — |
| **taylor_holiday** | **130** | **728** | **5.6** | **3,856** |
| jordan_west | 53 | 335 | 6.3 | — |

(Live DB, 2026-08-02.) The pipeline is not failing on him — his *emails* are short sales
copy that drive to the site. The substance is published as articles on commonthreadco.com
and has never been ingested. This is a **new source type**, not a bug.

## What was verified (probe-before-build, T1)

1. **Enumeration works.** `https://commonthreadco.com/sitemap_blogs_1.xml` → 722 article
   URLs across 13 blog handles. Shopify storefront, `robots.txt` `Allow: /`, no auth wall.
2. **Extraction is deterministic on exactly two templates.** 99/99 sampled pages resolved
   with a balanced-div scan on one of two wrappers:
   - `class="bc-content"` → long-form article
   - `class="description"` inside `blog-article-bg podcast …` → podcast episode show notes
3. **⚠️ Generic extractors do NOT work here.** `defuddle parse <url> --md` returned **892
   bytes of nav chrome and zero article body**. There is also **no JSON-LD** on any page
   (0 `application/ld+json` blocks on both templates sampled). Do not reach for a
   readability-style library — write the two-selector rule.
4. **⚠️ The `.atom` feed is a sync path only, never a backfill path.**
   `https://commonthreadco.com/blogs/<handle>.atom` serves the **full article HTML** in
   `<content type="html">` — clean, no scraping. But it caps at **30 entries and ignores
   pagination**: `?page=1`, `?page=2`, and `?page=8` returned byte-identical 356,076-byte
   responses. Backfill must go through the sitemap + HTML fetch.

### Corpus shape (stratified sample, 99 pages fetched)

| blog | URLs | template | avg body chars | verdict |
|---|---:|---|---:|---|
| coachs-corner | 307 | article | 7,309 | **ingest** (with news gate) |
| ecommerce-playbook | 307 | podcast | 1,122 | **exclude** — show notes only |
| thread | 26 | article | — | ingest |
| dtc-hotline | 18 | podcast | ~1,375 | exclude |
| tactics | 17 | article | 1,912 | ingest, low yield |
| bridges | 12 | article | **12,745** | **ingest — highest value** |
| sharpen-your-skills | 10 | article | 2,389 | ingest |
| outliers | 7 | article | 5,188 | ingest |
| bridges-live | 6 | article | 1,567 | marginal |
| upgrade-your-culture | 5 | article | — | ingest |
| taylor-reacts | 5 | article | 2,087 | ingest |
| research | 2 | article | — | ingest |

**Half the corpus is the CTC podcast archive at ~1.1K chars of show notes.** Ingesting it
would add 307 thin rows that dilute Taylor's source without adding operator substance.
Substantive set ≈ **385 articles**, and the top of it is exactly the wanted material —
longest sampled pages were *First-Order Profitability: The New Law for Ecommerce Businesses*
(25,841 chars), *Red To Black in 90 Days* (23,525), *Leverage Pricing as a Strategic Tool*
(15,494), *Planning and Tracking Daily Contribution Margin*, *Ecommerce Demand Forecasting*.

### The dilution risk this shares with Jordan West / Chew On This

~13–25% of recent `coachs-corner` is AI-written platform-news ("This Week in Ad Platforms:
Snapchat Opens to AI Agents…", "Google Ads New Terms of Service: What the July 2026 AI
Automation Changes…", "2026 Meta Summit Recap"). 2026 is news-heavy: 46 of 307
coachs-corner posts carry a 2026-07 `lastmod` alone. These are SEO content, not Taylor's
frameworks, and they would flood the newest-first slots.

**Reuse the existing gate pattern.** `newsletter_ingestor.is_promo_only()` already solved
the structurally identical problem — extend it to a `classify_article()` returning
`substantive | news_roundup | shownotes`, gate before extraction, store zero insights for
the latter two. Same head+middle+tail sampling; do not judge on the first N chars.

## Where it lands — reuse `newsletters`, do not add a table

`newsletter_insights` is what the whole downstream stack already understands: the `fts`
column + weighted GIN index, the rank normalization, the guide/chat source quota, the
InsightModal sibling-insight loader, the `/newsletters` browser, the speaker-page fallback.
A new `articles` table means re-doing Phase 3 for a second entity — for content that is
the same shape (title + long text + date + author).

- `newsletters.email_id` is **UNIQUE** → store the canonical article URL there. Natural
  dedupe key, zero migration needed for idempotency.
- Add `medium text default 'email'` (`'email' | 'article'`) and `url text` so the frontend
  can render "Read on commonthreadco.com" instead of a Gmail-shaped citation.
- Slug: **`taylor_holiday`** (same source, both media) so the two merge on his speaker page
  and in per-source counts. `medium` carries the distinction where it matters.
  *This is the one call worth confirming — see Decisions below.*

## Build slices (each with its own proof)

**Slice 1 — extractor + gate, offline.** `ctc_article_ingestor.py`: sitemap enumeration,
two-wrapper body extraction, `classify_article()`. Proof: run against 30 held-out URLs
(not the 99 already sampled — L4, judge brings its own fixtures) and paste the
template/length/classification table; ≥95% must extract non-empty on the article template.

**Slice 2 — migration + write path.** `medium` + `url` columns, `POST /ingest-article`
deriving source server-side from the URL host (never caller-supplied — defect #2 in
CLAUDE.md). Proof: ingest 5 articles, paste `select` showing 5 rows with correct
`medium='article'`, then re-run the same 5 and paste a row count still at 5.

**Slice 3 — backfill, harnessed.** `scripts/backfill_ctc_articles.py` on the
`job_runs`/`job_checkpoints` harness (`20260730_job_harness.sql`), dry-run default,
`--apply` flag, paced (single IP, be polite — 1 req/s, ~7 min for 385). Proof:
`HARNESS SELF-CHECK v1` 10/10, a kill-mid-run → resume-from-item-k+1 transcript, and a
second full run showing zero new rows.

**Slice 4 — daily sync.** n8n workflow polling the 8 substantive blogs' `.atom` feeds,
diffing against `/newsletters` by URL, POSTing new ones. **The Code node MUST iterate
`$input.all()` and return one item per entry** — this is the exact bug that cost 68% of
newsletter ingestion (CLAUDE.md defect #4). Proof: one execution log showing N entries
fetched → N POSTed, N > 1.

**Verification of the actual goal** (this is what "done" means, not "the rows exist):
re-run the same query mix used on 2026-08-01 — `OPEX floor operating expenses`,
`marginal CAC payback`, `four quarter accounting` — and paste the per-source result
counts before and after. `marginal CAC payback` currently returns 1 newsletter / 29 video.

## Cost and effort

- **Extraction spend:** ~385 articles × ~7K chars ≈ 700K input tokens one-time. Trivial.
- **Ongoing:** CTC publishes ~15–45 posts/month across the substantive blogs; after the
  news gate, maybe 10–20/month reach extraction.
- **Build:** slices 1–2 are half a day, slice 3 a few hours on the existing harness,
  slice 4 an hour. The risk is not volume — it is repeating a known defect, which is why
  each slice above names the defect it must not reintroduce.

## What the build actually taught us (beyond the scope above)

1. **CTC's rate limiter is the binding constraint, not extraction.** Ten feed requests
   back to back return 429 for minutes per IP. It took out this Mac during probing and
   then Railway — an IP that had been fetching cleanly seconds earlier. No
   `Retry-After` header, and it escalates from 429 to refusing connections. Everything
   is now serial and paced (15s between feeds, 20s between backfill pages), and 429 is
   classified as a whole-run stop rather than a per-item fault.
2. **A length floor is the wrong gate.** The first cut used 1,000 chars to exclude show
   notes, which would have silently deleted `marginal-frontier` (848 chars) and
   `can-you-say-dpa` (772) — genuinely short old posts, and `marginal-frontier` is
   precisely the Taylor material this job exists to capture. Template detection does
   the real work; the floor is now 400 and only catches extraction failure, which is
   *quarantined and surfaced*, never silently skipped.
3. **The newsletter prompt mis-attributes articles.** Unframed, it produced quote
   titles reading "(Operators Newsletter author)" and "Newsletter author, on
   nearshoring to Mexico". After framing, all quotes attribute to Taylor Holiday —
   which also means his speaker page (FTS on speaker name) now surfaces them.
4. **Classify after the dedupe check, not before.** The feeds return the same ~30 posts
   daily and classification can cost an LLM call each, so the original ordering burned
   ~300 calls a day to learn nothing.
5. **Yield is much higher than projected.** One 20,570-char article produced 105
   insights. At that rate ~400 articles could produce 15-25k insights, which would make
   `taylor_holiday` the largest source in the vault — bigger than Chase Dimond's
   19,168. **Worth watching during backfill:** if it crowds other sources out of
   Discover, the lever is the guide/chat source quota, not re-extraction.

## Decisions needed from Ethan

1. **Same slug or separate?** `taylor_holiday` for both email + articles (recommended —
   they merge everywhere), or a distinct `ctc_articles` source so the two can be filtered
   apart in the UI.
2. **Podcast show notes: exclude (recommended) or ingest?** 307 URLs at ~1.1K chars.
   Excluding keeps the source dense; the CTC podcast itself is on YouTube and could later
   go through the existing video pipeline instead, which is where it belongs.
3. **How aggressive is the news gate?** Dropping all platform-news loses genuinely useful
   items (e.g. *Google's July 2026 Demand Gen Drop*). Alternative: ingest them but tag
   `category='platform_news'` so guides can down-weight rather than lose them.
