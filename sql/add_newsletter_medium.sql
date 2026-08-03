-- Articles alongside emails in the same newsletter tables.
--
-- CTC long-form articles (commonthreadco.com) merge into the existing
-- `taylor_holiday` source rather than getting their own table: newsletter_insights
-- already carries the weighted fts index, the rank normalization, the guide/chat
-- source quota and the modal's sibling loader. `medium` is what separates them.
--
-- 'email'        — ingested from Gmail (every pre-existing row)
-- 'article'      — evergreen long-form from commonthreadco.com
-- 'article_news' — platform-news roundup, stored but down-weighted in search, because
--                  ~13-25% of recent coachs-corner is AI-written "this week in ad
--                  platforms" content that would otherwise flood the newest slots.
--
-- Lives in sql/ (not supabase/migrations/) so _run_startup_migration applies it on
-- every Railway boot with no manual step. Idempotent.
--
-- NOTE: that runner splits this file on ";", so no statement-terminating semicolon
-- may appear inside a comment here or the fragment after it is executed as SQL.

ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS medium text NOT NULL DEFAULT 'email';
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS url text;

-- Search joins newsletters to filter/down-weight by medium; source+medium is the
-- access pattern (e.g. "taylor_holiday, evergreen articles only").
CREATE INDEX IF NOT EXISTS idx_newsletters_medium ON newsletters (medium);
CREATE INDEX IF NOT EXISTS idx_newsletters_source_medium ON newsletters (source, medium);

-- email_id already carries a UNIQUE constraint and holds the canonical article URL
-- for article rows, so idempotency needs nothing further. This index just makes
-- lookup-by-url explicit for the sync diff.
CREATE INDEX IF NOT EXISTS idx_newsletters_url ON newsletters (url) WHERE url IS NOT NULL;
