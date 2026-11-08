"use client";

import React from "react";
import { Citation } from "@/lib/types";
import { BookOpen, ExternalLink, Hash, FileText } from "lucide-react";

interface CitationsPanelProps {
  citations: Citation[];
  activeCitationIndex?: number | null;
  onSelectCitation?: (index: number) => void;
}

export const CitationsPanel: React.FC<CitationsPanelProps> = ({
  citations,
  activeCitationIndex,
  onSelectCitation,
}) => {
  if (!citations || citations.length === 0) {
    return (
      <div className="p-4 text-center text-xs text-slate-500">
        <BookOpen className="w-8 h-8 text-slate-600 mx-auto mb-2 opacity-60" />
        <p>No verified citations retrieved for this query yet.</p>
        <p className="text-[11px] text-slate-600 mt-1">
          Citations will automatically appear here when authorized documents are referenced.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5 p-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">
          <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
          <span>Verified Sources ({citations.length})</span>
        </div>
        <span className="text-[10px] text-slate-500 font-mono">100% Grounded</span>
      </div>

      <div className="space-y-2">
        {citations.map((c, idx) => {
          const isActive = activeCitationIndex === idx;
          return (
            <div
              key={idx}
              onClick={() => onSelectCitation?.(idx)}
              className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                isActive
                  ? "bg-indigo-950/40 border-indigo-500/60 shadow-md shadow-indigo-950/20"
                  : "bg-slate-900/80 hover:bg-slate-850 border-slate-800 hover:border-slate-700"
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="w-5 h-5 flex items-center justify-center rounded-full bg-indigo-500/20 text-indigo-300 text-[10px] font-bold shrink-0 mt-0.5">
                  {idx + 1}
                </span>

                <div className="flex-1 min-w-0">
                  <h5 className="text-xs font-semibold text-slate-200 truncate" title={c.title}>
                    {c.title}
                  </h5>

                  {c.section_path && (
                    <div className="flex items-center gap-1 mt-1 text-[11px] text-indigo-300/80 truncate">
                      <Hash className="w-3 h-3 shrink-0" />
                      <span className="truncate">{c.section_path}</span>
                    </div>
                  )}

                  <div className="flex items-center justify-between gap-2 mt-2 pt-1.5 border-t border-slate-800/60 text-[10px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      <span className="truncate">{c.doc_id}</span>
                    </span>

                    {c.source_url ? (
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-0.5 text-indigo-400 hover:underline shrink-0"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <span>Open</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ) : (
                      <span className="uppercase tracking-wider text-[9px] bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">
                        {c.source || "local"}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

