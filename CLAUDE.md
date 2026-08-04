# Operators Vault — DTC Knowledge Base

## What This Is
Searchable knowledge base of DTC operator content: podcast transcripts + newsletter archives.
Powers RAG-based Q&A for ENT Agency internal research.

## Status: LIVE ✅ (last verified 2026-08-01)
- **413 videos** indexed across 5 podcast channels; 390 have extracted insights
- **1,530 newsletter issues**; ~1,190 have extracted insights (backlog draining, see below)
- **~56,000 video insights + ~25,500 newsletter insights** in DB
- `newsletters.processed` was reconciled 2026-08-01 and now matches reality on all
  1,530 rows. It had drifted BOTH ways (45 rows TRUE with zero insights, 679 FALSE
  that already had them). Even so, prefer the `newsletter_insights` anti-join as the
  coverage metric — that is what the re-queue paths use, so the flag cannot silently
  strand rows again.

## ⚠️ Newsletter layer was dead from ~2026-05 to 2026-08-01 — what broke, so it isn't reintroduced
Four independent defects, all verified against the live DB and the Gmail API:
1. **Extraction worker threw on every job.** `_newsletter_extract_worker` selected
   `retry_count`, a column no migration ever created → `UndefinedColumn` on the first
   query. 2026-06 and 2026-07: 30 issues stored, **0** insights. Fixed by
   `20260801_newsletter_extraction_repair.sql`.
2. **Attribution corrupted.** The n8n Parse node used `$('Source Config').first()`,
   which always returns config item #1, so every issue since ~2026-05-09 was filed as
   `nik_sharma`. **`/ingest-newsletter` now derives source from the From header
   server-side and treats a client-supplied `source` as a hint only.** Never
   reintroduce caller-supplied attribution.
3. **Dead pooled connections dropped ~68% of issues.** `newsletter_ingestor` used a
   raw `ThreadedConnectionPool`; Supabase closes idle connections and `getconn()`
   handed those dead sockets straight out, so the ingest POST 500'd, n8n aborted the
   run, and the 2-day window moved past the skipped issues permanently — 137 of 200
   issues in 100 days were lost. **Always go through `db_utils.connect()`** (probes
   with `SELECT 1`, retries transient drops). Do not re-add a connection pool here.
4. **⚠️ THE BIG ONE — the n8n Parse Email Body node discarded all but ONE email per run.**
   n8n Code nodes in *Run Once for All Items* mode execute **once**, and `$json` is
   only the **first** input item. The node read `const msg = $json` and returned a
   single element, so every run POSTed exactly one newsletter no matter how many
   Gmail returned. Verified against real executions:

   | execution | Gmail fetched | POSTed |
   |---|---|---|
   | 148835 | 6 | **1** |
   | 147883 | 6 | **1** |
   | 149677 | 3 | **1** |

   This was the largest single cause of the ~68% ingestion loss — larger than the
   connection failures. Backfilling `chase_dimond` after the fix recovered **126
   entire issues** that had never been ingested (883 → 1,009) and moved his latest
   issue from 2026-07-08 to current.

   **Rule: any n8n Code node that processes messages MUST iterate `$input.all()`
   and return one item per message.** Never `const msg = $json`. Also note the
   backfill workflow was set to `runOnceForEachItem`, where returning an *array* is
   the wrong shape and errors the whole run — it had never worked even once.
5. **Newsletters lost every search slot.** `newsletter_insights` had no `fts` column
   and was ranked on an inline *unweighted* tsvector against `insights.fts`, which is
   weighted — so ts_rank buried them (98 video / 2 newsletter on a 100-hit query).
   Fixed by `20260801_newsletter_insights_fts.sql` + rank normalization + a source
   quota in guide/chat context.

## ⚠️ The startup migration runner silently skipped the first statement of 3 of 5 files
`_run_startup_migration` split each file on `;` and skipped any fragment whose text
began with `--`. A file that opens with a comment header puts that comment and its
first statement in the SAME fragment, so **the first statement of every
comment-led migration never ran, on every boot.** Fixed 2026-08-03 by stripping
comment lines before the emptiness test.

Damage found: `channel_configs` **had never been created** (so `/channels` had been
quietly serving its hardcoded fallback), and `migrate_newsletter_retry.sql` had never
applied — which is **the actual root cause of defect #1 below**. The `retry_count`
column the extraction worker selected was not "a column no migration ever created";
the migration existed and was skipped at boot, silently, every time. All six files
now apply cleanly (verified in a real boot log).

