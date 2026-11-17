import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  Award,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Clock,
  DollarSign,
  Compass,
  Play,
  Scale,
  ShieldCheck,
} from 'lucide-react';

export default function RecommendationView() {
  const { response, loading, handleRunWorkflow } = useApp();
  const sectionD = response?.section_d_recommendation;

  if (loading) {
    return (
      <div className="glass-panel p-8 text-center py-16 space-y-4">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <div className="text-base font-semibold text-slate-200">
          Synthesizing Architecture Recommendation & Trade-Offs...
        </div>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Executing two-stage feasibility filtering, computing multi-objective utility scores, and compiling explicit conditions for change.
        </p>
      </div>
    );
  }

  if (!sectionD) {
    return (
      <div className="glass-panel p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="badge badge-indigo text-xs">Section D</span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Structured Recommendation & Trade-Offs
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Two-stage decision engine: hard constraint feasibility filtering followed by multi-objective trade-off scoring.
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            className="btn btn-primary text-xs px-4 py-2"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Generate Recommendation</span>
          </button>
        </div>

        {/* Two-Stage Decision Process Explainer Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
              <ShieldCheck className="w-4 h-4" /> Stage 1: Feasibility Filtering
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every candidate is verified against hard non-negotiable SLAs:
            </p>
            <ul className="text-xs text-slate-400 space-y-1 list-disc pl-4">
              <li><strong className="text-slate-300">p95 Latency Threshold:</strong> Hard cut-off if simulated p95 exceeds user SLA</li>
              <li><strong className="text-slate-300">Throughput Target:</strong> Rejects configurations unable to sustain offered QPS</li>
              <li><strong className="text-slate-300">Budget Cap:</strong> Rejects configurations exceeding monthly hosting spend</li>
            </ul>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2.5">
            <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs">
              <Scale className="w-4 h-4" /> Stage 2: Multi-Objective Trade-Offs
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Surviving feasible architectures are ranked using multi-objective preference scoring:
            </p>
            <ul className="text-xs text-slate-400 space-y-1 list-disc pl-4">
              <li><strong className="text-slate-300">Why It Won:</strong> Explicit rationale for selecting the highest-utility architecture</li>
              <li><strong className="text-slate-300">Why Alternatives Lost:</strong> Clear technical disqualification reasons</li>
              <li><strong className="text-slate-300">Conditions for Change:</strong> Explicit breaking-point thresholds where recommendation flips</li>
            </ul>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-emerald-400" />
            <span>Select a scenario in Section A and run the investigation to see the live recommendation.</span>
          </div>
          <span className="font-mono text-slate-500">Deterministic & Auditable</span>
        </div>
      </div>
    );
  }

  const winner = sectionD.winner || {};
  const winnerMetrics = winner.metrics || {};
  const whyWon = sectionD.why_it_won || [];
  const whyLost = sectionD.why_alternatives_lost || [];
  const tradeOffs = sectionD.trade_offs_and_risks || [];
  const conditionsForChange = sectionD.conditions_for_change || [];

  return (
    <div className="glass-panel p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="badge badge-indigo text-xs">Section D</span>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Structured Recommendation & Trade-Offs
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Auditable recommendation synthesis backed by SimPy simulations and two-stage feasibility filtering.
          </p>
        </div>
        <div>
          <span className="badge badge-emerald">
            <Award className="w-3.5 h-3.5" /> Optimal Fit Identified
          </span>
        </div>
      </div>

      {/* Winner Hero Card */}
      <div className="winner-card p-6 sm:p-7 rounded-2xl space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="badge badge-emerald text-xs font-bold tracking-wider">
              #1 Ranked Architecture
            </span>
            <h3 className="text-2xl sm:text-3xl font-black text-white mt-1.5 tracking-tight">
              {winner.name || winner.id || 'Selected Architecture'}
            </h3>
            <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl font-mono">
              {winner.topology_summary || winner.components?.join(' → ') || 'Topology generated by ORBIT engine'}
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-center">
              <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-center gap-1">
                <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency
              </div>
              <div className="text-lg font-bold text-white font-mono mt-0.5">
                {winnerMetrics.p95_latency_ms != null ? `${winnerMetrics.p95_latency_ms.toFixed(1)}ms` : '—'}
              </div>
            </div>

            <div className="px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-center">
              <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-center gap-1">
                <TrendingUp className="w-3 h-3 text-emerald-400" /> QPS
              </div>
              <div className="text-lg font-bold text-white font-mono mt-0.5">
                {winnerMetrics.throughput_qps != null ? `${Math.round(winnerMetrics.throughput_qps)}` : '—'}
              </div>
            </div>

            <div className="px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-center">
              <div className="text-[10px] text-slate-400 uppercase font-bold flex items-center justify-center gap-1">
                <DollarSign className="w-3 h-3 text-amber-400" /> Cost
              </div>
              <div className="text-lg font-bold text-white font-mono mt-0.5">
                {winner.estimated_cost_monthly != null ? `$${Math.round(winner.estimated_cost_monthly)}` : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Why it Won */}
        <div className="pt-4 border-t border-emerald-500/20">
          <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <CheckCircle className="w-4 h-4" /> Key Rationale (Why It Won)
          </h4>
          <ul className="space-y-2 text-xs sm:text-sm text-slate-200">
            {whyWon.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2.5">
                <ArrowRight className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Why Alternatives Lost & Trade-Offs Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Why Alternatives Lost */}
        <div className="p-4 sm:p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
          <h4 className="text-xs font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
            <XCircle className="w-3.5 h-3.5" /> Why Alternatives Lost
          </h4>
          <div className="space-y-2.5">
            {whyLost.length > 0 ? (
              whyLost.map((alt, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
                  <div className="text-xs font-bold text-slate-200">{alt.architecture_name || alt.id}</div>
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">{alt.reason}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-500 italic">No alternative architectures rejected.</p>
            )}
          </div>
        </div>

        {/* Trade-Offs & Operational Risks */}
        <div className="p-4 sm:p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
          <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Active Trade-Offs & Risks
          </h4>
          <ul className="space-y-2 text-xs sm:text-sm text-slate-300">
            {tradeOffs.length > 0 ? (
              tradeOffs.map((risk, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-2"></span>
                  <span>{risk}</span>
                </li>
              ))
            ) : (
              <li className="text-slate-500 italic">No critical risks flagged.</li>
            )}
          </ul>
        </div>
      </div>

      {/* Conditions for Change / Breaking Points */}
      <div className="p-4 sm:p-5 rounded-xl bg-slate-900/40 border border-slate-800 space-y-2.5">
        <h4 className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
          <Compass className="w-3.5 h-3.5 text-indigo-400" />
          Conditions for Change (Breaking Points)
        </h4>
        <p className="text-xs text-slate-400">
          The recommendation is valid for the current operating regime. It would dynamically switch if:
        </p>
        <ul className="space-y-2 text-xs sm:text-sm text-slate-300 pt-1">
          {conditionsForChange.length > 0 ? (
            conditionsForChange.map((cond, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0 mt-2"></span>
                <span>{cond}</span>
              </li>
            ))
          ) : (
            <li className="text-slate-500 italic">Operating regime within stable envelope.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
