"use client";

import { useState, useEffect, useCallback } from "react";
import { supabase } from "@/lib/supabase";
import { searchInsights, type Insight } from "@/lib/api";
import InsightCard from "@/components/InsightCard";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, Loader2, Sparkles, BookOpen, Vault, ArrowRight } from "lucide-react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";

const SOURCE_FILTERS = [
  { label: "All Sources", value: "" },
  { label: "9 Operators", value: "9operators" },
  { label: "Marketing Operator", value: "marketing_operator" },
  { label: "Finance Operators", value: "finance_operators" },
  { label: "Newsletters", value: "newsletters" },
];

const TYPE_FILTERS = [
  { label: "All Types", value: "" },
  { label: "Insights", value: "insight" },
  { label: "Frameworks", value: "framework" },
  { label: "Quotes", value: "quote" },
  { label: "Points of View", value: "pov" },
];

const EXAMPLE_SEARCHES = [
  "email marketing retention",
  "product launch strategy",
  "influencer ROI",
  "paid social scaling",
  "customer LTV",
  "DTC brand building",
];

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [results, setResults] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  const doSearch = useCallback(async (q: string, src: string) => {
    setLoading(true);
    setHasSearched(true);
    try {
      const token = session?.access_token;
      const podcast = src === "newsletters" ? "" : src;
      let data = await searchInsights(q || " ", token, podcast);
      if (src === "newsletters") {
        data = data.filter(i => i.author || (i.source && i.source.toLowerCase().includes("newsletter")));
      }
      if (typeFilter) {
        data = data.filter(i => i.type?.toLowerCase() === typeFilter || i.category?.toLowerCase() === typeFilter);
      }
      setResults(data);
    } catch (err) {
      console.error("Search error:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [session, typeFilter]);

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault();
    doSearch(query, source);
  };

  const handleSourceFilter = (value: string) => {
    setSource(value);
    if (hasSearched) doSearch(query, value);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 rounded-full bg-indigo-600/10 border border-indigo-500/20 px-4 py-1.5 text-sm text-indigo-300 mb-6">
          <Vault className="h-3.5 w-3.5" />
          DTC Operator Knowledge Base
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-4">
          Operators{" "}
          <span className="text-indigo-400 bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
            Vault
          </span>
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] max-w-2xl mx-auto mb-8">
          Search insights, frameworks, and strategies from 9 Operators, Marketing Operator, Finance Operators, and top DTC newsletters.
        </p>

        {/* Search */}
        <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
          <div className="relative flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
              <Input
                type="text"
                placeholder="Search insights, frameworks, strategies..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-10 h-12 text-base"
              />
            </div>
            <Button type="submit" size="lg" disabled={loading} className="shrink-0">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </Button>
          </div>
        </form>

        {/* Example searches */}
        {!hasSearched && (
          <div className="flex flex-wrap justify-center gap-2 mt-4">
            {EXAMPLE_SEARCHES.map((s) => (
              <button
                key={s}
                onClick={() => { setQuery(s); doSearch(s, source); }}
                className="text-xs px-3 py-1.5 rounded-full border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-indigo-500/40 hover:bg-indigo-600/10 transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Feature cards (shown before search) */}
      {!hasSearched && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-12 max-w-3xl mx-auto">
          <Link href="/guides" className="vault-card p-5 text-center group hover:border-indigo-500/40 transition-all cursor-pointer">
            <div className="h-10 w-10 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center mx-auto mb-3 group-hover:bg-indigo-600/30 transition-colors">
              <Sparkles className="h-5 w-5 text-indigo-400" />
            </div>
            <div className="font-semibold text-sm mb-1">Topic Guides</div>
            <div className="text-xs text-[var(--muted-foreground)]">AI-generated playbooks on any topic</div>
            <div className="flex items-center justify-center gap-1 mt-3 text-xs text-indigo-400 group-hover:gap-2 transition-all">
              Try it <ArrowRight className="h-3 w-3" />
            </div>
          </Link>
          <Link href="/ask" className="vault-card p-5 text-center group hover:border-indigo-500/40 transition-all cursor-pointer">
            <div className="h-10 w-10 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center mx-auto mb-3 group-hover:bg-violet-600/30 transition-colors">
              <BookOpen className="h-5 w-5 text-violet-400" />
            </div>
            <div className="font-semibold text-sm mb-1">Ask the Vault</div>
            <div className="text-xs text-[var(--muted-foreground)]">Chat with your operator knowledge base</div>
            <div className="flex items-center justify-center gap-1 mt-3 text-xs text-violet-400 group-hover:gap-2 transition-all">
              Ask now <ArrowRight className="h-3 w-3" />
            </div>
          </Link>
          <Link href="/speakers" className="vault-card p-5 text-center group hover:border-indigo-500/40 transition-all cursor-pointer">
            <div className="h-10 w-10 rounded-lg bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center mx-auto mb-3 group-hover:bg-emerald-600/30 transition-colors">
              <Vault className="h-5 w-5 text-emerald-400" />
            </div>
            <div className="font-semibold text-sm mb-1">Speakers</div>
            <div className="text-xs text-[var(--muted-foreground)]">Browse insights by operator</div>
            <div className="flex items-center justify-center gap-1 mt-3 text-xs text-emerald-400 group-hover:gap-2 transition-all">
              Browse <ArrowRight className="h-3 w-3" />
            </div>
          </Link>
        </div>
      )}

      {/* Filters */}
      {hasSearched && (
        <div className="mb-6 flex flex-col sm:flex-row gap-3">
          {/* Source pills */}
          <div className="flex flex-wrap gap-2 items-center">
            {SOURCE_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => handleSourceFilter(f.value)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all border ${
                  source === f.value
                    ? "bg-indigo-600/20 text-indigo-300 border-indigo-500/40"
                    : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-indigo-500/30 hover:text-[var(--foreground)]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="h-px sm:h-auto sm:w-px bg-[var(--border)] my-1 sm:mx-2" />
          {/* Type pills */}
          <div className="flex flex-wrap gap-2 items-center">
            {TYPE_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => { setTypeFilter(f.value); if (hasSearched) doSearch(query, source); }}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all border ${
                  typeFilter === f.value
                    ? "bg-amber-600/20 text-amber-300 border-amber-500/40"
                    : "border-[var(--border)] text-[var(--muted-foreground)] hover:border-amber-500/30 hover:text-[var(--foreground)]"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {hasSearched && (
        <div>
          {loading ? (
            <div className="flex items-center justify-center py-24">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
            </div>
          ) : results.length > 0 ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm text-[var(--muted-foreground)]">
                  {results.length} insight{results.length !== 1 ? "s" : ""} found
                  {query ? ` for "${query}"` : ""}
                </p>
                {!session && (
                  <Badge variant="secondary" className="text-xs">
                    Sign in for video insights
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {results.map((insight, i) => (
                  <InsightCard key={insight.id || i} insight={insight} />
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-24">
              <div className="text-4xl mb-4">🔍</div>
              <div className="font-semibold text-lg mb-2">No results found</div>
              <div className="text-[var(--muted-foreground)] text-sm">
                Try different keywords or browse all sources
              </div>
              <Button variant="outline" className="mt-4" onClick={() => doSearch("", "")}>
                Browse all insights
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
