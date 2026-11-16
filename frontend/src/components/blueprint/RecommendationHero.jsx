import React from 'react';
import { useApp } from '../../context/AppContext';
import { Sparkles, Terminal } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  return (
    <div className="rounded-2xl bg-gradient-to-b from-[#0f172a] to-[#0c101a] border border-emerald-500/40 p-6 lg:p-7 shadow-lg shadow-black/40 space-y-5">
      {/* Header Row: Badges, Title, and Primary CTA */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge badge-emerald text-xs font-semibold py-0.5 px-2.5 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Recommended Architecture</span>
            </span>
            <span className="badge badge-zinc text-xs text-slate-300 font-mono">
              Calibrated Empirical Baseline
            </span>
          </div>

          <h1 className="text-xl lg:text-2xl font-bold text-white tracking-tight">
            {title}
          </h1>

          <p className="text-xs text-slate-400 font-mono">
            Pipeline: {topology}
          </p>
        </div>

        {/* Generate Implementation Prompt Action Button */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="btn btn-primary text-xs py-2 px-4 flex items-center gap-2 shadow-md shadow-indigo-950/40"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Diagram Section */}
      <div className="pt-2 border-t border-white/[0.06]">
        <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">
          System Topology Flow
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
