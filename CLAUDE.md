# Operators Vault — DTC Knowledge Base

## What This Is
Searchable knowledge base of DTC operator content: podcast transcripts + newsletter archives.
Powers RAG-based Q&A for ENT Agency internal research.

## Status: LIVE ✅ (2026-03-07)
- 37 videos processed (9operators / marketing_operator / finance_operators)
- Newsletter pipeline live: 5 sources

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
- `FPWjPuFq2jkPkJmj` — Daily sync (ACTIVE — every 24h, `newer_than:2d`)

## Pending ⚠️
- [ ] **BACKFILL NEEDED:** Run `sbhJSZEELdkQZVnG` manually to pull ~200+ historical emails per source
