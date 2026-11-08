"use client";

import React, { useState } from "react";
import { ChatMessage, Citation } from "@/lib/types";
import { ConflictNotice } from "./ConflictNotice";
import { ApprovalModal } from "./ApprovalModal";
import {
  BrainCircuit,
  Bot,
  User,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Clock,
  Sparkles,
} from "lucide-react";

interface MessageListProps {
  messages: ChatMessage[];
  onSelectCitation?: (citation: Citation) => void;
  onApproveTool?: (message: ChatMessage) => Promise<void>;
  onRejectTool?: (message: ChatMessage) => Promise<void>;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  onSelectCitation,
  onApproveTool,
  onRejectTool,
}) => {
  const [expandedSteps, setExpandedSteps] = useState<Record<string, boolean>>({});

  const toggleSteps = (id: string) => {
    setExpandedSteps((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const renderContentWithCitations = (content: string, citations?: Citation[]) => {
    if (!citations || citations.length === 0) {
      return <p className="whitespace-pre-wrap leading-relaxed">{content}</p>;
    }

    // Split text and replace [^1], [^2], [1] with interactive badge links
    const parts = content.split(/(\[\^?\d+\])/g);
    return (
      <div className="whitespace-pre-wrap leading-relaxed">
        {parts.map((part, i) => {
          const match = part.match(/\[\^?(\d+)\]/);
          if (match) {
            const index = parseInt(match[1], 10) - 1;
            const citation = citations[index];
            return (
              <button
                key={i}
                onClick={() => citation && onSelectCitation?.(citation)}
                className="inline-flex items-center justify-center px-1.5 py-0.2 mx-0.5 text-[10px] font-bold font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 rounded hover:bg-indigo-500/40 transition cursor-pointer"
                title={citation ? `${citation.title} (${citation.section_path || citation.doc_id})` : "Citation"}
              >
                {part}
              </button>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const hasSteps = message.steps_executed && message.steps_executed.length > 0;
        const isStepsOpen = expandedSteps[message.id] ?? false;

        return (
          <div
            key={message.id}
            className={`flex items-start gap-3.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-sm shadow-md ${
                isUser
                  ? "bg-indigo-600 text-white"
                  : "bg-slate-800 text-indigo-400 border border-slate-700"
              }`}
            >
              {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble Content */}
            <div className={`flex flex-col max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
              <div
                className={`p-4 rounded-2xl shadow-sm text-sm ${
                  isUser
                    ? "bg-indigo-600 text-white rounded-tr-none"
                    : "bg-slate-850/90 border border-slate-750 text-slate-100 rounded-tl-none backdrop-blur-sm"
                }`}
              >
                {/* Agent reasoning steps execution accordion */}
                {!isUser && hasSteps && (
                  <div className="mb-3 pb-2.5 border-b border-slate-750">
                    <button
                      onClick={() => toggleSteps(message.id)}
                      className="flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-indigo-300 transition"
                    >
                      <BrainCircuit className="w-3.5 h-3.5 text-indigo-400" />
                      <span>Agent Orchestration Steps ({message.steps_executed?.length})</span>
                      {isStepsOpen ? (
                        <ChevronUp className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5" />
                      )}
                    </button>

                    {isStepsOpen && (
                      <div className="mt-2.5 p-2.5 bg-slate-900/90 rounded-xl border border-slate-800 space-y-1.5 animate-in fade-in duration-150">
                        {message.steps_executed?.map((step, idx) => (
                          <div
                            key={idx}
                            className="flex items-center gap-2 text-[11px] font-mono text-slate-300"
                          >
                            <span className="w-4 h-4 flex items-center justify-center rounded-full bg-slate-800 text-indigo-400 text-[9px] font-bold">
                              {idx + 1}
                            </span>
                            <span className="text-slate-400">Node:</span>
                            <span className="text-indigo-300 font-semibold">{step}</span>
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 ml-auto" />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Conflict Notice callout if detected */}
                {!isUser && message.conflict_notices && message.conflict_notices.length > 0 && (
                  <ConflictNotice notices={message.conflict_notices} />
                )}

                {/* Primary message text */}
                <div className="text-sm">
                  {renderContentWithCitations(message.content, message.citations)}
                </div>

                {/* Streaming indicator */}
                {message.isStreaming && (
                  <div className="flex items-center gap-1.5 mt-2 text-xs text-indigo-400 animate-pulse">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Reasoning and synthesizing verified citations...</span>
                  </div>
                )}

                {/* Tool call approval modal if action requires confirmation */}
                {!isUser && message.approval_required && message.tool_request && (
                  <ApprovalModal
                    toolRequest={message.tool_request}
                    riskLevel={message.tool_risk_level}
                    onApprove={async () => {
                      if (onApproveTool) await onApproveTool(message);
                    }}
                    onReject={async () => {
                      if (onRejectTool) await onRejectTool(message);
                    }}
                  />
                )}

                {/* Tool result status tag */}
                {!isUser && message.tool_result && (
                  <div className="mt-2.5 pt-2 border-t border-slate-750 flex items-center gap-2 text-xs text-slate-400">
                    <Cpu className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Action {message.tool_result.tool_name || message.tool_result.tool || "tool"} execution:</span>
                    <span
                      className={`font-semibold ${
                        message.tool_result.success ? "text-emerald-400" : "text-amber-400"
                      }`}
                    >
                      {message.tool_result.status || (message.tool_result.success ? "Success" : "Pending")}
                    </span>
                  </div>
                )}
              </div>

              {/* Timestamp & Confidence Metadata */}
              <div className="flex items-center gap-2 mt-1 px-1 text-[11px] text-slate-500">
                <Clock className="w-3 h-3" />
                <span>
                  {new Date(message.timestamp).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
                {!isUser && message.confidence !== undefined && (
                  <>
                    <span>•</span>
                    <span className="text-indigo-400/80 font-mono">
                      Confidence: {(message.confidence * 100).toFixed(0)}%
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

