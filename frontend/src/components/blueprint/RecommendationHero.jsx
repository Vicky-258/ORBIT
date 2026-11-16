import React from 'react';
import { useApp } from '../../context/AppContext';
import { Sparkles, Terminal, CheckCircle2 } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  return (
    <div className="saas-hero p-6 sm:p-7 shadow-2xl relative overflow-hidden">
      {/* Background Accent Mesh */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

      {/* Header Row: Badges, Title, and Primary CTA */}
      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="badge-saas bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5 shadow-sm">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
              <span className="font-semibold text-xs">Recommended Blueprint</span>
            </span>

            <span className="badge-saas bg-white/[0.05] text-slate-300 border border-white/[0.1] text-xs">
              Empirical Baseline Verified
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-tight">
            {title}
          </h1>

          <p className="text-xs text-slate-300 flex items-center gap-2 leading-relaxed">
            <span className="text-slate-400 font-medium">Pipeline:</span>
            <span className="text-slate-200 font-medium">{topology}</span>
          </p>
        </div>

        {/* Generate Implementation Prompt Action Button */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="btn-saas-primary text-xs py-2.5 px-4 rounded-xl flex items-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/50"
          >
            <Terminal className="w-4 h-4 text-indigo-200" />
            <span className="font-semibold">Generate AI Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Diagram Section */}
      <div className="relative z-10 pt-5 mt-5 border-t border-white/[0.08]">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-300 tracking-tight">
              System Topology Flow
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <span className="text-xs text-slate-400 font-medium">
            Interactive Architecture Canvas
          </span>
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
