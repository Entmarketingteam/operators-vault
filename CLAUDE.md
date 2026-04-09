# Operators Vault — DTC Knowledge Base

## What This Is
Searchable knowledge base of DTC operator content: podcast transcripts + newsletter archives.
Powers RAG-based Q&A for ENT Agency internal research.

## Status: LIVE ✅ (last updated 2026-04-08)
- **308 videos** indexed across 4 podcast channels
- **5 newsletter sources** — daily sync active
- **11,000+ insights** in DB (273 junk entries cleaned 2026-03-27)

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

### Newsletter Sources (5)
1. Nik Sharma
2. Taylor Holiday / CTC
3. Matt Bertulli
4. Chase Dimond
5. Operators Newsletter

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
