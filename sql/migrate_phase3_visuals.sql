-- Phase 3: Visual moments (screen-share/slide detection)
-- Store visual moments detected in transcripts (e.g. "shows slide", "screen share", etc.)

CREATE TABLE IF NOT EXISTS visual_moments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  podcast TEXT NOT NULL,
  start_time_sec NUMERIC(10,2) NOT NULL,
  end_time_sec NUMERIC(10,2),
  description TEXT,  -- What's shown (e.g. "Slide: Pricing framework", "Screen share: Dashboard")
  transcript_excerpt TEXT,  -- Context from transcript
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_visual_moments_video_id ON visual_moments(video_id);
CREATE INDEX IF NOT EXISTS idx_visual_moments_podcast ON visual_moments(podcast);
CREATE INDEX IF NOT EXISTS idx_visual_moments_start_time ON visual_moments(start_time_sec);

-- FTS index for visual moments search
ALTER TABLE visual_moments ADD COLUMN IF NOT EXISTS fts tsvector;
CREATE INDEX IF NOT EXISTS idx_visual_moments_fts ON visual_moments USING GIN(fts);

-- Trigger to update FTS
CREATE OR REPLACE FUNCTION update_visual_moments_fts() RETURNS TRIGGER AS $$
BEGIN
  NEW.fts :=
    setweight(to_tsvector('english_unaccent', coalesce(NEW.description, '')), 'A') ||
    setweight(to_tsvector('english_unaccent', coalesce(NEW.transcript_excerpt, '')), 'B');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_visual_moments_fts ON visual_moments;
CREATE TRIGGER trigger_visual_moments_fts BEFORE INSERT OR UPDATE ON visual_moments
FOR EACH ROW EXECUTE FUNCTION update_visual_moments_fts();

-- Search function for visual moments
CREATE OR REPLACE FUNCTION search_visual_moments(
  search_query TEXT,
  result_limit INTEGER DEFAULT 20,
  result_offset INTEGER DEFAULT 0,
  filter_podcast TEXT DEFAULT NULL,
  filter_video_id TEXT DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  video_id TEXT,
  podcast TEXT,
  start_time_sec NUMERIC,
  end_time_sec NUMERIC,
  description TEXT,
  transcript_excerpt TEXT,
  rank REAL
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    v.id,
    v.video_id,
    v.podcast,
    v.start_time_sec,
    v.end_time_sec,
    v.description,
    v.transcript_excerpt,
    (
      ts_rank_cd(v.fts, websearch_to_tsquery('english_unaccent', search_query)) * 2.0 +
      similarity(coalesce(v.description, ''), search_query) * 0.5
    )::REAL AS rank
  FROM visual_moments v
  WHERE
    (
      v.fts @@ websearch_to_tsquery('english_unaccent', search_query)
      OR similarity(coalesce(v.description, ''), search_query) > 0.15
    )
    AND (filter_podcast IS NULL OR v.podcast = filter_podcast)
    AND (filter_video_id IS NULL OR v.video_id = filter_video_id)
  ORDER BY rank DESC
  LIMIT result_limit
  OFFSET result_offset;
END;
$$;
