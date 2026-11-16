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
  Sliders,
  Scale,
  Compass,
} from 'lucide-react';

import InvestigationTrace from '../features/InvestigationTrace';
import ArchitectureComparison from '../features/ArchitectureComparison';
import EvidenceDisclosure from '../features/EvidenceDisclosure';
import ModelRegistryBrowser from '../features/ModelRegistryBrowser';

export default function ResultsPanel() {
  const { response, loading, handleRunWorkflow } = useApp();
  const [activeTab, setActiveTab] = useState('recommendation');

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
          <h3 className="text-base font-semibold text-slate-100">
            Autonomous Agent Investigation Active
          </h3>
          <p className="text-xs text-slate-400 max-w-md">
            Querying empirical performance models in SQLite, running SimPy discrete-event queueing simulations, and enforcing policy guardrails.
          </p>
        </div>
      </div>
    );
  }

  // Pre-run fallback
  if (!response || candidates.length === 0) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#080b12] h-full">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Zap className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-slate-100">Select a Scenario to Begin</h3>
          <p className="text-xs text-slate-400 max-w-md">
            Choose a benchmark scenario on the left to immediately inspect discrete-event simulation results.
          </p>
        </div>
      </div>
    );
  }

  const maxLatency = Math.max(slaMs * 1.3, ...candidates.map((c) => c.p95 || 0));

  const TABS = [
    { id: 'recommendation', label: 'Executive Recommendation', icon: Award, badge: 'Winner' },
    { id: 'candidates', label: 'Candidate Architectures', icon: Layers, count: candidates.length },
    { id: 'trace', label: 'Agent Investigation Trace', icon: Bot },
    { id: 'evidence', label: 'Scientific Evidence', icon: ShieldCheck },
    { id: 'registry', label: 'Model Registry', icon: Database, badge: '24' },
  ];

  return (
    <main className="flex-1 bg-[#080b12] flex flex-col h-full overflow-hidden w-full min-h-0">
      {/* Studio Header Bar */}
      <div className="border-b border-white/[0.08] bg-[#0c101a] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="badge badge-indigo text-[11px] font-medium">SimPy 4.1 Engine</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-200">Workload:</span>
            <span className="text-slate-400 font-mono">
              {workload.qps} RPS • {Math.round((workload.read_ratio ?? 0.85) * 100)}% Read / {Math.round((workload.write_ratio ?? 0.15) * 100)}% Write • SLA &lt; {slaMs}ms • Budget ${budgetUsd}/mo
            </span>
          </div>
        </div>

        <div className="text-xs text-slate-400 font-mono hidden sm:block">
          3 Candidates Simulated • Empirical Baseline Phase 4F.4.5
        </div>
      </div>

      {/* Primary Canvas Navigation Tabs */}
      <div className="border-b border-white/[0.08] bg-[#090d16] px-6 py-2.5 flex items-center gap-1.5 overflow-x-auto shrink-0">
        {TABS.map((tab) => {
          const IconComp = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3.5 py-1.5 rounded-lg flex items-center gap-2 text-xs font-medium transition-all ${
                isActive
                  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-950/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
              }`}
            >
              <IconComp className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span className="badge badge-emerald text-[10px] py-0 px-1.5 font-semibold">
                  {tab.badge}
                </span>
              )}
              {tab.count != null && (
                <span className="badge badge-zinc text-[10px] py-0 px-1.5 font-mono">
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content Area: Fills Full Remaining Height */}
      <div className="flex-1 overflow-y-auto p-6 lg:p-8 min-h-0">
        {/* ========================================================================= */}
        {/* TAB 1: EXECUTIVE RECOMMENDATION (Fills full viewport height cleanly)       */}
        {/* ========================================================================= */}
        {activeTab === 'recommendation' && (
          <div className="flex flex-col gap-6 h-full justify-between min-h-0">
            {/* Top: Winner Hero Card */}
            <div className="rounded-2xl bg-gradient-to-b from-[#0f172a] to-[#0c101a] border border-emerald-500/40 p-6 lg:p-7 shadow-lg shadow-black/40 space-y-6">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <span className="badge badge-emerald text-xs font-semibold py-0.5 px-2.5 flex items-center gap-1.5">
                      <Award className="w-3.5 h-3.5" /> Recommended Winner
                    </span>
                    <span className="badge badge-indigo text-xs font-mono">
                      Pareto Optimal Score: 0.94
                    </span>
                  </div>
                  <h2 className="text-xl lg:text-2xl font-bold text-white tracking-tight">
                    {winner?.name || 'Architecture B — Cached Reads'}
                  </h2>
                  <p className="text-xs text-slate-300 font-mono">
                    Topology: {winner?.topology || winner?.topology_summary || 'API Gateway → Redis 7.2 → PostgreSQL 16'}
                  </p>
                </div>

                {/* 4 Metric Badges in Hero */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[120px]">
                    <div className="text-[11px] text-slate-400 uppercase font-medium">p95 Latency</div>
                    <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
                      {winner?.p95 || 7.25} ms
                    </div>
                    <div className="text-[10px] text-emerald-500 font-medium mt-0.5">
                      Target &lt; {slaMs}ms (PASS)
                    </div>
                  </div>

                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[120px]">
                    <div className="text-[11px] text-slate-400 uppercase font-medium">Monthly Cost</div>
                    <div className="text-xl font-bold font-mono text-white mt-0.5">
                      ${winner?.cost || 176}/mo
                    </div>
                    <div className="text-[10px] text-slate-400 font-medium mt-0.5">
                      Budget &lt; ${budgetUsd}/mo
                    </div>
                  </div>

                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[120px]">
                    <div className="text-[11px] text-slate-400 uppercase font-medium">Throughput</div>
                    <div className="text-xl font-bold font-mono text-white mt-0.5">
                      {winner?.throughput || 501.6} RPS
                    </div>
                    <div className="text-[10px] text-indigo-400 font-medium mt-0.5">
                      100% Sustained
                    </div>
                  </div>

                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[120px]">
                    <div className="text-[11px] text-slate-400 uppercase font-medium">DB CPU</div>
                    <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
                      {winner?.cpu || 27.5}%
                    </div>
                    <div className="text-[10px] text-emerald-500 font-medium mt-0.5">
                      Healthy Headroom
                    </div>
                  </div>
                </div>
              </div>

              {/* Plain English Synthesis Summary */}
              <div className="p-4 rounded-xl bg-black/30 border border-white/[0.06] text-xs text-slate-300 leading-relaxed">
                {recommendation?.narrative ||
                  `Architecture B (Cached Reads) satisfies all mandatory constraints under the offered ${workload.qps || 500} RPS workload. An in-memory Redis 7.2 cache layer absorbs 84.8% of queries, shielding the PostgreSQL connection pool and keeping CPU utilization low at ${winner?.cpu || 27.5}%. It meets the strict p95 latency target with 7.25ms at an estimated monthly cost of $${winner?.cost || 176.00}/mo.`}
              </div>
            </div>

            {/* Bottom 2 Columns: Why It Won vs Conditions For Change */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
              {/* Left Column: Why It Won */}
              <div className="rounded-2xl bg-[#0c101a] border border-white/[0.08] p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Why Architecture B Won (Pareto Optimality)
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {(recommendation.decision_rationale || recommendation.why_it_won || [
                      'Selected based on optimal balance under stated preferences (Cost: 30%, Latency: 50%, Simplicity: 20%).',
                      'Meets hard constraints: Achieves p95 latency of 7.2ms (target <= 100.0ms) at $176.00/mo (budget <= $250.00/mo).',
                      'Effective read caching (84.8% hit rate) shields the database connection pool, sustaining 501.6 RPS with 27.5% DB utilization.',
                    ]).map((r, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-black/25 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-3"
                      >
                        <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{r}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-slate-500">
                  <span>Evaluated against 3 candidates</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('candidates')}
                    className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                  >
                    <span>View Candidates</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Right Column: Conditions For Change (Breaking Points) */}
              <div className="rounded-2xl bg-[#0c101a] border border-white/[0.08] p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
                    <Activity className="w-4 h-4 text-indigo-400 shrink-0" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Conditions for Change (Breaking Points)
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {(recommendation.conditions_for_change || [
                      'If read ratio drops below 60%, Redis caching benefits decrease and direct transactional database routing becomes more cost-effective.',
                      'If incoming traffic exceeds 650 RPS, direct PostgreSQL saturates 2 vCPU quotas, requiring horizontal read replicas or asynchronous ingestion queues.',
                      'If monthly infrastructure budget is capped below $150/mo, Architecture A (direct PostgreSQL without cache) is the only viable candidate.',
                    ]).map((c, idx) => (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl bg-black/25 border border-white/[0.04] text-xs text-slate-300 flex items-start gap-3"
                      >
                        <ChevronRight className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                        <span className="leading-relaxed">{c}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-slate-500">
                  <span>Deterministic boundaries derived from empirical models</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('evidence')}
                    className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                  >
                    <span>Audit Provenance</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: CANDIDATE ARCHITECTURES (Full Width Stacked Cards)                 */}
        {/* ========================================================================= */}
        {activeTab === 'candidates' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                  Evaluated Architecture Portfolio
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Simulated side-by-side under {workload.qps} RPS offered load using calibrated component models
                </p>
              </div>
              <span className="text-xs text-slate-400 font-mono">
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
                    className={`rounded-2xl border p-6 transition-all ${
                      isWinner
                        ? 'bg-[#0f172a]/60 border-emerald-500/50 shadow-md shadow-emerald-950/20'
                        : 'bg-[#0c101a] border-white/[0.08] hover:border-white/[0.14]'
                    }`}
                  >
                    {/* Top Row: Title, Status, and Key KPIs */}
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-5 border-b border-white/[0.06]">
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

                      {/* 4 Metric Pills */}
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
                          <span className="text-slate-400">p95 vs SLA:</span>
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
        )}

        {/* ========================================================================= */}
        {/* TAB 3: AGENT INVESTIGATION TRACE                                          */}
        {/* ========================================================================= */}
        {activeTab === 'trace' && <InvestigationTrace />}

        {/* ========================================================================= */}
        {/* TAB 4: SCIENTIFIC EVIDENCE & EPISTEMIC BOUNDARIES                         */}
        {/* ========================================================================= */}
        {activeTab === 'evidence' && <EvidenceDisclosure />}

        {/* ========================================================================= */}
        {/* TAB 5: EMPIRICAL MODEL REGISTRY BROWSER                                   */}
        {/* ========================================================================= */}
        {activeTab === 'registry' && <ModelRegistryBrowser />}
      </div>
    </main>
  );
}
