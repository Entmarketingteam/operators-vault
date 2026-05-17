const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE || "https://superb-smile-production.up.railway.app";

export interface Insight {
  id: string;
  title: string;
  description: string;
  source?: string;
  podcast?: string;
  category?: string;
  speaker?: string;
  speaker_name?: string;
  type?: string;
  score?: number;
  timestamp?: string;
  episode_title?: string;
  published_at?: string;
  author?: string;
  video_id?: string;
  start_time_sec?: string | number;
  is_multimodal?: boolean;
  // Newsletter-specific
  newsletter_id?: string;
  subject?: string;
  via_mention?: boolean;
}

export interface NewsletterDetail {
  id: string;
  source: string;
  author: string;
  subject: string;
  published_at?: string;
  body_text: string;
  insights: Array<{ id: string; category: string; title: string; description: string }>;
}

export interface Speaker {
  id: string;
  slug?: string;
  name: string;
  company?: string;
  title?: string;
  bio?: string;
  photo_url?: string;
  twitter_handle?: string;
  linkedin_url?: string;
  insight_count?: number;
  top_insights?: Insight[];
  insights?: Insight[];
  is_host?: boolean;
  host_podcast?: string;
  insights_via_mention?: boolean;
}

export interface Episode {
  id: string;
  title: string;
  podcast?: string;
  thumbnail_url?: string;
  published_at?: string;
  duration?: string;
  duration_seconds?: number;
  description?: string;
  video_id?: string;
  is_multimodal?: boolean;
}

export interface TopicGuide {
  topic: string;
  content: string;
  sources?: Insight[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Insight[];
}

export interface VisualMoment {
  id: string;
  start_time_sec: number;
  end_time_sec: number;
  description: string;
  transcript_excerpt?: string;
}

export async function searchInsights(query: string, token?: string, podcast?: string, limit = 100): Promise<Insight[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (podcast) params.set("podcast", podcast);
  params.set("limit", String(limit));

  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Newsletter insights (public)
  const newsletterRes = await fetch(
    `${API_BASE}/newsletter-insights?${params}`,
    { headers }
  ).catch(() => null);

  let results: Insight[] = [];

  if (newsletterRes?.ok) {
    const data = await newsletterRes.json();
    // Newsletter API uses "insights"
    const items = Array.isArray(data) ? data : data.results || data.insights || data.hits || [];
    results = [...results, ...items];
  }

  // Video insights (authenticated)
  if (token) {
    const videoRes = await fetch(
      `${API_BASE}/search?${params}`,
      { headers }
    ).catch(() => null);

    if (videoRes?.ok) {
      const data = await videoRes.json();
      // Search API uses "hits"
      const items = Array.isArray(data) ? data : data.hits || data.results || data.insights || [];
      results = [...results, ...items];
    }
  }

  return results;
}

export async function getSpeakers(): Promise<Speaker[]> {
  const res = await fetch(`${API_BASE}/speakers`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : data.speakers || [];
}

export async function getSpeaker(id: string): Promise<Speaker | null> {
  const res = await fetch(`${API_BASE}/speakers/${id}`).catch(() => null);
  if (!res?.ok) return null;
  return res.json();
}

export async function getEpisodes(): Promise<Episode[]> {
  const res = await fetch(`${API_BASE}/episodes?limit=500`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  const raw: Array<Record<string, unknown>> = Array.isArray(data) ? data : data.episodes || [];
  return raw.map((r) => ({
    id: (r.video_id as string) || (r.id as string) || "",
    title: (r.title as string) || "",
    podcast: r.podcast as string | undefined,
    thumbnail_url: r.thumbnail_url as string | undefined,
    published_at: r.published_at as string | undefined,
    duration: r.duration as string | undefined,
    duration_seconds: r.duration_seconds as number | undefined,
    description: r.description as string | undefined,
    video_id: (r.video_id as string) || undefined,
    is_multimodal: r.is_multimodal as boolean | undefined,
  }));
}

export interface NewsletterSource {
  slug: string;
  author: string;
  active: boolean;
}

export interface NewsletterInsight {
  id: string;
  source: string;
  author: string;
  category?: string;
  title: string;
  description: string;
  subject?: string;
  published_at?: string;
}

export interface Newsletter {
  id: string;
  source: string;
  author: string;
  subject: string;
  published_at?: string;
  processed: boolean;
  body_len?: number;
}

export async function getNewsletterSources(): Promise<NewsletterSource[]> {
  const res = await fetch(`${API_BASE}/newsletter-sources`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  return data.sources || [];
}

export async function getNewsletterInsights(source?: string, limit = 100): Promise<NewsletterInsight[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (source) params.set("source", source);
  const res = await fetch(`${API_BASE}/newsletter-insights?${params}`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : data.insights || [];
}

export async function getNewsletterDetail(newsletterId: string): Promise<NewsletterDetail | null> {
  const res = await fetch(`${API_BASE}/newsletters/${newsletterId}`).catch(() => null);
  if (!res?.ok) return null;
  return res.json();
}

export async function getVisualMoments(videoId: string, token: string): Promise<VisualMoment[]> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  
  const res = await fetch(`${API_BASE}/visual-moments?video_id=${videoId}`, { headers }).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  return data.moments || [];
}

export async function generateTopicGuide(topic: string): Promise<TopicGuide> {
  const res = await fetch(`${API_BASE}/topic-guide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error(`Failed to generate guide: ${res.statusText}`);
  return res.json();
}

export async function sendChatMessage(
  message: string,
  history: Array<{ role: string; content: string }>,
  token?: string
): Promise<{ reply: string; citations?: number; sources?: Insight[] }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/ask`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, history, context_limit: 20 }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`);
  return res.json();
}
