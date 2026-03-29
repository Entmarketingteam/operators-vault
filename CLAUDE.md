# Operators Vault — DTC Knowledge Base

## What This Is
Searchable knowledge base of DTC operator content: podcast transcripts + newsletter archives.
Powers RAG-based Q&A for ENT Agency internal research.

## Status: LIVE ✅ (2026-03-15)
- 37 videos processed (9operators / marketing_operator / finance_operators)
- Newsletter pipeline live: 5 sources — fully fixed 2026-03-15

## Deploy
- **Railway:** `https://superb-smile-production.up.railway.app`
- **Supabase:** `wbdwnlzbgugewtmvahwg`

## Newsletter Sources (5)
1. Nik Sharma
2. Taylor Holiday / CTC
3. Matt Bertulli
4. Chase Dimond
5. Operators Newsletter

## n8n Workflows
- `sbhJSZEELdkQZVnG` — Historical backfill (run manually)
- `FPWjPuFq2jkPkJmj` — Daily sync newsletter (ACTIVE — every 24h, `newer_than:2d`)
- `n2dv5cUA5ZaF3TPK` — YouTube Auto-Ingest (ACTIVE — daily 2am cron, RSS→dedup→POST /process→Slack #ecas-ops)

## YouTube Channel IDs (for RSS feeds)
- `UCuGneytUApsb7SEynqoZ0ug` — @Operators9 (9operators + titans)
- `UCLCl2hY_E08Q9q2X1p6ouMA` — @MarketingOperators (marketing_operator)
- `UChL5rAxddwU_EnbhZofhDjw` — @FinanceOperatorsFOPS (finance_operators)

## Gmail Credential
- n8n credential ID: `DrHd2VFfLvVKxa8N` (Marketingteam@nickient.com) — updated 2026-03-15
- Old credential `LrrTIA7Dv6yJoAuP` is dead (invalid_rapt OAuth error) — do not use

## Pipeline Fixes (2026-03-15)
- `insight_extractor._anthropic_message`: routes through agent server proxy first, falls back to direct Anthropic API
- `store_newsletter_insights`: always marks processed=TRUE even when 0 insights extracted
- `upsert_newsletter`: updates body_text if new body is 2x longer (fixes truncated-then-processed emails)
- Both n8n workflows: Source Config hardcoded (no fetch()), recursive MIME parser for 3-level Beehiiv nesting

## Pending
- No open backfill items — pipeline fully operational ✅
