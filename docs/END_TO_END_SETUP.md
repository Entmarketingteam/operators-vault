# End-to-End Setup & Verification Guide

This guide ensures the entire Operators Vault stack works correctly for processing 36 videos.

## ✅ What's Been Fixed

### 1. Deepgram SDK v5 Compatibility (CRITICAL FIX)
- **Problem**: Code was using old v2 API (`Deepgram` class) which doesn't exist in v5.3.2
- **Fix**: Updated to use `DeepgramClient` and `PrerecordedOptions` (v5 API)
- **Files**: `deepgram_client.py`
- **Status**: ✅ Fixed and deployed

### 2. Anthropic API Model Update
- **Problem**: Using outdated model name `claude-sonnet-4-20250514`
- **Fix**: Updated to latest model `claude-sonnet-4-5-20250929`
- **Files**: `insight_extractor.py`, `api.py`, `visual_extractor.py`, `company_extractor.py`
- **Status**: ✅ Fixed and deployed

### 3. Enhanced Error Logging
- **Added**: Detailed error messages for transcription failures
- **Files**: `pipeline.py`, `api.py`, `deepgram_client.py`
- **Status**: ✅ Fixed and deployed

## 🔧 Required Environment Variables

### Railway (Backend)
Set these in Railway → Variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | ✅ Yes | Supabase PostgreSQL connection string |
| `DEEPGRAM_API_KEY` | ✅ Yes | Audio transcription |
| `ANTHROPIC_API_KEY` | ✅ Yes | Insight extraction (LLM) |
| `YOUTUBE_API_KEY` | ✅ Yes | Fetch new videos from channels |
| `SUPABASE_URL` | ✅ Yes | Frontend auth & config |
| `SUPABASE_ANON_KEY` | ✅ Yes | Frontend auth |
| `SUPABASE_JWT_SECRET` | ✅ Yes | Verify Bearer tokens for `/search` |
| `CORS_ORIGINS` | Optional | CORS allowed origins (default: `*`) |

### Supabase
1. **Database**: Ensure schema is applied (`sql/schema.sql`)
2. **Auth**: Enable Email/Password and Google OAuth in Dashboard
3. **API Keys**: Get from Settings → API

## 🧪 Verification Steps

### Step 1: Run End-to-End Verification Script

```bash
python scripts/verify_end_to_end.py
```

This tests:
- ✅ Database connection
- ✅ Deepgram API (client creation)
- ✅ Anthropic API (actual API call)
- ✅ YouTube API (optional)
- ✅ Supabase Auth config
- ✅ Railway API endpoints
- ✅ Processing pipeline imports

### Step 2: Test Railway Health Endpoint

```bash
curl https://superb-smile-production.up.railway.app/health
```

Should return:
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "youtube": "ok",
    "deepgram": "ok",
    "anthropic": "ok"
  }
}
```

### Step 3: Test Processing One Video

```bash
# Trigger async processing
curl -X POST https://superb-smile-production.up.railway.app/process-one/async \
  -H "Content-Type: application/json" \
  -d '{"video_id": "TEST_VIDEO_ID", "podcast": "9operators"}'

# Get job_id from response, then check status
curl https://superb-smile-production.up.railway.app/jobs/{job_id}
```

### Step 4: Process All 36 Videos

```bash
# Trigger sync (fetches new + processes unprocessed)
curl -X POST https://superb-smile-production.up.railway.app/sync/async

# Or use GET endpoint (for cron)
curl https://superb-smile-production.up.railway.app/trigger-sync

# Check job status
curl https://superb-smile-production.up.railway.app/jobs/{job_id}
```

## 📊 Monitoring Processing

### Check Job Status
```bash
GET /jobs/{job_id}
```

Response includes:
- `status`: `running` | `done` | `error`
- `result`: `{upserted, processed, video_ids, errors}`
- `logs`: `{stdout, stderr}` - detailed logs from processing

### Check Stats
```bash
GET /stats
```

Shows per-podcast:
- Total videos
- Processed (have transcription)
- Unprocessed
- Seed links count

## 🔍 Troubleshooting

### If Videos Fail to Process

1. **Check Railway Logs**:
   - Railway Dashboard → Logs
   - Look for `[deepgram]`, `[transcribe]`, `[ERROR]` messages

2. **Check Job Logs**:
   ```bash
   GET /jobs/{job_id}
   # Look at logs.stderr for detailed errors
   ```

3. **Common Issues**:
   - **Deepgram fails**: Check `DEEPGRAM_API_KEY` is set and valid
   - **Anthropic fails**: Check `ANTHROPIC_API_KEY` is set and valid
   - **Empty transcript**: Check audio file downloaded successfully
   - **Database errors**: Check `DATABASE_URL` connection string

### Verify Deepgram v5 Fix

Check logs for:
- ✅ `[deepgram] transcribe: DeepgramClient created successfully`
- ❌ `[deepgram] transcribe: Deepgram SDK not installed` (old error)

### Verify Anthropic Model

Check logs for:
- ✅ Successful API calls with model `claude-sonnet-4-5-20250929`
- ❌ Model not found errors (would indicate wrong model name)

## 🚀 Deployment Checklist

Before processing 36 videos:

- [ ] All environment variables set in Railway
- [ ] `verify_end_to_end.py` passes all tests
- [ ] `/health` endpoint shows all checks OK
- [ ] Test processing one video successfully
- [ ] Check Railway logs for any errors
- [ ] Verify Deepgram v5 API is working (check logs)
- [ ] Verify Anthropic API is working (check logs)

## 📝 Processing Flow

1. **Fetch New Videos** (`/fetch-new` or `/sync`)
   - Fetches from YouTube channels
   - Upserts into `videos` table

2. **Process Videos** (`/process-new` or `/sync`)
   - Downloads audio (yt-dlp)
   - Transcribes (Deepgram v5)
   - Extracts insights (Anthropic Claude)
   - Stores in database

3. **Monitor Progress**
   - Check `/jobs/{job_id}` for status
   - Check `/stats` for counts
   - Check Railway logs for details

## 🎯 Success Criteria

After running sync, you should see:
- ✅ 36 videos in `videos` table
- ✅ 36 transcriptions in `transcriptions` table
- ✅ Multiple insights in `insights` table
- ✅ No errors in job logs
- ✅ `/stats` shows `processed: 36`

## 📞 Next Steps

1. **Run verification**: `python scripts/verify_end_to_end.py`
2. **Trigger sync**: `POST /sync/async` or `GET /trigger-sync`
3. **Monitor**: Check `/jobs/{job_id}` until `status: done`
4. **Verify**: Check `/stats` to confirm all videos processed
