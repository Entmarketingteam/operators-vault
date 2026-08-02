-- Give newsletter_insights the same weighted FTS column that insights already has.
-- Owner: operators-vault Supabase project wbdwnlzbgugewtmvahwg.
--
-- Why: search ranked video and newsletter hits against each other in one
-- `hits.sort(key=rank)` (api.py _search_postgres), but the two sides computed
-- ts_rank over structurally different vectors:
--
--   insights.fts            generated column, english_unaccent,
--                           setweight A=title, B=description, C=extras
--   newsletter_insights     to_tsvector('english', title || ' ' || description)
--                           computed inline per query, UNWEIGHTED
--
-- ts_rank scores a weighted vector far higher than an unweighted one, so
-- newsletters lost nearly every slot regardless of relevance — a CAC query on
-- the Discover page returned 98 video / 2 newsletter out of 100. /topic-guide
-- and /chat inherit that ranking, which is why generated guides cite podcast
-- timestamps and nothing else.
--
-- Mirroring the definition makes the two ranks comparable in kind. api.py still
-- min-max normalizes each side before merging, because equal weighting does not
-- by itself guarantee equal scale across two different corpora.

alter table newsletter_insights
  add column if not exists fts tsvector
  generated always as (
    setweight(to_tsvector('english_unaccent', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english_unaccent', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english_unaccent', coalesce(source_chunk, '')), 'C')
  ) stored;

create index if not exists idx_newsletter_insights_fts_weighted
  on newsletter_insights using gin (fts);

-- The old unweighted expression index backed the inline to_tsvector() call that
-- api.py no longer issues. Dropping it reclaims the space and stops Postgres
-- maintaining a second, redundant GIN index on every insert.
drop index if exists idx_newsletter_insights_fts;
