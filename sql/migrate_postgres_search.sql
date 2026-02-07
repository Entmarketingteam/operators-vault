-- Operators Vault: Postgres full-text search migration (replaces Meilisearch)
-- Run in Supabase SQL Editor. Adds FTS + pg_trgm for insights and segments (timestamp moments).

-- ============================================
-- Step 1: Extensions and text search config
-- ============================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION immutable_unaccent(text)
RETURNS text AS $$
  SELECT unaccent($1);
$$ LANGUAGE sql IMMUTABLE;

DROP TEXT SEARCH CONFIGURATION IF EXISTS english_unaccent CASCADE;
CREATE TEXT SEARCH CONFIGURATION english_unaccent (COPY = english);
ALTER TEXT SEARCH CONFIGURATION english_unaccent
  ALTER MAPPING FOR hword, hword_part, word
  WITH unaccent, english_stem;

-- ============================================
-- Step 2: Segments – add video_id/podcast for search
-- ============================================
ALTER TABLE segments
  ADD COLUMN IF NOT EXISTS video_id TEXT,
  ADD COLUMN IF NOT EXISTS podcast TEXT;

-- Backfill from transcriptions + videos
UPDATE segments s
SET video_id = t.video_id,
    podcast = v.podcast
FROM transcriptions t
JOIN videos v ON v.video_id = t.video_id
WHERE s.transcription_id = t.id
  AND (s.video_id IS NULL OR s.podcast IS NULL);

CREATE INDEX IF NOT EXISTS idx_segments_video_id ON segments(video_id);
CREATE INDEX IF NOT EXISTS idx_segments_podcast ON segments(podcast);

