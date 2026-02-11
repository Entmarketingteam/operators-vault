-- Phase 2: People & Companies
-- Add companies table, enhance people table, add linking tables

-- Companies: brands, SaaS companies, etc. mentioned in episodes
CREATE TABLE IF NOT EXISTS companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  type TEXT,  -- 'brand' | 'saas' | 'other'
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_type ON companies(type);

-- Link insights to companies (many-to-many)
CREATE TABLE IF NOT EXISTS insight_companies (
  insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  PRIMARY KEY (insight_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_insight_companies_insight ON insight_companies(insight_id);
CREATE INDEX IF NOT EXISTS idx_insight_companies_company ON insight_companies(company_id);

-- Link videos to companies (many-to-many)
CREATE TABLE IF NOT EXISTS video_companies (
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  PRIMARY KEY (video_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_video_companies_video ON video_companies(video_id);
CREATE INDEX IF NOT EXISTS idx_video_companies_company ON video_companies(company_id);

-- Enhance people table: add slug for URLs
ALTER TABLE people ADD COLUMN IF NOT EXISTS slug TEXT;
ALTER TABLE people ADD COLUMN IF NOT EXISTS bio TEXT;
CREATE INDEX IF NOT EXISTS idx_people_slug ON people(slug) WHERE slug IS NOT NULL;

-- Link insights to people (for quotes, frameworks by person)
CREATE TABLE IF NOT EXISTS insight_people (
  insight_id UUID NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
  person_id UUID NOT NULL REFERENCES people(id) ON DELETE CASCADE,
  PRIMARY KEY (insight_id, person_id)
);

CREATE INDEX IF NOT EXISTS idx_insight_people_insight ON insight_people(insight_id);
CREATE INDEX IF NOT EXISTS idx_insight_people_person ON insight_people(person_id);

-- Add slug to companies for URLs
ALTER TABLE companies ADD COLUMN IF NOT EXISTS slug TEXT;
CREATE INDEX IF NOT EXISTS idx_companies_slug ON companies(slug) WHERE slug IS NOT NULL;
