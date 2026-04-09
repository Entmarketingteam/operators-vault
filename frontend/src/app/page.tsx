"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { supabase } from "@/lib/supabase";
import { searchInsights, getNewsletterDetail, type Insight, type NewsletterDetail } from "@/lib/api";
import {
  Search, Loader2, Sparkles, BookOpen, Users, Lightbulb,
  Quote, BookMarked, MessageSquare, Layers, Play, Mail,
  Podcast, ExternalLink, TrendingUp, TrendingDown, Wrench, Target,
  DollarSign, ShoppingCart, Megaphone, BarChart2, Package,
  RefreshCw, Star, X, Monitor, Gift, AlertTriangle,
  Inbox, MailOpen, Activity, Zap, Building2, FileText,
  PieChart, CreditCard, Clock, LayoutGrid
} from "lucide-react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { signInWithGoogle } from "@/lib/supabase";
import { haptic } from "@/lib/haptics";

// ─── Topic Groups (organized into sections) ────────────────────────────────

interface Topic {
  label: string;
  query: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}

interface TopicGroup {
  section: string;
  sectionColor: string;
  topics: Topic[];
}

const TOPIC_GROUPS: TopicGroup[] = [
  {
    section: "Unit Economics & True Metrics",
    sectionColor: "emerald",
    topics: [
      { label: "MER",                   query: "marketing efficiency ratio",                icon: TrendingUp,     color: "emerald" },
      { label: "nCAC / Blended CAC",    query: "blended CAC acquisition cost",              icon: DollarSign,     color: "emerald" },
      { label: "LTV:nCAC Ratio",        query: "LTV customer lifetime value acquisition",   icon: BarChart2,      color: "teal"    },
      { label: "Net Profit",            query: "net profit profitability margin",            icon: PieChart,       color: "green"   },
      { label: "Contribution Margin",   query: "contribution margin unit economics",         icon: Activity,       color: "green"   },
      { label: "Payback Period",        query: "payback period acquisition recover",         icon: Clock,          color: "teal"    },
      { label: "Incrementality",        query: "incrementality lift holdout test",           icon: Layers,         color: "sky"     },
      { label: "ROAS vs Real Metrics",  query: "ROAS blended efficiency reporting",          icon: AlertTriangle,  color: "amber"   },
      { label: "Cash Conversion Cycle", query: "cash conversion inventory working capital",  icon: RefreshCw,      color: "teal"    },
      { label: "Revenue Quality",       query: "revenue quality recurring repeat",           icon: TrendingUp,     color: "green"   },
    ]
  },
  {
    section: "Email & SMS",
    sectionColor: "violet",
    topics: [
      { label: "Email Marketing",       query: "email marketing revenue strategy",           icon: Mail,           color: "violet"  },
      { label: "Welcome Flow",          query: "welcome flow onboarding sequence",           icon: MailOpen,       color: "violet"  },
      { label: "Abandoned Cart",        query: "abandoned cart recovery email",              icon: ShoppingCart,   color: "violet"  },
      { label: "Win-Back / Re-engage",  query: "winback re-engage lapsed customer",          icon: RefreshCw,      color: "blue"    },
      { label: "Email Segmentation",    query: "email segmentation subscribers list",        icon: Users,          color: "blue"    },
      { label: "Email Deliverability",  query: "deliverability open rate inbox",             icon: Inbox,          color: "sky"     },
      { label: "SMS Marketing",         query: "SMS text marketing campaigns",               icon: MessageSquare,  color: "indigo"  },
      { label: "Klaviyo / ESP Setup",   query: "Klaviyo email automation flows",             icon: Zap,            color: "indigo"  },
      { label: "Send Cadence & Timing", query: "send frequency cadence timing",              icon: Clock,          color: "slate"   },
    ]
  },
  {
    section: "Retention & Subscription",
    sectionColor: "emerald",
    topics: [
      { label: "Retention Strategy",   query: "retention repeat purchase loyalty",           icon: RefreshCw,      color: "emerald" },
      { label: "Subscription Models",  query: "subscription recurring revenue model",        icon: CreditCard,     color: "emerald" },
      { label: "Churn Prevention",     query: "churn cancel save prevention",                icon: TrendingDown,   color: "rose"    },
      { label: "Post-Purchase Upsell", query: "post purchase upsell cross sell",             icon: ShoppingCart,   color: "teal"    },
      { label: "LTV & CLV",           query: "lifetime value cohort repurchase",             icon: TrendingUp,     color: "emerald" },
      { label: "Subscription Pricing", query: "subscription pricing quarterly upfront",      icon: DollarSign,     color: "teal"    },
      { label: "VIP & Loyalty",        query: "VIP loyalty high value customer",             icon: Star,           color: "amber"   },
    ]
  },
  {
    section: "Paid Acquisition",
    sectionColor: "blue",
    topics: [
      { label: "Paid Social / Meta",   query: "paid social Meta Facebook ads",              icon: BarChart2,      color: "blue"    },
      { label: "Creative Testing",     query: "creative testing hooks ad performance",       icon: Lightbulb,      color: "indigo"  },
      { label: "Video Ads & UGC",      query: "video ads UGC content creator",              icon: Play,           color: "violet"  },
      { label: "CTV / Connected TV",   query: "connected TV streaming ads CTV",             icon: Monitor,        color: "sky"     },
      { label: "Attribution Setup",    query: "attribution reporting Northbeam Triple Whale", icon: Target,        color: "rose"    },
      { label: "Media Mix / MMM",      query: "media mix model channel allocation",         icon: PieChart,       color: "amber"   },
    ]
  },
  {
    section: "Growth & Brand",
    sectionColor: "amber",
    topics: [
      { label: "Product Launch",       query: "product launch checklist strategy",          icon: Package,        color: "amber"   },
      { label: "Giveaways",            query: "giveaway contest brand",                     icon: Gift,           color: "rose"    },
      { label: "Brand Collaborations", query: "brand collaboration partnership collab",     icon: Building2,      color: "rose"    },
      { label: "AOV & Bundle Strategy",query: "average order value bundle upsell",          icon: LayoutGrid,     color: "teal"    },
      { label: "Pricing & Offers",     query: "pricing discount offer conversion",          icon: DollarSign,     color: "amber"   },
      { label: "Influencer / Creator", query: "influencer creator affiliate campaign",      icon: Megaphone,      color: "rose"    },
      { label: "IRL Events & Content", query: "events pop-up experiential content",         icon: Star,           color: "yellow"  },
      { label: "D2C vs Wholesale",     query: "wholesale retail Amazon channel DTC",        icon: ShoppingCart,   color: "slate"   },
    ]
  },
  {
    section: "Operations & Finance",
    sectionColor: "slate",
    topics: [
      { label: "Cash Flow & Inventory", query: "cash flow inventory working capital",       icon: TrendingUp,     color: "green"   },
      { label: "Forecasting & P&L",    query: "forecast planning growth P&L",               icon: FileText,       color: "slate"   },
      { label: "Revenue Milestones",   query: "revenue scale million growth stage",         icon: BarChart2,      color: "indigo"  },
      { label: "Lender / Debt",        query: "debt loan credit line borrowing",            icon: AlertTriangle,  color: "amber"   },
      { label: "Shopify & Tech Stack", query: "Shopify tech stack tools integration",       icon: Wrench,         color: "slate"   },
      { label: "AI Tools for ECOM",    query: "AI automation tools efficiency",             icon: Sparkles,       color: "fuchsia" },
      { label: "Agency Operations",    query: "agency team structure media buying",         icon: Users,          color: "slate"   },
      { label: "DTC Analytics",        query: "analytics dashboard reporting data",         icon: Activity,       color: "sky"     },
    ]
  },
];

