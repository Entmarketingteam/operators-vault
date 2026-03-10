"use client";

import { useState, useEffect } from "react";
import { getSpeakers, type Speaker } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Search, Users, ChevronRight } from "lucide-react";
import Link from "next/link";

function SpeakerCard({ speaker }: { speaker: Speaker }) {
  const initials = speaker.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <Link href={`/speakers/${speaker.id}`}>
      <div className="vault-card p-5 group cursor-pointer h-full flex flex-col">
        <div className="flex items-start gap-4 mb-3">
          <Avatar className="h-12 w-12 shrink-0">
            {speaker.photo_url && <AvatarImage src={speaker.photo_url} alt={speaker.name} />}
            <AvatarFallback className="text-sm">{initials}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="font-semibold group-hover:text-indigo-300 transition-colors truncate">{speaker.name}</div>
            {speaker.company && (
              <div className="text-sm text-[var(--muted-foreground)] truncate">{speaker.company}</div>
            )}
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)] group-hover:text-indigo-400 transition-colors shrink-0 mt-0.5" />
        </div>
        {speaker.bio && (
          <p className="text-sm text-[var(--muted-foreground)] line-clamp-3 flex-1 leading-relaxed">
            {speaker.bio}
          </p>
        )}
        {speaker.insight_count !== undefined && (
          <div className="mt-3 pt-3 border-t border-[var(--border)]">
            <Badge variant="secondary" className="text-xs">
              {speaker.insight_count} insight{speaker.insight_count !== 1 ? "s" : ""}
            </Badge>
          </div>
        )}
      </div>
    </Link>
  );
}

// Fallback speakers from known sources
const FALLBACK_SPEAKERS: Speaker[] = [
  { id: "nik-sharma", name: "Nik Sharma", company: "Sharma Brands", bio: "DTC operator and investor. Founder of Sharma Brands.", insight_count: 0 },
  { id: "taylor-holiday", name: "Taylor Holiday", company: "Common Thread Collective", bio: "CEO of Common Thread Collective. DTC marketing expert.", insight_count: 0 },
  { id: "matt-bertulli", name: "Matt Bertulli", company: "Pela Case / Lomi", bio: "Co-founder of Pela Case and Lomi. Sustainable DTC pioneer.", insight_count: 0 },
  { id: "chase-dimond", name: "Chase Dimond", company: "Boundless Labs", bio: "Email marketing expert and DTC newsletter author.", insight_count: 0 },
];

export default function SpeakersPage() {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getSpeakers().then((data) => {
      setSpeakers(data.length > 0 ? data : FALLBACK_SPEAKERS);
      setLoading(false);
    }).catch(() => {
      setSpeakers(FALLBACK_SPEAKERS);
      setLoading(false);
    });
  }, []);

  const filtered = speakers.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.company?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 rounded-full bg-emerald-600/10 border border-emerald-500/20 px-4 py-1.5 text-sm text-emerald-300 mb-6">
          <Users className="h-3.5 w-3.5" />
          Operator Profiles
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold tracking-tight mb-3">
          Speakers &{" "}
          <span className="text-emerald-400 bg-gradient-to-r from-emerald-400 to-teal-400 bg-clip-text text-transparent">
            Operators
          </span>
        </h1>
        <p className="text-lg text-[var(--muted-foreground)] max-w-xl">
          Browse insights by the operators who shared them.
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-sm mb-8">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
        <Input
          placeholder="Search speakers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : filtered.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((speaker) => (
            <SpeakerCard key={speaker.id} speaker={speaker} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">👥</div>
          <div className="font-semibold mb-1">No speakers found</div>
          <div className="text-[var(--muted-foreground)] text-sm">Try a different search</div>
        </div>
      )}
    </div>
  );
}
