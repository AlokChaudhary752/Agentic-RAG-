import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ShieldCheck, MessageSquare, BarChart3, Lock, Cpu } from "lucide-react";

export const metadata: Metadata = {
  title: "Enterprise Knowledge Agent | Permission-Aware RAG",
  description: "Production-grade, permission-aware, agentic RAG platform with zero permission leaks and MCP tool orchestration.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased flex flex-col">
        {/* Navigation Header */}
        <header className="h-16 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center text-white shadow-md shadow-indigo-600/30">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-white">
                  Enterprise Knowledge Agent
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold">
                  v0.1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
                <Lock className="w-2.5 h-2.5 text-emerald-400" />
                <span>Zero-Leak Permission-Aware RAG & MCP Platform</span>
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-1.5">
            <Link
              href="/"
              className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl text-slate-300 hover:text-white hover:bg-slate-800/80 transition"
            >
              <MessageSquare className="w-4 h-4 text-indigo-400" />
              <span>Chat Assistant</span>
            </Link>

            <Link
              href="/admin"
              className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold rounded-xl text-slate-300 hover:text-white hover:bg-slate-800/80 transition"
            >
              <BarChart3 className="w-4 h-4 text-cyan-400" />
              <span>Admin & Eval Dashboard</span>
            </Link>
          </nav>
        </header>

        {/* Page Body */}
        <main className="flex-1 flex flex-col">{children}</main>
      </body>
    </html>
  );
}

