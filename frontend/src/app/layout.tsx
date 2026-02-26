import type { Metadata, Viewport } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "アキ先生 — Anime Fluency Engine",
  description: "ローカルAIで日本語を学ぼう",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#111827",
};

const NAV_ITEMS = [
  { href: "/chat", label: "会話", icon: "💬" },
  { href: "/drills", label: "ドリル", icon: "🃏" },
  { href: "/shadowing", label: "シャドー", icon: "🎙" },
  { href: "/dashboard", label: "記録", icon: "📊" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-gray-900 text-gray-100 flex flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-50 bg-gray-950 border-b border-gray-800 px-4 py-3">
          <div className="max-w-2xl mx-auto flex items-center justify-between">
            <Link href="/chat" className="font-bold text-lg text-white">
              アキ先生
            </Link>
            <span className="text-xs text-gray-500">v1.0</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-6">
          {children}
        </main>

        {/* Bottom nav */}
        <nav className="sticky bottom-0 z-50 bg-gray-950 border-t border-gray-800">
          <div className="max-w-2xl mx-auto flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex-1 flex flex-col items-center py-3 gap-0.5 text-gray-400 hover:text-white transition-colors"
              >
                <span className="text-xl">{item.icon}</span>
                <span className="text-xs">{item.label}</span>
              </Link>
            ))}
          </div>
        </nav>
      </body>
    </html>
  );
}
