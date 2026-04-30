---
project: Operators Vault Ingestion
status: newsletter sync OK, Railway YouTube transcripts broken
last_updated: 2026-04-30
---

# RESUME-HERE — Operators Vault Ingestion

> Auto-ingest newsletters + YouTube transcripts into the Operators knowledge base.

## Last session state

Newsletter sync: FIXED. YouTube ingest n8n workflow: FIXED. **Railway yt-dlp / transcript extraction: BROKEN.** All workflows alert via `marketingteam@entagency.co`.

---

## Blockers

1. **Fix Railway yt-dlp / transcript extraction** — root cause unknown, currently failing transcript pull. Check Railway logs + yt-dlp version pinning
2. **Decide whether to migrate transcript work off Railway** — alternatives: Deepgram on Railway, or Modal / direct YouTube Data API captions

---

## Backlog

- Add a daily digest of new ingested content to Slack/email
- Backfill historical newsletter archive for the operators we care about

## Resume Prompt

```
Read RESUME-HERE.md in Entmarketingteam/operators-vault. Tail the Railway logs
for the transcript service and help me debug the yt-dlp failure.
```
