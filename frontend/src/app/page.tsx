"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { supabase, signInWithGoogle } from "@/lib/supabase";
import { 
  searchInsights, 
  getNewsletterDetail, 
  getVisualMoments,
  type Insight, 
  type NewsletterDetail,
  type VisualMoment
} from "@/lib/api";
import {
  Search, Loader2, Sparkles, BookOpen, Users, Lightbulb,
  Quote, BookMarked, MessageSquare, Layers, Play, Mail,
  Podcast, ExternalLink, TrendingUp, TrendingDown, Wrench, Target,
  DollarSign, ShoppingCart, Megaphone, BarChart2, Package,
  RefreshCw, Star, X, Monitor, Gift, AlertTriangle,
  Inbox, MailOpen, Activity, Zap, Building2, FileText,
  PieChart, CreditCard, Clock, LayoutGrid, PlayCircle
} from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { haptic } from "@/lib/haptics";

// ─── Constants & Helpers ──────────────────────────────────────────────────

const colors: Record<string, { pill: string; dot: string; badge: string; text: string }> = {
  indigo:  { pill: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",   dot: "bg-indigo-400",  badge: "bg-indigo-500/10 text-indigo-300 border-indigo-400/20",  text: "text-indigo-300"  },
  amber:   { pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",     dot: "bg-amber-400",   badge: "bg-amber-500/10 text-amber-300 border-amber-400/20",   text: "text-amber-300"   },
  rose:    { pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",         dot: "bg-rose-400",    badge: "bg-rose-500/10 text-rose-300 border-rose-400/20",        text: "text-rose-300"    },
  violet:  { pill: "bg-violet-500/15 text-violet-300 border-violet-500/30",   dot: "bg-violet-400",  badge: "bg-violet-500/10 text-violet-300 border-violet-400/20",  text: "text-violet-300"  },
  emerald: { pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",dot: "bg-emerald-400", badge: "bg-emerald-500/10 text-emerald-300 border-emerald-400/20",text: "text-emerald-300" },
  sky:     { pill: "bg-sky-500/15 text-sky-300 border-sky-500/30",            dot: "bg-sky-400",     badge: "bg-sky-500/10 text-sky-300 border-sky-400/20",           text: "text-sky-300"     },
  blue:    { pill: "bg-blue-500/15 text-blue-300 border-blue-500/30",         dot: "bg-blue-400",    badge: "bg-blue-500/10 text-blue-300 border-blue-400/20",        text: "text-blue-300"    },
  teal:    { pill: "bg-teal-500/15 text-teal-300 border-teal-500/30",         dot: "bg-teal-400",    badge: "bg-teal-500/10 text-teal-300 border-teal-400/20",        text: "text-teal-300"    },
  green:   { pill: "bg-green-500/15 text-green-300 border-green-500/30",      dot: "bg-green-400",   badge: "bg-green-500/10 text-green-300 border-green-400/20",     text: "text-green-300"   },
  yellow:  { pill: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",   dot: "bg-yellow-400",  badge: "bg-yellow-500/10 text-yellow-300 border-yellow-400/20",  text: "text-yellow-300"  },
  fuchsia: { pill: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",dot: "bg-fuchsia-400", badge: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-400/20",text: "text-fuchsia-300" },
  slate:   { pill: "bg-slate-500/15 text-slate-300 border-slate-500/30",     dot: "bg-slate-400",   badge: "bg-slate-500/10 text-slate-300 border-slate-400/20",   text: "text-slate-300"   },
};

const sectionAccent: Record<string, string> = {
  emerald: "text-emerald-400",
  violet:  "text-violet-400",
  blue:    "text-blue-400",
  amber:   "text-amber-400",
  slate:   "text-slate-400",
  green:   "text-green-400",
};

function getCategoryColor(category?: string): string {
  const c = (category || "").toLowerCase();
  if (c.includes("framework")) return "amber";
  if (c.includes("tactical")) return "blue";
  if (c.includes("pov") || c.includes("perspective") || c.includes("point")) return "rose";
  if (c.includes("quote")) return "violet";
  if (c.includes("stor") || c.includes("anecdote") || c.includes("case")) return "emerald";
  if (c.includes("business idea")) return "indigo";
  if (c.includes("creator") || c.includes("influencer")) return "teal";
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

// ─── Spotlight Card ────────────────────────────────────────────────────────

function SpotlightCard({ insight, label, onExpand }: { insight: Insight; label: string; onExpand: (i: Insight) => void }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isVideo = !!insight.video_id;

  return (
    <button
      className={`w-full text-left vault-card p-6 mb-6 border ${c.pill.split(" ")[2]} relative overflow-hidden group cursor-pointer`}
      onClick={() => onExpand(insight)}
    >
      <div className={`absolute inset-0 opacity-5 ${c.pill.split(" ")[0]}`} />
      <div className="relative">
        <div className="flex items-center gap-2 mb-3">
          <span className={`text-xs font-bold uppercase tracking-widest ${c.text}`}>{label}</span>
          <span className={`h-1 w-1 rounded-full ${c.dot}`} />
          <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${c.badge}`}>
            {insight.category?.replace("and", "&")}
          </span>
          {insight.is_multimodal && (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
              <Monitor className="h-2.5 w-2.5" /> Multimodal
            </span>
          )}
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
          <span className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full border ${c.pill}`}>
            {isVideo ? <><Play className="h-3 w-3" /> Watch clip</> : <><ExternalLink className="h-3 w-3" /> Read more</>}
          </span>
        </div>
      </div>
    </button>
  );
}

// ─── Insight Detail Modal ─────────────────────────────────────────────────

function InsightModal({ insight, onClose, session }: { insight: Insight; onClose: () => void; session: Session | null }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isVideo = !!insight.video_id;
  const startSec = Math.floor(Number(insight.start_time_sec ?? 0));
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${startSec}s`
    : undefined;
  const isNewsletter = !insight.podcast && (insight.author || insight.source);

  const [newsletter, setNewsletter] = useState<NewsletterDetail | null>(null);
  const [loadingNewsletter, setLoadingNewsletter] = useState(false);
  const [showFullText, setShowFullText] = useState(false);
  
  const [visualMoments, setVisualMoments] = useState<VisualMoment[]>([]);
  const [loadingMoments, setLoadingMoments] = useState(false);

  // Load full newsletter when it's a newsletter insight with a newsletter_id
  useEffect(() => {
    if (isNewsletter && insight.newsletter_id) {
      setLoadingNewsletter(true);
      getNewsletterDetail(insight.newsletter_id).then(d => {
        setNewsletter(d);
        setLoadingNewsletter(false);
      });
    }
  }, [insight.newsletter_id, isNewsletter]);

  // Load visual moments for videos
  useEffect(() => {
    if (isVideo && insight.video_id && session?.access_token) {
      setLoadingMoments(true);
      getVisualMoments(insight.video_id, session.access_token).then(moments => {
        setVisualMoments(moments);
        setLoadingMoments(false);
      });
    }
  }, [insight.video_id, isVideo, session?.access_token]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Group sibling insights by category
  const siblingsByCategory = newsletter?.insights
    ? newsletter.insights.reduce((acc, ins) => {
        if (ins.id === insight.id) return acc; // skip the current one
        const cat = ins.category || "Other";
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(ins);
        return acc;
      }, {} as Record<string, typeof newsletter.insights>)
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative z-10 w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl animate-scale-in"
        onClick={e => e.stopPropagation()}
      >
        <div className={`absolute top-0 inset-x-0 h-1 rounded-t-2xl ${c.dot}`} />

        <div className="p-5 sm:p-6">
          <div className="sm:hidden mx-auto mb-4 h-1 w-10 rounded-full bg-white/20" />

          {/* meta */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 py-0.5 rounded border ${isNewsletter ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"}`}>
              {isNewsletter ? <Mail className="h-2.5 w-2.5" /> : <Podcast className="h-2.5 w-2.5" />}
              {source}
            </span>
            {insight.category && (
              <span className={`text-[11px] px-1.5 py-0.5 rounded border ${c.badge}`}>
                {insight.category?.replace("and", "&").replace("perspectives","").replace("exercises","").replace("case studies","")}
              </span>
            )}
            {speaker && <span className={`text-[11px] font-medium ${c.text}`}>{speaker}</span>}
            {insight.is_multimodal && (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
                <Monitor className="h-2.5 w-2.5" /> Multimodal
              </span>
            )}
            {newsletter?.published_at && (
              <span className="text-[11px] text-[var(--muted-foreground)]">
                {new Date(newsletter.published_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </span>
            )}
          </div>

          {/* newsletter subject */}
          {newsletter?.subject && (
            <p className="text-[11px] font-semibold text-[var(--muted-foreground)] mb-2 italic">&ldquo;{newsletter.subject}&rdquo;</p>
          )}

          {/* title */}
          <h2 className="text-base sm:text-lg font-bold leading-snug mb-3">
            {insight.title?.replace(/\*\*/g, "")}
          </h2>

          {/* description */}
          {insight.description && (
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed whitespace-pre-wrap">
              {insight.description}
            </p>
          )}

          {/* ── Visual Timeline (Multimodal Data) ── */}
          {isVideo && (visualMoments.length > 0 || loadingMoments) && (
            <div className="mt-6 space-y-4">
              <div className="flex items-center gap-2">
                <div className="h-px flex-1 bg-[var(--border)]" />
                <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] whitespace-nowrap flex items-center gap-1.5">
                  <Monitor className="h-3 w-3" /> Visual Timeline
                </span>
                <div className="h-px flex-1 bg-[var(--border)]" />
              </div>
              
              {loadingMoments ? (
                <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  <Loader2 className="h-3 w-3 animate-spin" /> Analyzing video timeline…
                </div>
              ) : (
                <div className="space-y-3 relative pl-4 border-l border-[var(--border)] ml-2">
                  {visualMoments.map((m, idx) => (
                    <div key={m.id} className="relative group">
                      <div className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full border-2 border-[var(--card)] bg-indigo-500`} />
                      <div className="flex items-start gap-3">
                        <a 
                          href={`https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(m.start_time_sec)}s`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] font-mono font-bold text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded shrink-0 hover:bg-indigo-500/20 transition-colors"
                        >
                          {Math.floor(m.start_time_sec / 60)}:{(Math.floor(m.start_time_sec % 60)).toString().padStart(2, '0')}
                        </a>
                        <p className="text-xs text-[var(--muted-foreground)] leading-tight group-hover:text-[var(--foreground)] transition-colors pt-0.5">
                          {m.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Newsletter extras ── */}
          {isNewsletter && (
            <div className="mt-5 space-y-4">
              {loadingNewsletter && (
                <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  <Loader2 className="h-3 w-3 animate-spin" /> Loading full newsletter…
                </div>
              )}

              {/* Sibling insights from the same issue */}
              {siblingsByCategory && Object.keys(siblingsByCategory).length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-px flex-1 bg-[var(--border)]" />
                    <span className="text-[11px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] whitespace-nowrap">
                      {newsletter!.insights.length - 1} more insights from this issue
                    </span>
                    <div className="h-px flex-1 bg-[var(--border)]" />
                  </div>
                  <div className="space-y-3">
                    {Object.entries(siblingsByCategory).map(([cat, items]) => {
                      const catColor = getCategoryColor(cat);
                      const cc = colors[catColor];
                      return (
                        <div key={cat}>
                          <span className={`text-[10px] font-bold uppercase tracking-widest ${cc.text}`}>
                            {cat.replace("and", "&")}
                          </span>
                          <div className="mt-1 space-y-1">
                            {items.map(ins => (
                              <div key={ins.id} className={`rounded-lg border ${cc.badge} px-3 py-2`}>
                                <p className="text-xs font-semibold leading-snug">{ins.title?.replace(/\*\*/g, "")}</p>
                                {ins.description && (
                                  <p className="text-[11px] text-[var(--muted-foreground)] mt-0.5 line-clamp-2">{ins.description}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Full newsletter body text */}
              {newsletter?.body_text && newsletter.body_text.length > 100 && (
                <div>
                  <button
                    onClick={() => setShowFullText(v => !v)}
                    className="flex items-center gap-2 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    <FileText className="h-3.5 w-3.5" />
                    {showFullText ? "Hide" : "Read"} full newsletter ({Math.round(newsletter.body_text.length / 1000)}k chars)
                  </button>
                  {showFullText && (
                    <div className="mt-3 p-4 rounded-xl bg-white/3 border border-[var(--border)] text-xs text-[var(--muted-foreground)] leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                      {newsletter.body_text}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* actions */}
          <div className="flex items-center gap-3 mt-5 pt-4 border-t border-[var(--border)]">
            {youtubeUrl && (
              <a
                href={youtubeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg border ${c.pill}`}
              >
                <Play className="h-3.5 w-3.5" /> Watch clip
              </a>
            )}
            <button
              onClick={onClose}
              className="ml-auto text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Insight Row ──────────────────────────────────────────────────────────

function InsightRow({ insight, onExpand }: { insight: Insight; onExpand: (i: Insight) => void }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isNewsletter = !insight.podcast && (insight.author || insight.source);

  return (
    <button
      className="w-full text-left group flex items-start gap-3 px-4 py-4 sm:py-3.5 vault-card hover:border-indigo-500/30 transition-all cursor-pointer"
      onClick={() => onExpand(insight)}
    >
      <div className={`shrink-0 mt-2 h-1.5 w-1.5 rounded-full ${c.dot}`} />
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-1.5 mb-1">
          <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 py-0.5 rounded border ${isNewsletter ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"}`}>
            {isNewsletter ? <Mail className="h-2.5 w-2.5" /> : <Podcast className="h-2.5 w-2.5" />}
            {source}
          </span>
          {insight.category && (
            <span className={`text-[11px] px-1.5 py-0.5 rounded border ${c.badge}`}>
              {insight.category?.replace("and", "&").replace("perspectives","").replace("exercises","").replace("case studies","")}
            </span>
          )}
          {insight.is_multimodal && (
            <span className="inline-flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 animate-pulse">
              <Monitor className="h-2 w-2" /> Multi
            </span>
          )}
        </div>
        <p className="text-sm font-semibold leading-snug group-hover:text-indigo-300 transition-colors line-clamp-2">
          {insight.title?.replace(/\*\*/g, "")}
        </p>
        <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-2 mt-0.5">
          {insight.description}
        </p>
        {speaker && (
          <p className="text-[11px] text-[var(--muted-foreground)] mt-1">
            <span className={`font-medium ${c.text}`}>{speaker}</span>
          </p>
        )}
      </div>
      <div className="shrink-0 flex items-center self-center ml-2">
        <ExternalLink className="h-3.5 w-3.5 text-[var(--muted-foreground)] opacity-0 group-hover:opacity-60 transition-opacity" />
      </div>
    </button>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [activeTopic, setActiveTopic] = useState("");
  const [results, setResults] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoaded, setSessionLoaded] = useState(false);
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);
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
    doSearch(query, source, typeFilter, session?.access_token);
  }, [sessionLoaded, session?.access_token, source, typeFilter]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    doSearch(query, source, typeFilter, session?.access_token);
  };

  const handleTopicClick = (topicQuery: string) => {
    setQuery(topicQuery);
    setActiveTopic(topicQuery);
    setSource("");
    setTypeFilter("");
    doSearch(topicQuery, "", "", session?.access_token);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const toggleActionLens = (lens: string) => {
    setQuery(prev => {
      let newQuery;
      if (prev.startsWith(lens)) {
        newQuery = prev.replace(lens, "");
      } else {
        const otherLens = lens === "!mistakes " ? "!tactical " : "!mistakes ";
        const clean = prev.startsWith(otherLens) ? prev.replace(otherLens, "") : prev;
        newQuery = `${lens}${clean}`;
      }
      doSearch(newQuery, source, typeFilter, session?.access_token);
      return newQuery;
    });
    haptic("selection");
  };

  const clearFilters = () => {
    setQuery("");
    setSource("");
    setTypeFilter("");
    setActiveTopic("");
    doSearch("", "", "", session?.access_token);
  };

  // Grouped results for visual interest
  const sourceBreakdown = results.reduce((acc, r) => {
    const key = r.podcast ? getPodcastShortName(r.podcast) : (r.author || r.source || "Newsletter");
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const hasFilters = query || source || typeFilter;

  return (
    <div className="flex flex-col lg:flex-row min-h-screen bg-[var(--background)]">
      {/* ─── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="lg:w-64 lg:shrink-0 lg:border-r border-[var(--border)] p-4 sm:p-5 flex flex-col gap-8 bg-[var(--card)]/30 backdrop-blur-sm lg:sticky lg:top-0 lg:h-screen overflow-y-auto custom-scrollbar">
        <div className="flex items-center gap-2.5 px-1 py-2">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-900/40">
            <Layers className="h-4.5 w-4.5 text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight text-white/90">ECOM Operators Vault</span>
        </div>

        {/* Categories */}
        <div className="space-y-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Unit Economics & True Metrics</div>
          <div className="space-y-0.5">
            {[
              { label: "MER",                  query: 'MER OR "marketing efficiency ratio"',           icon: Activity,     color: "violet"  },
              { label: "nCAC / Blended CAC",    query: 'nCAC OR "blended CAC" OR "acquisition cost"',   icon: Target,       color: "emerald" },
              { label: "LTV:nCAC Ratio",       query: 'LTV OR nCAC OR "customer value"',               icon: BarChart2,    color: "rose"    },
              { label: "Net Profit",           query: '"net profit" OR profitability',                 icon: DollarSign,   color: "green"   },
              { label: "Contribution Margin",  query: '"contribution margin" OR "unit economics"',     icon: PieChart,     color: "blue"    },
              { label: "Payback Period",       query: '"payback period" OR "customer return"',         icon: Clock,        color: "amber"   },
              { label: "Incrementality",       query: 'incrementality OR "holdout test"',              icon: Zap,          color: "sky"     },
              { label: "ROAS vs Real Metrics", query: 'ROAS OR "real metrics" OR efficiency',          icon: AlertTriangle,color: "rose"    },
              { label: "Cash Conversion Cycle", query: '"cash conversion" OR "inventory" OR capital',   icon: RefreshCw,    color: "teal"    },
              { label: "Revenue Quality",       query: '"revenue quality" OR recurring OR repeat',      icon: TrendingUp,   color: "green"   },
            ].map(item => (
              <button
                key={item.label}
                onClick={() => handleTopicClick(item.query)}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all group ${activeTopic === item.query ? "bg-indigo-600/10 text-indigo-300 font-medium border border-indigo-500/20 shadow-sm" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"}`}
              >
                <item.icon className={`h-3 w-3 shrink-0 ${activeTopic === item.query ? "text-indigo-400" : "opacity-60 group-hover:opacity-100"}`} />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Growth Playbooks */}
        <div className="space-y-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Growth Playbooks</div>
          <div className="space-y-0.5">
            {[
              { label: "Tier 1: Validation ($0-1M)", query: "product market fit validation hook acquisition", icon: Zap },
              { label: "Tier 2: Efficiency ($1-10M)", query: "unit economics efficiency scaling contribution", icon: Activity },
              { label: "Tier 3: Scale ($10M+)", query: "operations logistics management organization", icon: Layers },
            ].map(item => (
              <button
                key={item.label}
                onClick={() => handleTopicClick(item.query)}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all group ${activeTopic === item.query ? "bg-emerald-600/10 text-emerald-300 font-medium border border-emerald-500/20 shadow-sm" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"}`}
              >
                <item.icon className={`h-3 w-3 shrink-0 ${activeTopic === item.query ? "text-emerald-400" : "opacity-60 group-hover:opacity-100"}`} />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Newsletter sources */}
        <div className="space-y-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Email & SMS</div>
          <div className="space-y-0.5">
            {[
              { label: "Email Marketing",      query: 'Email OR Klaviyo OR newsletter',                icon: Mail,         color: "violet"  },
              { label: "Welcome Flow",         query: '"welcome flow" OR automation OR sequence',      icon: Inbox,        color: "emerald" },
              { label: "Abandoned Cart",       query: '"abandoned cart" OR recovery',                  icon: ShoppingCart, color: "rose"    },
              { label: "Win-Back / Re-engage", query: 'winback OR re-engagement OR "churn prevention"', icon: RefreshCw,    color: "blue"    },
              { label: "Email Segmentation",   query: 'segmentation OR "list hygiene"',                icon: Users,        color: "teal"    },
              { label: "Email Deliverability", query: 'deliverability OR "inbox placement"',           icon: Megaphone,    color: "sky"     },
              { label: "SMS Marketing",        query: 'SMS OR Attentive OR Postscript',                icon: MessageSquare,color: "amber"   },
              { label: "Klaviyo / ESP Setup",  query: 'Klaviyo OR "ESP configuration"',                icon: Wrench,       color: "slate"   },
              { label: "Send Cadence & Timing", query: '"send cadence" OR "timing" OR frequency',        icon: Clock,        color: "yellow"  },
            ].map(item => (
              <button
                key={item.label}
                onClick={() => handleTopicClick(item.query)}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all group ${activeTopic === item.query ? "bg-indigo-600/10 text-indigo-300 font-medium border border-indigo-500/20 shadow-sm" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"}`}
              >
                <item.icon className={`h-3 w-3 shrink-0 ${activeTopic === item.query ? "text-indigo-400" : "opacity-60 group-hover:opacity-100"}`} />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] mb-2 px-2">Retention & Subscription</div>
          <div className="space-y-0.5">
            {[
              { label: "Retention Strategy",   query: 'retention OR "customer journey" OR LTV',        icon: RefreshCw,    color: "violet"  },
              { label: "Subscription Models",  query: 'subscription OR "recurring revenue"',           icon: CreditCard,   color: "emerald" },
              { label: "Churn Prevention",     query: 'churn OR "winback" OR retention',               icon: TrendingDown, color: "rose"    },
              { label: "Post-Purchase Upsell", query: '"post purchase" OR "upsell" OR AOV',            icon: ShoppingCart, color: "blue"    },
            ].map(item => (
              <button
                key={item.label}
                onClick={() => handleTopicClick(item.query)}
                className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-xs transition-all group ${activeTopic === item.query ? "bg-indigo-600/10 text-indigo-300 font-medium border border-indigo-500/20 shadow-sm" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-white/5"}`}
              >
                <item.icon className={`h-3 w-3 shrink-0 ${activeTopic === item.query ? "text-indigo-400" : "opacity-60 group-hover:opacity-100"}`} />
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Global Nav */}
        <div className="mt-auto space-y-4 pt-4 border-t border-[var(--border)]">
          <div className="space-y-0.5">
            {[
              { href: "/guides", icon: Sparkles, label: "Topic Guides" },
              { href: "/ask",    icon: BookOpen,  label: "Ask the Vault" },
              { href: "/episodes", icon: PlayCircle, label: "Episodes" },
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
      <div className="flex-1 min-w-0 px-4 sm:px-5 lg:px-6 py-4 sm:py-5">

        {/* Search */}
        <form onSubmit={handleSearch} className="mb-4">
          <div className="relative max-w-2xl">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
            <input
              ref={searchRef}
              type="text"
              placeholder="Search for DTC strategies, case studies, formulas..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-xl py-3 pl-11 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all placeholder:text-[var(--muted-foreground)]"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-white/5 text-[var(--muted-foreground)]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </form>

        {/* Action Lenses */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => toggleActionLens("!mistakes ")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all ${query.startsWith("!mistakes ") ? "bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-lg shadow-rose-900/20" : "bg-[var(--card)]/50 border-[var(--border)] text-[var(--muted-foreground)] hover:border-rose-500/30 hover:text-rose-200"}`}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            The Mistake Map ⚠️
          </button>
          <button
            onClick={() => toggleActionLens("!tactical ")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold border transition-all ${query.startsWith("!tactical ") ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-lg shadow-emerald-900/20" : "bg-[var(--card)]/50 border-[var(--border)] text-[var(--muted-foreground)] hover:border-emerald-500/30 hover:text-emerald-200"}`}
          >
            <Zap className="h-3.5 w-3.5" />
            Tactical Micro-Wins ⚡
          </button>
        </div>

        {/* Quick Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-6">
          <button
            onClick={() => setSource("")}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${!source ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40" : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-white/10"}`}
          >
            All Sources
          </button>
          {[
            { id: "newsletters", label: "Newsletters", icon: Mail },
            { id: "9operators", label: "9 Operators", icon: Podcast },
            { id: "marketing_operator", label: "Marketing Operator", icon: Podcast },
            { id: "finance_operators", label: "Finance Operators", icon: Podcast },
            { id: "titans", label: "TITANS", icon: Star },
          ].map(src => (
            <button
              key={src.id}
              onClick={() => setSource(src.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${source === src.id ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40" : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-white/10"}`}
            >
              <src.icon className="h-3 w-3" />
              {src.label}
            </button>
          ))}
          <div className="w-px h-4 bg-[var(--border)] mx-1" />
          <button
            onClick={() => setTypeFilter("")}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${!typeFilter ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40" : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-white/10"}`}
          >
            All Types
          </button>
          {["Tactical Recommendation", "Framework", "Case Study", "Quote", "Tool"].map(type => (
            <button
              key={type}
              onClick={() => setTypeFilter(type)}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${typeFilter === type ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40" : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-white/10"}`}
            >
              {type}
            </button>
          ))}
        </div>

        {/* Results */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--muted-foreground)]">
            <Loader2 className="h-8 w-8 animate-spin mb-4 text-indigo-500" />
            <p className="text-sm font-medium animate-pulse">Sourcing expert knowledge...</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-5 px-1">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                <span className="text-sm font-bold tracking-tight">
                  {results.length} insight{results.length !== 1 ? "s" : ""}
                </span>
                {/* Source breakdown dots */}
                {results.length > 0 && (
                  <span className="flex items-center gap-2 flex-wrap">
                    {Object.entries(sourceBreakdown).sort((a, b) => b[1] - a[1]).map(([src, count]) => (
                      <span key={src} className="text-[11px] text-[var(--muted-foreground)] flex items-center gap-1">
                        <span className="h-1 w-1 rounded-full bg-indigo-400/60 inline-block" />
                        {count} from {src}
                      </span>
                    ))}
                  </span>
                )}
              </div>
              {!session && sessionLoaded && (
                <button onClick={() => signInWithGoogle()} className="text-xs text-indigo-400 hover:underline hidden sm:inline shrink-0">
                  Sign in for video insights →
                </button>
              )}
            </div>
            {/* Thin results nudge */}
            {results.length < 6 && hasFilters && (
              <div className="mb-6 flex items-center gap-2 text-xs text-[var(--muted-foreground)] bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2">
                <BookOpen className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span>Limited coverage on this topic — try</span>
                <Link href="/ask" className="text-indigo-400 hover:text-indigo-300 font-medium underline underline-offset-2">Ask the Vault</Link>
                <span>for a synthesized answer.</span>
              </div>
            )}

            <div className="stagger">
              {results.length > 0 ? (
                results.map((insight, i) => {
                  // Spotlight the first few highly relevant results
                  const isSpotlight = i < 2 && !hasFilters;
                  if (isSpotlight) {
                    return (
                      <SpotlightCard
                        key={insight.id || i}
                        insight={insight}
                        label="Featured Insight"
                        onExpand={setSelectedInsight}
                      />
                    );
                  }
                  return (
                    <InsightRow key={insight.id || i} insight={insight} onExpand={setSelectedInsight} />
                  );
                })
              ) : (
                <div className="py-20 text-center">
                  <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-[var(--secondary)] mb-4">
                    <Search className="h-8 w-8 text-[var(--muted-foreground)]" />
                  </div>
                  <h3 className="text-lg font-bold mb-1">No matches found</h3>
                  <p className="text-[var(--muted-foreground)] text-sm max-w-xs mx-auto">Try adjusting your filters or search for something less specific.</p>
                  <button onClick={clearFilters} className="mt-6 text-indigo-400 text-sm font-semibold hover:underline">Clear all filters</button>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Insight detail modal */}
      {selectedInsight && (
        <InsightModal insight={selectedInsight} session={session} onClose={() => setSelectedInsight(null)} />
      )}
    </div>
  );
}
