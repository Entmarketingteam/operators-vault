"use client";

import { useState, useRef, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { sendChatMessage, type Insight } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Send, Loader2, ChevronDown, ChevronUp, Vault, User, Bot } from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Insight[];
}

const STARTER_QUESTIONS = [
  "What are the best retention strategies for DTC brands?",
  "How do operators think about email marketing?",
  "What frameworks do operators use for scaling paid social?",
  "How should I think about influencer ROI?",
];

function SourcesPanel({ sources }: { sources: Insight[] }) {
  const [open, setOpen] = useState(false);
  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs text-[var(--muted-foreground)] hover:text-indigo-300 transition-colors"
      >
        <span>{sources.length} source{sources.length !== 1 ? "s" : ""}</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div key={i} className="vault-card p-3 text-xs">
              <div className="font-medium text-[var(--foreground)] mb-0.5 line-clamp-1">{s.title}</div>
              {(s.source || s.author) && (
                <div className="text-indigo-300">{s.source || s.author}</div>
              )}
              {s.description && (
                <div className="text-[var(--muted-foreground)] mt-1 line-clamp-2">{s.description}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div className={cn(
        "shrink-0 h-8 w-8 rounded-full flex items-center justify-center mt-0.5",
        isUser
          ? "bg-indigo-600/20 border border-indigo-500/30"
          : "bg-violet-600/20 border border-violet-500/30"
      )}>
        {isUser
          ? <User className="h-4 w-4 text-indigo-400" />
          : <Bot className="h-4 w-4 text-violet-400" />
        }
      </div>

      {/* Content */}
      <div className={cn("flex flex-col max-w-[80%]", isUser ? "items-end" : "items-start")}>
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-indigo-600/20 border border-indigo-500/30 text-[var(--foreground)]"
            : "bg-[var(--card)] border border-[var(--border)] text-[var(--foreground)]"
        )}>
          {message.content.split("\n").map((line, i) => (
            <span key={i}>
              {line}
              {i < message.content.split("\n").length - 1 && <br />}
            </span>
          ))}
        </div>
        {!isUser && message.sources && (
          <SourcesPanel sources={message.sources} />
        )}
      </div>
    </div>
  );
}

export default function AskPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Hi! I'm the Operators Vault assistant. Ask me anything about DTC strategy, marketing, email, influencers, or anything the operators have covered. I'll pull from the vault to give you grounded answers.",
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (e?: React.FormEvent, messageOverride?: string) => {
    e?.preventDefault();
    const text = messageOverride || input;
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const token = session?.access_token;
      const response = await sendChatMessage(text, history, token);

      const assistantMsg: Message = {
        role: "assistant",
        content: response.reply || "I couldn't find a specific answer for that. Try rephrasing or searching the vault directly.",
        sources: response.sources,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: "Sorry, I ran into an error. Please try again.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 py-8 flex flex-col" style={{ height: "calc(100vh - 8rem)" }}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 shrink-0">
        <div className="h-10 w-10 rounded-xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
          <Vault className="h-5 w-5 text-violet-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold">Ask the Vault</h1>
          <p className="text-sm text-[var(--muted-foreground)]">Answers grounded in operator knowledge</p>
        </div>
        {!session && (
          <Badge variant="secondary" className="ml-auto text-xs">
            Sign in for video insights
          </Badge>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-6 pb-4">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="shrink-0 h-8 w-8 rounded-full bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
              <Bot className="h-4 w-4 text-violet-400" />
            </div>
            <div className="bg-[var(--card)] border border-[var(--border)] rounded-2xl px-4 py-3 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
              <span className="text-sm text-[var(--muted-foreground)]">Searching the vault...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Starters (shown when only welcome message) */}
      {messages.length === 1 && (
        <div className="shrink-0 mb-4">
          <div className="text-xs text-[var(--muted-foreground)] mb-2">Try asking:</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {STARTER_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => handleSend(undefined, q)}
                className="text-left text-xs p-3 rounded-xl border border-[var(--border)] text-[var(--muted-foreground)] hover:border-indigo-500/40 hover:text-[var(--foreground)] hover:bg-indigo-600/5 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="shrink-0 pt-4 border-t border-[var(--border)]">
        <form onSubmit={handleSend} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about DTC strategy..."
            className="h-11"
            disabled={loading}
          />
          <Button type="submit" disabled={loading || !input.trim()} size="icon" className="h-11 w-11 shrink-0">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  );
}
