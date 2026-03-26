"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { supabase } from "@/lib/supabase";
import { searchInsights, type Insight } from "@/lib/api";
import {
  Search, Loader2, Sparkles, BookOpen, Users, Lightbulb,
  Quote, BookMarked, MessageSquare, Layers, Play, Mail,
  Podcast, ExternalLink, TrendingUp, Wrench, Target,
  DollarSign, ShoppingCart, Megaphone, BarChart2, Package,
  RefreshCw, Star, ChevronRight, X
} from "lucide-react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { signInWithGoogle } from "@/lib/supabase";

// ─── Constants ────────────────────────────────────────────────────────────────

// Content types (map to DB categories)
const CONTENT_TYPES = [
  { label: "All Content",       value: "",                          icon: Layers,       color: "slate"   },
  { label: "Frameworks",        value: "Frameworks and exercises",  icon: Lightbulb,    color: "amber"   },
  { label: "Tactical Recs",     value: "Tactical recommendations",  icon: Target,       color: "indigo"  },
  { label: "Points of View",    value: "Points of view",            icon: MessageSquare,color: "rose"    },
  { label: "Quotes",            value: "Quotes",                    icon: Quote,        color: "violet"  },
  { label: "Stories",           value: "Stories and case studies",  icon: BookMarked,   color: "emerald" },
  { label: "Tools & Products",  value: "Tools and products",        icon: Wrench,       color: "sky"     },
];

// ECOM topic quick-selects (trigger keyword search)
const ECOM_TOPICS = [
  { label: "Email Marketing",       query: "email marketing retention",              icon: Mail,        color: "violet" },
  { label: "Paid Social",           query: "paid social facebook meta ads scaling",  icon: BarChart2,   color: "blue"   },
  { label: "Retention & LTV",       query: "retention ltv customer lifetime value",  icon: RefreshCw,   color: "emerald"},
  { label: "Product Launch",        query: "product launch new product strategy",    icon: Package,     color: "amber"  },
  { label: "Influencer / Creator",  query: "influencer creator marketing campaign",  icon: Megaphone,   color: "rose"   },
  { label: "Brand Building",        query: "brand building dtc identity positioning",icon: Star,        color: "yellow" },
  { label: "DTC Strategy",          query: "dtc direct to consumer strategy growth", icon: ShoppingCart,color: "indigo" },
  { label: "Pricing & Offers",      query: "pricing offer discount promotion aov",   icon: DollarSign,  color: "teal"   },
  { label: "Subscription",          query: "subscription recurring revenue model",   icon: RefreshCw,   color: "sky"    },
  { label: "Operations",            query: "operations supply chain fulfillment 3pl", icon: Wrench,     color: "slate"  },
  { label: "Finance & P&L",         query: "finance profit loss margin contribution",icon: TrendingUp,  color: "green"  },
  { label: "AI & Automation",       query: "ai automation tools efficiency workflow",icon: Sparkles,    color: "fuchsia"},
];

const SOURCE_FILTERS = [
  { label: "All Sources",         value: "" },
  { label: "9 Operators",         value: "9operators" },
  { label: "Marketing Operator",  value: "marketing_operator" },
  { label: "Finance Operators",   value: "finance_operators" },
  { label: "TITANS",              value: "titans" },
  { label: "Newsletters",         value: "newsletters" },
];