Two rules follow, and both are load-bearing:
- **A migration file in `sql/` must contain no semicolon inside any comment** — the
  splitter is still naive, and the fragment after such a semicolon gets executed as
  SQL. This cost three failed attempts while adding `add_newsletter_medium.sql`.
- **`sql/` is the self-applying path** (registered in the `_run_startup_migration`
  tuple). `supabase/migrations/*.sql` is the historical record and needs manual
  application. Put anything that must survive a fresh boot in `sql/`.

## ⚠️ Duplicate `/topic-guide` route (pre-existing, not yet resolved)
`api.py` defines `@app.post("/topic-guide")` **twice** (~line 2441 and ~line 3652).
FastAPI matches in registration order, so **the earlier one serves and the later
one — the version with persistent caching — is unreachable dead code.** The
caching feature has therefore never run. The source quota is applied to the
handler that actually serves. Decide whether to keep or delete the cached copy
before touching this endpoint.

## ⚠️ YouTube access: no proxy, residential IP only
YouTube blocks **datacenter** IPs, which is the only reason the Webshare proxy ever
existed. That account is banned (`402 Payment Required`), and it is not being replaced.
Caption pulls now run from a **residential IP**, where no proxy is needed at all.
A single IP rate-limits (`IpBlocked`) under bulk load, so backfill is paced across days.

**Canonical owner of caption→insight backfill:** `scripts/backfill_captions_job.py`,
scheduled DAILY 09:15 as Windows task **"ENT Vault Caption Backfill"** on the Alienware
box (Tailscale `100.120.248.8`, `C:\Users\ejatc\operators-vault`). It replaces the
Webshare proxy path for backlog work. Harness state lives in `job_runs` /
`job_checkpoints` (migration `supabase/migrations/20260730_job_harness.sql`).
Do NOT re-add a proxy or run this from Railway — Railway is a datacenter IP and will fail.

## URLs
- **Frontend:** `https://operators-vault.vercel.app`
- **Backend API:** `https://superb-smile-production.up.railway.app`
- **Supabase project:** `wbdwnlzbgugewtmvahwg`
- **Railway:** auto-deploys from GitHub `master` branch

## Deploy Commands
```bash
# Frontend — build + deploy + alias
cd frontend && npm run build
VERCEL_TOKEN=$(doppler secrets get VERCEL_TOKEN --project ent-agency-automation --config dev --plain)
vercel --prod --token "$VERCEL_TOKEN" --yes
vercel alias set <deployment-url> operators-vault.vercel.app --token "$VERCEL_TOKEN"

# Backend — just push to GitHub, Railway auto-deploys
git push
```

---

## Content Sources

### Podcast Channels (308 videos)
| Slug | Channel | YouTube Channel ID |
|------|---------|-------------------|
| `9operators` | @Operators9 | `UCuGneytUApsb7SEynqoZ0ug` |
| `marketing_operator` | @MarketingOperators | `UCLCl2hY_E08Q9q2X1p6ouMA` |
| `finance_operators` | @FinanceOperatorsFOPS | `UChL5rAxddwU_EnbhZofhDjw` |
| `titans` | @Operators9 (TITANS series) | `UCuGneytUApsb7SEynqoZ0ug` |

### Newsletter Sources (7)
Configured in the `newsletter_source_configs` table (DB-driven). The dict in
`newsletter_ingestor._NEWSLETTER_SOURCES_FALLBACK` is only a fallback for when that
table is unreachable — keep the two in sync.
⚠️ `NEWSLETTER_SOURCES` loads at **module import time**, so adding a row requires a
Railway restart before the new source is accepted.

| Slug | Author | Sender |
|------|--------|--------|
| `nik_sharma` | Nik Sharma | niksharma@workweek.com |
| `taylor_holiday` | Taylor Holiday / CTC | taylorholiday@commonthreadco.com |
| `matt_bertulli` | Matt Bertulli | m@mattbertulli.com |
| `chase_dimond` | Chase Dimond | chase@chasedimond.com, ecomemailmarketer@mail.beehiiv.com |
| `operators_newsletter` | Operators Newsletter | news@operatorscontent.com |
| `jordan_west` | Jordan West (Social Commerce Club) | jordanwestnewsletter@mail.beehiiv.com |
| `chew_on_this` | Chew On This (Obvi) | chew-on-this@mail.beehiiv.com |

`unclassified` is a reserved slug for issues whose sender could not be resolved —
they are quarantined there, never guessed and never dropped.

