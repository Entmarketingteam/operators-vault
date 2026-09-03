> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Railway API calls – sync and process

Use these so sync/process return **202 immediately** and run in the background. Avoids 502 "Application failed to respond" from long-running requests.

## Recommended: GET trigger (cron / n8n)

- **Full sync (fetch new + process all):**  
  `GET https://<your-railway-url>/trigger-sync`  
  If you set `SYNC_TRIGGER_KEY` in Railway → Variables, use:  
  `GET https://<your-railway-url>/trigger-sync?key=<SYNC_TRIGGER_KEY>`

- **Process unprocessed only:**  
  `GET https://<your-railway-url>/trigger-process-new`  
  Or with key: `GET .../trigger-process-new?key=<SYNC_TRIGGER_KEY>`

Response: **202** with JSON like:
```json
{"job_id": "uuid", "status": "running", "type": "sync", "jobs": "/jobs/uuid"}
```

Poll status: `GET https://<your-railway-url>/jobs/<job_id>`

## POST async (same behavior)

- **POST /sync/async** – full sync, returns 202 + job_id  
- **POST /process-new/async** – process all unprocessed, returns 202 + job_id  

## Check progress

- **GET /jobs/{job_id}** – `status`: `running` | `done` | `error`; when `done`, `result` has `upserted`, `processed`, `video_ids`
- **GET /stats** – per-podcast counts (videos, processed, unprocessed)

## Railway config

- **railway.json** in the repo sets `healthcheckPath: "/health"` so Railway pings `/health` for readiness.
- Ensure the service **port** in Railway matches the app (app uses `PORT` from env; Procfile uses `$PORT`).
