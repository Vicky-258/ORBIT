import React from 'react';
import { useApp } from '../../context/AppContext';
import { Sliders, Play, AlertTriangle, Activity, Clock, DollarSign, ArrowRightLeft } from 'lucide-react';
import { CANONICAL_PRESETS } from '../../constants/presets';

export default function WorkloadSummary() {
  const {
    workloadInputs,
    response,
    isStale,
    setIsWorkloadDrawerOpen,
    handleRunWorkflow,
    loading,
    selectedPresetId,
  } = useApp();

  const decisionWorkload = response?.decision_result?.workload || response?.workload || {};
  const currentPreset = CANONICAL_PRESETS.find((p) => p.id === selectedPresetId);

  const qps = workloadInputs.qps || decisionWorkload.request_rate_rps || 500;
  const slaMs = workloadInputs.p95_sla_ms || decisionWorkload.p95_latency_target_ms || 100;
  const readPct = Math.round((workloadInputs.read_ratio ?? 0.85) * 100);
  const writePct = Math.round((workloadInputs.write_ratio ?? 0.15) * 100);
  const budgetUsd = workloadInputs.budget_usd || decisionWorkload.max_monthly_budget_usd;

  return (
    <div className="border-b border-white/[0.08] bg-[#0c1220]/80 backdrop-blur-lg px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs shrink-0 shadow-sm relative z-10">
      {/* Left: Workload Title & Profile */}
      <div className="flex items-center gap-3.5 flex-wrap">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.8)]" />
            <span className="text-xs font-medium text-slate-400">
              Workload Profile:
            </span>
          </div>
          <span className="font-bold text-slate-100 text-sm tracking-tight">
            {currentPreset?.title?.replace(/Scenario \d+: /, '') || 'Custom Application'}
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/25 shadow-xs">
            {readPct >= 70 ? 'Read-Heavy' : writePct >= 60 ? 'Write-Heavy' : 'Balanced'}
          </span>
        </div>

        {/* Separator */}
        <span className="text-white/10 hidden md:inline">|</span>

        {/* Inline SaaS Requirement Chips */}
        <div className="hidden lg:flex items-center gap-2 font-sans text-xs">
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-white/[0.08] text-slate-200 shadow-xs font-medium">
            <Activity className="w-3.5 h-3.5 text-indigo-400" />
            <span>{qps} RPS</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-white/[0.08] text-slate-200 shadow-xs font-medium">
            <Clock className="w-3.5 h-3.5 text-emerald-400" />
            <span>&lt; {slaMs} ms p95</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-white/[0.08] text-slate-200 shadow-xs font-medium">
            <ArrowRightLeft className="w-3.5 h-3.5 text-cyan-400" />
            <span>{readPct}% Read / {writePct}% Write</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 border border-white/[0.08] text-slate-200 shadow-xs font-medium">
            <DollarSign className="w-3.5 h-3.5 text-amber-400" />
            <span>{budgetUsd ? `< $${budgetUsd}/mo` : 'Unconstrained'}</span>
          </div>
        </div>
      </div>

      {/* Right: Actions & Stale Warning */}
      <div className="flex items-center gap-2.5">
        {/* Stale Warning Indicator */}
        {isStale && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] animate-pulse font-medium">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>Inputs modified (results stale)</span>
          </div>
        )}

        {/* Edit Workload Button */}
        <button
          type="button"
          onClick={() => setIsWorkloadDrawerOpen(true)}
          className="btn-saas-secondary text-xs py-1.5 px-3 rounded-lg flex items-center gap-1.5 cursor-pointer"
          title="Open workload editor drawer"
        >
          <Sliders className="w-3.5 h-3.5 text-slate-400" />
          <span>Edit Workload</span>
        </button>

        {/* Run / Re-run Simulation Button */}
        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading}
          className={`btn-saas-primary text-xs py-1.5 px-3.5 rounded-lg flex items-center gap-1.5 cursor-pointer ${
            isStale ? 'ring-2 ring-indigo-400/40' : ''
          }`}
        >
          {loading ? (
            <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Play className="w-3 h-3 fill-current" />
          )}
          <span>{loading ? 'Simulating...' : isStale ? 'Re-run Simulation' : 'Run Simulation'}</span>
        </button>
      </div>
    </div>
  );
}
