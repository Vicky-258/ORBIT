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
    <div className="saas-hero p-6 sm:p-7 relative overflow-hidden">
      {/* Header Row: Badges, Title, and Primary CTA */}
      <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-5">
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge-saas badge-emerald text-xs font-semibold flex items-center gap-1.5 shadow-2xs">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Recommended Architecture</span>
            </span>

            <span className="badge-saas badge-zinc text-xs font-medium">
              Empirical Baseline Verified
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight leading-tight">
            {title}
          </h1>

          <p className="text-xs text-slate-600 flex items-center gap-2 leading-relaxed">
            <span className="text-slate-400 font-medium">Pipeline:</span>
            <span className="text-slate-700 font-medium">{topology}</span>
          </p>
        </div>

        {/* Generate Implementation Prompt Action Button */}
        <div className="shrink-0">
          <button
            type="button"
            onClick={() => setIsPromptModalOpen(true)}
            className="btn-saas-primary text-xs py-2 px-4 rounded-lg flex items-center gap-2 cursor-pointer font-medium shadow-xs"
          >
            <Terminal className="w-3.5 h-3.5" />
            <span>Generate Implementation Prompt</span>
          </button>
        </div>
      </div>

      {/* Topology Diagram Section */}
      <div className="relative z-10 pt-5 mt-5 border-t border-slate-200">
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700 tracking-tight">
              System Topology Flow
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          </div>
          <span className="text-xs text-slate-500 font-normal">
            Component Data Flow
          </span>
        </div>
        <ArchitectureTopology nodes={nodes} topologyStr={topology} />
      </div>
    </div>
  );
}
