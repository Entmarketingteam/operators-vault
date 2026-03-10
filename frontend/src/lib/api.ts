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
}

export interface Speaker {
  id: string;
  name: string;
  company?: string;
  bio?: string;
  photo_url?: string;
  insight_count?: number;
  top_insights?: Insight[];
}

export interface Episode {
  id: string;
  title: string;
  podcast?: string;
  thumbnail_url?: string;
  published_at?: string;
  duration?: string;
  description?: string;
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

export async function searchInsights(query: string, token?: string, podcast?: string): Promise<Insight[]> {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (podcast) params.set("podcast", podcast);

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
    const items = Array.isArray(data) ? data : data.results || data.insights || [];
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
      const items = Array.isArray(data) ? data : data.results || data.insights || [];
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
  const res = await fetch(`${API_BASE}/episodes`).catch(() => null);
  if (!res?.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : data.episodes || [];
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
  _history: Array<{ role: string; content: string }>,
  token?: string
): Promise<{ reply: string; citations?: number; sources?: Insight[] }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, context_limit: 10 }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`);
  return res.json();
}