// Color tokens
const colors: Record<string, { pill: string; dot: string; badge: string; text: string }> = {
  slate:   { pill: "bg-slate-500/15 text-slate-300 border-slate-500/30",   dot: "bg-slate-400",   badge: "bg-slate-500/10 text-slate-300 border-slate-400/20",   text: "text-slate-300"   },
  amber:   { pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",   dot: "bg-amber-400",   badge: "bg-amber-500/10 text-amber-300 border-amber-400/20",   text: "text-amber-300"   },
  indigo:  { pill: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",dot: "bg-indigo-400",  badge: "bg-indigo-500/10 text-indigo-300 border-indigo-400/20", text: "text-indigo-300"  },
  rose:    { pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",      dot: "bg-rose-400",    badge: "bg-rose-500/10 text-rose-300 border-rose-400/20",       text: "text-rose-300"    },
  violet:  { pill: "bg-violet-500/15 text-violet-300 border-violet-500/30",dot: "bg-violet-400",  badge: "bg-violet-500/10 text-violet-300 border-violet-400/20", text: "text-violet-300"  },
  emerald: { pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",dot:"bg-emerald-400",badge:"bg-emerald-500/10 text-emerald-300 border-emerald-400/20",text:"text-emerald-300"},
  sky:     { pill: "bg-sky-500/15 text-sky-300 border-sky-500/30",         dot: "bg-sky-400",     badge: "bg-sky-500/10 text-sky-300 border-sky-400/20",          text: "text-sky-300"     },
  blue:    { pill: "bg-blue-500/15 text-blue-300 border-blue-500/30",      dot: "bg-blue-400",    badge: "bg-blue-500/10 text-blue-300 border-blue-400/20",       text: "text-blue-300"    },
  teal:    { pill: "bg-teal-500/15 text-teal-300 border-teal-500/30",      dot: "bg-teal-400",    badge: "bg-teal-500/10 text-teal-300 border-teal-400/20",       text: "text-teal-300"    },
  green:   { pill: "bg-green-500/15 text-green-300 border-green-500/30",   dot: "bg-green-400",   badge: "bg-green-500/10 text-green-300 border-green-400/20",    text: "text-green-300"   },
  yellow:  { pill: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",dot: "bg-yellow-400",  badge: "bg-yellow-500/10 text-yellow-300 border-yellow-400/20", text: "text-yellow-300"  },
  fuchsia: { pill: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",dot:"bg-fuchsia-400",badge:"bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-400/20",text:"text-fuchsia-300"},
};

function getCategoryColor(category?: string): string {
  const c = (category || "").toLowerCase();
  if (c.includes("framework")) return "amber";
  if (c.includes("tactical")) return "indigo";
  if (c.includes("pov") || c.includes("perspective") || c.includes("point")) return "rose";
  if (c.includes("quote")) return "violet";
  if (c.includes("story") || c.includes("case")) return "emerald";
  if (c.includes("tool") || c.includes("product")) return "sky";
  return "slate";
}

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

// ─── Spotlight Card (featured insight) ────────────────────────────────────────

function SpotlightCard({ insight, label }: { insight: Insight; label: string }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isVideo = !!insight.video_id;
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(Number(insight.start_time_sec ?? 0))}`
    : undefined;

  const content = (
    <div className={`vault-card p-6 mb-6 border ${c.pill.split(" ")[2]} relative overflow-hidden group cursor-pointer`}>
      {/* BG gradient */}
      <div className={`absolute inset-0 opacity-5 ${c.pill.split(" ")[0]}`} />
      <div className="relative">
        <div className="flex items-center gap-2 mb-3">
          <span className={`text-xs font-bold uppercase tracking-widest ${c.text}`}>{label}</span>
          <span className={`h-1 w-1 rounded-full ${c.dot}`} />
          <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${c.badge}`}>
            {insight.category?.replace("and", "&")}
          </span>
        </div>
        <h2 className="text-lg font-bold leading-snug mb-3 group-hover:text-indigo-200 transition-colors">
          {insight.title?.replace(/\*\*/g, "")}
        </h2>
        <p className="text-sm text-[var(--muted-foreground)] leading-relaxed mb-4 line-clamp-3">
          {insight.description}
        </p>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)]">
            {source && (
              <span className="flex items-center gap-1">
                {insight.podcast ? <Podcast className="h-3 w-3" /> : <Mail className="h-3 w-3" />}
                {source}
              </span>
            )}
            {speaker && <span className={`font-medium ${c.text}`}>{speaker}</span>}
          </div>
          {isVideo && (
            <span className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${c.pill}`}>
              <Play className="h-3 w-3" /> Watch clip
            </span>
          )}
        </div>
      </div>
    </div>
  );

  return youtubeUrl ? (
    <a href={youtubeUrl} target="_blank" rel="noopener noreferrer">{content}</a>
  ) : <div>{content}</div>;
}

// ─── Insight Row ──────────────────────────────────────────────────────────────

function InsightRow({ insight }: { insight: Insight }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const isVideo = !!insight.video_id;
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(Number(insight.start_time_sec ?? 0))}`
    : undefined;
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isNewsletter = !insight.podcast && (insight.author || insight.source);

  const inner = (
    <div className="group flex items-start gap-3 px-4 py-3.5 vault-card hover:border-indigo-500/30 transition-all cursor-pointer">
      <div className={`shrink-0 mt-2 h-1.5 w-1.5 rounded-full ${c.dot}`} />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-1.5 mb-1">
          <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 py-0.5 rounded border ${isNewsletter ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"}`}>
            {isNewsletter ? <Mail className="h-2.5 w-2.5" /> : <Podcast className="h-2.5 w-2.5" />}
            {source}
          </span>
          {insight.category && (
            <span className={`text-[11px] px-1.5 py-0.5 rounded border ${c.badge}`}>
              {insight.category.replace("and", "&").replace("and perspectives","").replace("and exercises","").replace("and case studies","")}
            </span>
          )}
        </div>
        <p className="text-sm font-semibold leading-snug group-hover:text-indigo-300 transition-colors line-clamp-1">
          {insight.title?.replace(/\*\*/g, "")}
        </p>
        <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-1 mt-0.5">
          {insight.description}
        </p>
        {speaker && (
          <p className="text-[11px] text-[var(--muted-foreground)] mt-1">
            <span className={`font-medium ${c.text}`}>{speaker}</span>
          </p>
        )}
      </div>
      <div className="shrink-0 flex items-center self-center ml-2">
        {isVideo ? (
          <span className="flex items-center gap-1 text-xs text-indigo-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            <Play className="h-3 w-3" /> Watch
          </span>
        ) : (
          <ExternalLink className="h-3.5 w-3.5 text-[var(--muted-foreground)] opacity-0 group-hover:opacity-60 transition-opacity" />
        )}
      </div>
    </div>
  );

  return youtubeUrl
    ? <a href={youtubeUrl} target="_blank" rel="noopener noreferrer">{inner}</a>
    : inner;
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [activeTopic, setActiveTopic] = useState("");
  const [results, setResults] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setSessionLoaded(true);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  const doSearch = useCallback(async (
    q: string, src: string, type: string, token?: string
  ) => {
    setLoading(true);
    try {
      const podcast = src === "newsletters" ? "" : src;
      const searchQ = q || "DTC ecommerce brand growth marketing operator";
      let data = await searchInsights(searchQ, token, podcast);

      if (src === "newsletters") {
        data = data.filter(i => !i.podcast && (i.author || i.source));
      }
      if (type) {
        data = data.filter(i => {
          const cat = (i.category || "").toLowerCase();
          const t = type.toLowerCase();
          return cat.includes(t.split(" ")[0]);
        });
      }
      setResults(data);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!sessionLoaded) return;
    doSearch("", "", "", session?.access_token);
  }, [sessionLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard shortcut: / focuses search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    setActiveTopic("");
    doSearch(query, source, typeFilter, session?.access_token);
  };

  const handleTopic = (topic: typeof ECOM_TOPICS[0]) => {
    const next = activeTopic === topic.label ? "" : topic.label;
    setActiveTopic(next);
    setTypeFilter("");
    setQuery(next ? topic.query : "");
    doSearch(next ? topic.query : "", source, "", session?.access_token);
  };

  const handleType = (type: string) => {
    setTypeFilter(type);
    setActiveTopic("");
    doSearch(query || "", source, type, session?.access_token);
  };

  const handleSource = (src: string) => {
    setSource(src);
    doSearch(query || activeTopic ? (query || ECOM_TOPICS.find(t => t.label === activeTopic)?.query || "") : "", src, typeFilter, session?.access_token);
  };

  const clearAll = () => {
    setQuery(""); setSource(""); setTypeFilter(""); setActiveTopic("");
    doSearch("", "", "", session?.access_token);
  };

  const hasFilters = !!(query || source || typeFilter || activeTopic);
  const spotlight = results[0];
  const listResults = results.slice(1);

  // Count type per current dataset
  const typeCounts = CONTENT_TYPES.slice(1).reduce((acc, t) => {
    acc[t.value] = results.filter(r => r.category?.toLowerCase().includes(t.value.split(" ")[0].toLowerCase())).length;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">

      {/* ─── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-[var(--border)] py-5 px-3 gap-5 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">

        {/* ECOM Topics */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">ECOM Topics</div>
          <div className="space-y-0.5">
            {ECOM_TOPICS.map((topic) => {
              const Icon = topic.icon;
              const c = colors[topic.color] || colors.indigo;
              const active = activeTopic === topic.label;
              return (
                <button
                  key={topic.label}
                  onClick={() => handleTopic(topic)}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all text-left ${
                    active ? `${c.pill} border` : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"
                  }`}
                >
                  <Icon className="h-3 w-3 shrink-0" />
                  {topic.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content Type */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Content Type</div>
          <div className="space-y-0.5">
            {CONTENT_TYPES.map(({ label, value, icon: Icon, color }) => {
              const c = colors[color];
              const active = typeFilter === value;
              const count = value ? typeCounts[value] : results.length;
              return (
                <button
                  key={value}
                  onClick={() => handleType(value)}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all text-left ${
                    active ? `${c.pill} border` : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"
                  }`}
                >
                  <Icon className="h-3 w-3 shrink-0" />
                  <span className="flex-1">{label}</span>
                  {count > 0 && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${active ? "bg-white/20" : "bg-white/5 text-[var(--muted-foreground)]"}`}>
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Source */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Source</div>
          <div className="space-y-0.5">
            {SOURCE_FILTERS.map(({ label, value }) => {
              const active = source === value;
              return (
                <button
                  key={value}
                  onClick={() => handleSource(value)}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-all text-left ${
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

        {/* Tools */}
        <div>
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">AI Tools</div>
          <div className="space-y-0.5">
            {[
              { href: "/guides", icon: Sparkles, label: "Topic Guides" },
              { href: "/ask",    icon: BookOpen,  label: "Ask the Vault" },
            ].map(({ href, icon: Icon, label }) => (
              <Link key={href} href={href} className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5 transition-all">
                <Icon className="h-3 w-3 shrink-0" />{label}
              </Link>
            ))}
          </div>
        </div>

        {!session && sessionLoaded && (
          <div className="mt-auto pt-2 border-t border-[var(--border)]">
            <button onClick={() => signInWithGoogle()} className="w-full text-xs px-3 py-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 font-medium transition-colors">
              Sign in for video insights
            </button>
          </div>
        )}
      </aside>

      {/* ─── Main ─────────────────────────────────────────────────────────── */}
      <div className="flex-1 min-w-0 px-4 sm:px-6 py-5">

        {/* Search */}
        <form onSubmit={handleSearch} className="mb-4">
          <div className="relative max-w-2xl">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
            <input
              ref={searchRef}
              type="text"
              placeholder='Search insights… or press "/" to focus'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-10 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--secondary)] text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 transition-all"
            />
          </div>
        </form>

        {/* Mobile ECOM topic chips */}
        <div className="lg:hidden flex flex-wrap gap-1.5 mb-4">
          {ECOM_TOPICS.map((topic) => {
            const c = colors[topic.color] || colors.indigo;
            return (
              <button key={topic.label} onClick={() => handleTopic(topic)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-all ${activeTopic === topic.label ? `${c.pill}` : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"}`}
              >{topic.label}</button>
            );
          })}
        </div>

        {/* Mobile type chips */}
        <div className="lg:hidden flex flex-wrap gap-1.5 mb-4">
          {CONTENT_TYPES.map(({ label, value, color }) => {
            const c = colors[color];
            return (
              <button key={value} onClick={() => handleType(value)}
                className={`text-xs px-2.5 py-1 rounded-full border transition-all ${typeFilter === value ? `${c.pill}` : "border-[var(--border)] text-[var(--muted-foreground)]"}`}
              >{label}</button>
            );
          })}
        </div>

        {/* Active filter bar */}
        {hasFilters && (
          <div className="flex flex-wrap items-center gap-2 mb-4 text-xs">
            <span className="text-[var(--muted-foreground)]">Filtered by:</span>
            {activeTopic && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/5 border border-[var(--border)]">
                {activeTopic}
                <button onClick={() => { setActiveTopic(""); setQuery(""); doSearch("", source, typeFilter, session?.access_token); }}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            {typeFilter && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/5 border border-[var(--border)]">
                {CONTENT_TYPES.find(t => t.value === typeFilter)?.label}
                <button onClick={() => handleType("")}><X className="h-3 w-3" /></button>
              </span>
            )}
            {source && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/5 border border-[var(--border)]">
                {SOURCE_FILTERS.find(f => f.value === source)?.label}
                <button onClick={() => handleSource("")}><X className="h-3 w-3" /></button>
              </span>
            )}
            {query && !activeTopic && (
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/5 border border-[var(--border)]">
                &ldquo;{query}&rdquo;
                <button onClick={() => { setQuery(""); doSearch("", source, typeFilter, session?.access_token); }}>
                  <X className="h-3 w-3" />
                </button>
              </span>
            )}
            <button onClick={clearAll} className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] underline underline-offset-2 ml-1">
              Clear all
            </button>
          </div>
        )}

        {/* Result count */}
        {!loading && (
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs text-[var(--muted-foreground)]">
              {results.length} insight{results.length !== 1 ? "s" : ""}
              {activeTopic ? ` on ${activeTopic}` : typeFilter ? ` · ${CONTENT_TYPES.find(t=>t.value===typeFilter)?.label}` : ""}
            </span>
            {!session && sessionLoaded && (
              <button onClick={() => signInWithGoogle()} className="text-xs text-indigo-400 hover:underline hidden sm:inline">
                Sign in for video insights →
              </button>
            )}
          </div>
        )}

        {/* Results */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-7 w-7 animate-spin text-indigo-400" />
          </div>
        ) : results.length === 0 ? (
          <div className="text-center py-24">
            <div className="text-4xl mb-3">🔍</div>
            <div className="font-semibold mb-1">No results found</div>
            <div className="text-sm text-[var(--muted-foreground)] mb-4">Try different keywords or clear filters</div>
            <button onClick={clearAll} className="text-sm px-4 py-2 rounded-lg border border-[var(--border)] hover:bg-white/5 transition-colors">
              Clear filters
            </button>
          </div>
        ) : (
          <>
            {/* Spotlight */}
            {spotlight && hasFilters && (
              <SpotlightCard
                insight={spotlight}
                label={activeTopic || CONTENT_TYPES.find(t => t.value === typeFilter)?.label || "Top Result"}
              />
            )}

            {/* List */}
            <div className="space-y-1">
              {(hasFilters ? listResults : results).map((insight, i) => (
                <InsightRow key={insight.id || i} insight={insight} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