**Not subscribed** (verified absent from the mailbox 2026-08-01, searched all folders
including spam/trash): Cody Plofker, Andrew Faris / AJF Growth. Adding them needs a
subscribe from marketingteam@nickient.com, not a code change.

**Promo gate:** Jordan West and Chew On This run 30-50% promo (webinar invites,
agency hiring posts). `newsletter_ingestor.is_promo_only()` runs before extraction and
flags those `promo_only`, storing zero insights. It samples head+middle+tail — judging
on the first N chars misclassifies sponsor-funded issues, because the sponsor block
sits above the substance.

---

## n8n Workflows
| ID | Name | Schedule | Status |
|----|------|----------|--------|
| `FPWjPuFq2jkPkJmj` | Newsletter Daily Sync | Every 24h (`newer_than:2d`) | ACTIVE |
| `n2dv5cUA5ZaF3TPK` | YouTube Auto-Ingest | Daily 2am cron | ACTIVE |
| `sbhJSZEELdkQZVnG` | Historical Backfill | Manual only | INACTIVE |

**YouTube Auto-Ingest flow:** RSS feeds → diff against `/episodes` → POST `/process-one/async` for new videos → Slack summary to #ecas-ops

---

## Gmail Credential (n8n)
- Active: `DrHd2VFfLvVKxa8N` (Marketingteam@nickient.com)
- Dead (do not use): `LrrTIA7Dv6yJoAuP` — invalid_rapt OAuth error

---

## Frontend Features (operators-vault.vercel.app)

### Discover Page (/)
- Full-text search across all insights
- Left sidebar: 40+ topic filters grouped by section (Unit Economics, Email, Retention, Paid Acquisition, Growth, Ops)
- Content type filters: Frameworks, POVs, Quotes, Stories, Business Ideas, Products, Creator Tactics
- Source filter: by podcast or newsletters
- Result count with per-source breakdown ("23 from 9 Operators · 8 from Nik Sharma")
- Click any card → InsightModal with full content
- Thin results nudge (<6 results) → "Try Ask the Vault"

### InsightModal
- Full title + description
- For newsletter insights: shows newsletter subject/date, sibling insights from same issue, collapsible full body text
- For video insights: "Watch clip" button → YouTube at timestamp

### Speaker Pages (/speakers/[id])
- 3-tier fallback for surfacing insights:
  1. Explicit `insight_people` DB join
  2. FTS on insight text for speaker name
  3. FTS on transcript segments
  4. FTS on newsletter_insights
- Noisy attribution titles filtered ("Host introducing X", "Y via X")
- Shows amber badge when insights sourced via mention vs. explicit link

### Ask Page (/ask)
- RAG-based Q&A over full vault
- Authenticated (JWT required)
- Returns citations + sources
- **QA result (2026-03-28):** 87% pass rate across 15 test queries

### Other Pages
- `/episodes` — browse all indexed episodes
- `/newsletters` — browse newsletter archive
- `/speakers` — all speaker profiles
- `/guides` — AI-generated topic guides

---

## Backend Architecture (api.py on Railway)

### Search
- `websearch_to_tsquery` for FTS (more permissive than `plainto_tsquery`)
- Keyword OR-fallback in `/chat`: if full question returns 0 hits, strips stop words and retries with `keyword1 OR keyword2 OR ...`
- `/newsletter-insights` returns `newsletter_id` field for modal context loading

### Key Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /search` | FTS search over video insights (auth required) |
| `GET /newsletter-insights` | FTS search over newsletter insights (public) |
| `GET /speakers` | All speaker profiles |
| `GET /speakers/{id}` | Speaker detail with 4-tier insight fallback |
| `GET /newsletters/{id}` | Full newsletter body + all extracted insights |
| `GET /episodes` | All indexed episodes |
| `POST /process-one/async` | Ingest a single YouTube video by ID |
| `POST /chat` | RAG Q&A (auth required) |
| `GET /channels` | Active YouTube channel configs |

---

## Known Content Gaps (from QA 2026-03-28)
- **3PL / logistics** — thin coverage; 3 episodes ingested 2026-04-05 but transcription ongoing
- **Creator partnerships** — sparse; 2 episodes ingested
- **Unit economics depth** — CAC payback / contribution margin could go deeper

## Open Items
- No end-to-end test of Google sign-in → video insights flow documented
- Custom domain beyond vercel.app not set up
- `insight_people` table not populated by batch extraction — speaker pages rely on FTS fallback
