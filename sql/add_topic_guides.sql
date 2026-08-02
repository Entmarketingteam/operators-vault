CREATE TABLE IF NOT EXISTS topic_guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic TEXT UNIQUE NOT NULL,
  content TEXT NOT NULL,
  sources_json JSONB,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_topic_guides_topic ON topic_guides(topic);
