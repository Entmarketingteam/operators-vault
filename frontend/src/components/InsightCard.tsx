import { type Insight } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { User, Podcast, Mail, Tag } from "lucide-react";

function getSourceVariant(source?: string): "podcast" | "newsletter" {
  if (!source) return "podcast";
  const s = source.toLowerCase();
  if (s.includes("newsletter") || s.includes("nik sharma") || s.includes("ctc") || s.includes("dimond") || s.includes("bertulli")) {
    return "newsletter";
  }
  return "podcast";
}

function getPodcastShortName(podcast?: string): string {
  if (!podcast) return "";
  const map: Record<string, string> = {
    "9operators": "9 Operators",
    "9_operators": "9 Operators",
    "marketing_operator": "Marketing Operator",
    "finance_operators": "Finance Operators",
    "titans": "TITANS",
  };
  return map[podcast.toLowerCase()] || podcast;
}

export default function InsightCard({ insight }: { insight: Insight }) {
  const speaker = insight.speaker_name || insight.speaker;
  const source = insight.source || insight.podcast || insight.author;
  const sourceVariant = getSourceVariant(source);
  const displaySource = insight.podcast ? getPodcastShortName(insight.podcast) : (insight.author || source);

  return (
    <Card className="group cursor-default flex flex-col h-full">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap gap-1.5 mb-2">
          {displaySource && (
            <Badge variant={sourceVariant}>
              {sourceVariant === "podcast" ? (
                <Podcast className="h-3 w-3 mr-1" />
              ) : (
                <Mail className="h-3 w-3 mr-1" />
              )}
              {displaySource}
            </Badge>
          )}
          {insight.category && (
            <Badge variant="category">
              <Tag className="h-3 w-3 mr-1" />
              {insight.category}
            </Badge>
          )}
          {insight.type && insight.type !== insight.category && (
            <Badge variant="secondary">{insight.type}</Badge>
          )}
        </div>
        <CardTitle className="text-sm font-semibold leading-snug line-clamp-2 group-hover:text-indigo-300 transition-colors">
          {insight.title}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-between gap-3">
        <CardDescription className="text-xs line-clamp-3">
          {insight.description}
        </CardDescription>
        {speaker && (
          <div className="flex items-center gap-1.5 mt-auto pt-2 border-t border-[var(--border)]">
            <User className="h-3 w-3 text-[var(--muted-foreground)]" />
            <span className="text-xs text-[var(--muted-foreground)]">
              From: <span className="text-indigo-300 font-medium">{speaker}</span>
            </span>
          </div>
        )}
        {insight.episode_title && (
          <div className="text-xs text-[var(--muted-foreground)] truncate mt-1">
            {insight.episode_title}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
