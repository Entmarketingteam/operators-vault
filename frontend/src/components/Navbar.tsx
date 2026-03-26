"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { supabase, signInWithGoogle, signOut } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { LogIn, LogOut, Menu, X, ShoppingBag } from "lucide-react";
import type { Session } from "@supabase/supabase-js";
import { cn } from "@/lib/utils";

const navLinks = [
  { href: "/", label: "Discover" },
  { href: "/newsletters", label: "Newsletters" },
  { href: "/episodes", label: "Episodes" },
  { href: "/speakers", label: "Speakers" },
  { href: "/guides", label: "Guides" },
  { href: "/ask", label: "Ask" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => setSession(s));
    return () => subscription.unsubscribe();
  }, []);

  const user = session?.user;
  const initials = user?.email?.slice(0, 2).toUpperCase() || "?";

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--background)]/90 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group shrink-0">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600/20 border border-indigo-500/30 group-hover:bg-indigo-600/30 transition-colors">
              <ShoppingBag className="h-4 w-4 text-indigo-400" />
            </div>
            <span className="font-bold text-base tracking-tight leading-none">
              <span className="text-indigo-400">ECOM</span>{" "}
              <span className="text-[var(--foreground)]">Operators</span>{" "}
              <span className="text-violet-400">Vault</span>
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "px-3.5 py-1.5 rounded-lg text-sm font-medium transition-colors",
                  pathname === link.href
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Auth */}
          <div className="hidden md:flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={user.user_metadata?.avatar_url} />
                  <AvatarFallback>{initials}</AvatarFallback>
                </Avatar>
                <Button variant="ghost" size="sm" onClick={() => signOut()}>
                  <LogOut className="h-4 w-4" />
                  Sign out
                </Button>
              </div>
            ) : (
              <Button size="sm" onClick={() => signInWithGoogle()}>
                <LogIn className="h-4 w-4" />
                Sign in
              </Button>
            )}
          </div>

          {/* Mobile toggle */}
          <button
            className="md:hidden p-2 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-3 border-t border-[var(--border)]">
            <nav className="flex flex-col gap-1 mb-3">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "px-3.5 py-2 rounded-lg text-sm font-medium transition-colors",
                    pathname === link.href
                      ? "bg-indigo-600/20 text-indigo-300"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
                  )}
                  onClick={() => setMobileOpen(false)}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            {user ? (
              <Button variant="outline" size="sm" className="w-full" onClick={() => signOut()}>
                <LogOut className="h-4 w-4" /> Sign out
              </Button>
            ) : (
              <Button size="sm" className="w-full" onClick={() => signInWithGoogle()}>
                <LogIn className="h-4 w-4" /> Sign in with Google
              </Button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
