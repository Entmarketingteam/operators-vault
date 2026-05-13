-- Enable RLS on all public tables to resolve Supabase advisor warning
-- rls_disabled_in_public. Backend uses service_role (bypasses RLS); frontend
-- anon client is auth-only and does not query tables directly, so no policies
-- are required. Applied to project wbdwnlzbgugewtmvahwg on 2026-05-13.

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insight_people ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.newsletter_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.newsletter_source_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.newsletters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.people ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seed_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.speaker_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.video_people ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.visual_moments ENABLE ROW LEVEL SECURITY;
