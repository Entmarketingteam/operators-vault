-- Phase 1: YouTube stats columns + TITANS podcast support
-- Run in Supabase SQL Editor after schema.sql. Safe to run multiple times (ADD COLUMN IF NOT EXISTS).

-- Videos: add YouTube statistics and rich metadata
ALTER TABLE videos ADD COLUMN IF NOT EXISTS view_count BIGINT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS like_count BIGINT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS comment_count BIGINT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS channel_title TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS tags TEXT;

-- Podcast values: 9operators, marketing_operator, finance_operators, titans (no enum constraint)
