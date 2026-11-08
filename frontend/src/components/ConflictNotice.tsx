"use client";

import React from "react";
import { AlertTriangle, GitCompare, CheckCircle2 } from "lucide-react";

interface ConflictNoticeProps {
  notices: string[];
}

export const ConflictNotice: React.FC<ConflictNoticeProps> = ({ notices }) => {
  if (!notices || notices.length === 0) return null;

  return (
    <div className="my-3 p-3.5 bg-amber-950/40 border border-amber-600/40 rounded-xl shadow-inner text-amber-200">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
        <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
          Knowledge Conflict Detected & Resolved
        </span>
      </div>

      <div className="space-y-1.5 text-xs text-amber-100/90 leading-relaxed pl-6">
        {notices.map((notice, idx) => (
          <div key={idx} className="flex items-start gap-2">
            <GitCompare className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
            <p>{notice}</p>
          </div>
        ))}
      </div>

      <div className="mt-2.5 pt-2 border-t border-amber-700/30 flex items-center gap-1.5 text-[11px] text-amber-300/80 pl-6">
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
        <span>Grounded answer prefers approved, authoritative, and newer source document.</span>
      </div>
    </div>
  );
};

