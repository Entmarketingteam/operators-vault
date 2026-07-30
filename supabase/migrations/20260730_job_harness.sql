-- Loop-harness state for autonomous jobs (loop-harness skill §4).
-- Owner: operators-vault Supabase project wbdwnlzbgugewtmvahwg.
create table if not exists job_runs (
  run_id uuid primary key default gen_random_uuid(),
  job_name text not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',  -- running|succeeded|circuit_open|failed
  handoff jsonb
);
create index if not exists job_runs_latest on job_runs (job_name, started_at desc);

create table if not exists job_checkpoints (
  job_name text not null,
  item_key text not null,
  status text not null,                    -- pending|done|quarantined
  evidence jsonb,
  error text,
  updated_at timestamptz not null default now(),
  primary key (job_name, item_key)
);