// Flat list for lookup
const ALL_TOPICS = TOPIC_GROUPS.flatMap(g => g.topics);

// ─── Content Type Filters ─────────────────────────────────────────────────

const CONTENT_TYPES = [
  { label: "All Content",      value: "",                              icon: Layers,        color: "slate"   },
  { label: "Frameworks",       value: "Frameworks and exercises",      icon: Lightbulb,     color: "amber"   },
  { label: "Points of View",   value: "Points of view",                icon: MessageSquare, color: "rose"    },
  { label: "Quotes",           value: "Quotes",                        icon: Quote,         color: "violet"  },
  { label: "Stories",          value: "Stories and anecdotes",         icon: BookMarked,    color: "emerald" },
  { label: "Business Ideas",   value: "Business ideas",                icon: Zap,           color: "indigo"  },
  { label: "Products",         value: "Products",                      icon: Package,       color: "sky"     },
  { label: "Creator Tactics",  value: "Creator and Influencer Tactics",icon: Megaphone,     color: "teal"    },
];

const SOURCE_FILTERS = [
  { label: "All Sources",         value: "" },
  { label: "9 Operators",         value: "9operators" },
  { label: "Marketing Operator",  value: "marketing_operator" },
  { label: "Finance Operators",   value: "finance_operators" },
  { label: "TITANS",              value: "titans" },
  { label: "Newsletters",         value: "newsletters" },
];

// ─── Color tokens ─────────────────────────────────────────────────────────

