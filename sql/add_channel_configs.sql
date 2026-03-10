-- Migration: DB-backed channel and newsletter source configs
-- Idempotent: safe to run multiple times

CREATE TABLE IF NOT EXISTS channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,           -- e.g. "9operators"
    channel_handle TEXT NOT NULL,        -- e.g. "Operators9" (no @)
    display_name TEXT NOT NULL,          -- e.g. "9 Operators"
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed existing channels
INSERT INTO channel_configs (slug, channel_handle, display_name) VALUES
    ('9operators', 'Operators9', '9 Operators'),
    ('marketing_operator', 'MarketingOperators', 'Marketing Operators'),
    ('finance_operators', 'FinanceOperatorsFOPS', 'Finance Operators')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS newsletter_source_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    author TEXT NOT NULL,
    gmail_query TEXT NOT NULL,           -- e.g. "from:niksharma@workweek.com"
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO newsletter_source_configs (slug, author, gmail_query) VALUES
    ('nik_sharma', 'Nik Sharma', 'from:niksharma@workweek.com'),
    ('taylor_holiday', 'Taylor Holiday / CTC', 'from:taylorholiday@commonthreadco.com'),
    ('matt_bertulli', 'Matt Bertulli', 'from:m@mattbertulli.com'),
    ('chase_dimond', 'Chase Dimond', 'from:chase@chasedimond.com OR from:ecomemailmarketer@mail.beehiiv.com'),
    ('operators_newsletter', 'Operators Newsletter', 'from:news@operatorscontent.com')
ON CONFLICT (slug) DO NOTHING;
