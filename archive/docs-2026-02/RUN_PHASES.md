> **ARCHIVED — historical, does not reflect current state.** See `CLAUDE.md` at the repo root for what is actually true today. Archived 2026-09-03.

# Running the phases: pull data and process

Run these from the project root with `.env` containing at least `DATABASE_URL` (Supabase connection string). For YouTube fetch you also need `YOUTUBE_API_KEY`.

## One-command flows

```powershell
cd c:\Users\ethan.atchley\operators-vault
```

**Option A – CSV only (no YouTube API)**  
Uses your combined CSV (e.g. `Operators and Titans Podcast Historically until February 10 2026.csv` in Downloads). Seeds 9 Operators + TITANS from that file, then processes unprocessed videos.

```powershell
python scripts/run_all.py --csv-only
```

**Option B – YouTube fetch + process**  
Applies schema + Phase 1 migration, fetches from YouTube (and TITANS playlist if `YOUTUBE_PLAYLIST_TITANS` is set), then processes.

```powershell
python scripts/run_all.py
```

**Option C – CSV then YouTube then process**  
Seeds from CSVs (including the combined file) first, then fetches new from YouTube, then processes.

```powershell
python scripts/run_all.py --seed-csvs
```

## Step-by-step (same order as above)

1. **Schema** (if fresh DB)  
   `python scripts/run_schema.py`

2. **Phase 1 migration** (YouTube stats columns + TITANS)  
   `python scripts/run_migrate_phase1.py`

3. **Seed from CSVs** (optional)  
   Loads from `DEFAULT_CSV_PATHS` (see `youtube_client.py`), including:
   - `operators_and_titans` → path to your combined CSV; podcast inferred per row (TITANS vs 9operators).
   - Other keys if those CSV files exist in Downloads.  
   `python pipeline.py --seed-csvs`

4. **Fetch from YouTube** (optional, needs `YOUTUBE_API_KEY`)  
   `python pipeline.py --fetch-new`

5. **Process new** (transcribe + extract insights)  
   `python pipeline.py --process-new`

## Other options

- **Schema only:** `python scripts/run_all.py --schema-only`
- **Migration only:** `python scripts/run_all.py --migration-only`
- **Skip schema:** `python scripts/run_all.py --no-schema` (e.g. after first run)

## If the DB is unreachable

`DATABASE_URL` must point to a reachable Supabase instance. If you see "could not translate host name" or connection errors, run these commands from a machine/network that can reach Supabase (e.g. your own PC, not a restricted sandbox).