const colors: Record<string, { pill: string; dot: string; badge: string; text: string }> = {
  slate:   { pill: "bg-slate-500/15 text-slate-300 border-slate-500/30",      dot: "bg-slate-400",   badge: "bg-slate-500/10 text-slate-300 border-slate-400/20",    text: "text-slate-300"   },
  amber:   { pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",      dot: "bg-amber-400",   badge: "bg-amber-500/10 text-amber-300 border-amber-400/20",    text: "text-amber-300"   },
  indigo:  { pill: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",   dot: "bg-indigo-400",  badge: "bg-indigo-500/10 text-indigo-300 border-indigo-400/20",  text: "text-indigo-300"  },
  rose:    { pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",         dot: "bg-rose-400",    badge: "bg-rose-500/10 text-rose-300 border-rose-400/20",        text: "text-rose-300"    },
  violet:  { pill: "bg-violet-500/15 text-violet-300 border-violet-500/30",   dot: "bg-violet-400",  badge: "bg-violet-500/10 text-violet-300 border-violet-400/20",  text: "text-violet-300"  },
  emerald: { pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",dot: "bg-emerald-400", badge: "bg-emerald-500/10 text-emerald-300 border-emerald-400/20",text: "text-emerald-300" },
  sky:     { pill: "bg-sky-500/15 text-sky-300 border-sky-500/30",            dot: "bg-sky-400",     badge: "bg-sky-500/10 text-sky-300 border-sky-400/20",           text: "text-sky-300"     },
  blue:    { pill: "bg-blue-500/15 text-blue-300 border-blue-500/30",         dot: "bg-blue-400",    badge: "bg-blue-500/10 text-blue-300 border-blue-400/20",        text: "text-blue-300"    },
  teal:    { pill: "bg-teal-500/15 text-teal-300 border-teal-500/30",         dot: "bg-teal-400",    badge: "bg-teal-500/10 text-teal-300 border-teal-400/20",        text: "text-teal-300"    },
  green:   { pill: "bg-green-500/15 text-green-300 border-green-500/30",      dot: "bg-green-400",   badge: "bg-green-500/10 text-green-300 border-green-400/20",     text: "text-green-300"   },
  yellow:  { pill: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",   dot: "bg-yellow-400",  badge: "bg-yellow-500/10 text-yellow-300 border-yellow-400/20",  text: "text-yellow-300"  },
  fuchsia: { pill: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",dot: "bg-fuchsia-400", badge: "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-400/20",text: "text-fuchsia-300" },
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

function InsightModal({ insight, onClose }: { insight: Insight; onClose: () => void }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || insight.source || "");
  const colorKey = getCategoryColor(insight.category);
  const c = colors[colorKey];
  const isVideo = !!insight.video_id;
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(Number(insight.start_time_sec ?? 0))}`
    : undefined;
  const isNewsletter = !insight.podcast && (insight.author || insight.source);

  const [newsletter, setNewsletter] = useState<NewsletterDetail | null>(null);
  const [loadingNewsletter, setLoadingNewsletter] = useState(false);
  const [showFullText, setShowFullText] = useState(false);

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
                {insight.category.replace("and", "&")}
              </span>
            )}
            {speaker && <span className={`text-[11px] font-medium ${c.text}`}>{speaker}</span>}
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
              {insight.category.replace("and", "&").replace("perspectives","").replace("exercises","").replace("case studies","")}
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

  const handleTopic = (topic: Topic) => {
    haptic("selection");
    const next = activeTopic === topic.label ? "" : topic.label;
    setActiveTopic(next);
    setTypeFilter("");
    setQuery(next ? topic.query : "");
    doSearch(next ? topic.query : "", source, "", session?.access_token);
  };

  const handleType = (type: string) => {
    haptic("selection");
    setTypeFilter(type);
    setActiveTopic("");
    doSearch(query || "", source, type, session?.access_token);
  };

  const handleSource = (src: string) => {
    haptic("selection");
    setSource(src);
    const activeTopicQuery = ALL_TOPICS.find(t => t.label === activeTopic)?.query;
    doSearch(query || activeTopicQuery || "", src, typeFilter, session?.access_token);
  };

  const clearAll = () => {
    haptic("impact");
    setQuery(""); setSource(""); setTypeFilter(""); setActiveTopic("");
    doSearch("", "", "", session?.access_token);
  };

  const hasFilters = !!(query || source || typeFilter || activeTopic);
  const spotlight = results[0];
  const listResults = results.slice(1);

  const typeCounts = CONTENT_TYPES.slice(1).reduce((acc, t) => {
    acc[t.value] = results.filter(r => r.category?.toLowerCase().includes(t.value.split(" ")[0].toLowerCase())).length;
    return acc;
  }, {} as Record<string, number>);

  const sourceBreakdown = results.reduce((acc, r) => {
    const key = r.podcast ? getPodcastShortName(r.podcast) : (r.author || r.source || "Newsletter");
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="flex min-h-[calc(100vh-4rem)]">

      {/* ─── Sidebar ──────────────────────────────────────────────────────── */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-[var(--border)] py-5 px-3 gap-6 sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto">

        {/* Topic Groups */}
        {TOPIC_GROUPS.map((group) => (
          <div key={group.section}>
            <div className={`text-[10px] font-bold uppercase tracking-widest mb-2 px-2 ${sectionAccent[group.sectionColor] || "text-[var(--muted-foreground)]"}`}>
              {group.section}
            </div>
            <div className="space-y-0.5">
              {group.topics.map((topic) => {
                const Icon = topic.icon;
                const c = colors[topic.color] || colors.indigo;
                const active = activeTopic === topic.label;
                return (
                  <button
                    key={topic.label}
                    onClick={() => handleTopic(topic)}
                    className={`btn-base w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium text-left ${
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
        ))}

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
                  className={`btn-base w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium text-left ${
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
                  className={`btn-base w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-left ${
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

        {/* AI Tools */}
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
      <div className="flex-1 min-w-0 px-4 sm:px-5 lg:px-6 py-4 sm:py-5">

        {/* Search */}
        <form onSubmit={handleSearch} className="mb-4">
          <div className="relative max-w-2xl">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
            <input
              ref={searchRef}
              type="text"
              placeholder='Search insights…'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full h-11 sm:h-10 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--secondary)] text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/50 transition-all"
            />
          </div>
        </form>

        {/* Mobile: horizontal-scroll topic rows per section */}
        <div className="lg:hidden mb-3 space-y-2">
          {TOPIC_GROUPS.map((group) => (
            <div key={group.section}>
              <div className={`text-[10px] font-bold uppercase tracking-wider mb-1.5 px-0.5 ${sectionAccent[group.sectionColor] || "text-[var(--muted-foreground)]"}`}>
                {group.section}
              </div>
              <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
                {group.topics.map((topic) => {
                  const c = colors[topic.color] || colors.indigo;
                  const active = activeTopic === topic.label;
                  return (
                    <button
                      key={topic.label}
                      onClick={() => handleTopic(topic)}
                      className={`flex-shrink-0 text-xs px-3 py-2 rounded-full border transition-all whitespace-nowrap ${
                        active ? `${c.pill}` : "border-[var(--border)] text-[var(--muted-foreground)]"
                      }`}
                    >
                      {topic.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Mobile type chips — horizontal scroll */}
        <div className="lg:hidden mb-3">
          <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5 text-[var(--muted-foreground)]">Content Type</div>
          <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}>
            {CONTENT_TYPES.map(({ label, value, color }) => {
              const c = colors[color];
              return (
                <button
                  key={value}
                  onClick={() => handleType(value)}
                  className={`flex-shrink-0 text-xs px-3 py-2 rounded-full border transition-all whitespace-nowrap ${
                    typeFilter === value ? `${c.pill}` : "border-[var(--border)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Active filter bar */}
        {hasFilters && (
          <div className="flex flex-wrap items-center gap-2 mb-3 text-xs">
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

        {/* Result count + source breakdown */}
        {!loading && (
          <div className="mb-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold">
                  {results.length} insight{results.length !== 1 ? "s" : ""}
                </span>
                {activeTopic && (
                  <span className="text-xs text-[var(--muted-foreground)]">on <span className="text-[var(--foreground)]">{activeTopic}</span></span>
                )}
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
              <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)] bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2">
                <BookOpen className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span>Limited coverage on this topic — try</span>
                <Link href="/ask" className="text-indigo-400 hover:text-indigo-300 font-medium underline underline-offset-2">Ask the Vault</Link>
                <span>for a synthesized answer.</span>
              </div>
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
            {spotlight && hasFilters && (
              <div className="animate-scale-in">
                <SpotlightCard
                  insight={spotlight}
                  label={activeTopic || CONTENT_TYPES.find(t => t.value === typeFilter)?.label || "Top Result"}
                  onExpand={setSelectedInsight}
                />
              </div>
            )}
            <div className="space-y-1 stagger">
              {(hasFilters ? listResults : results).map((insight, i) => (
                <InsightRow key={insight.id || i} insight={insight} onExpand={setSelectedInsight} />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Insight detail modal */}
      {selectedInsight && (
        <InsightModal insight={selectedInsight} onClose={() => setSelectedInsight(null)} />
      )}
    </div>
  );
}
