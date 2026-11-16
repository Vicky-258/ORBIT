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
    <div className="border-b border-slate-200 bg-slate-50/80 backdrop-blur-xs px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 text-xs shrink-0">
      {/* Left: Workload Title & Profile */}
      <div className="flex items-center gap-3.5 flex-wrap">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-medium text-slate-500">
            Active Workload:
          </span>
          <span className="font-bold text-slate-900 text-sm tracking-tight">
            {currentPreset?.title?.replace(/Scenario \d+: /, '') || 'Custom Application'}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-200/80 text-slate-700 border border-slate-300/60">
            {readPct >= 70 ? 'Read-Heavy' : writePct >= 60 ? 'Write-Heavy' : 'Balanced'}
          </span>
        </div>

        {/* Separator */}
        <span className="text-slate-300 hidden md:inline">|</span>

        {/* Inline Requirement Chips */}
        <div className="hidden lg:flex items-center gap-2 font-sans text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-2xs font-medium">
            <Activity className="w-3.5 h-3.5 text-slate-500" />
            <span>{qps} RPS</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-2xs font-medium">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>&lt; {slaMs} ms p95</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-2xs font-medium">
            <ArrowRightLeft className="w-3.5 h-3.5 text-slate-500" />
            <span>{readPct}% Read / {writePct}% Write</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white border border-slate-200 text-slate-700 shadow-2xs font-medium">
            <DollarSign className="w-3.5 h-3.5 text-slate-500" />
            <span>{budgetUsd ? `< $${budgetUsd}/mo` : 'Unconstrained'}</span>
          </div>
        </div>
      </div>

      {/* Right: Actions & Stale Warning */}
      <div className="flex items-center gap-2.5">
        {/* Stale Warning Indicator */}
        {isStale && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium shadow-2xs">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Inputs modified (results stale)</span>
          </div>
        )}

        {/* Edit Workload Button */}
        <button
          type="button"
          onClick={() => setIsWorkloadDrawerOpen(true)}
          className="btn-saas-secondary text-xs py-1.5 px-3 rounded-md flex items-center gap-1.5 cursor-pointer font-medium"
          title="Open workload editor drawer"
        >
          <Sliders className="w-3.5 h-3.5 text-slate-500" />
          <span>Customize Parameters</span>
        </button>

        {/* Run / Re-run Simulation Button */}
        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading}
          className={`btn-saas-primary text-xs py-1.5 px-3.5 rounded-md flex items-center gap-1.5 cursor-pointer font-medium ${
            isStale ? 'ring-2 ring-slate-400' : ''
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
