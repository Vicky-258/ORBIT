import React from 'react';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, Terminal } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  return (
    <div className="bg-[#111622] rounded-xl border border-white/[0.08] p-6 sm:p-7 relative overflow-hidden shadow-lg shadow-black/20">
      {/* Header Row: Badges, Title, and Primary CTA */}
      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge-saas bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Recommended Architecture</span>
            </span>

            <span className="badge-saas bg-white/[0.04] text-slate-400 border border-white/[0.08] text-xs font-medium">
              Empirical Baseline Verified
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-tight">
            {title}
          </h1>

          <p className="text-xs text-slate-400 flex items-center gap-2 leading-relaxed">
            <span className="text-slate-500 font-medium">Pipeline:</span>
            <span className="text-slate-300 font-medium">{topology}</span>
          </p>
        </div>

        {/* Generate Implementation Prompt Action Button */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="btn btn-primary text-xs py-2 px-4 rounded-lg flex items-center gap-2 cursor-pointer font-medium"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Diagram Section */}
      <div className="relative z-10 pt-5 mt-5 border-t border-white/[0.06]">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-300 tracking-tight">
              System Topology Flow
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs text-slate-500 font-mono">
            Component Data Flow
          </span>
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
