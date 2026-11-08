"use client";

import React, { useState, useEffect } from "react";
import { BenchmarkChart } from "@/components/BenchmarkChart";
import { BenchmarkData } from "@/lib/types";
import { fetchBenchmarkData } from "@/lib/api";
import {
  BarChart3,
  ShieldCheck,
  CheckCircle2,
  FileCheck2,
  History,
  Lock,
  RefreshCw,
  Search,
} from "lucide-react";

export default function AdminPage() {
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await fetchBenchmarkData();
      setBenchmarkData(data);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="flex-1 max-w-7xl mx-auto w-full px-4 py-6 space-y-8">
      {/* Header & Status Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white">
              Enterprise Knowledge Governance & Evaluation Dashboard
            </h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" />
              Regression Gates Active
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Empirical benchmarking, automated RAGAS metrics, zero permission leak assertions, and immutable audit logs.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition self-start sm:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          <span>Refresh Benchmark Run</span>
        </button>
      </div>

      {/* Benchmark KPIs & Comparison Table */}
      {benchmarkData ? (
        <BenchmarkChart data={benchmarkData} />
      ) : (
        <div className="p-12 text-center text-slate-500 text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-400" />
          <p>Loading empirical benchmark evaluation data...</p>
        </div>
      )}

      {/* Governance & STRIDE Threat Mitigation Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs uppercase tracking-wider mb-2">
            <Lock className="w-4 h-4" />
            <span>Dual-Layer ACL Enforcement</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Every query applies HNSW boolean pre-filtering inside Qdrant before vector distance computation, followed by a secondary post-retrieval ACL assertion that fails closed.
          </p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-xs uppercase tracking-wider mb-2">
            <FileCheck2 className="w-4 h-4" />
            <span>Conflict Resolution Protocol</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Super-deduplication detects near-duplicate or contradictory chunks across documents, weighting by authority score and recency to prioritize approved policies over drafts.
          </p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs uppercase tracking-wider mb-2">
            <ShieldCheck className="w-4 h-4" />
            <span>Human-In-The-Loop Safety</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            MCP tools are classified by risk tier: read operations execute immediately, while write_high actions (such as Jira ticket creation) suspend execution for manual employee review.
          </p>
        </div>
      </div>
    </div>
  );
}

