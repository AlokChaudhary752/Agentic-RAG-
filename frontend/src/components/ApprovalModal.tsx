"use client";

import React, { useState } from "react";
import { ToolRequest } from "@/lib/types";
import { AlertCircle, CheckCircle, XCircle, ShieldAlert, Cpu } from "lucide-react";

interface ApprovalModalProps {
  toolRequest: ToolRequest;
  riskLevel?: string;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  toolRequest,
  riskLevel = "write_high",
  onApprove,
  onReject,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleAction = async (decision: "approve" | "reject") => {
    setIsSubmitting(true);
    try {
      if (decision === "approve") {
        await onApprove();
      } else {
        await onReject();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="my-4 p-4 bg-slate-900 border-2 border-amber-500/60 rounded-2xl shadow-xl">
      <div className="flex items-center gap-2 mb-2 text-amber-400">
        <ShieldAlert className="w-5 h-5 shrink-0 animate-pulse" />
        <h4 className="text-sm font-bold uppercase tracking-wider">
          Human-In-The-Loop Approval Required
        </h4>
        <span className="ml-auto text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 uppercase">
          {riskLevel}
        </span>
      </div>

      <p className="text-xs text-slate-300 mb-3">
        The agent has formulated an external tool action that modifies enterprise state. Please review the payload and approve or reject execution:
      </p>

      <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 font-mono text-xs text-slate-300 mb-4 overflow-x-auto">
        <div className="flex items-center gap-2 text-indigo-400 font-semibold mb-1">
          <Cpu className="w-3.5 h-3.5" />
          <span>MCP Tool: {toolRequest.tool}</span>
        </div>
        <pre className="text-[11px] text-slate-400 mt-2 whitespace-pre-wrap">
          {JSON.stringify(toolRequest.arguments, null, 2)}
        </pre>
      </div>

      <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
        <button
          onClick={() => handleAction("reject")}
          disabled={isSubmitting}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-rose-400 hover:text-rose-300 bg-rose-950/40 hover:bg-rose-900/50 border border-rose-800/60 rounded-lg transition disabled:opacity-50"
        >
          <XCircle className="w-3.5 h-3.5" />
          Reject Action
        </button>

        <button
          onClick={() => handleAction("approve")}
          disabled={isSubmitting}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-md transition disabled:opacity-50"
        >
          <CheckCircle className="w-3.5 h-3.5" />
          {isSubmitting ? "Executing..." : "Approve & Execute"}
        </button>
      </div>
    </div>
  );
};

