"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Sparkles, Shield, AlertCircle, Cpu, Languages } from "lucide-react";

interface MessageInputProps {
  onSendMessage: (query: string) => void;
  isLoading: boolean;
}

const SAMPLE_PROMPTS = [
  {
    label: "PTO Policy",
    query: "How many days of annual paid time off (PTO) do employees receive at Nimbus?",
    icon: Sparkles,
  },
  {
    label: "Salary Bands (ACL Test)",
    query: "What are the engineering salary bands and compensation ranges for L3 to L6?",
    icon: Shield,
  },
  {
    label: "Travel Per Diem (Conflict Test)",
    query: "What is the maximum daily meal per diem reimbursement for business travel?",
    icon: AlertCircle,
  },
  {
    label: "Jira Action (HITL Tool)",
    query: "Create a Jira ticket to patch the OpenSSL vulnerability in production redis cluster",
    icon: Cpu,
  },
  {
    label: "Hindi Query",
    query: "कर्मचारियों के लिए वार्षिक सवेतन अवकाश (PTO) की नीति क्या है?",
    icon: Languages,
  },
];

export const MessageInput: React.FC<MessageInputProps> = ({ onSendMessage, isLoading }) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSendMessage(text.trim());
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  return (
    <div className="space-y-3">
      {/* Quick Suggestion Chips */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
        <span className="text-[11px] text-slate-500 font-semibold uppercase tracking-wider shrink-0 mr-1">
          Try Query:
        </span>
        {SAMPLE_PROMPTS.map((prompt, idx) => {
          const Icon = prompt.icon;
          return (
            <button
              key={idx}
              onClick={() => onSendMessage(prompt.query)}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/60 text-slate-300 hover:text-white transition text-xs whitespace-nowrap shrink-0 disabled:opacity-50"
            >
              <Icon className="w-3 h-3 text-indigo-400" />
              <span>{prompt.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Input Bar */}
      <form onSubmit={handleSubmit} className="relative flex items-end bg-slate-850 border border-slate-700 rounded-2xl p-2 shadow-lg focus-within:border-indigo-500/80 focus-within:ring-2 focus-within:ring-indigo-500/20 transition">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask enterprise knowledge, search policies, or run approved tool actions... (Enter to send, Shift+Enter for newline)"
          rows={1}
          disabled={isLoading}
          className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 resize-none outline-none px-3 py-1.5 max-h-32 disabled:opacity-50"
        />

        <button
          type="submit"
          disabled={!text.trim() || isLoading}
          className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:hover:bg-indigo-600 transition shrink-0 ml-2 shadow-sm"
          title="Send query"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};

