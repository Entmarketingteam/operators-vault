"use client";

import { useState, useEffect } from "react";
import { getEpisodes, type Episode } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Search, PlayCircle, Calendar, Clock, ExternalLink } from "lucide-react";

function getPodcastVariant(podcast?: string): "podcast" | "newsletter" {
  return "podcast";
}

function getPodcastDisplayName(podcast?: string): string {
  if (!podcast) return "Podcast";
  const map: Record<string, string> = {
    "9operators": "9 Operators",
    "9_operators": "9 Operators",
    "marketing_operator": "Marketing Operator",
    "finance_operators": "Finance Operators",
    "titans": "TITANS",
  };
  return map[podcast.toLowerCase()] || podcast;
}

function getPodcastColor(podcast?: string): string {
  if (!podcast) return "indigo";
  const p = podcast.toLowerCase();
  if (p.includes("finance")) return "emerald";
  if (p.includes("marketing")) return "violet";
  if (p.includes("titans")) return "amber";
  return "indigo";
}

function EpisodeRow({ episode }: { episode: Episode }) {
  const color = getPodcastColor(episode.podcast);
  const colorMap: Record<string, string> = {
    indigo: "bg-indigo-600/20 border-indigo-500/30 text-indigo-300",
    emerald: "bg-emerald-600/20 border-emerald-500/30 text-emerald-300",
    violet: "bg-violet-600/20 border-violet-500/30 text-violet-300",
    amber: "bg-amber-600/20 border-amber-500/30 text-amber-300",
  };
  const iconColor: Record<string, string> = {
    indigo: "text-indigo-400",
    emerald: "text-emerald-400",
    violet: "text-violet-400",
    amber: "text-amber-400",
  };

  return (
    <div className="vault-card p-4 group cursor-default">
      <div className="flex gap-4 items-start">
        {/* Thumbnail or icon */}
        {episode.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={episode.thumbnail_url}
            alt={episode.title}
            className="w-16 h-16 sm:w-20 sm:h-20 rounded-lg object-cover shrink-0 bg-[var(--secondary)]"
          />
        ) : (
          <div className={`w-16 h-16 sm:w-20 sm:h-20 rounded-lg border flex items-center justify-center shrink-0 ${colorMap[color]}`}>
            <PlayCircle className={`h-7 w-7 ${iconColor[color]}`} />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap gap-2 mb-1.5">
            {episode.podcast && (
              <Badge variant="podcast" className={`text-xs ${colorMap[color]}`}>
                {getPodcastDisplayName(episode.podcast)}
              </Badge>
            )}
          </div>
          <h3 className="font-semibold text-sm sm:text-base leading-snug group-hover:text-indigo-300 transition-colors line-clamp-2 mb-1.5">
            {episode.title}
          </h3>
          {episode.description && (
            <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 leading-relaxed hidden sm:block">
              {episode.description}
            </p>
          )}
          <div className="flex flex-wrap items-center justify-between mt-2">
            <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--muted-foreground)]">
              {episode.published_at && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {new Date(episode.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </span>
              )}
              {episode.duration && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {episode.duration}
                </span>
              )}
            </div>
            {episode.video_id && (
              <a
                href={`https://youtube.com/watch?v=${episode.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border border-[var(--border)] text-[var(--muted-foreground)] hover:border-indigo-500/40 hover:text-indigo-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <ExternalLink className="h-3 w-3" />
                Watch
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Fallback data
const FALLBACK_EPISODES: Episode[] = [
  { id: "1", title: "How to Build a $100M DTC Brand from Scratch", podcast: "9operators", published_at: "2024-01-15" },
  { id: "2", title: "Email Marketing Mastery: Retention Strategies That Work", podcast: "marketing_operator", published_at: "2024-02-10" },
  { id: "3", title: "The Finance Behind Scaling DTC Brands", podcast: "finance_operators", published_at: "2024-02-20" },
  { id: "4", title: "Influencer Strategy in 2024", podcast: "9operators", published_at: "2024-03-05" },
  { id: "5", title: "Paid Social That Actually Converts", podcast: "marketing_operator", published_at: "2024-03-18" },
];

export default function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [podcastFilter, setPodcastFilter] = useState("");

  useEffect(() => {
    getEpisodes().then((data) => {
      setEpisodes(data.length > 0 ? data : FALLBACK_EPISODES);
      setLoading(false);
    }).catch(() => {
      setEpisodes(FALLBACK_EPISODES);
      setLoading(false);
    });
  }, []);

  const podcasts = Array.from(new Set(episodes.map(e => e.podcast).filter(Boolean)));

  const filtered = episodes.filter((e) => {
    const matchSearch = !search || e.title.toLowerCase().includes(search.toLowerCase());
    const matchPodcast = !podcastFilter || e.podcast === podcastFilter;
    return matchSearch && matchPodcast;
  });

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 rounded-full bg-violet-600/10 border border-violet-500/20 px-4 py-1.5 text-sm text-violet-300 mb-6">
          <PlayCircle className="h-3.5 w-3.5" />
          Episode Catalog
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-3">
          Episode{" "}
          <span className="text-violet-400 bg-gradient-to-r from-violet-400 to-purple-400 bg-clip-text text-transparent">
            Catalog
          </span>
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] max-w-xl">
          Browse all episodes from 9 Operators, Marketing Operator, Finance Operators, and TITANS.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
          <Input
            placeholder="Search episodes..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setPodcastFilter("")}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all border ${
              podcastFilter === ""
                ? "bg-violet-600/20 text-violet-300 border-violet-500/40"
                : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-violet-500/30 hover:text-[var(--foreground)]"
            }`}
          >
            All Shows
          </button>
          {podcasts.map((p) => (
            <button
              key={p}
              onClick={() => setPodcastFilter(p || "")}
              className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all border ${
                podcastFilter === p
                  ? "bg-violet-600/20 text-violet-300 border-violet-500/40"
                  : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-violet-500/30 hover:text-[var(--foreground)]"
              }`}
            >
              {getPodcastDisplayName(p)}
            </button>
          ))}
        </div>
      </div>

      {/* Count */}
      {!loading && (
        <p className="text-sm text-[var(--muted-foreground)] mb-4">
          {filtered.length} episode{filtered.length !== 1 ? "s" : ""}
        </p>
      )}

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="space-y-3">
          {filtered.map((ep) => (
            <EpisodeRow key={ep.id} episode={ep} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">🎙️</div>
          <div className="font-semibold mb-1">No episodes found</div>
          <div className="text-sm text-[var(--muted-foreground)]">Try clearing your filters</div>
        </div>
      )}
    </div>
  );
}
