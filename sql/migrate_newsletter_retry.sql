-- Add retry tracking + dead-letter fields to newsletters so failed Claude
-- extractions surface instead of silently sitting at processed=FALSE forever.
ALTER TABLE newsletters
  ADD COLUMN IF NOT EXISTS retry_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_error TEXT,
  ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMPTZ;

-- Index helps the worker re-pick failed-but-retryable items quickly.
CREATE INDEX IF NOT EXISTS idx_newsletters_unprocessed_retry
  ON newsletters (processed, retry_count)
  WHERE processed = FALSE;
