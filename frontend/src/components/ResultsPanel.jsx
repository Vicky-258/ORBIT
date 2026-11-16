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
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#080b12] h-full">
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
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#080b12] h-full">
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
    <main className="flex-1 bg-[#080b12] flex flex-col h-full overflow-y-auto w-full min-h-0">
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

        <div className="text-xs text-slate-400 font-mono">
          3 Candidates Evaluated • Empirical Baseline Phase 4F.4.5
        </div>
      </div>

      {/* Main Full-Width Canvas */}
      <div className="p-6 lg:p-8 space-y-6 flex-1 w-full">
        {/* Section 1: Candidate Architecture Portfolio (Full Width Stacked Cards) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-100 tracking-tight">
                Evaluated Architecture Candidates
              </h2>
              <p className="text-xs text-slate-400">
                Simulated side-by-side under {workload.qps} RPS offered load using calibrated component models
              </p>
            </div>
            <span className="text-xs text-slate-500 font-mono">
              SLA Cutoff: {slaMs} ms • Budget: ${budgetUsd}/mo
            </span>
          </div>

          <div className="space-y-4">
            {candidates.map((cand) => {
              const isWinner = cand.id === winner?.id;
              const isViolated = !cand.slaMet || !cand.feasible;

              return (
                <div
                  key={cand.id}
                  className={`rounded-xl border p-5 transition-all ${
                    isWinner
                      ? 'bg-[#0f172a]/60 border-emerald-500/50 shadow-sm shadow-emerald-950/20'
                      : 'bg-[#0e1320] border-white/[0.08] hover:border-white/[0.14]'
                  }`}
                >
                  {/* Top Row: Title, Status, and Key KPIs */}
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-white/[0.06]">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2.5">
                        {isWinner ? (
                          <span className="badge badge-emerald text-xs font-semibold py-0.5 px-2.5 flex items-center gap-1.5">
                            <Award className="w-3.5 h-3.5" /> Recommended Winner
                          </span>
                        ) : isViolated ? (
                          <span className="badge badge-rose text-xs font-medium py-0.5 px-2.5">
                            SLA Violated
                          </span>
                        ) : (
                          <span className="badge badge-zinc text-xs font-medium py-0.5 px-2.5">
                            Feasible Alternative
                          </span>
                        )}
                        <h3 className="text-base font-bold text-slate-100">
                          {cand.name}
                        </h3>
                      </div>
                      <p className="text-xs text-slate-400 font-mono">
                        {cand.topology || cand.topology_summary}
                      </p>
                    </div>

                    {/* 4 Metric Pills in a Row */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 shrink-0 text-center font-mono">
                      <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[110px]">
                        <div className="text-[10px] text-slate-400 uppercase font-sans">p95 Latency</div>
                        <div
                          className={`text-sm font-bold mt-0.5 ${
                            cand.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {cand.p95} ms
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[110px]">
                        <div className="text-[10px] text-slate-400 uppercase font-sans">Monthly Cost</div>
                        <div
                          className={`text-sm font-bold mt-0.5 ${
                            cand.cost <= budgetUsd ? 'text-slate-100' : 'text-rose-400'
                          }`}
                        >
                          ${cand.cost}/mo
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[110px]">
                        <div className="text-[10px] text-slate-400 uppercase font-sans">Throughput</div>
                        <div className="text-sm font-bold text-slate-100 mt-0.5">
                          {cand.throughput} RPS
                        </div>
                      </div>

                      <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[110px]">
                        <div className="text-[10px] text-slate-400 uppercase font-sans">DB CPU</div>
                        <div
                          className={`text-sm font-bold mt-0.5 ${
                            cand.cpu < 60 ? 'text-emerald-400' : cand.cpu < 85 ? 'text-amber-400' : 'text-rose-400'
                          }`}
                        >
                          {cand.cpu}%
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Middle Row: Visual Topology Nodes + Progress Bar */}
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-4 items-center">
                    {/* Topology Chain (6 cols) */}
                    <div className="lg:col-span-6 flex items-center gap-1.5 flex-wrap font-mono text-xs">
                      <span className="text-[11px] text-slate-500 uppercase font-sans mr-2 font-medium">Flow:</span>
                      {(cand.topologyNodes || []).map((node, nIdx) => (
                        <React.Fragment key={nIdx}>
                          <div className="px-2.5 py-1.5 rounded-lg bg-black/30 border border-white/[0.08] text-slate-200 flex items-center gap-1.5 text-xs">
                            {node.type === 'ingress' && <Server className="w-3.5 h-3.5 text-slate-400" />}
                            {node.type === 'cache' && <Zap className="w-3.5 h-3.5 text-cyan-400" />}
                            {node.type === 'database' && <Database className="w-3.5 h-3.5 text-indigo-400" />}
                            {node.type === 'queue' && <Layers className="w-3.5 h-3.5 text-amber-400" />}
                            {node.type === 'worker' && <Cpu className="w-3.5 h-3.5 text-emerald-400" />}
                            <span>{node.name}</span>
                          </div>
                          {nIdx < cand.topologyNodes.length - 1 && (
                            <ArrowRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>

                    {/* Progress Bar (3 cols) */}
                    <div className="lg:col-span-3 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">p95 Latency vs SLA:</span>
                        <span className="font-mono text-slate-300">{cand.p95}ms / {slaMs}ms</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-black/40 overflow-hidden border border-white/[0.06]">
                        <div
                          className={`h-full rounded-full transition-all ${
                            cand.p95 <= slaMs ? 'bg-emerald-500' : 'bg-rose-500'
                          }`}
                          style={{ width: `${Math.min(100, (cand.p95 / maxLatency) * 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* Verdict (3 cols) */}
                    <div className="lg:col-span-3 text-xs flex items-center justify-start lg:justify-end">
                      {isWinner ? (
                        <div className="text-emerald-400 flex items-center gap-1.5 font-medium">
                          <CheckCircle2 className="w-4 h-4 shrink-0" />
                          <span>Meets all constraints at lowest cost</span>
                        </div>
                      ) : isViolated ? (
                        <div className="text-rose-400 flex items-center gap-1.5 font-medium">
                          <XCircle className="w-4 h-4 shrink-0" />
                          <span>{cand.rejectionReasons?.[0] || 'Latency exceeds SLA'}</span>
                        </div>
                      ) : (
                        <div className="text-slate-400 flex items-center gap-1.5">
                          <Info className="w-4 h-4 shrink-0" />
                          <span>Feasible, but higher cost than winner</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Deep-Dive Workspace Tabs */}
        <div className="space-y-4 pt-4">
          <div className="border-b border-white/[0.08] flex items-center gap-2 pb-2">
            {[
              { id: 'rationale', label: 'Decision Rationale & Trade-Offs', icon: Activity },
              { id: 'trace', label: 'Autonomous Agent Trace', icon: Bot },
              { id: 'evidence', label: 'Scientific Evidence & Provenance', icon: ShieldCheck },
              { id: 'registry', label: 'Empirical Model Registry (24)', icon: Database },
            ].map((t) => {
              const IconComp = t.icon;
              const isTabActive = activeTab === t.id;

              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setActiveTab(t.id)}
                  className={`px-3.5 py-2 rounded-lg flex items-center gap-2 text-xs font-medium transition-all ${
                    isTabActive
                      ? 'bg-white/[0.08] text-white shadow-sm border border-white/[0.06]'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
                  }`}
                >
                  <IconComp className="w-4 h-4" />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab 1: Rationale & Trade-Offs */}
          {activeTab === 'rationale' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Why It Won */}
              <div className="p-6 rounded-xl bg-[#0e1320] border border-white/[0.08] space-y-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Why Architecture B Won (Pareto Optimal)
                  </h4>
                </div>
                <div className="space-y-2.5">
                  {(recommendation.decision_rationale || recommendation.why_it_won || []).map(
                    (r, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-lg bg-black/25 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2.5"
                      >
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{r}</span>
                      </div>
                    )
                  )}
                </div>
              </div>

              {/* Conditions for Change */}
              <div className="p-6 rounded-xl bg-[#0e1320] border border-white/[0.08] space-y-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Conditions for Change (Breaking Points)
                  </h4>
                </div>
                <div className="space-y-2.5">
                  {(recommendation.conditions_for_change || []).map((c, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg bg-black/25 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-2.5"
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
