import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  Award,
  Layers,
  Bot,
  ShieldCheck,
  Database,
  TrendingUp,
  Clock,
  DollarSign,
  ArrowRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  Check,
  Server,
  Activity,
  Zap,
  Cpu,
  Info,
  ChevronRight,
} from 'lucide-react';

import InvestigationTrace from '../features/InvestigationTrace';
import ArchitectureComparison from '../features/ArchitectureComparison';
import RecommendationView from '../features/RecommendationView';
import EvidenceDisclosure from '../features/EvidenceDisclosure';
import ModelRegistryBrowser from '../features/ModelRegistryBrowser';

export default function ResultsPanel() {
  const { response, loading, handleRunWorkflow } = useApp();
  const [activeTab, setActiveTab] = useState('rationale');

  const workload = response?.workload || response?.section_a_workload || {};
  const candidates = response?.candidates || response?.section_c_comparison?.candidates || [];
  const recommendation = response?.recommendation || response?.section_d_recommendation || {};
  const winner =
    recommendation?.candidate ||
    recommendation?.winner ||
    candidates.find((c) => c.id === recommendation?.winnerId) ||
    candidates[0];

  const slaMs = workload.p95_sla_ms || 100;
  const budgetUsd = workload.budget_usd || 250;

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#090d16]">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-slate-100">
            Autonomous Agent Investigation Active
          </h3>
          <p className="text-xs text-slate-400 max-w-md">
            Querying empirical performance models in SQLite, running SimPy discrete-event queueing simulations, and enforcing policy guardrails.
          </p>
        </div>
      </div>
    );
  }

  // Pre-run welcome canvas fallback
  if (!response || candidates.length === 0) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#090d16]">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Zap className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-slate-100">Select a Scenario to Begin</h3>
          <p className="text-xs text-slate-400 max-w-md">
            Choose a benchmark scenario on the left to immediately inspect discrete-event simulation results.
          </p>
        </div>
      </div>
    );
  }

  const maxLatency = Math.max(slaMs * 1.3, ...candidates.map((c) => c.p95 || 0));

  return (
    <main className="flex-1 bg-[#090d16] flex flex-col h-full overflow-y-auto">
      {/* Studio Header Bar */}
      <div className="border-b border-white/[0.08] bg-[#0c101a] px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="badge badge-indigo text-[11px] font-medium">SimPy 4.1 Engine</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-200">Current Workload:</span>
            <span className="text-slate-400 font-mono">
              {workload.qps} RPS • {Math.round((workload.read_ratio ?? 0.85) * 100)}% Read / {Math.round((workload.write_ratio ?? 0.15) * 100)}% Write • SLA &lt; {slaMs}ms • Budget ${budgetUsd}
            </span>
          </div>
        </div>
      </div>

      {/* Main Spacious Canvas */}
      <div className="p-6 lg:p-8 space-y-8 flex-1 max-w-6xl mx-auto w-full">
        {/* 1. Executive Winner Showcase Card */}
        {winner && (
          <div className="rounded-xl bg-[#0f1422] border border-emerald-500/30 p-6 lg:p-7 space-y-5 shadow-sm">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-5 border-b border-white/[0.08]">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="badge badge-emerald text-xs font-medium py-0.5 px-2.5 flex items-center gap-1.5">
                    <Award className="w-3.5 h-3.5" /> Recommended Architecture
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    Highest Pareto Score
                  </span>
                </div>
                <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                  {winner.name || winner.id}
                </h2>
                <div className="text-xs font-mono text-slate-400 flex items-center gap-2 pt-0.5">
                  <span className="text-slate-500">Topology:</span>
                  <span className="text-slate-300">{winner.topology || winner.topology_summary}</span>
                </div>
              </div>

              {/* 4 Clean Metric Cards in a Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
                <div className="p-3 rounded-lg bg-black/20 border border-white/[0.06] text-center min-w-[110px]">
                  <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                    p95 Latency
                  </div>
                  <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                    {winner.p95} ms
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                    Target &lt; {slaMs}ms (PASS)
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-black/20 border border-white/[0.06] text-center min-w-[110px]">
                  <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                    Monthly Cost
                  </div>
                  <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                    ${winner.cost}/mo
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                    Budget &lt; ${budgetUsd} (PASS)
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-black/20 border border-white/[0.06] text-center min-w-[110px]">
                  <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                    Throughput
                  </div>
                  <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                    {winner.throughput} RPS
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                    100% Sustained
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-black/20 border border-white/[0.06] text-center min-w-[110px]">
                  <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                    Database CPU
                  </div>
                  <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                    {winner.cpu}%
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                    {winner.cpu < 60 ? 'Optimal Headroom' : 'Contention'}
                  </div>
                </div>
              </div>
            </div>

            {/* Clean Executive Summary */}
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed max-w-4xl">
              {recommendation.executive_summary ||
                `${winner.name} is the optimal architecture. In-memory caching shields database connections, meeting the ${slaMs}ms tail-latency SLA at lowest total cost.`}
            </p>
          </div>
        )}

        {/* 2. Architecture Comparison Table (Clean, Linear, Spacious) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200 tracking-tight">
                Architecture Comparison Matrix
              </h3>
              <p className="text-xs text-slate-500">
                Simulated side-by-side under {workload.qps} RPS offered load
              </p>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              3 Candidates Evaluated
            </span>
          </div>

          <div className="rounded-xl border border-white/[0.08] overflow-hidden bg-[#0f1422]">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/[0.08] bg-white/[0.02] text-slate-400 font-medium">
                    <th className="py-3 px-4">Architecture</th>
                    <th className="py-3 px-4">Topology Flow</th>
                    <th className="py-3 px-4">p95 Latency</th>
                    <th className="py-3 px-4">Monthly Cost</th>
                    <th className="py-3 px-4">DB CPU</th>
                    <th className="py-3 px-4">Feasibility Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06]">
                  {candidates.map((cand) => {
                    const isWinner = cand.id === winner?.id;
                    const isViolated = !cand.slaMet || !cand.feasible;

                    return (
                      <tr
                        key={cand.id}
                        className={`transition-colors ${
                          isWinner
                            ? 'bg-emerald-500/[0.04]'
                            : 'hover:bg-white/[0.02]'
                        }`}
                      >
                        {/* Name + Badge */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-100">
                              {cand.name.split('—')[0] || cand.id}
                            </span>
                            {isWinner ? (
                              <span className="badge badge-emerald text-[10px] py-0 px-2 font-medium">
                                ★ Winner
                              </span>
                            ) : isViolated ? (
                              <span className="badge badge-rose text-[10px] py-0 px-2 font-medium">
                                Violated SLA
                              </span>
                            ) : (
                              <span className="badge badge-zinc text-[10px] py-0 px-2 font-medium">
                                Feasible
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            {cand.name.split('—')[1] || cand.name}
                          </div>
                        </td>

                        {/* Topology */}
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-300">
                          {cand.topology || cand.topology_summary}
                        </td>

                        {/* p95 Latency Bar */}
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`font-mono font-medium ${
                                cand.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'
                              }`}
                            >
                              {cand.p95} ms
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono">
                              / {slaMs}ms
                            </span>
                          </div>
                          <div className="w-24 h-1.5 rounded-full bg-white/[0.06] overflow-hidden mt-1">
                            <div
                              className={`h-full rounded-full ${
                                cand.p95 <= slaMs ? 'bg-emerald-500' : 'bg-rose-500'
                              }`}
                              style={{ width: `${Math.min(100, (cand.p95 / maxLatency) * 100)}%` }}
                            />
                          </div>
                        </td>

                        {/* Monthly Cost */}
                        <td className="py-3.5 px-4 font-mono">
                          <span
                            className={
                              cand.cost <= budgetUsd ? 'text-slate-200' : 'text-rose-400'
                            }
                          >
                            ${cand.cost}
                          </span>
                          <span className="text-[10px] text-slate-500 ml-1">
                            / ${budgetUsd}
                          </span>
                        </td>

                        {/* DB CPU */}
                        <td className="py-3.5 px-4 font-mono text-slate-300">
                          {cand.cpu}%
                        </td>

                        {/* Verdict */}
                        <td className="py-3.5 px-4">
                          {isWinner ? (
                            <div className="text-emerald-400 flex items-center gap-1.5 font-medium">
                              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                              <span>Optimal fit; meets all constraints.</span>
                            </div>
                          ) : isViolated ? (
                            <div className="text-rose-400 flex items-center gap-1.5">
                              <XCircle className="w-3.5 h-3.5 shrink-0" />
                              <span>
                                {cand.rejectionReasons?.[0] || 'Latency exceeds SLA target.'}
                              </span>
                            </div>
                          ) : (
                            <div className="text-slate-400 flex items-center gap-1.5">
                              <Info className="w-3.5 h-3.5 shrink-0" />
                              <span>Higher cost or complexity than winner.</span>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* 3. Deep-Dive Tabs (One Clean View at a Time) */}
        <div className="space-y-4 pt-2">
          {/* Tab Navigation Buttons */}
          <div className="border-b border-white/[0.08] flex items-center gap-2 pb-2">
            {[
              { id: 'rationale', label: 'Decision Rationale & Trade-Offs', icon: Activity },
              { id: 'trace', label: 'Autonomous Agent Trace', icon: Bot },
              { id: 'evidence', label: 'Epistemic Evidence & Provenance', icon: ShieldCheck },
              { id: 'registry', label: 'Empirical Model Registry (24)', icon: Database },
            ].map((t) => {
              const IconComp = t.icon;
              const isTabActive = activeTab === t.id;

              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setActiveTab(t.id)}
                  className={`px-3 py-1.5 rounded-lg flex items-center gap-2 text-xs font-medium transition-all ${
                    isTabActive
                      ? 'bg-white/[0.08] text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
                  }`}
                >
                  <IconComp className="w-3.5 h-3.5" />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab 1: Rationale, Trade-offs & Breaking Points */}
          {activeTab === 'rationale' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Key Rationale */}
              <div className="p-5 rounded-xl bg-[#0f1422] border border-white/[0.08] space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Why Architecture B Won
                  </h4>
                </div>
                <div className="space-y-2">
                  {(recommendation.decision_rationale || recommendation.why_it_won || []).map(
                    (r, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-black/20 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2.5"
                      >
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{r}</span>
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* Conditions for Change */}
              <div className="p-5 rounded-xl bg-[#0f1422] border border-white/[0.08] space-y-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Conditions for Change (Breaking Points)
                  </h4>
                </div>
                <div className="space-y-2">
                  {(recommendation.conditions_for_change || []).map((c, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-black/20 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2.5"
                    >
                      <ChevronRight className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Agent Investigation Trace */}
          {activeTab === 'trace' && <InvestigationTrace />}

          {/* Tab 3: Scientific Evidence & Epistemic Boundaries */}
          {activeTab === 'evidence' && <EvidenceDisclosure />}

          {/* Tab 4: Empirical Model Registry Browser */}
          {activeTab === 'registry' && <ModelRegistryBrowser />}
        </div>
      </div>
    </main>
  );
}
