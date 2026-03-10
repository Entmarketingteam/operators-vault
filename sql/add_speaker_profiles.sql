CREATE TABLE IF NOT EXISTS speaker_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    bio TEXT,
    twitter_handle TEXT,
    linkedin_url TEXT,
    photo_url TEXT,
    company TEXT,
    title TEXT,
    website TEXT,
    source TEXT DEFAULT 'manual',  -- 'manual' | 'perplexity' | 'auto'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_slug ON speaker_profiles(slug);
