-- Add host fields to speaker_profiles (idempotent)
ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS is_host BOOLEAN DEFAULT FALSE;
ALTER TABLE speaker_profiles ADD COLUMN IF NOT EXISTS host_podcast TEXT;
CREATE INDEX IF NOT EXISTS idx_speaker_profiles_is_host ON speaker_profiles(is_host) WHERE is_host = TRUE;
