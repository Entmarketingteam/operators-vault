-- Operators Vault: 9 Operators, Marketing Operator, Finance Operator
-- Supabase/Postgres schema: videos, transcriptions, segments, insights, people
-- Supports podcast/source_channel for filtering (9operators, marketing_operator, finance_operators).

-- Videos: one row per YouTube episode
CREATE TABLE IF NOT EXISTS videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT UNIQUE NOT NULL,
  title TEXT,
  duration_seconds INT,
  channel_id TEXT,
  podcast TEXT NOT NULL,  -- '9operators' | 'marketing_operator' | 'finance_operators'
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_podcast ON videos(podcast);
CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id);

-- Transcriptions: full transcript per video (Deepgram)
CREATE TABLE IF NOT EXISTS transcriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  raw_text TEXT,
  language TEXT DEFAULT 'en',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transcriptions_video_id ON transcriptions(video_id);

-- Segments: time-bounded utterances (optional; for diarization/segments)
CREATE TABLE IF NOT EXISTS segments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transcription_id UUID REFERENCES transcriptions(id) ON DELETE CASCADE,
  start_time_sec NUMERIC(10,2) NOT NULL,
  end_time_sec NUMERIC(10,2) NOT NULL,
  text TEXT,
  speaker_label TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_segments_transcription_id ON segments(transcription_id);

-- Insights: extracted per chunk; category and podcast for filtering
CREATE TABLE IF NOT EXISTS insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  podcast TEXT NOT NULL,
  category TEXT NOT NULL,  -- Frameworks and exercises | Points of view | Business ideas | Stories and anecdotes | Quotes | Products
  title TEXT,
  description TEXT,
  start_time_sec NUMERIC(10,2),
  end_time_sec NUMERIC(10,2),
  framework_markdown TEXT,
  source_chunk TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_insights_video_id ON insights(video_id);
CREATE INDEX IF NOT EXISTS idx_insights_podcast ON insights(podcast);
CREATE INDEX IF NOT EXISTS idx_insights_category ON insights(category);

-- People: optional; guests/speakers for future linking
CREATE TABLE IF NOT EXISTS people (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  role_or_title TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Optional: video_people many-to-many
CREATE TABLE IF NOT EXISTS video_people (
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  PRIMARY KEY (video_id, person_id)
);
