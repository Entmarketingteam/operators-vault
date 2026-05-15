import { NextRequest, NextResponse } from "next/server";
import { GoogleAuth } from "google-auth-library";
import { createClient } from "@supabase/supabase-js";

export const runtime = "nodejs";
export const maxDuration = 60;

const ADK_URL = process.env.ADK_CLOUD_RUN_URL!;
const SA_KEY_B64 = process.env.GCP_VERCEL_INVOKER_KEY_B64!;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

let cachedAuth: GoogleAuth | null = null;
function getAuth() {
  if (!cachedAuth) {
    const credentials = JSON.parse(
      Buffer.from(SA_KEY_B64, "base64").toString("utf-8"),
    );
    cachedAuth = new GoogleAuth({ credentials });
  }
  return cachedAuth;
}

interface AdkEvent {
  content?: {
    role?: string;
    parts?: Array<{
      text?: string;
      functionResponse?: { name: string; response: any };
    }>;
  };
}

interface SourceHit {
  id?: string;
  title?: string;
  description?: string;
  source?: string;
  podcast?: string;
  category?: string;
  author?: string;
}

function extractFromEvents(events: AdkEvent[]): {
  reply: string;
  sources: SourceHit[];
} {
  const textChunks: string[] = [];
  const sourcesById = new Map<string, SourceHit>();

  for (const ev of events) {
    const parts = ev.content?.parts ?? [];
    for (const p of parts) {
      if (p.text) textChunks.push(p.text);

      const fr = p.functionResponse?.response;
      if (fr && Array.isArray(fr.hits)) {
        for (const hit of fr.hits as SourceHit[]) {
          const key = hit.id ?? `${hit.title}|${hit.source ?? hit.podcast}`;
          if (!sourcesById.has(key)) {
            sourcesById.set(key, {
              ...hit,
              author: hit.source ?? hit.podcast,
            });
          }
        }
      }
    }
  }

  return {
    reply: textChunks.join("").trim(),
    sources: Array.from(sourcesById.values()).slice(0, 12),
  };
}

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return NextResponse.json(
      { error: "Sign in required" },
      { status: 401 },
    );
  }
  const userJwt = authHeader.slice(7);

  const supabase = createClient(SUPABASE_URL, SUPABASE_ANON);
  const { data: userData, error: userErr } = await supabase.auth.getUser(userJwt);
  if (userErr || !userData?.user) {
    return NextResponse.json(
      { error: "Invalid session" },
      { status: 401 },
    );
  }
  const userId = userData.user.id;

  const { message } = (await req.json()) as { message: string };
  if (!message?.trim()) {
    return NextResponse.json({ error: "message required" }, { status: 400 });
  }

  const auth = getAuth();
  const client = await auth.getIdTokenClient(ADK_URL);
  const sessionId = crypto.randomUUID();

  await client.request({
    url: `${ADK_URL}/apps/app/users/${encodeURIComponent(userId)}/sessions/${sessionId}`,
    method: "POST",
    data: {},
  });

  const runRes = await client.request<AdkEvent[]>({
    url: `${ADK_URL}/run`,
    method: "POST",
    data: {
      appName: "app",
      userId,
      sessionId,
      newMessage: { role: "user", parts: [{ text: message }] },
    },
    timeout: 55000,
  });

  const { reply, sources } = extractFromEvents(runRes.data ?? []);
  return NextResponse.json({ reply, sources, citations: sources.length });
}
