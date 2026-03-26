"use client";

import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/lib/supabase";
import { searchInsights, type Insight } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Search, Loader2, Sparkles, BookOpen, Users, Lightbulb,
  Quote, BookMarked, MessageSquare, Layers, Play, Mail,
  Podcast, ChevronRight, ExternalLink, TrendingUp
} from "lucide-react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { signInWithGoogle } from "@/lib/supabase";

// ─── Types ────────────────────────────────────────────────────────────────────

const TYPE_FILTERS = [
  { label: "All Insights", value: "", icon: Layers, color: "indigo" },
  { label: "Frameworks", value: "framework", icon: Lightbulb, color: "amber" },
  { label: "Quotes", value: "quote", icon: Quote, color: "violet" },
  { label: "Stories", value: "story", icon: BookMarked, color: "emerald" },
  { label: "Points of View", value: "pov", icon: MessageSquare, color: "rose" },
  { label: "Opinions", value: "opinion", icon: TrendingUp, color: "sky" },
];

const SOURCE_FILTERS = [
  { label: "All Sources", value: "", shortLabel: "All" },
  { label: "9 Operators", value: "9operators", shortLabel: "9OPS" },
  { label: "Marketing Operator", value: "marketing_operator", shortLabel: "MKT" },
  { label: "Finance Operators", value: "finance_operators", shortLabel: "FIN" },
  { label: "TITANS", value: "titans", shortLabel: "TTN" },
  { label: "Newsletters", value: "newsletters", shortLabel: "NWS" },
];

const EXAMPLE_SEARCHES = [
  "email retention", "paid social scaling", "product launch",
  "influencer ROI", "customer LTV", "brand building",
];

