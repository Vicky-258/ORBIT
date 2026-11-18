import React from 'react';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, Terminal } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || recommendation?.selected_architecture_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  const isConclusive = recommendation?.is_conclusive !== false && Boolean(winner && winner.name !== 'INCONCLUSIVE');

  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-6 sm:p-8 space-y-7 shadow-xl">
      {/* Top Row: Clean single-badge status + Main Title + Primary CTA */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 pb-1">
        <div className="space-y-2">
          {/* Subtle status tag */}
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Recommended Architecture</span>
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              SimPy Discrete-Event Grounded
            </span>
          </div>

          {/* Prominent Hero Title */}
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight leading-snug">
            {title}
          </h1>

          <p className="text-xs text-zinc-400 font-mono">
            {topology}
          </p>
        </div>

        {/* Generate Implementation Prompt CTA */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="h-10 px-5 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-bold flex items-center gap-2 transition-all shadow-sm cursor-pointer active:scale-95"
          >
            <Terminal className="w-4 h-4 stroke-[2.5]" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Connected System Topology Flow */}
      <div className="pt-2">
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
