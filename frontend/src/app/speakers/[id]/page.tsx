"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { getSpeaker, type Speaker } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import InsightCard from "@/components/InsightCard";
import { Loader2, ArrowLeft, Building2, Lightbulb } from "lucide-react";
import Link from "next/link";

export default function SpeakerDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [speaker, setSpeaker] = useState<Speaker | null>(null);
  const [loading, setLoading] = useState(true);

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
            {speaker.insight_count !== undefined && (
              <div className="flex items-center gap-2 mt-4">
                <Badge variant="default">
                  <Lightbulb className="h-3 w-3 mr-1" />
                  {speaker.insight_count} insights in vault
                </Badge>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Top insights */}
      {speaker.top_insights && speaker.top_insights.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Top Insights</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {speaker.top_insights.map((insight, i) => (
              <InsightCard key={insight.id || i} insight={insight} />
            ))}
          </div>
        </div>
      )}

      {(!speaker.top_insights || speaker.top_insights.length === 0) && (
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
    </div>
  );
}
