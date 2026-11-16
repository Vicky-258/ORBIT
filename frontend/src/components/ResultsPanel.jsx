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
  Sliders,
  Sparkles,
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
  const [activeTab, setActiveTab] = useState('overview');

  const workload = response?.workload || response?.section_a_workload || {};
  const candidates = response?.candidates || response?.section_c_comparison?.candidates || [];
  const recommendation = response?.recommendation || response?.section_d_recommendation || {};
  const winner = recommendation?.candidate || recommendation?.winner || candidates.find(c => c.id === recommendation?.winnerId) || candidates[0];

  const slaMs = workload.p95_sla_ms || 100;
  const budgetUsd = workload.budget_usd || 250;

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#08090e]">
        <div className="w-12 h-12 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="space-y-1">
          <h3 className="text-base font-bold text-white">Autonomous Agent Investigation Active</h3>
          <p className="text-xs text-zinc-400 max-w-md">
            Querying empirical performance models in SQLite, running SimPy discrete-event queueing simulations, and enforcing policy guardrails.
          </p>
        </div>
      </div>
    );
  }

  // Pre-run welcome canvas fallback (only if response completely missing)
  if (!response || candidates.length === 0) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#08090e]">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
          <Zap className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-white">Select a Scenario to Begin</h3>
          <p className="text-xs text-zinc-400 max-w-md">
            Choose a benchmark scenario on the left to immediately inspect discrete-event simulation results.
          </p>
        </div>
      </div>
    );
  }

  // Max scale for visual bars
  const maxLatency = Math.max(slaMs * 1.5, ...candidates.map(c => c.p95 || 0));
  const maxCost = Math.max(budgetUsd * 1.25, ...candidates.map(c => c.cost || 0));

  return (
    <div className="flex-1 bg-[#08090e] flex flex-col h-full overflow-y-auto">
      {/* Studio Header Bar */}
      <div className="border-b border-zinc-800/80 bg-[#0b0c13] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="badge badge-indigo text-xs">SimPy 4.1 Studio</span>
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">Simulated Evaluation:</span>
            <span className="text-xs text-zinc-400 font-mono">
              {workload.qps} RPS • {workload.read_ratio * 100}% Read • SLA &lt; {slaMs}ms • Budget ${budgetUsd}
            </span>
          </div>
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1.5 text-xs">
          {[
            { id: 'overview', label: 'Architecture Matrix', icon: Award },
            { id: 'rationale', label: 'Decision Rationale', icon: Activity },
            { id: 'trace', label: 'Agent Trace', icon: Bot },
            { id: 'evidence', label: 'Evidence & Provenance', icon: ShieldCheck },
            { id: 'registry', label: 'Model Registry (24)', icon: Database },
          ].map((t) => {
            const IconComp = t.icon;
            const isTabActive = activeTab === t.id;

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all font-semibold ${
                  isTabActive
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60'
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
      <div className="p-6 lg:p-8 space-y-6 flex-1">
        {/* 1. Executive Winner Showcase Card */}
        {winner && (
          <div className="relative rounded-2xl bg-gradient-to-r from-emerald-950/40 via-zinc-900/60 to-indigo-950/30 border border-emerald-500/40 p-6 shadow-xl shadow-emerald-950/20 overflow-hidden">
            <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-500/5 rounded-full blur-3xl -z-10 pointer-events-none" />

            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5 pb-5 border-b border-zinc-800/80">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="badge badge-emerald text-xs font-bold uppercase tracking-wider py-0.5 px-2.5 flex items-center gap-1">
                    <Award className="w-3.5 h-3.5" /> Recommended Winner
                  </span>
                  <span className="text-xs text-zinc-400 font-mono">
                    Highest Pareto Utility Score
                  </span>
                </div>
                <h2 className="text-2xl font-black text-white tracking-tight">
                  {winner.name || winner.id}
                </h2>
                <div className="text-xs font-mono text-emerald-400 flex items-center gap-2 pt-0.5">
                  <span className="text-zinc-400">Topology:</span>
                  <span>{winner.topology || winner.topology_summary}</span>
                </div>
              </div>

              {/* 4 KPI Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 shrink-0">
                {/* Latency */}
                <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 font-semibold uppercase flex items-center justify-center gap-1">
                    <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.p95} ms
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium">
                    SLA &lt; {slaMs}ms (PASS)
                  </div>
                </div>

                {/* Monthly Cost */}
                <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 font-semibold uppercase flex items-center justify-center gap-1">
                    <DollarSign className="w-3 h-3 text-emerald-400" /> Monthly Cost
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    ${winner.cost}/mo
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium">
                    Budget &lt; ${budgetUsd} (PASS)
                  </div>
                </div>

                {/* Throughput */}
                <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 font-semibold uppercase flex items-center justify-center gap-1">
                    <TrendingUp className="w-3 h-3 text-indigo-400" /> Throughput
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.throughput} RPS
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium">
                    100% Sustained
                  </div>
                </div>

                {/* Database CPU */}
                <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 font-semibold uppercase flex items-center justify-center gap-1">
                    <Cpu className="w-3 h-3 text-amber-400" /> DB CPU
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.cpu}%
                  </div>
                  <div className="text-[10px] text-emerald-400 font-medium">
                    {winner.cpu < 60 ? 'Healthy Pool' : 'Saturated'}
                  </div>
                </div>
              </div>
            </div>

            {/* Why It Won Bullet Points */}
            <div className="pt-4 space-y-2">
              <span className="text-[11px] font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Why This Architecture Won:
              </span>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                {(recommendation.decision_rationale || recommendation.why_it_won || []).slice(0, 3).map((r, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/80 text-xs text-zinc-300 flex items-start gap-2">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{r}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 2. Candidate Architectures In Play (Side-by-Side 3-Card Grid) */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
              <span>Candidate Architectures Evaluated Under Workload</span>
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              3 Architectures Simulated Side-by-Side
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
                      ? 'bg-zinc-900/90 border-emerald-500/60 ring-1 ring-emerald-500/50 shadow-lg shadow-emerald-500/5'
                      : 'bg-zinc-900/40 border-zinc-800/80 hover:border-zinc-700'
                  }`}
                >
                  <div className="space-y-4">
                    {/* Card Header & Status */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs font-bold text-white flex items-center gap-1.5">
                          <span>{cand.name.split('—')[0] || cand.id}</span>
                        </div>
                        <h4 className="text-sm font-bold text-zinc-200 mt-0.5">
                          {cand.name.split('—')[1] || cand.name}
                        </h4>
                      </div>

                      {isWinner ? (
                        <span className="badge badge-emerald text-[10px] shrink-0 font-bold">
                          ★ WINNER
                        </span>
                      ) : isViolated ? (
                        <span className="badge badge-rose text-[10px] shrink-0 font-bold">
                          ✕ SLA VIOLATED
                        </span>
                      ) : (
                        <span className="badge badge-zinc text-[10px] shrink-0 font-bold">
                          FEASIBLE
                        </span>
                      )}
                    </div>

                    {/* Visual Topology Diagram Flow */}
                    <div className="p-3 rounded-xl bg-zinc-950/80 border border-zinc-800 space-y-1.5">
                      <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                        Topology Flow
                      </div>
                      <div className="flex items-center gap-1.5 flex-wrap text-xs font-mono">
                        {(cand.topologyNodes || []).map((node, nIdx) => (
                          <React.Fragment key={nIdx}>
                            <div className="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 flex items-center gap-1 text-[11px]">
                              {node.type === 'ingress' && <Server className="w-3 h-3 text-zinc-400" />}
                              {node.type === 'cache' && <Zap className="w-3 h-3 text-cyan-400" />}
                              {node.type === 'database' && <Database className="w-3 h-3 text-indigo-400" />}
                              {node.type === 'queue' && <Layers className="w-3 h-3 text-amber-400" />}
                              {node.type === 'worker' && <Cpu className="w-3 h-3 text-emerald-400" />}
                              <span>{node.name}</span>
                            </div>
                            {nIdx < cand.topologyNodes.length - 1 && (
                              <ArrowRight className="w-3 h-3 text-zinc-600 shrink-0" />
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
                          <span className="text-zinc-400 flex items-center gap-1">
                            <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency:
                          </span>
                          <span className={`font-mono font-bold ${cand.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {cand.p95} ms <span className="text-zinc-500 font-normal">/ {slaMs}ms SLA</span>
                          </span>
                        </div>
                        <div className="relative w-full h-2 rounded-full bg-zinc-950 overflow-hidden border border-zinc-800">
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
                          <span className="text-zinc-400 flex items-center gap-1">
                            <DollarSign className="w-3 h-3 text-amber-400" /> Monthly Cost:
                          </span>
                          <span className={`font-mono font-bold ${cand.cost <= budgetUsd ? 'text-emerald-400' : 'text-rose-400'}`}>
                            ${cand.cost} <span className="text-zinc-500 font-normal">/ ${budgetUsd} budget</span>
                          </span>
                        </div>
                        <div className="relative w-full h-2 rounded-full bg-zinc-950 overflow-hidden border border-zinc-800">
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
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-800/80 text-[11px] font-mono text-center">
                      <div className="p-1.5 rounded bg-zinc-950 border border-zinc-800/80">
                        <div className="text-[9px] text-zinc-500 uppercase">p50 Latency</div>
                        <div className="text-zinc-200 font-bold">{cand.p50} ms</div>
                      </div>
                      <div className="p-1.5 rounded bg-zinc-950 border border-zinc-800/80">
                        <div className="text-[9px] text-zinc-500 uppercase">Throughput</div>
                        <div className="text-zinc-200 font-bold">{cand.throughput} RPS</div>
                      </div>
                      <div className="p-1.5 rounded bg-zinc-950 border border-zinc-800/80">
                        <div className="text-[9px] text-zinc-500 uppercase">DB CPU</div>
                        <div className="text-zinc-200 font-bold">{cand.cpu}%</div>
                      </div>
                    </div>
                  </div>

                  {/* Verdict Footer */}
                  <div className="mt-4 pt-3 border-t border-zinc-800/80 text-xs">
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
                      <div className="text-zinc-400 flex items-start gap-1.5">
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

        {/* 3. Deep-Dive Workspace Tabs */}
        <div className="pt-4">
          {activeTab === 'overview' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Trade-Offs & Risks */}
              <div className="panel p-5 space-y-3 bg-zinc-900/40 border-zinc-800/80">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Main Trade-Offs & Architectural Risks
                  </h4>
                </div>
                <div className="space-y-2">
                  {(recommendation.main_trade_offs || recommendation.trade_offs_and_risks || []).map((t, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80 text-xs text-zinc-300 flex items-start gap-2">
                      <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{t}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Conditions For Change */}
              <div className="panel p-5 space-y-3 bg-zinc-900/40 border-zinc-800/80">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                    Conditions for Change (When to Pivot Architecture)
                  </h4>
                </div>
                <div className="space-y-2">
                  {(recommendation.conditions_for_change || []).map((c, idx) => (
                    <div key={idx} className="p-3 rounded-xl bg-zinc-950 border border-zinc-800/80 text-xs text-zinc-300 flex items-start gap-2">
                      <ChevronRight className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'rationale' && <RecommendationView />}
          {activeTab === 'trace' && <InvestigationTrace />}
          {activeTab === 'evidence' && <EvidenceDisclosure />}
          {activeTab === 'registry' && <ModelRegistryBrowser />}
        </div>
      </div>
    </div>
  );
}
