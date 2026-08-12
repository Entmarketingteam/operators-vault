CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE insights ADD COLUMN IF NOT EXISTS embedding halfvec(512);
ALTER TABLE newsletter_insights ADD COLUMN IF NOT EXISTS embedding halfvec(512);

CREATE INDEX IF NOT EXISTS insights_embedding_hnsw_idx
  ON insights USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS newsletter_insights_embedding_hnsw_idx
  ON newsletter_insights USING hnsw (embedding halfvec_cosine_ops);
