"use client";

import { useState, useEffect } from "react";
import { generateTopicGuide, type TopicGuide } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import type { Session } from "@supabase/supabase-js";
import { signInWithGoogle } from "@/lib/supabase";
import { LogIn, Lock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Sparkles, Loader2, Copy, Check, BookOpen, Tag, ChevronDown, ChevronUp } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { haptic } from "@/lib/haptics";

const EXAMPLE_TOPICS = [
  "Product Launch Strategy",
  "Email Marketing Retention",
  "Influencer Campaign ROI",
  "Paid Social Scaling",
  "Customer LTV Optimization",
  "DTC Brand Building",
  "Subscription Business",
  "Community Building",
];

function SourceCard({ insight, index }: { insight: { title?: string; description?: string; source?: string; author?: string; speaker?: string; speaker_name?: string }, index: number }) {
  const [expanded, setExpanded] = useState(false);
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.source || insight.author;

  return (
    <div className="vault-card p-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="shrink-0 h-6 w-6 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-xs font-medium text-indigo-300">
            {index + 1}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium leading-snug line-clamp-2">{insight.title || "Source"}</div>
            {source && <div className="text-xs text-indigo-300 mt-0.5">{source}</div>}
            {speaker && <div className="text-xs text-[var(--muted-foreground)]">By {speaker}</div>}
          </div>
        </div>
        <button className="text-[var(--muted-foreground)] shrink-0">
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>
      {expanded && insight.description && (
        <div className="mt-3 pt-3 border-t border-[var(--border)] text-sm text-[var(--muted-foreground)] leading-relaxed">
          {insight.description}
        </div>
      )}
    </div>
  );
}

export default function GuidesPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [topic, setTopic] = useState("");
  const [guide, setGuide] = useState<TopicGuide | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setSessionLoading(false);
    });
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mx-auto max-w-md px-4 py-24 text-center">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600/10 border border-indigo-500/20 mb-6">
          <Lock className="h-8 w-8 text-indigo-400" />
        </div>
        <h1 className="text-3xl font-bold mb-3">Sign in to access Guides</h1>
        <p className="text-[var(--muted-foreground)] mb-8">
          AI-powered playbooks synthesized from operator knowledge are available to signed-in members.
        </p>
        <button
          onClick={() => signInWithGoogle()}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold transition-colors"
        >
          <LogIn className="h-4 w-4" />
          Sign in with Google
        </button>
      </div>
    );
  }

  const handleGenerate = async (e?: React.FormEvent, topicOverride?: string) => {
    e?.preventDefault();
    const t = topicOverride || topic;
    if (!t.trim()) return;
    haptic("impact");
    setLoading(true);
    setError("");
    setGuide(null);
    try {
      const result = await generateTopicGuide(t.trim());
      haptic("success");
      setGuide(result);
    } catch (err) {
      haptic("warning");
      setError("Failed to generate guide. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!guide) return;
    haptic("selection");
    navigator.clipboard.writeText(guide.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 rounded-full bg-indigo-600/10 border border-indigo-500/20 px-4 py-1.5 text-sm text-indigo-300 mb-6">
          <Sparkles className="h-3.5 w-3.5" />
          AI-Powered Playbooks
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-4">
          Topic{" "}
          <span className="text-indigo-400 bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
            Guides
          </span>
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] max-w-xl mx-auto">
          Enter any DTC or marketing topic and get an AI-generated playbook synthesized from operator knowledge.
        </p>
      </div>

      {/* Input */}
      <div className="vault-card p-6 mb-8 glow-border">
        <form onSubmit={handleGenerate} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <BookOpen className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
            <Input
              type="text"
              placeholder="What do you want to learn? e.g. Email Marketing Retention"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="pl-10 h-12 text-base"
            />
          </div>
          <Button type="submit" size="lg" disabled={loading || !topic.trim()} className="shrink-0">
            {loading ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="h-4 w-4" /> Generate Guide</>
            )}
          </Button>
        </form>

        {/* Example topics */}
        <div className="mt-4">
          <div className="text-xs text-[var(--muted-foreground)] mb-2">Example topics:</div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_TOPICS.map((t) => (
              <button
                key={t}
                onClick={() => {
                  haptic("selection");
                  setTopic(t);
                  handleGenerate(undefined, t);
                }}
                disabled={loading}
                className="btn-base text-xs px-3 py-1.5 rounded-full border border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:border-indigo-500/40 hover:bg-indigo-600/10 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Tag className="h-3 w-3 inline mr-1" />
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="vault-card border-red-500/30 bg-red-600/10 p-4 mb-6 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-center py-16">
          <div className="inline-flex items-center gap-3 text-indigo-300">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="text-lg">Synthesizing operator knowledge...</span>
          </div>
          <p className="text-sm text-[var(--muted-foreground)] mt-2">
            This may take a moment as we search the vault
          </p>
        </div>
      )}

      {/* Guide output */}
      {guide && !loading && (
        <div>
          {/* Header */}
          <div className="flex items-start justify-between gap-4 mb-6">
            <div>
              <h2 className="text-2xl font-bold mb-1">{guide.topic || topic}</h2>
              <div className="text-sm text-[var(--muted-foreground)]">
                {guide.sources?.length ? `Based on ${guide.sources.length} sources from the vault` : "Generated from operator knowledge"}
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={handleCopy} className="shrink-0">
              {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>

          {/* Content */}
          <div className="vault-card p-8 mb-8">
            <div className="prose-vault">
              <ReactMarkdown>{guide.content}</ReactMarkdown>
            </div>
          </div>

          {/* Sources */}
          {guide.sources && guide.sources.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-4">
                <h3 className="text-lg font-semibold">Sources</h3>
                <Badge variant="secondary">{guide.sources.length}</Badge>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {guide.sources.map((source, i) => (
                  <SourceCard key={i} insight={source} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* Generate another */}
          <div className="mt-8 pt-6 border-t border-[var(--border)] text-center">
            <Button
              variant="outline"
              onClick={() => { haptic("selection"); setGuide(null); setTopic(""); }}
            >
              Generate Another Guide
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
