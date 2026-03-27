"use client";

import { useState, useEffect } from "react";
import { getEpisodes, type Episode } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Search, PlayCircle, Calendar, Clock } from "lucide-react";
import { haptic } from "@/lib/haptics";

function getPodcastDisplayName(podcast?: string): string {
  if (!podcast) return "Podcast";
  const map: Record<string, string> = {
    "9operators": "Nine Operators",
    "9_operators": "Nine Operators",
    "marketing_operator": "Marketing Operators",
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

const colorStyles: Record<string, { badge: string; dot: string }> = {
  indigo: {
    badge: "bg-indigo-500/20 text-indigo-200 border-indigo-500/30",
    dot: "bg-indigo-400",
  },
  emerald: {
    badge: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30",
    dot: "bg-emerald-400",
  },
  violet: {
    badge: "bg-violet-500/20 text-violet-200 border-violet-500/30",
    dot: "bg-violet-400",
  },
  amber: {
    badge: "bg-amber-500/20 text-amber-200 border-amber-500/30",
    dot: "bg-amber-400",
  },
};

function formatDuration(seconds?: number): string | null {
  if (!seconds) return null;
  const mins = Math.round(seconds / 60);
  return `${mins} MIN`;
}

function getDescriptionPreview(description?: string): string {
  if (!description) return "";
  // Strip sponsor links and chapter headers, get first real paragraph
  const lines = description.split("\n").filter((l) => {
    const trimmed = l.trim();
    return (
      trimmed.length > 60 &&
      !trimmed.startsWith("http") &&
      !trimmed.startsWith("00:") &&
      !trimmed.startsWith("Chapters") &&
      !trimmed.startsWith("Powered By") &&
      !trimmed.includes("https://")
    );
  });
  return lines[0] || "";
}

function EpisodeCard({ episode }: { episode: Episode }) {
  const color = getPodcastColor(episode.podcast);
  const styles = colorStyles[color];
  const duration = formatDuration(episode.duration_seconds);
  const preview = getDescriptionPreview(episode.description);

  return (
    <a
      href={episode.video_id ? `https://youtube.com/watch?v=${episode.video_id}` : "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="group block vault-card overflow-hidden transition-all hover:border-[var(--primary)]/40 hover:shadow-lg hover:shadow-indigo-900/20"
    >
      <div className="flex flex-col sm:flex-row">
        {/* Thumbnail */}
        <div className="relative sm:w-72 sm:shrink-0 aspect-video sm:aspect-auto overflow-hidden bg-[var(--secondary)]">
          {episode.thumbnail_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={episode.thumbnail_url}
              alt={episode.title}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : episode.podcast && (episode.podcast === "marketing_operator" || episode.podcast === "finance_operators") ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/podcasts/${episode.podcast}.avif`}
              alt={getPodcastDisplayName(episode.podcast)}
              className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity"
            />
          ) : (
            <div className={`w-full h-full flex items-center justify-center ${styles.badge}`}>
              <PlayCircle className="h-12 w-12 opacity-60" />
            </div>
          )}
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
          <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="flex items-center gap-1.5 bg-black/70 backdrop-blur-sm text-white text-xs font-medium px-3 py-1.5 rounded-full">
              <PlayCircle className="h-3.5 w-3.5" />
              Watch
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex flex-col justify-between p-5 flex-1 min-w-0">
          <div>
            {/* Meta row */}
            <div className="flex flex-wrap items-center gap-2 mb-3">
              {episode.podcast && (
                <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${styles.badge}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${styles.dot}`} />
                  {getPodcastDisplayName(episode.podcast)}
                </span>
              )}
              {episode.published_at && (
                <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
                  <Calendar className="h-3 w-3" />
                  {new Date(episode.published_at).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              )}
              {duration && (
                <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
                  <Clock className="h-3 w-3" />
                  {duration}
                </span>
              )}
            </div>

            {/* Title */}
            <h3 className="font-bold text-lg leading-snug mb-3 group-hover:text-indigo-300 transition-colors line-clamp-3">
              {episode.title}
            </h3>

            {/* Description preview */}
            {preview && (
              <p className="text-sm text-[var(--muted-foreground)] leading-relaxed line-clamp-3 hidden sm:block">
                {preview}
              </p>
            )}
          </div>

          {/* Play button */}
          <div className="mt-4">
            <span className="inline-flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-full bg-indigo-600/20 border border-indigo-500/40 text-indigo-300 group-hover:bg-indigo-600/40 group-hover:border-indigo-400/60 group-hover:text-indigo-200 transition-all">
              <PlayCircle className="h-4 w-4" />
              Play Episode
            </span>
          </div>
        </div>
      </div>
    </a>
  );
}

export default function EpisodesPage() {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [podcastFilter, setPodcastFilter] = useState("");

  useEffect(() => {
    getEpisodes().then((data) => {
      setEpisodes(data);
      setLoading(false);
    }).catch(() => {
      setLoading(false);
    });
  }, []);

  const podcasts = Array.from(new Set(episodes.map(e => e.podcast).filter(Boolean)));

  const filtered = episodes.filter((e) => {
    const matchSearch = !search || e.title.toLowerCase().includes(search.toLowerCase()) ||
      (e.description || "").toLowerCase().includes(search.toLowerCase());
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
          Browse all episodes from 9 Operators, Marketing Operators, Finance Operators, and TITANS.
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
            onClick={() => { haptic("selection"); setPodcastFilter(""); }}
            className={`btn-base px-3.5 py-1.5 rounded-full text-xs font-semibold border ${
              podcastFilter === ""
                ? "bg-violet-600/20 text-violet-300 border-violet-500/40"
                : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-violet-500/30 hover:text-[var(--foreground)]"
            }`}
          >
            All Shows
          </button>
          {podcasts.map((p) => {
            const color = getPodcastColor(p);
            const styles = colorStyles[color];
            return (
              <button
                key={p}
                onClick={() => { haptic("selection"); setPodcastFilter(p || ""); }}
                className={`btn-base px-3.5 py-1.5 rounded-full text-xs font-semibold border ${
                  podcastFilter === p
                    ? `${styles.badge}`
                    : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-violet-500/30 hover:text-[var(--foreground)]"
                }`}
              >
                {getPodcastDisplayName(p)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Count */}
      {!loading && (
        <p className="text-sm text-[var(--muted-foreground)] mb-6">
          {filtered.length} episode{filtered.length !== 1 ? "s" : ""}
        </p>
      )}

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="space-y-4 stagger">
          {filtered.map((ep) => (
            <EpisodeCard key={ep.id} episode={ep} />
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
