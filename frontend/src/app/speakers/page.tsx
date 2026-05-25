"use client";

import { useState, useEffect } from "react";
import { getSpeakers, type Speaker } from "@/lib/api";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Search, Users, Mic, ChevronRight, Twitter } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/utils";

function initials(name: string) {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

function HostCard({ speaker }: { speaker: Speaker }) {
  return (
    <Link href={`/speakers/${speaker.slug || speaker.id}`}>
      <div className="vault-card p-6 group cursor-pointer flex flex-col h-full hover:border-indigo-500/40 transition-all">
        <div className="flex items-start gap-4 mb-4">
          <Avatar className="h-16 w-16 shrink-0 ring-2 ring-indigo-500/20 group-hover:ring-indigo-500/50 transition-all">
            {speaker.photo_url && <AvatarImage src={speaker.photo_url} alt={speaker.name} />}
            <AvatarFallback className="text-base bg-indigo-600/20 text-indigo-300">{initials(speaker.name)}</AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-base group-hover:text-indigo-300 transition-colors">{speaker.name}</div>
            {speaker.title && (
              <div className="text-sm text-indigo-400 truncate">{speaker.title}</div>
            )}
            {speaker.company && (
              <div className="text-sm text-[var(--muted-foreground)] truncate">{speaker.company}</div>
            )}
          </div>
        </div>
        {speaker.bio && (
          <p className="text-sm text-[var(--muted-foreground)] line-clamp-3 flex-1 leading-relaxed mb-4">
            {speaker.bio}
          </p>
        )}
        <div className="flex items-center justify-between mt-auto pt-3 border-t border-[var(--border)]">
          <div className="flex items-center gap-2">
            {(speaker.insight_count ?? 0) > 0 && (
              <Badge variant="secondary" className="text-xs">
                {speaker.insight_count} insights
              </Badge>
            )}
            {speaker.twitter_handle && (
              <a
                href={`https://twitter.com/${speaker.twitter_handle}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-[var(--muted-foreground)] hover:text-sky-400 transition-colors"
              >
                <Twitter className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
          <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)] group-hover:text-indigo-400 transition-colors" />
        </div>
      </div>
    </Link>
  );
}

function SpeakerCard({ speaker }: { speaker: Speaker }) {
  return (
    <Link href={`/speakers/${speaker.slug || speaker.id}`}>
      <div className="vault-card p-5 group cursor-pointer h-full flex flex-col">
        <div className="flex items-start gap-4 mb-3">
          <Avatar className="h-12 w-12 shrink-0">
            {speaker.photo_url && <AvatarImage src={speaker.photo_url} alt={speaker.name} />}
            <AvatarFallback className="text-sm">{initials(speaker.name)}</AvatarFallback>
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
        {(speaker.insight_count ?? 0) > 0 && (
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

const PODCAST_META: Record<string, { label: string; color: string; dot: string }> = {
  "9operators": {
    label: "9 Operators",
    color: "text-violet-300 bg-violet-600/10 border-violet-500/20",
    dot: "bg-violet-400",
  },
  marketing_operator: {
    label: "Marketing Operators",
    color: "text-indigo-300 bg-indigo-600/10 border-indigo-500/20",
    dot: "bg-indigo-400",
  },
};

export default function SpeakersPage() {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getSpeakers().then((data) => {
      setSpeakers(data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const hosts9 = speakers.filter((s) => s.is_host && s.host_podcast === "9operators");
  const hostsMarketing = speakers.filter((s) => s.is_host && s.host_podcast === "marketing_operator");
  const guests = speakers.filter((s) => !s.is_host);

  const filteredGuests = guests.filter((s) =>
    !search ||
    (s.name || "").toLowerCase().includes(search.toLowerCase()) ||
    (s.company || "").toLowerCase().includes(search.toLowerCase())
  );

  const filteredHosts9 = hosts9.filter((s) =>
    !search ||
    (s.name || "").toLowerCase().includes(search.toLowerCase()) ||
    (s.company || "").toLowerCase().includes(search.toLowerCase())
  );

  const filteredHostsMarketing = hostsMarketing.filter((s) =>
    !search ||
    (s.name || "").toLowerCase().includes(search.toLowerCase()) ||
    (s.company || "").toLowerCase().includes(search.toLowerCase())
  );

  const showHosts = !search || filteredHosts9.length > 0 || filteredHostsMarketing.length > 0;

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
      <div className="relative max-w-sm mb-10">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
        <Input
          placeholder="Search speakers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : (
        <>
          {/* Hosts sections */}
          {showHosts && (
            <div className="mb-12 space-y-10">
              {(["9operators", "marketing_operator"] as const).map((podcast) => {
                const podcastHosts = podcast === "9operators" ? filteredHosts9 : filteredHostsMarketing;
                if (podcastHosts.length === 0) return null;
                const meta = PODCAST_META[podcast];
                return (
                  <div key={podcast}>
                    <div className="flex items-center gap-3 mb-5">
                      <div className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium", meta.color)}>
                        <Mic className="h-3 w-3" />
                        {meta.label} Hosts
                      </div>
                      <div className="h-px flex-1 bg-[var(--border)]" />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
                      {podcastHosts.map((speaker) => (
                        <HostCard key={speaker.id} speaker={speaker} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Guest speakers */}
          {filteredGuests.length > 0 && (
            <div>
              {!search && (
                <div className="flex items-center gap-3 mb-5">
                  <div className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--muted-foreground)]">
                    <Users className="h-3 w-3" />
                    Featured Guests
                  </div>
                  <div className="h-px flex-1 bg-[var(--border)]" />
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 stagger">
                {filteredGuests.map((speaker) => (
                  <SpeakerCard key={speaker.id} speaker={speaker} />
                ))}
              </div>
            </div>
          )}

          {filteredHosts9.length === 0 && filteredHostsMarketing.length === 0 && filteredGuests.length === 0 && (
            <div className="text-center py-16">
              <div className="text-4xl mb-3">👥</div>
              <div className="font-semibold mb-1">No speakers found</div>
              <div className="text-[var(--muted-foreground)] text-sm">Try a different search</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
