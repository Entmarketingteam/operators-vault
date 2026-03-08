-- Newsletter ingestion tables
-- Sources: nik_sharma | taylor_holiday | matt_bertulli | chase_dimond | operators_newsletter

CREATE TABLE IF NOT EXISTS newsletters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_id TEXT UNIQUE NOT NULL,           -- Gmail message ID
  source TEXT NOT NULL,                     -- nik_sharma | taylor_holiday | matt_bertulli | chase_dimond | operators_newsletter
  author TEXT,
  subject TEXT,
  published_at TIMESTAMPTZ,
  body_text TEXT,                           -- cleaned plain text
  processed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_newsletters_source ON newsletters(source);
CREATE INDEX IF NOT EXISTS idx_newsletters_email_id ON newsletters(email_id);
CREATE INDEX IF NOT EXISTS idx_newsletters_processed ON newsletters(processed);
CREATE INDEX IF NOT EXISTS idx_newsletters_published_at ON newsletters(published_at DESC);

CREATE INDEX IF NOT EXISTS idx_newsletters_fts ON newsletters
  USING GIN (to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_text, '')));

CREATE TABLE IF NOT EXISTS newsletter_insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  newsletter_id UUID NOT NULL REFERENCES newsletters(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  category TEXT NOT NULL,
  title TEXT,
  description TEXT,
  source_chunk TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_newsletter_insights_newsletter_id ON newsletter_insights(newsletter_id);
CREATE INDEX IF NOT EXISTS idx_newsletter_insights_source ON newsletter_insights(source);
CREATE INDEX IF NOT EXISTS idx_newsletter_insights_category ON newsletter_insights(category);

CREATE INDEX IF NOT EXISTS idx_newsletter_insights_fts ON newsletter_insights
  USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
