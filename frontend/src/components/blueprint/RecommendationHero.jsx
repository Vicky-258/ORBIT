import React from 'react';
import { useApp } from '../../context/AppContext';
import { CheckCircle2, AlertCircle, HelpCircle, Terminal, Cpu } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || recommendation?.selected_architecture_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  // Truth in evaluation status
  const isConclusive = recommendation?.is_conclusive !== false && Boolean(winner && winner.name !== 'INCONCLUSIVE');
  const feasibilityStatus = winner?.feasibility_status || recommendation?.feasibility_status || (isConclusive ? 'FEASIBLE' : 'UNCERTAIN');

  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-6 sm:p-7 relative overflow-hidden shadow-xl">
      {/* Header Row: Badges, Title, and Primary CTA */}
      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            {isConclusive ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Recommended Architecture</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-semibold">
                <HelpCircle className="w-3.5 h-3.5" />
                <span>Evaluation Pending More Context</span>
              </span>
            )}

            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-800 text-zinc-300 border border-zinc-700 text-xs font-medium">
              <Cpu className="w-3 h-3 text-zinc-400" />
              <span>SimPy Discrete-Event Grounded</span>
            </span>

            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.06] text-[11px] font-mono">
              Status: {feasibilityStatus}
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-tight">
            {title}
          </h1>

          <p className="text-xs text-zinc-400 flex items-center gap-2 leading-relaxed">
            <span className="text-zinc-500 font-medium">Pipeline:</span>
            <span className="text-zinc-200 font-mono font-medium">{topology}</span>
          </p>
        </div>

        {/* Generate Implementation Prompt Action Button */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="h-9 px-4 rounded-xl bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-semibold flex items-center gap-2 transition-all shadow-sm cursor-pointer active:scale-95"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Diagram Section */}
      <div className="relative z-10 pt-6 mt-6 border-t border-white/[0.06]">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-200 tracking-tight">
              System Topology Flow
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          </div>
          <span className="text-[11px] text-zinc-400 font-mono">
            Simulated Component Flow
          </span>
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