-- FTS on segments (text + speaker_label)
ALTER TABLE segments
  ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (
    to_tsvector('english_unaccent', coalesce(text, '') || ' ' || coalesce(speaker_label, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_segments_fts ON segments USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_segments_text_trgm ON segments USING gin(text gin_trgm_ops);

-- ============================================
-- Step 3: Insights – FTS column and indexes
-- ============================================
ALTER TABLE insights
  ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english_unaccent', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english_unaccent', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english_unaccent', coalesce(framework_markdown, '') || ' ' || coalesce(source_chunk, '')), 'C')
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_insights_fts ON insights USING gin(fts);
CREATE INDEX IF NOT EXISTS idx_insights_title_trgm ON insights USING gin(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_insights_description_trgm ON insights USING gin(description gin_trgm_ops);

-- ============================================
-- Step 4: Videos – optional FTS for episode search
-- ============================================
ALTER TABLE videos
  ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (
    to_tsvector('english_unaccent', coalesce(title, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_videos_fts ON videos USING gin(fts);

-- ============================================
-- Step 5: Search functions (no anon grant – private vault)
-- ============================================

-- Search insights (keyword + fuzzy)
CREATE OR REPLACE FUNCTION search_insights(
  search_query TEXT,
  result_limit INTEGER DEFAULT 20,
  result_offset INTEGER DEFAULT 0,
  filter_podcast TEXT DEFAULT NULL,
  filter_category TEXT DEFAULT NULL,
  filter_video_id TEXT DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  video_id TEXT,
  podcast TEXT,
  category TEXT,
  title TEXT,
  description TEXT,
  start_time_sec NUMERIC,
  end_time_sec NUMERIC,
  rank REAL,
  headline_title TEXT,
  headline_description TEXT
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    i.id,
    i.video_id,
    i.podcast,
    i.category,
    i.title,
    i.description,
    i.start_time_sec,
    i.end_time_sec,
    (
      ts_rank_cd(i.fts, websearch_to_tsquery('english_unaccent', search_query)) * 2.0 +
      GREATEST(
        similarity(i.title, search_query),
        similarity(i.description, search_query) * 0.5
      )
    )::REAL AS rank,
    ts_headline(
      'english_unaccent',
      coalesce(i.title, ''),
      websearch_to_tsquery('english_unaccent', search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=25, MinWords=5'
    ) AS headline_title,
    ts_headline(
      'english_unaccent',
      coalesce(i.description, ''),
      websearch_to_tsquery('english_unaccent', search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=60, MinWords=15, MaxFragments=2'
    ) AS headline_description
  FROM insights i
  WHERE
    (
      i.fts @@ websearch_to_tsquery('english_unaccent', search_query)
      OR similarity(i.title, search_query) > 0.15
      OR similarity(i.description, search_query) > 0.1
    )
    AND (filter_podcast IS NULL OR i.podcast = filter_podcast)
    AND (filter_category IS NULL OR i.category = filter_category)
    AND (filter_video_id IS NULL OR i.video_id = filter_video_id)
  ORDER BY rank DESC
  LIMIT result_limit
  OFFSET result_offset;
END;
$$;

-- Search moments (segments with timestamps for jump-to)
CREATE OR REPLACE FUNCTION search_moments(
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
  text TEXT,
  speaker_label TEXT,
  rank REAL,
  headline TEXT
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id,
    s.video_id,
    s.podcast,
    s.start_time_sec,
    s.end_time_sec,
    s.text,
    s.speaker_label,
    (
      ts_rank_cd(s.fts, websearch_to_tsquery('english_unaccent', search_query)) * 2.0 +
      similarity(s.text, search_query)
    )::REAL AS rank,
    ts_headline(
      'english_unaccent',
      coalesce(s.text, ''),
      websearch_to_tsquery('english_unaccent', search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=50, MinWords=15, MaxFragments=2'
    ) AS headline
  FROM segments s
  WHERE
    s.video_id IS NOT NULL
    AND (
      s.fts @@ websearch_to_tsquery('english_unaccent', search_query)
      OR similarity(s.text, search_query) > 0.1
    )
    AND (filter_podcast IS NULL OR s.podcast = filter_podcast)
    AND (filter_video_id IS NULL OR s.video_id = filter_video_id)
  ORDER BY rank DESC
  LIMIT result_limit
  OFFSET result_offset;
END;
$$;

-- Combined search (insights + moments, top N each)
CREATE OR REPLACE FUNCTION search_all(
  search_query TEXT,
  result_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
  source TEXT,
  result_id TEXT,
  result_title TEXT,
  result_snippet TEXT,
  video_id TEXT,
  podcast TEXT,
  start_time_sec NUMERIC,
  rank REAL
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  (SELECT
    'insight'::TEXT AS source,
    i.id::TEXT AS result_id,
    i.title AS result_title,
    ts_headline('english_unaccent', coalesce(i.description, i.title, ''), websearch_to_tsquery('english_unaccent', search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=40, MinWords=15') AS result_snippet,
    i.video_id,
    i.podcast,
    i.start_time_sec,
    (ts_rank_cd(i.fts, websearch_to_tsquery('english_unaccent', search_query)) * 2.0)::REAL AS rank
  FROM insights i
  WHERE i.fts @@ websearch_to_tsquery('english_unaccent', search_query)
  ORDER BY rank DESC
  LIMIT result_limit)
  UNION ALL
  (SELECT
    'moment'::TEXT AS source,
    s.id::TEXT AS result_id,
    coalesce(s.speaker_label, 'Segment') AS result_title,
    ts_headline('english_unaccent', coalesce(s.text, ''), websearch_to_tsquery('english_unaccent', search_query),
      'StartSel=<mark>, StopSel=</mark>, MaxWords=40, MinWords=15') AS result_snippet,
    s.video_id,
    s.podcast,
    s.start_time_sec,
    (ts_rank_cd(s.fts, websearch_to_tsquery('english_unaccent', search_query)) * 1.5)::REAL AS rank
  FROM segments s
  WHERE s.video_id IS NOT NULL AND s.fts @@ websearch_to_tsquery('english_unaccent', search_query)
  ORDER BY rank DESC
  LIMIT result_limit)
  ORDER BY rank DESC
  LIMIT result_limit;
END;
$$;

-- Do not grant to anon (private vault: FastAPI calls with service connection)
