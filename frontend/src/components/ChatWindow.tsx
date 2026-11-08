"use client";

import React, { useState, useEffect } from "react";
import { PersonaSwitcher } from "./PersonaSwitcher";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { CitationsPanel } from "./CitationsPanel";
import { ChatMessage, Citation, Persona } from "@/lib/types";
import { getActivePersona, setActivePersona } from "@/lib/personas";
import { sendChatMessage, submitToolApproval } from "@/lib/api";
import { Trash2, ShieldAlert, Sparkles, PanelRightClose, PanelRightOpen } from "lucide-react";

export const ChatWindow: React.FC = () => {
  const [persona, setPersona] = useState<Persona>(getActivePersona());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);
  const [showCitationsPanel, setShowCitationsPanel] = useState(true);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);

  // Initialize with greeting
  useEffect(() => {
    const initialGreeting: ChatMessage = {
      id: "msg-welcome",
      role: "assistant",
      content: `Hello ${persona.name.split(" ")[0]}! I am the Enterprise Knowledge Agent. I answer questions over company documents (Google Drive, Notion, Confluence, Slack, Jira, PDFs) and execute authorized tools with strict permission isolation.\n\nAsk any question or pick a suggestion below to begin.`,
      timestamp: new Date().toISOString(),
    };
    setMessages([initialGreeting]);
    setThreadId(`thread-${Date.now()}`);
  }, [persona]);

  const handleSelectPersona = (newPersona: Persona) => {
    setActivePersona(newPersona);
    setPersona(newPersona);
    setActiveCitations([]);
    setSelectedCitationIndex(null);
  };

  const handleSendMessage = async (query: string) => {
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: query,
      timestamp: new Date().toISOString(),
    };

    const assistantPlaceholderId = `asst-${Date.now()}`;
    const initialAssistantMsg: ChatMessage = {
      id: assistantPlaceholderId,
      role: "assistant",
      content: "",
      steps_executed: ["understand"],
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    setIsLoading(true);

    try {
      await sendChatMessage(
        query,
        persona,
        threadId,
        (partialUpdate) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantPlaceholderId
                ? { ...m, ...partialUpdate, id: assistantPlaceholderId }
                : m
            )
          );

          if (partialUpdate.citations && partialUpdate.citations.length > 0) {
            setActiveCitations(partialUpdate.citations);
          }
        }
      );
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Failed to execute query";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantPlaceholderId
            ? {
                ...m,
                content: `⚠️ Error executing query: ${errorMsg}. Please verify backend connection.`,
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleApproveTool = async (message: ChatMessage) => {
    if (!message.tool_request) return;
    setIsLoading(true);

    try {
      await submitToolApproval(
        message.thread_id || threadId || `thread-${Date.now()}`,
        true,
        message.content || "Execute approved tool",
        persona,
        (partialUpdate) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === message.id ? { ...m, ...partialUpdate, approval_required: false } : m
            )
          );
        }
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleRejectTool = async (message: ChatMessage) => {
    setIsLoading(true);
    try {
      await submitToolApproval(
        message.thread_id || threadId || `thread-${Date.now()}`,
        false,
        message.content || "Reject tool action",
        persona,
        (partialUpdate) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === message.id ? { ...m, ...partialUpdate, approval_required: false } : m
            )
          );
        }
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: `Conversation reset. Ready for your next query as ${persona.name}.`,
        timestamp: new Date().toISOString(),
      },
    ]);
    setActiveCitations([]);
    setSelectedCitationIndex(null);
    setThreadId(`thread-${Date.now()}`);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-7xl mx-auto px-4 py-3 gap-3">
      {/* Top Controls Bar */}
      <div className="flex items-center justify-between bg-slate-900/90 border border-slate-800 p-2.5 rounded-2xl shadow-sm backdrop-blur-md">
        <div className="flex items-center gap-3">
          <PersonaSwitcher activePersona={persona} onSelectPersona={handleSelectPersona} />

          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 pl-2 border-l border-slate-800">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-mono text-[11px] text-slate-300">Qdrant ACL Pre-Filtering Active</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCitationsPanel(!showCitationsPanel)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-xl transition"
            title="Toggle Citations Panel"
          >
            {showCitationsPanel ? (
              <>
                <PanelRightClose className="w-3.5 h-3.5 text-indigo-400" />
                <span className="hidden sm:inline">Hide Citations</span>
              </>
            ) : (
              <>
                <PanelRightOpen className="w-3.5 h-3.5 text-indigo-400" />
                <span className="hidden sm:inline">Show Citations ({activeCitations.length})</span>
              </>
            )}
          </button>

          <button
            onClick={handleClearChat}
            className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-xl transition"
            title="Clear conversation"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Chat & Citations Layout */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Messages Stream Container */}
        <div className="flex-1 flex flex-col bg-slate-900/60 border border-slate-800 rounded-2xl shadow-sm overflow-hidden backdrop-blur-sm">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <MessageList
              messages={messages}
              onSelectCitation={(citation) => {
                const idx = activeCitations.findIndex((c) => c.doc_id === citation.doc_id);
                setSelectedCitationIndex(idx >= 0 ? idx : null);
                setShowCitationsPanel(true);
              }}
              onApproveTool={handleApproveTool}
              onRejectTool={handleRejectTool}
            />
          </div>

          {/* Bottom Chat Input */}
          <div className="p-3 border-t border-slate-800 bg-slate-900/80">
            <MessageInput onSendMessage={handleSendMessage} isLoading={isLoading} />
          </div>
        </div>

        {/* Right Collapsible Citations Panel */}
        {showCitationsPanel && (
          <div className="w-80 hidden lg:flex flex-col bg-slate-900/80 border border-slate-800 rounded-2xl shadow-sm overflow-hidden animate-in slide-in-from-right duration-150">
            <div className="flex-1 overflow-y-auto">
              <CitationsPanel
                citations={activeCitations}
                activeCitationIndex={selectedCitationIndex}
                onSelectCitation={(idx) => setSelectedCitationIndex(idx)}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

