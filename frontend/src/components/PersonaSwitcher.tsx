"use client";

import React, { useState } from "react";
import { Persona } from "@/lib/types";
import { PERSONAS } from "@/lib/personas";
import { ShieldCheck, UserCheck, ChevronDown, Lock } from "lucide-react";

interface PersonaSwitcherProps {
  activePersona: Persona;
  onSelectPersona: (persona: Persona) => void;
}

export const PersonaSwitcher: React.FC<PersonaSwitcherProps> = ({
  activePersona,
  onSelectPersona,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const getClearanceBadge = (clearance: string) => {
    switch (clearance) {
      case "RESTRICTED":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      case "CONFIDENTIAL":
        return "bg-amber-500/20 text-amber-400 border-amber-500/30";
      case "INTERNAL":
        return "bg-blue-500/20 text-blue-400 border-blue-500/30";
      default:
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-3 py-2 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-xl transition shadow-sm text-left"
        title="Switch user identity and clearance"
      >
        <span className="text-2xl">{activePersona.avatar}</span>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-100">{activePersona.name}</span>
            <span
              className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${getClearanceBadge(
                activePersona.clearance
              )}`}
            >
              {activePersona.clearance}
            </span>
          </div>
          <span className="text-xs text-slate-400">{activePersona.role}</span>
        </div>
        <ChevronDown className="w-4 h-4 text-slate-400 ml-2" />
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-80 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl p-2 z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="px-3 py-2 border-b border-slate-800 mb-1">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
              Permission-Aware Personas
            </p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Select a persona to test vector-level ACL filtering and isolation in real time.
            </p>
          </div>

          <div className="space-y-1">
            {PERSONAS.map((persona) => {
              const isSelected = persona.id === activePersona.id;
              return (
                <button
                  key={persona.id}
                  onClick={() => {
                    onSelectPersona(persona);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-start gap-3 p-2.5 rounded-xl text-left transition ${
                    isSelected
                      ? "bg-indigo-600/20 border border-indigo-500/40 text-white"
                      : "hover:bg-slate-800/60 text-slate-300"
                  }`}
                >
                  <span className="text-2xl mt-0.5">{persona.avatar}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-sm font-medium text-slate-200 truncate">
                        {persona.name}
                      </span>
                      <span
                        className={`text-[9px] uppercase font-bold px-1.5 py-0.2 rounded border ${getClearanceBadge(
                          persona.clearance
                        )}`}
                      >
                        {persona.clearance}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">{persona.role}</p>
                    <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {persona.description}
                    </p>
                    <div className="flex items-center gap-1 mt-1.5 text-[10px] text-slate-500">
                      <Lock className="w-3 h-3 text-slate-400" />
                      <span>Groups: {persona.groups.join(", ")}</span>
                    </div>
                  </div>
                  {isSelected && <UserCheck className="w-4 h-4 text-indigo-400 mt-1" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

