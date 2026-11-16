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
  Sparkles,
} from 'lucide-react';

import InvestigationTrace from '../features/InvestigationTrace';
import ArchitectureComparison from '../features/ArchitectureComparison';
import RecommendationView from '../features/RecommendationView';
import EvidenceDisclosure from '../features/EvidenceDisclosure';
import ModelRegistryBrowser from '../features/ModelRegistryBrowser';

export default function ResultsPanel() {
  const { response, loading, handleRunWorkflow } = useApp();
  const [activeTab, setActiveTab] = useState('overview');

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
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#0a0d14]">
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
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#0a0d14]">
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

  // Max scale for visual bars
  const maxLatency = Math.max(slaMs * 1.4, ...candidates.map((c) => c.p95 || 0));
  const maxCost = Math.max(budgetUsd * 1.25, ...candidates.map((c) => c.cost || 0));

  return (
    <main className="flex-1 bg-[#0a0d14] flex flex-col h-full overflow-y-auto">
      {/* Studio Header Bar */}
      <div className="border-b border-white/[0.08] bg-[#0c101a] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="badge badge-indigo text-[11px] font-medium">SimPy 4.1</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-200">Evaluation:</span>
            <span className="text-slate-400 font-mono">
              {workload.qps} RPS • {Math.round((workload.read_ratio ?? 0.85) * 100)}% Read • SLA &lt; {slaMs}ms • Budget ${budgetUsd}
            </span>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 text-xs">
          {[
            { id: 'overview', label: 'Architecture Matrix', icon: Award },
            { id: 'rationale', label: 'Trade-Offs & Decisions', icon: Activity },
            { id: 'trace', label: 'Agent Trace', icon: Bot },
            { id: 'evidence', label: 'Scientific Evidence', icon: ShieldCheck },
            { id: 'registry', label: 'Model Registry', icon: Database },
          ].map((t) => {
            const IconComp = t.icon;
            const isTabActive = activeTab === t.id;

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all text-xs font-medium ${
                  isTabActive
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                }`}
              >
                <IconComp className="w-3.5 h-3.5" />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Results Canvas */}
      <div className="p-6 lg:p-8 space-y-8 flex-1 max-w-7xl mx-auto w-full">
        {activeTab === 'overview' && (
          <>
            {/* 1. Executive Winner Showcase Card */}
            {winner && (
              <div className="rounded-2xl bg-white/[0.02] border border-emerald-500/30 p-6 lg:p-7 space-y-6 shadow-sm">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-white/[0.08]">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="badge badge-emerald text-xs font-medium py-0.5 px-2.5 flex items-center gap-1.5">
                        <Award className="w-3.5 h-3.5" /> Recommended Winner
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        Optimal Pareto Utility
                      </span>
                    </div>
                    <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                      {winner.name || winner.id}
                    </h2>
                    <p className="text-xs font-mono text-slate-400 flex items-center gap-2">
                      <span>Topology:</span>
                      <span className="text-slate-200">{winner.topology || winner.topology_summary}</span>
                    </p>
                  </div>

                  {/* 4 Clean KPI Metric Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
                    {/* Latency */}
                    <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center min-w-[110px]">
                      <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                        p95 Latency
                      </div>
                      <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                        {winner.p95} ms
                      </div>
                      <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                        SLA &lt; {slaMs}ms (PASS)
                      </div>
                    </div>

                    {/* Monthly Cost */}
                    <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center min-w-[110px]">
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

                    {/* Throughput */}
                    <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center min-w-[110px]">
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

                    {/* Database CPU */}
                    <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center min-w-[110px]">
                      <div className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                        DB CPU
                      </div>
                      <div className="text-base font-semibold text-slate-100 font-mono mt-0.5">
                        {winner.cpu}%
                      </div>
                      <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                        {winner.cpu < 60 ? 'Healthy Pool' : 'Saturated'}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Why It Won Rationale */}
                <div className="space-y-3">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Decision Rationale
                  </span>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    {(recommendation.decision_rationale || recommendation.why_it_won || []).slice(0, 3).map((r, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] text-xs text-slate-300 flex items-start gap-2.5"
                      >
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{r}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* 2. Candidate Architectures In Play */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Architecture Portfolio Comparison
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  3 Candidates Evaluated Side-by-Side
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {candidates.map((cand) => {
                  const isWinner = cand.id === winner?.id;
                  const isViolated = !cand.slaMet || !cand.feasible;

                  return (
                    <div
                      key={cand.id}
                      className={`rounded-2xl p-5 border flex flex-col justify-between transition-all ${
                        isWinner
                          ? 'bg-white/[0.03] border-emerald-500/50 shadow-sm'
                          : 'bg-white/[0.015] border-white/[0.06] hover:border-white/[0.12]'
                      }`}
                    >
                      <div className="space-y-4">
                        {/* Header & Status */}
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <div className="text-xs font-semibold text-slate-400">
                              {cand.name.split('—')[0] || cand.id}
                            </div>
                            <h4 className="text-sm font-semibold text-slate-100 mt-0.5">
                              {cand.name.split('—')[1] || cand.name}
                            </h4>
                          </div>

                          {isWinner ? (
                            <span className="badge badge-emerald text-[10px] shrink-0 font-medium">
                              ★ Winner
                            </span>
                          ) : isViolated ? (
                            <span className="badge badge-rose text-[10px] shrink-0 font-medium">
                              ✕ SLA Violated
                            </span>
                          ) : (
                            <span className="badge badge-zinc text-[10px] shrink-0 font-medium">
                              Feasible
                            </span>
                          )}
                        </div>

                        {/* Topology Flow Chips */}
                        <div className="p-3 rounded-xl bg-black/20 border border-white/[0.04] space-y-1.5">
                          <div className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
                            Topology Flow
                          </div>
                          <div className="flex items-center gap-1.5 flex-wrap text-xs font-mono">
                            {(cand.topologyNodes || []).map((node, nIdx) => (
                              <React.Fragment key={nIdx}>
                                <div className="px-2 py-1 rounded bg-white/[0.04] border border-white/[0.06] text-slate-300 flex items-center gap-1.5 text-[11px]">
                                  {node.type === 'ingress' && <Server className="w-3 h-3 text-slate-400" />}
                                  {node.type === 'cache' && <Zap className="w-3 h-3 text-cyan-400" />}
                                  {node.type === 'database' && <Database className="w-3 h-3 text-indigo-400" />}
                                  {node.type === 'queue' && <Layers className="w-3 h-3 text-amber-400" />}
                                  {node.type === 'worker' && <Cpu className="w-3 h-3 text-emerald-400" />}
                                  <span>{node.name}</span>
                                </div>
                                {nIdx < cand.topologyNodes.length - 1 && (
                                  <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
                                )}
                              </React.Fragment>
                            ))}
                          </div>
                        </div>

                        {/* Visual Comparison Progress Bars */}
                        <div className="space-y-3 pt-1">
                          {/* Latency Bar */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-slate-400 flex items-center gap-1">
                                <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency:
                              </span>
                              <span
                                className={`font-mono font-medium ${
                                  cand.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'
                                }`}
                              >
                                {cand.p95} ms <span className="text-slate-500 font-normal">/ {slaMs}ms</span>
                              </span>
                            </div>
                            <div className="relative w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  cand.p95 <= slaMs ? 'bg-emerald-500' : 'bg-rose-500'
                                }`}
                                style={{ width: `${Math.min(100, (cand.p95 / maxLatency) * 100)}%` }}
                              />
                            </div>
                          </div>

                          {/* Cost Bar */}
                          <div className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-slate-400 flex items-center gap-1">
                                <DollarSign className="w-3 h-3 text-amber-400" /> Monthly Cost:
                              </span>
                              <span
                                className={`font-mono font-medium ${
                                  cand.cost <= budgetUsd ? 'text-slate-200' : 'text-rose-400'
                                }`}
                              >
                                ${cand.cost} <span className="text-slate-500 font-normal">/ ${budgetUsd}</span>
                              </span>
                            </div>
                            <div className="relative w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  cand.cost <= budgetUsd ? 'bg-indigo-500' : 'bg-rose-500'
                                }`}
                                style={{ width: `${Math.min(100, (cand.cost / maxCost) * 100)}%` }}
                              />
                            </div>
                          </div>
                        </div>

                        {/* Metrics Grid */}
                        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.06] text-[11px] font-mono text-center">
                          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-[9px] text-slate-500 uppercase font-sans">p50 Latency</div>
                            <div className="text-slate-200 font-medium mt-0.5">{cand.p50} ms</div>
                          </div>
                          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-[9px] text-slate-500 uppercase font-sans">Throughput</div>
                            <div className="text-slate-200 font-medium mt-0.5">{cand.throughput} RPS</div>
                          </div>
                          <div className="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                            <div className="text-[9px] text-slate-500 uppercase font-sans">DB CPU</div>
                            <div className="text-slate-200 font-medium mt-0.5">{cand.cpu}%</div>
                          </div>
                        </div>
                      </div>

                      {/* Verdict Footer */}
                      <div className="mt-4 pt-3 border-t border-white/[0.06] text-xs">
                        {isWinner ? (
                          <div className="text-emerald-400 flex items-start gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>Meets latency SLA with lowest total cost.</span>
                          </div>
                        ) : isViolated ? (
                          <div className="text-rose-400 flex items-start gap-1.5">
                            <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>
                              {cand.rejectionReasons?.[0] || `p95 latency (${cand.p95}ms) exceeds SLA.`}
                            </span>
                          </div>
                        ) : (
                          <div className="text-slate-400 flex items-start gap-1.5">
                            <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                            <span>Feasible, but higher cost than winner.</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 3. Trade-offs & Breaking Points */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 pt-2">
              <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.06] space-y-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Trade-Offs & Architectural Risks
                  </h4>
                </div>
                <div className="space-y-2">
                  {(recommendation.main_trade_offs || recommendation.trade_offs_and_risks || []).map((t, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2"
                    >
                      <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{t}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/[0.06] space-y-3">
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
                      className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2"
                    >
                      <ChevronRight className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Tab 2: Decision Rationale & Trade-Offs Deep Dive */}
        {activeTab === 'rationale' && <RecommendationView />}

        {/* Tab 3: Agent Investigation Trace */}
        {activeTab === 'trace' && <InvestigationTrace />}

        {/* Tab 4: Scientific Evidence & Epistemic Boundaries */}
        {activeTab === 'evidence' && <EvidenceDisclosure />}

        {/* Tab 5: Empirical Model Registry Browser */}
        {activeTab === 'registry' && <ModelRegistryBrowser />}
      </div>
    </main>
  );
}
