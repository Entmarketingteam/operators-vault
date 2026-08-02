# Spec 1: Long-Form Audio Ingestion (90+ Minutes)

## Problem

The Operators Vault transcription pipeline (`deepgram_client.py`) did not handle audio files longer than ~90 minutes without risk of client-side timeout, memory pressure, or unbounded Deepgram request hangs. Videos like masterminds, full-day events, and multi-hour podcasts (5–6 hours common) would either fail silently or timeout mid-transcription.

## Solution: Chunking + Stitching

**Workflow:**
1. Check audio duration via `ffprobe` 
2. If > 60 min, split into ~60-min chunks via ffmpeg
3. Transcribe each chunk separately with explicit timeout (1200s / 20 min per chunk)
4. Stitch utterance timestamps back together with offsets (preserving original timeline)
5. Clean up temporary chunk files
6. Return combined result as single response

**Why 60-min chunks?**
- Fits comfortably within Deepgram's response-time SLA (typically 2–5 min for 60 min of audio, depending on model)
- 20-min client-side timeout per chunk gives ample buffer for network jitter
- Deepgram nova-2 diarization stability drops after ~90 min in a single call (empirically observed in prior long-form ingests)
- Allows independent retry on a single chunk without re-transcribing the whole file

## Implementation

**File:** `~/Desktop/operators-vault/deepgram_client.py`

**New Functions:**
- `_get_audio_duration_sec(audio_path: Path) -> float | None` — probe via ffprobe
- `_split_audio_chunks(audio_path: Path, chunk_duration_sec: int = 3600) -> list[Path]` — ffmpeg split; returns list of temp paths
- `_transcribe_chunk(..., timeout_sec: int = 1200)` — single-chunk transcribe with explicit timeout kwarg passed to Deepgram SDK

**Modified:**
- `transcribe()` now checks duration, conditionally chunks, loops over chunks with timestamp offset tracking, stitches results
- Temp chunk files auto-cleaned on success or error

## Verification

**Test 1: Duration Check**
```bash
# Confirm a 6-hour file is detected as needing chunking
python3 -c "
from pathlib import Path
from deepgram_client import _get_audio_duration_sec
audio = Path('/tmp/hudson_ecom_mastermind.m4a')
dur = _get_audio_duration_sec(audio)
print(f'Duration: {dur:.0f} sec ({dur/3600:.2f} hours)')
assert dur > 3600, 'Expected > 60 min'
"
```

**Test 2: Chunking**
```bash
# Ingest a real long-form stream and verify status
curl 'https://superb-smile-production.up.railway.app/jobs/{job_id}' | jq .status
# Expected: "completed" (not "failed" or "timeout")
```

**Test 3: Timestamp Integrity**
```bash
# Query DB for the ingested Hudson streams
psql -h db.supabase.co -U postgres -d operators_vault -c "
SELECT video_id, COUNT(*) as utterance_count, 
  MAX(end_time_sec) as max_timestamp
FROM segments 
WHERE podcast = 'hudson_legrande_mastermind'
GROUP BY video_id;"

# Expected: max_timestamp aligns with original video duration (e.g., 20800+ sec for ~5.8 hour video)
```

## Decision Rule: When to Chunk

| Audio Length | Action | Reasoning |
|---|---|---|
| < 60 min | Send whole | Fits well within Deepgram limits |
| 60–90 min | Send whole, but monitor | Edge case; may timeout on slow connection |
| 90+ min | **Always chunk** | Reduces risk; preserves diarization quality |

Controlled via `chunk_long_audio=True` parameter in `transcribe()` (default: True). Can be disabled for testing or short bursts.

## Rollback

If chunking causes issues (e.g., timestamp misalignment):
- Pass `chunk_long_audio=False` to `transcribe()` to force single-call behavior
- Add to environment: `DEEPGRAM_NO_CHUNK=1` to flip default globally

## Future Improvements

1. **Adaptive chunk size** — detect audio bitrate and adjust chunk size (low-bitrate audio can use larger chunks)
2. **Parallel chunking** — transcribe 2–3 chunks concurrently if Deepgram quota allows (risk: diarization consistency)
3. **Resume on failure** — if chunk N fails, store which chunks succeeded and resume from N+1 on retry