const colorMap: Record<string, { pill: string; badge: string; dot: string }> = {
  indigo: { pill: "bg-indigo-600/20 text-indigo-300 border-indigo-500/40", badge: "bg-indigo-500/20 text-indigo-200 border-indigo-500/30", dot: "bg-indigo-400" },
  amber:  { pill: "bg-amber-600/20 text-amber-300 border-amber-500/40",   badge: "bg-amber-500/20 text-amber-200 border-amber-500/30",   dot: "bg-amber-400"  },
  violet: { pill: "bg-violet-600/20 text-violet-300 border-violet-500/40", badge: "bg-violet-500/20 text-violet-200 border-violet-500/30", dot: "bg-violet-400" },
  emerald:{ pill: "bg-emerald-600/20 text-emerald-300 border-emerald-500/40", badge: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30", dot: "bg-emerald-400" },
  rose:   { pill: "bg-rose-600/20 text-rose-300 border-rose-500/40",       badge: "bg-rose-500/20 text-rose-200 border-rose-500/30",       dot: "bg-rose-400"   },
  sky:    { pill: "bg-sky-600/20 text-sky-300 border-sky-500/40",           badge: "bg-sky-500/20 text-sky-200 border-sky-500/30",           dot: "bg-sky-400"    },
};

function getPodcastShortName(podcast?: string): string {
  const map: Record<string, string> = {
    "9operators": "9 Operators",
    "9_operators": "9 Operators",
    "marketing_operator": "Marketing Operator",
    "finance_operators": "Finance Operators",
    "titans": "TITANS",
  };
  return podcast ? (map[podcast.toLowerCase()] || podcast) : "";
}

function getTypeColor(type?: string, category?: string): string {
  const t = (type || category || "").toLowerCase();
  if (t.includes("framework")) return "amber";
  if (t.includes("quote")) return "violet";
  if (t.includes("story") || t.includes("stories")) return "emerald";
  if (t.includes("pov") || t.includes("opinion")) return "rose";
  return "indigo";
}

// ─── Insight Row ──────────────────────────────────────────────────────────────

function InsightRow({ insight }: { insight: Insight }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const isVideo = !!insight.video_id;
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(Number(insight.start_time_sec ?? 0))}`
    : undefined;
  const typeColor = getTypeColor(insight.type, insight.category);
  const colors = colorMap[typeColor];
  const typeLabel = insight.type || insight.category || "insight";
  const isNewsletter = !insight.podcast && (insight.author || insight.source);

  const inner = (
    <div className="group flex items-start gap-4 p-4 vault-card hover:border-indigo-500/40 transition-all cursor-pointer">
      {/* Type indicator */}
      <div className={`shrink-0 mt-0.5 h-2 w-2 rounded-full ${colors.dot} opacity-80`} />

      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          {/* Source badge */}
          <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${isNewsletter ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"}`}>
            {isNewsletter ? <Mail className="h-3 w-3" /> : <Podcast className="h-3 w-3" />}
            {source}
          </span>
          {/* Type pill */}
          <span className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full border ${colors.badge}`}>
            {typeLabel}
          </span>
        </div>

        <h3 className="text-sm font-semibold leading-snug mb-1 group-hover:text-indigo-300 transition-colors line-clamp-2">
          {insight.title}
        </h3>
        <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-2">
          {insight.description}
        </p>

        {speaker && (
          <div className="mt-2 text-xs text-[var(--muted-foreground)]">
            <span className="text-indigo-400 font-medium">{speaker}</span>
          </div>
        )}
      </div>

      {/* Action */}
      <div className="shrink-0 flex items-center gap-1.5">
        {isVideo ? (
          <div className="flex items-center gap-1 text-xs text-indigo-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            <Play className="h-3.5 w-3.5" /> Watch
          </div>
        ) : (
          <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </div>
    </div>
  );

  if (youtubeUrl) {
    return (
      <a href={youtubeUrl} target="_blank" rel="noopener noreferrer">
        {inner}
      </a>
    );
  }
  return inner;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [results, setResults] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setSessionLoaded(true);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  const doSearch = useCallback(async (q: string, src: string, type: string, token?: string) => {
    setLoading(true);
    try {
      const podcast = src === "newsletters" ? "" : src;
      let data = await searchInsights(q || "DTC marketing ecommerce brand growth", token, podcast);
      if (src === "newsletters") {
        data = data.filter(i => !i.podcast && (i.author || i.source));
      }
      if (type) {
        data = data.filter(i =>
          i.type?.toLowerCase().includes(type) ||
          i.category?.toLowerCase().includes(type)
        );
      }
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on mount once session is known
  useEffect(() => {
    if (!sessionLoaded) return;
    doSearch(query, source, typeFilter, session?.access_token);
  }, [sessionLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    doSearch(query, source, typeFilter, session?.access_token);
  };

  const handleTypeFilter = (type: string) => {
    setTypeFilter(type);
    doSearch(query, source, type, session?.access_token);
  };

  const handleSourceFilter = (src: string) => {
    setSource(src);
    doSearch(query, src, typeFilter, session?.access_token);
  };

  const handleExampleSearch = (s: string) => {
    setQuery(s);
    doSearch(s, source, typeFilter, session?.access_token);
  };

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="hidden lg:flex flex-col w-56 shrink-0 border-r border-[var(--border)] py-6 px-4 gap-6 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">

        {/* Browse by Type */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--muted-foreground)] mb-3 px-1">Browse</div>
          <div className="space-y-0.5">
            {TYPE_FILTERS.map(({ label, value, icon: Icon, color }) => {
              const colors = colorMap[color];
              const active = typeFilter === value;
              return (
                <button
                  key={value}
                  onClick={() => handleTypeFilter(value)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left ${
                    active
                      ? `${colors.pill} border`
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Filter by Source */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--muted-foreground)] mb-3 px-1">Source</div>
          <div className="space-y-0.5">
            {SOURCE_FILTERS.map(({ label, value }) => {
              const active = source === value;
              return (
                <button
                  key={value}
                  onClick={() => handleSourceFilter(value)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all text-left ${
                    active
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 font-medium"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"
                  }`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60 shrink-0" />
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Quick links */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--muted-foreground)] mb-3 px-1">Tools</div>
          <div className="space-y-0.5">
            <Link href="/guides" className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5 transition-all">
              <Sparkles className="h-3.5 w-3.5 shrink-0" /> Topic Guides
            </Link>
            <Link href="/ask" className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5 transition-all">
              <BookOpen className="h-3.5 w-3.5 shrink-0" /> Ask the Vault
            </Link>
            <Link href="/speakers" className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5 transition-all">
              <Users className="h-3.5 w-3.5 shrink-0" /> Speakers
            </Link>
            <Link href="/episodes" className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5 transition-all">
              <Play className="h-3.5 w-3.5 shrink-0" /> Episodes
            </Link>
          </div>
        </div>

        {/* Auth */}
        {!session && sessionLoaded && (
          <div className="mt-auto">
            <div className="vault-card p-3 text-center">
              <p className="text-xs text-[var(--muted-foreground)] mb-2">Sign in for video insights</p>
              <button
                onClick={() => signInWithGoogle()}
                className="w-full text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
              >
                Sign in with Google
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 px-4 sm:px-6 lg:px-8 py-6">

        {/* Search bar */}
        <form onSubmit={handleSearch} className="mb-4">
          <div className="relative max-w-2xl">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
            <Input
              type="text"
              placeholder="Search insights, frameworks, strategies..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-10 h-11 text-sm"
            />
          </div>
        </form>

        {/* Example chips */}
        <div className="flex flex-wrap gap-1.5 mb-5">
          {EXAMPLE_SEARCHES.map((s) => (
            <button
              key={s}
              onClick={() => handleExampleSearch(s)}
              className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                query === s
                  ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40"
                  : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-indigo-500/30 hover:bg-indigo-600/10"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Mobile type/source filters */}
        <div className="lg:hidden mb-4 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {TYPE_FILTERS.map(({ label, value, color }) => {
              const colors = colorMap[color];
              return (
                <button key={value} onClick={() => handleTypeFilter(value)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                    typeFilter === value ? `${colors.pill}` : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >{label}</button>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {SOURCE_FILTERS.map(({ shortLabel, value }) => (
              <button key={value} onClick={() => handleSourceFilter(value)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-all ${
                  source === value ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40" : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >{shortLabel}</button>
            ))}
          </div>
        </div>

        {/* Active filter label */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {typeFilter || source ? (
              <div className="flex items-center gap-2 flex-wrap">
                {typeFilter && (
                  <Badge variant="secondary" className="text-xs gap-1">
                    {TYPE_FILTERS.find(f => f.value === typeFilter)?.label}
                    <button onClick={() => handleTypeFilter("")} className="ml-1 hover:text-foreground">×</button>
                  </Badge>
                )}
                {source && (
                  <Badge variant="secondary" className="text-xs gap-1">
                    {SOURCE_FILTERS.find(f => f.value === source)?.label}
                    <button onClick={() => handleSourceFilter("")} className="ml-1 hover:text-foreground">×</button>
                  </Badge>
                )}
              </div>
            ) : null}
            {!loading && (
              <span className="text-xs text-[var(--muted-foreground)]">
                {results.length} insights{query ? ` for "${query}"` : ""}
              </span>
            )}
          </div>
          {!session && sessionLoaded && (
            <span className="text-xs text-[var(--muted-foreground)] hidden sm:inline">
              <button onClick={() => signInWithGoogle()} className="text-indigo-400 hover:underline">Sign in</button> for video insights
            </span>
          )}
        </div>

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-7 w-7 animate-spin text-indigo-400" />
          </div>
        ) : results.length > 0 ? (
          <div className="space-y-1.5">
            {results.map((insight, i) => (
              <InsightRow key={insight.id || i} insight={insight} />
            ))}
          </div>
        ) : (
          <div className="text-center py-24">
            <div className="text-4xl mb-3">🔍</div>
            <div className="font-semibold mb-1">No results found</div>
            <div className="text-sm text-[var(--muted-foreground)] mb-4">Try different keywords or clear your filters</div>
            <button
              onClick={() => { setQuery(""); setSource(""); setTypeFilter(""); doSearch("", "", "", session?.access_token); }}
              className="text-sm px-4 py-2 rounded-lg border border-[var(--border)] hover:bg-white/5 transition-colors"
            >
              Clear filters
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
