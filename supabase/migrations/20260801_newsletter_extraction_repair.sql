-- Repair the newsletter extraction pipeline.
-- Owner: operators-vault Supabase project wbdwnlzbgugewtmvahwg.
--
-- Why: api.py `_newsletter_extract_worker` has always opened each job with
--   SELECT processed, COALESCE(retry_count, 0) FROM newsletters WHERE id = %s
-- but `retry_count` / `last_error` were never created by any migration. Every
-- extraction job therefore threw UndefinedColumn on its first query, so no
-- newsletter has produced a searchable insight since ~2026-05 (2026-06 and
-- 2026-07: 30 issues stored, 0 with insights). Verified by direct probe.
--
-- `promo_only` lands here too so the ingest-time promo gate needs no second
-- migration.

-- last_error_at is referenced by the worker's retry/dead-letter UPDATE. It was
-- missing too, which made the failure *recorder* fail: the UPDATE threw
-- UndefinedColumn, the surrounding handler swallowed it as a warning, and
-- retry_count stayed 0 while extraction was quietly failing. Same bug class as
-- retry_count, one layer deeper — the error path was never exercised.
alter table newsletters
  add column if not exists retry_count   integer not null default 0,
  add column if not exists last_error    text,
  add column if not exists last_error_at timestamptz,
  add column if not exists promo_only    boolean not null default false;

-- Worker re-queue scans for unextracted rows; keep that lookup cheap.
create index if not exists newsletters_unprocessed
  on newsletters (processed, published_at desc)
  where processed = false;
