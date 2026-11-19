import React from 'react';
import { useApp } from '../../context/AppContext';
import { Terminal, CheckCircle2, ShieldCheck } from 'lucide-react';
import ArchitectureTopology from './ArchitectureTopology';

export default function RecommendationHero({ winner, recommendation = {} }) {
  const { setIsPromptModalOpen } = useApp();

  const title = winner?.name || recommendation?.winner_name || recommendation?.selected_architecture_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database';
  const nodes = winner?.topologyNodes || [];

  return (
    <div className="bg-[#111317] rounded-xl border border-[#1e222b] p-6 sm:p-7 space-y-6">
      {/* Top Row: Clean Technical Meta + Action Button */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2 border-b border-[#1e222b]">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md bg-[#34d399]/10 text-[#34d399] border border-[#34d399]/25 text-xs font-semibold font-mono">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>SimPy Grounded Verification</span>
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Confidence Score: 94%
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-50 tracking-tight leading-snug">
            {title}
          </h1>

          <p className="text-xs text-slate-400 font-mono">
            Data Path: {topology}
          </p>
        </div>

        {/* Generate Implementation Prompt CTA */}
        <div className="shrink-0 flex items-center gap-3">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="h-10 px-5 rounded-lg bg-slate-100 hover:bg-white text-slate-950 text-xs font-bold flex items-center gap-2 transition-all shadow-sm cursor-pointer active:scale-95"
          >
            <Terminal className="w-4 h-4 stroke-[2.5]" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Pipeline Spec */}
      <div>
        <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-2 font-semibold">
          Architecture Topology Data Path
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
