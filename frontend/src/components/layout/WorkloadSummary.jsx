import React from 'react';
import { useApp } from '../../context/AppContext';
import { Sliders, Play, AlertTriangle, ArrowRight } from 'lucide-react';
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
    <div className="border-b border-white/[0.08] bg-[#090d16] px-5 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
      {/* Left: Workload Title & Profile */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <span className="text-slate-400 font-medium">Your Workload:</span>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100">
            {currentPreset?.title?.replace(/Scenario \d+: /, '') || 'Custom API'}
          </span>
          <span className="badge badge-zinc text-[10px] py-0 px-2 font-mono">
            {readPct >= 70 ? 'Read-Heavy' : writePct >= 60 ? 'Write-Heavy' : 'Balanced'}
          </span>
        </div>

        {/* Separator */}
        <span className="text-slate-600 hidden md:inline">•</span>

        {/* Inline KPI Chips */}
        <div className="hidden lg:flex items-center gap-3 text-slate-300 font-mono text-[11px]">
          <span>Traffic: <strong className="text-slate-100">{qps} RPS</strong></span>
          <span className="text-slate-600">|</span>
          <span>Max Latency: <strong className="text-slate-100">&lt; {slaMs} ms</strong></span>
          <span className="text-slate-600">|</span>
          <span>Traffic Mix: <strong className="text-slate-100">{readPct}% R / {writePct}% W</strong></span>
          <span className="text-slate-600">|</span>
          <span>Budget: <strong className="text-slate-100">{budgetUsd ? `< $${budgetUsd}/mo` : 'Unconstrained'}</strong></span>
        </div>
      </div>

      {/* Right: Actions & Stale Warning */}
      <div className="flex items-center gap-2.5">
        {/* Stale Warning Indicator */}
        {isStale && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span>Workload modified (results stale)</span>
          </div>
        )}

        {/* Edit Workload Button */}
        <button
          type="button"
          onClick={() => setIsWorkloadDrawerOpen(true)}
          className="btn btn-secondary text-xs py-1 px-2.5 flex items-center gap-1.5"
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
          className={`btn ${isStale ? 'btn-primary' : 'btn-secondary'} text-xs py-1 px-3 flex items-center gap-1.5`}
        >
          {loading ? (
            <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5 fill-current" />
          )}
          <span>{loading ? 'Simulating...' : isStale ? 'Re-run Simulation' : 'Run Simulation'}</span>
        </button>
      </div>
    </div>
  );
}
