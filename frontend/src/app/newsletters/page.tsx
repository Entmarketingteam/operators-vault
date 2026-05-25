"use client";

import { useState, useEffect } from "react";
import { getNewsletterSources, getNewsletterInsights, type NewsletterInsight, type NewsletterSource } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Mail, Search, Loader2, Tag, ChevronDown, ChevronUp, User } from "lucide-react";
import { haptic } from "@/lib/haptics";

const SOURCE_COLORS: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  nik_sharma:     { bg: "bg-indigo-500/15", text: "text-indigo-300", border: "border-indigo-500/30", dot: "bg-indigo-400" },
  taylor_holiday: { bg: "bg-amber-500/15",  text: "text-amber-300",  border: "border-amber-500/30",  dot: "bg-amber-400"  },
  matt_bertulli:  { bg: "bg-emerald-500/15",text: "text-emerald-300",border: "border-emerald-500/30",dot: "bg-emerald-400" },
  chase_dimond:   { bg: "bg-violet-500/15", text: "text-violet-300", border: "border-violet-500/30", dot: "bg-violet-400"  },
  operators_newsletter: { bg: "bg-sky-500/15", text: "text-sky-300", border: "border-sky-500/30", dot: "bg-sky-400" },
};

const DEFAULT_COLOR = { bg: "bg-indigo-500/15", text: "text-indigo-300", border: "border-indigo-500/30", dot: "bg-indigo-400" };

function getColor(source: string) {
  return SOURCE_COLORS[source] || DEFAULT_COLOR;
}

function categoryColor(category?: string): string {
  const c = (category || "").toLowerCase();
  if (c.includes("framework")) return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  if (c.includes("quote")) return "bg-violet-500/10 text-violet-300 border-violet-500/20";
  if (c.includes("story") || c.includes("stories")) return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (c.includes("pov") || c.includes("perspective") || c.includes("opinion")) return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  return "bg-sky-500/10 text-sky-300 border-sky-500/20";
}

function InsightCard({ insight }: { insight: NewsletterInsight }) {
  const [expanded, setExpanded] = useState(false);
  const color = getColor(insight.source);

  return (
    <div
      className="vault-card p-4 cursor-pointer"
      onClick={() => { haptic("selection"); setExpanded(!expanded); }}
    >
      <div className="flex items-start gap-3">
        <div className={`shrink-0 mt-1 h-1.5 w-1.5 rounded-full ${color.dot}`} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${color.bg} ${color.text} ${color.border}`}>
              <Mail className="h-3 w-3" />
              {insight.author || "Operator"}
            </span>
            {insight.category && (
              <span className={`text-xs px-2 py-0.5 rounded-full border ${categoryColor(insight.category)}`}>
                {insight.category}
              </span>
            )}
          </div>

          <h3 className="text-sm font-semibold leading-snug mb-1 hover:text-indigo-300 transition-colors">
            {(insight.title || "").replace(/\*\*/g, "")}
          </h3>

          {!expanded && (
            <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 leading-relaxed">
              {insight.description}
            </p>
          )}

          {expanded && (
            <p className="text-xs text-[var(--muted-foreground)] leading-relaxed mt-1">
              {insight.description}
            </p>
          )}

          {insight.subject && (
            <div className="mt-2 text-xs text-[var(--muted-foreground)] flex items-center gap-1">
              <Tag className="h-3 w-3 shrink-0" />
              <span className="truncate italic">{insight.subject}</span>
            </div>
          )}
        </div>

        <button className="shrink-0 text-[var(--muted-foreground)] mt-0.5">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}

export default function NewslettersPage() {
  const [sources, setSources] = useState<NewsletterSource[]>([]);
  const [insights, setInsights] = useState<NewsletterInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    Promise.all([
      getNewsletterSources(),
      getNewsletterInsights("", 500),
    ]).then(([srcs, ins]) => {
      setSources(srcs);
      setInsights(ins);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const filtered = insights.filter((ins) => {
    const matchSource = !activeSource || ins.source === activeSource;
    const matchSearch = !search ||
      (ins.title || "").toLowerCase().includes(search.toLowerCase()) ||
      (ins.description || "").toLowerCase().includes(search.toLowerCase()) ||
      (ins.author || "").toLowerCase().includes(search.toLowerCase());
    return matchSource && matchSearch;
  });

  // Group by category for the active view
  const categories = Array.from(new Set(filtered.map(i => i.category).filter(Boolean)));

  return (
    <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 rounded-full bg-emerald-600/10 border border-emerald-500/20 px-4 py-1.5 text-sm text-emerald-300 mb-6">
          <Mail className="h-3.5 w-3.5" />
          Newsletter Archive
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-3">
          Newsletter{" "}
          <span className="bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
            Insights
          </span>
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] max-w-xl">
          Extracted insights from 5 top DTC operator newsletters — Nik Sharma, Taylor Holiday, Matt Bertulli, Chase Dimond, and Operators Newsletter.
        </p>
      </div>

      {/* Source filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => { haptic("selection"); setActiveSource(""); }}
          className={`btn-base flex items-center gap-2 px-3.5 py-2 rounded-full text-sm font-medium border ${
            activeSource === ""
              ? "bg-emerald-600/20 text-emerald-300 border-emerald-500/40"
              : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          }`}
        >
          <User className="h-3.5 w-3.5" />
          All Authors
        </button>
        {sources.map((src) => {
          const color = getColor(src.slug);
          return (
            <button
              key={src.slug}
              onClick={() => { haptic("selection"); setActiveSource(src.slug); }}
              className={`btn-base flex items-center gap-2 px-3.5 py-2 rounded-full text-sm font-medium border ${
                activeSource === src.slug
                  ? `${color.bg} ${color.text} ${color.border}`
                  : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${color.dot}`} />
              {src.author}
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative max-w-md mb-6">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
        <Input
          placeholder="Search insights..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Count */}
      {!loading && (
        <p className="text-sm text-[var(--muted-foreground)] mb-6">
          {filtered.length} insight{filtered.length !== 1 ? "s" : ""}
          {activeSource ? ` from ${sources.find(s => s.slug === activeSource)?.author}` : ""}
          {search ? ` matching "${search}"` : ""}
        </p>
      )}

      {/* Results */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">📬</div>
          <div className="font-semibold mb-1">No insights found</div>
          <div className="text-sm text-[var(--muted-foreground)]">Try clearing your filters</div>
        </div>
      ) : categories.length > 1 && !search ? (
        // Grouped by category when browsing
        <div className="space-y-10 stagger">
          {categories.map((cat) => {
            const catInsights = filtered.filter(i => i.category === cat);
            return (
              <div key={cat}>
                <div className="flex items-center gap-3 mb-4">
                  <h2 className="text-sm font-semibold uppercase tracking-widest text-[var(--muted-foreground)]">{cat}</h2>
                  <Badge variant="secondary">{catInsights.length}</Badge>
                </div>
                <div className="space-y-2">
                  {catInsights.map((ins) => (
                    <InsightCard key={ins.id} insight={ins} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        // Flat list when searching or single source
        <div className="space-y-2 stagger">
          {filtered.map((ins) => (
            <InsightCard key={ins.id} insight={ins} />
          ))}
        </div>
      )}
    </div>
  );
}
