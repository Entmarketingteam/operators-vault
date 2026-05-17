"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { getSpeaker, getNewsletterDetail, type Speaker, type Insight, type NewsletterDetail } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowLeft, Building2, Lightbulb, Mic, Twitter, Mail, Podcast, Play, FileText, X } from "lucide-react";
import Link from "next/link";

const PODCAST_LABELS: Record<string, string> = {
  "9operators": "9 Operators Host",
  "marketing_operator": "Marketing Operators Host",
};

const PODCAST_SHORT: Record<string, string> = {
  "9operators": "9 Operators",
  "9_operators": "9 Operators",
  "marketing_operator": "Marketing Operator",
  "finance_operators": "Finance Operators",
  "titans": "TITANS",
};

function getCategoryColor(cat?: string): string {
  const c = (cat || "").toLowerCase();
  if (c.includes("framework")) return "amber";
  if (c.includes("point") || c.includes("perspective")) return "rose";
  if (c.includes("quote")) return "violet";
  if (c.includes("stor")) return "emerald";
  if (c.includes("business")) return "indigo";
  if (c.includes("creator")) return "teal";
  if (c.includes("product") || c.includes("tool")) return "sky";
  return "slate";
}

const COLORS: Record<string, { pill: string; badge: string; dot: string; text: string }> = {
  amber:   { pill: "bg-amber-500/15 text-amber-300 border-amber-500/30",   badge: "bg-amber-500/10 text-amber-300 border-amber-400/20",   dot: "bg-amber-400",   text: "text-amber-300"   },
  rose:    { pill: "bg-rose-500/15 text-rose-300 border-rose-500/30",     badge: "bg-rose-500/10 text-rose-300 border-rose-400/20",     dot: "bg-rose-400",    text: "text-rose-300"    },
  violet:  { pill: "bg-violet-500/15 text-violet-300 border-violet-500/30", badge: "bg-violet-500/10 text-violet-300 border-violet-400/20", dot: "bg-violet-400", text: "text-violet-300" },
  emerald: { pill: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30", badge: "bg-emerald-500/10 text-emerald-300 border-emerald-400/20", dot: "bg-emerald-400", text: "text-emerald-300" },
  indigo:  { pill: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30", badge: "bg-indigo-500/10 text-indigo-300 border-indigo-400/20", dot: "bg-indigo-400", text: "text-indigo-300" },
  sky:     { pill: "bg-sky-500/15 text-sky-300 border-sky-500/30",         badge: "bg-sky-500/10 text-sky-300 border-sky-400/20",         dot: "bg-sky-400",    text: "text-sky-300"    },
  teal:    { pill: "bg-teal-500/15 text-teal-300 border-teal-500/30",       badge: "bg-teal-500/10 text-teal-300 border-teal-400/20",       dot: "bg-teal-400",   text: "text-teal-300"   },
  slate:   { pill: "bg-slate-500/15 text-slate-300 border-slate-500/30",    badge: "bg-slate-500/10 text-slate-300 border-slate-400/20",    dot: "bg-slate-400",  text: "text-slate-300"  },
};

// Inline insight modal for speaker page
function SpeakerInsightModal({ insight, onClose }: { insight: Insight; onClose: () => void }) {
  const colorKey = getCategoryColor(insight.category);
  const c = COLORS[colorKey] || COLORS.slate;
  const source = insight.podcast ? (PODCAST_SHORT[insight.podcast] || insight.podcast) : (insight.author || insight.source || "");
  const isNewsletter = !insight.podcast && (insight.author || insight.source);
  const isVideo = !!insight.video_id;
  const youtubeUrl = isVideo
    ? `https://youtube.com/watch?v=${insight.video_id}&t=${Math.floor(Number(insight.start_time_sec ?? 0))}s`
    : undefined;

  const [newsletter, setNewsletter] = useState<NewsletterDetail | null>(null);
  const [showFullText, setShowFullText] = useState(false);

  useEffect(() => {
    if (isNewsletter && insight.newsletter_id) {
      getNewsletterDetail(insight.newsletter_id).then(setNewsletter);
    }
  }, [insight.newsletter_id, isNewsletter]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative z-10 w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto rounded-t-2xl sm:rounded-2xl border border-white/10 bg-[#0d0d14] shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className={`absolute top-0 inset-x-0 h-1 rounded-t-2xl ${c.dot}`} />
        <div className="p-5 sm:p-6">
          <div className="sm:hidden mx-auto mb-4 h-1 w-10 rounded-full bg-white/20" />

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
          </div>

          {newsletter?.subject && (
            <p className="text-[11px] text-slate-400 italic mb-2">&ldquo;{newsletter.subject}&rdquo;</p>
          )}

          <h2 className="text-base sm:text-lg font-bold leading-snug mb-3">
            {insight.title?.replace(/\*\*/g, "")}
          </h2>

          {insight.description && (
            <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-wrap">
              {insight.description}
            </p>
          )}

          {/* Sibling newsletter insights */}
          {newsletter && newsletter.insights.length > 1 && (
            <div className="mt-4">
              <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                {newsletter.insights.length - 1} more from this issue
              </p>
              <div className="space-y-1">
                {newsletter.insights.filter(i => i.id !== insight.id).slice(0, 8).map(ins => (
                  <div key={ins.id} className="rounded-lg border border-white/5 px-3 py-2 bg-white/3">
                    <p className="text-xs font-semibold">{ins.title?.replace(/\*\*/g, "")}</p>
                    {ins.description && <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-1">{ins.description}</p>}
                  </div>
                ))}
                {newsletter.insights.length > 9 && (
                  <p className="text-[11px] text-slate-500 text-center pt-1">
                    + {newsletter.insights.length - 9} more insights in this issue
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Full newsletter body */}
          {newsletter?.body_text && newsletter.body_text.length > 100 && (
            <div className="mt-4">
              <button
                onClick={() => setShowFullText(v => !v)}
                className="flex items-center gap-2 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
              >
                <FileText className="h-3.5 w-3.5" />
                {showFullText ? "Hide" : "Read"} full newsletter ({Math.round(newsletter.body_text.length / 1000)}k chars)
              </button>
              {showFullText && (
                <div className="mt-2 p-3 rounded-lg bg-white/3 border border-white/5 text-xs text-slate-400 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
                  {newsletter.body_text}
                </div>
              )}
            </div>
          )}

          <div className="flex items-center gap-3 mt-5 pt-4 border-t border-white/10">
            {youtubeUrl && (
              <a href={youtubeUrl} target="_blank" rel="noopener noreferrer"
                className={`flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg border ${c.pill}`}>
                <Play className="h-3.5 w-3.5" /> Watch clip
              </a>
            )}
            <button onClick={onClose} className="ml-auto text-sm text-slate-400 hover:text-white">Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SpeakerDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [speaker, setSpeaker] = useState<Speaker | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);

  useEffect(() => {
    if (id) {
      getSpeaker(id).then((data) => {
        setSpeaker(data);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (!speaker) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-16 text-center">
        <div className="text-4xl mb-4">🔍</div>
        <div className="font-semibold text-lg mb-2">Speaker not found</div>
        <Link href="/speakers">
          <Button variant="outline" className="mt-2">
            <ArrowLeft className="h-4 w-4" /> Back to Speakers
          </Button>
        </Link>
      </div>
    );
  }

  const initials = speaker.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const insights = speaker.insights || speaker.top_insights || [];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
      <Link href="/speakers">
        <Button variant="ghost" size="sm" className="mb-6 -ml-1">
          <ArrowLeft className="h-4 w-4" /> All Speakers
        </Button>
      </Link>

      {/* Profile header */}
      <div className="vault-card p-6 sm:p-8 mb-8">
        <div className="flex flex-col sm:flex-row gap-5 sm:items-start">
          <Avatar className="h-20 w-20 shrink-0">
            {speaker.photo_url && <AvatarImage src={speaker.photo_url} alt={speaker.name} />}
            <AvatarFallback className="text-xl">{initials}</AvatarFallback>
          </Avatar>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold mb-1">{speaker.name}</h1>
            {speaker.company && (
              <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-3">
                <Building2 className="h-4 w-4" />
                {speaker.company}
              </div>
            )}
            {speaker.bio && (
              <p className="text-[var(--muted-foreground)] leading-relaxed max-w-2xl">{speaker.bio}</p>
            )}
            <div className="flex flex-wrap items-center gap-2 mt-4">
              {speaker.is_host && speaker.host_podcast && (
                <Badge className="bg-indigo-600/20 text-indigo-300 border-indigo-500/30 hover:bg-indigo-600/30">
                  <Mic className="h-3 w-3 mr-1" />
                  {PODCAST_LABELS[speaker.host_podcast] ?? "Podcast Host"}
                </Badge>
              )}
              {(insights.length > 0 || (speaker.insight_count ?? 0) > 0) && (
                <Badge variant="default">
                  <Lightbulb className="h-3 w-3 mr-1" />
                  {speaker.insight_count ?? insights.length} insights in vault
                </Badge>
              )}
              {speaker.twitter_handle && (
                <a
                  href={`https://twitter.com/${speaker.twitter_handle}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] hover:text-sky-400 transition-colors"
                >
                  <Twitter className="h-3.5 w-3.5" />
                  @{speaker.twitter_handle}
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Top insights */}
      {insights.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <h2 className="text-xl font-semibold">
              {speaker.insights_via_mention ? "Episodes & content mentioning" : "Insights from"} {speaker.name}
            </h2>
            {speaker.insights_via_mention && (
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">
                via transcript search
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {insights.map((insight, i) => {
              const colorKey = getCategoryColor(insight.category);
              const c = COLORS[colorKey] || COLORS.slate;
              const source = insight.podcast ? (PODCAST_SHORT[insight.podcast] || insight.podcast) : (insight.author || insight.source || "");
              const isNewsletter = !insight.podcast && (insight.author || insight.source);
              return (
                <button
                  key={insight.id || i}
                  className={`vault-card text-left p-4 group cursor-pointer hover:border-indigo-500/30 transition-all`}
                  onClick={() => setSelectedInsight(insight)}
                >
                  <div className="flex flex-wrap items-center gap-1.5 mb-2">
                    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${isNewsletter ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-indigo-500/10 text-indigo-300 border-indigo-500/20"}`}>
                      {source}
                    </span>
                    {insight.category && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded border ${c.badge}`}>
                        {insight.category.replace("and", "&").replace("perspectives","").replace("exercises","")}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-semibold leading-snug mb-1.5 group-hover:text-indigo-300 transition-colors line-clamp-2">
                    {insight.title?.replace(/\*\*/g, "")}
                  </p>
                  <p className="text-xs text-[var(--muted-foreground)] leading-relaxed line-clamp-3">
                    {insight.description}
                  </p>
                  <div className={`mt-2 text-[10px] font-semibold ${c.text} opacity-0 group-hover:opacity-100 transition-opacity`}>
                    Read more →
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {insights.length === 0 && (
        <div className="text-center py-12 vault-card">
          <div className="text-3xl mb-3">💡</div>
          <div className="font-medium mb-1">No indexed insights yet</div>
          <div className="text-sm text-[var(--muted-foreground)]">
            Search the vault to find insights from {speaker.name}
          </div>
          <Link href={`/?q=${encodeURIComponent(speaker.name)}`}>
            <Button variant="outline" className="mt-4" size="sm">Search insights</Button>
          </Link>
        </div>
      )}

      {selectedInsight && (
        <SpeakerInsightModal insight={selectedInsight} onClose={() => setSelectedInsight(null)} />
      )}
    </div>
  );
}
