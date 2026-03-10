import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Operators Vault — DTC Knowledge Base",
  description: "Search insights and frameworks from top DTC operators. Podcasts, newsletters, and expert knowledge in one place.",
  openGraph: {
    title: "Operators Vault",
    description: "Search insights from 9 Operators, Marketing Operator, Finance Operators, and top DTC newsletters.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen`}>
        <Navbar />
        <main className="min-h-[calc(100vh-4rem)]">
          {children}
        </main>
        <footer className="border-t border-[var(--border)] py-8 mt-16">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-[var(--muted-foreground)]">
            <div>© {new Date().getFullYear()} Operators Vault — ENT Agency</div>
            <div className="flex gap-6">
              <a href="/" className="hover:text-[var(--foreground)] transition-colors">Discover</a>
              <a href="/guides" className="hover:text-[var(--foreground)] transition-colors">Guides</a>
              <a href="/ask" className="hover:text-[var(--foreground)] transition-colors">Ask</a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
