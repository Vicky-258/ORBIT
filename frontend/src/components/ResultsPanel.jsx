import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import {
  Award,
  Layers,
  Bot,
  ShieldCheck,
  Database,
  ArrowRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Check,
  Server,
  Zap,
  Cpu,
  Info,
  ChevronRight,
  Copy,
  Clock,
  Sparkles,
} from 'lucide-react';

import InvestigationTrace from '../features/InvestigationTrace';
import EvidenceDisclosure from '../features/EvidenceDisclosure';
import ModelRegistryBrowser from '../features/ModelRegistryBrowser';
import { generateAIPrompt } from '../utils/aiPromptGenerator';

export default function ResultsPanel() {
  const { response, loading } = useApp();
  const [activeTab, setActiveTab] = useState('blueprint');
  const [techSubTab, setTechSubTab] = useState('trace');
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  // Canonical decision object is the single source of truth
  const decisionResult = response?.decision_result || response?.decisionResult;

  const workload = decisionResult?.workload || response?.workload || response?.section_a_workload || {};
  const candidates = response?.candidates || response?.section_c_comparison?.candidates || [];
  const recommendation = response?.recommendation || response?.section_d_recommendation || {};
  const explanation = decisionResult?.explanation || {};

  const winner = recommendation.winner || candidates.find((c) => c.id === recommendation.winner_id) || candidates[0];

  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;
  const maxLatency = Math.max(slaMs * 1.3, ...candidates.map((c) => c.p95 || 0));

  const handleCopyPrompt = () => {
    const promptText = generateAIPrompt(winner, workload, recommendation, decisionResult);
    navigator.clipboard.writeText(promptText);
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2500);
  };

  // Loading state
  if (loading) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 bg-[#070a12]">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-slate-100">
            Simulating Architectures & Testing SLAs...
          </h3>
          <p className="text-xs text-slate-400 max-w-md">
            Running discrete-event simulation queues, testing database CPU load, and finding the best architecture for your workload.
          </p>
        </div>
      </main>
    );
  }

  // Pre-selection empty state
  if (!response) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4 bg-[#070a12]">
        <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Zap className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-slate-100">Select a Project Scenario</h3>
          <p className="text-xs text-slate-400 max-w-md">
            Pick what you are building on the left to see the recommended architecture blueprint.
          </p>
        </div>
      </main>
    );
  }

  const PRIMARY_TABS = [
    { id: 'blueprint', label: 'Architecture Blueprint', icon: Award, highlight: true },
    { id: 'compare', label: 'Compare Options', icon: Layers, count: candidates.length },
    { id: 'technical', label: 'Technical Proof & Benchmarks', icon: ShieldCheck },
  ];

  return (
    <main className="flex-1 flex flex-col min-w-0 bg-[#070a12] overflow-hidden">
      {/* Studio Header Bar */}
      <div className="border-b border-white/[0.08] bg-[#0c101a] px-6 py-3 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <span className="badge badge-emerald text-[11px] font-medium">Ready</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-200">Workload Target:</span>
            <span className="text-slate-400 font-mono">
              {workload.qps || workload.request_rate_rps || 500} requests/sec • {Math.round((workload.read_ratio ?? 0.85) * 100)}% Reads • Max SLA {slaMs}ms {budgetUsd ? `• Budget < $${budgetUsd}/mo` : ''}
            </span>
          </div>
        </div>

        <div className="text-xs text-slate-400 font-mono hidden sm:block">
          Simulated under {candidates.length} Architecture Topologies
        </div>
      </div>

      {/* Primary Top Navigation Tabs (Progressive Disclosure) */}
      <div className="border-b border-white/[0.08] bg-[#090d16] px-6 py-2.5 flex items-center justify-between gap-4 overflow-x-auto shrink-0">
        <div className="flex items-center gap-2">
          {PRIMARY_TABS.map((tab) => {
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
                {tab.count != null && (
                  <span className="badge badge-zinc text-[10px] py-0 px-1.5 font-mono">
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Secondary AI Prompt Action in Tab Bar */}
        <button
          type="button"
          onClick={handleCopyPrompt}
          className="btn btn-secondary text-xs py-1.5 px-3 hidden md:flex items-center gap-1.5 text-slate-300 hover:text-white"
          title="Copy architecture boundaries for Cursor, Claude Code, or Copilot"
        >
          {copiedPrompt ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-medium">Copied AI Prompt!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-slate-400" />
              <span>Copy Prompt for AI</span>
            </>
          )}
        </button>
      </div>

      {/* Tab Content Area: 100% Viewport Height Utilization */}
      <div className="flex-1 overflow-y-auto p-6 lg:p-8 min-h-0">
        {/* ========================================================================= */}
        {/* TAB 1: ARCHITECTURE BLUEPRINT (Developer-Friendly & Intuitive)            */}
        {/* ========================================================================= */}
        {activeTab === 'blueprint' && (
          <div className="flex flex-col gap-6 h-full justify-between min-h-0">
            {/* Top: Recommended Blueprint Hero Card */}
            <div className="rounded-2xl bg-gradient-to-b from-[#0f172a] to-[#0c101a] border border-emerald-500/40 p-6 lg:p-7 shadow-lg shadow-black/40 space-y-5">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <span className="badge badge-emerald text-xs font-semibold py-0.5 px-2.5 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" /> Recommended Architecture
                    </span>
                    <span className="badge badge-zinc text-xs text-slate-300">
                      Best Balance of Speed, Cost & Simplicity
                    </span>
                  </div>
                  <h2 className="text-xl lg:text-2xl font-bold text-white tracking-tight">
                    {winner?.name || 'Recommended Architecture'}
                  </h2>
                  <p className="text-xs text-slate-300 font-mono">
                    Pipeline: {winner?.topology || winner?.topology_summary || 'Sync API ➔ Relational Database'}
                  </p>
                </div>

                {/* 4 Plain-English Metric Badges with Honest Evidence Labels */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
                  {/* Metric 1: Response Time */}
                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[125px]">
                    <div className="flex items-center justify-center gap-1 text-[11px] text-slate-400 uppercase font-medium">
                      <span>Response Time</span>
                      <span className="badge badge-emerald text-[9px] py-0 px-1 font-mono">[Simulated]</span>
                    </div>
                    <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
                      {winner?.p95 != null ? `~${winner.p95} ms` : '—'}
                    </div>
                    <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                      Target: &lt;{slaMs}ms
                    </div>
                  </div>

                  {/* Metric 2: Estimated Cost (Honest: Not modelled if absent) */}
                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[125px]">
                    <div className="flex items-center justify-center gap-1 text-[11px] text-slate-400 uppercase font-medium">
                      <span>Monthly Cost</span>
                      <span className={`badge text-[9px] py-0 px-1 font-mono ${winner?.cost != null ? 'badge-zinc' : 'badge-amber'}`}>
                        {winner?.cost != null ? '[Assumed]' : '[Not modelled]'}
                      </span>
                    </div>
                    <div className="text-xl font-bold font-mono text-white mt-0.5">
                      {winner?.cost != null ? `$${winner.cost}/mo` : 'Unavailable'}
                    </div>
                    <div className="text-[10px] text-slate-400 font-medium mt-0.5">
                      {winner?.cost != null && budgetUsd != null
                        ? (winner.cost <= budgetUsd ? `$${budgetUsd - winner.cost} under budget` : `$${winner.cost - budgetUsd} over budget`)
                        : (budgetUsd ? `Budget: < $${budgetUsd}/mo` : 'Not modelled')}
                    </div>
                  </div>

                  {/* Metric 3: Simulated Throughput (Correction B: Never say "100% Sustained") */}
                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[125px]">
                    <div className="flex items-center justify-center gap-1 text-[11px] text-slate-400 uppercase font-medium">
                      <span>Throughput</span>
                      <span className="badge badge-indigo text-[9px] py-0 px-1 font-mono">[Simulated]</span>
                    </div>
                    <div className="text-xl font-bold font-mono text-white mt-0.5">
                      {winner?.throughput != null ? `${winner.throughput} req/sec` : '—'}
                    </div>
                    <div className="text-[10px] text-indigo-400 font-medium mt-0.5">
                      Offered load simulated
                    </div>
                  </div>

                  {/* Metric 4: Database Load */}
                  <div className="px-4 py-3 rounded-xl bg-black/40 border border-white/[0.08] text-center min-w-[125px]">
                    <div className="flex items-center justify-center gap-1 text-[11px] text-slate-400 uppercase font-medium">
                      <span>Database Load</span>
                      <span className={`badge text-[9px] py-0 px-1 font-mono ${winner?.cpu != null ? 'badge-zinc' : 'badge-amber'}`}>
                        {winner?.cpu != null ? '[Estimated]' : '[Not modelled]'}
                      </span>
                    </div>
                    <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
                      {winner?.cpu != null ? `${winner.cpu}% CPU` : 'Not modelled'}
                    </div>
                    <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                      {winner?.cpu != null ? (winner.cpu < 60 ? 'Safe Headroom' : 'Moderate Load') : 'Hardware model pending'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Developer Plain-English Summary Banner */}
              <div className="p-4 rounded-xl bg-black/30 border border-white/[0.06] text-xs text-slate-300 leading-relaxed flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <span className="font-semibold text-slate-100">Why this blueprint fits your project:</span>
                  <p>
                    {recommendation?.executive_summary || `Recommended ${winner?.name || 'Architecture'} based on discrete-event simulation performance and constraint satisfaction.`}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleCopyPrompt}
                    className="btn btn-primary text-xs py-2 px-3.5 flex items-center gap-1.5"
                  >
                    {copiedPrompt ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-white" />
                        <span>Prompt Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Prompt for AI</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Bottom 2 Columns: Senior Architect Mentorship Q&A */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
              {/* Left Column: Why This Blueprint Fits Best */}
              <div className="rounded-2xl bg-[#0c101a] border border-white/[0.08] p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-3.5">
                  <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      Why This Blueprint Fits Best
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {(recommendation.decision_rationale || [
                      'Selected based on optimal balance of latency, cost, and operational simplicity.',
                      `Meets mandatory SLA target with tail latency well within limits.`,
                      'Avoids unneeded infrastructure moving parts for this workload profile.',
                    ]).map((point, pIdx) => (
                      <div key={pIdx} className="p-3.5 rounded-xl bg-black/25 border border-white/[0.04] text-xs text-slate-300 space-y-1">
                        <div className="font-semibold text-emerald-400 flex items-center gap-1.5">
                          <Check className="w-3.5 h-3.5 shrink-0" />
                          <span>Key Decision Factor #{pIdx + 1}</span>
                        </div>
                        <p className="text-slate-400 leading-relaxed pl-5">
                          {point}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-slate-500">
                  <span>Want to see how other options compare?</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('compare')}
                    className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                  >
                    <span>Compare {candidates.length} Options</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Right Column: Objective Trade-Offs & When to Reconsider (Correction C) */}
              <div className="rounded-2xl bg-[#0c101a] border border-white/[0.08] p-6 flex flex-col justify-between space-y-4">
                <div className="space-y-3.5">
                  <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                      When Should You Reconsider This Architecture?
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {(recommendation.conditions_for_change || [
                      'When direct PostgreSQL stops being sufficient: If incoming traffic exceeds 650 RPS or read ratio exceeds 80%.',
                      'When asynchronous processing is unnecessary: When write traffic remains low and APIs require synchronous consistency.',
                      'When should you reconsider this architecture? If write traffic increases substantially, cache invalidation becomes harder, or cache hit rate falls.',
                    ]).map((cond, cIdx) => (
                      <div key={cIdx} className="p-3.5 rounded-xl bg-black/25 border border-white/[0.04] text-xs text-slate-300 space-y-1">
                        <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                          <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          <span>Condition #{cIdx + 1}</span>
                        </div>
                        <p className="text-slate-400 leading-relaxed pl-5">
                          {cond}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-slate-500">
                  <span>Backed by empirical regression benchmarks</span>
                  <button
                    type="button"
                    onClick={() => setActiveTab('technical')}
                    className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
                  >
                    <span>View Technical Proof</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: COMPARE OPTIONS (Candidate Architecture Breakdown)                */}
        {/* ========================================================================= */}
        {activeTab === 'compare' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                  Compare Evaluated Architecture Options
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  See how each design performed under {workload.qps || workload.request_rate_rps || 500} requests/sec offered load
                </p>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                SLA Limit: {slaMs} ms {budgetUsd ? `• Budget: < $${budgetUsd}/mo` : ''}
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
                    {/* Top Row: Title, Status, and Key KPIs with Evidence Badges */}
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

                      {/* 4 Metric Pills with Inline Provenance Badges */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 shrink-0 text-center font-mono">
                        {/* Response Time */}
                        <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[115px]">
                          <div className="text-[10px] text-slate-400 uppercase font-sans flex items-center justify-center gap-1">
                            <span>Response Time</span>
                            <span className="badge badge-emerald text-[8px] py-0 px-1 font-mono">[Simulated]</span>
                          </div>
                          <div
                            className={`text-sm font-bold mt-0.5 ${
                              cand.p95 != null && cand.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'
                            }`}
                          >
                            {cand.p95 != null ? `${cand.p95} ms` : '—'}
                          </div>
                        </div>

                        {/* Monthly Cost */}
                        <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[115px]">
                          <div className="text-[10px] text-slate-400 uppercase font-sans flex items-center justify-center gap-1">
                            <span>Monthly Cost</span>
                            <span className="badge badge-zinc text-[8px] py-0 px-1 font-mono">
                              {cand.cost != null ? '[Assumed]' : '[Not modelled]'}
                            </span>
                          </div>
                          <div
                            className={`text-sm font-bold mt-0.5 ${
                              cand.cost != null && budgetUsd != null && cand.cost > budgetUsd
                                ? 'text-rose-400'
                                : 'text-slate-100'
                            }`}
                          >
                            {cand.cost != null ? `$${cand.cost}/mo` : 'Unavailable'}
                          </div>
                        </div>

                        {/* Throughput */}
                        <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[115px]">
                          <div className="text-[10px] text-slate-400 uppercase font-sans flex items-center justify-center gap-1">
                            <span>Throughput</span>
                            <span className="badge badge-indigo text-[8px] py-0 px-1 font-mono">[Simulated]</span>
                          </div>
                          <div className="text-sm font-bold text-slate-100 mt-0.5">
                            {cand.throughput != null ? `${cand.throughput} RPS` : '—'}
                          </div>
                        </div>

                        {/* DB CPU */}
                        <div className="p-2.5 rounded-lg bg-black/25 border border-white/[0.06] min-w-[115px]">
                          <div className="text-[10px] text-slate-400 uppercase font-sans flex items-center justify-center gap-1">
                            <span>DB CPU</span>
                            <span className="badge badge-zinc text-[8px] py-0 px-1 font-mono">
                              {cand.cpu != null ? '[Estimated]' : '[Not modelled]'}
                            </span>
                          </div>
                          <div
                            className={`text-sm font-bold mt-0.5 ${
                              cand.cpu != null
                                ? (cand.cpu < 60 ? 'text-emerald-400' : cand.cpu < 85 ? 'text-amber-400' : 'text-rose-400')
                                : 'text-slate-400'
                            }`}
                          >
                            {cand.cpu != null ? `${cand.cpu}%` : 'Not modelled'}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Middle Row: Visual Flow + Progress Bar */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-4 items-center">
                      {/* Flow Chain (6 cols) */}
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
                          <span className="text-slate-400">Response vs SLA:</span>
                          <span className="font-mono text-slate-300">
                            {cand.p95 != null ? `${cand.p95}ms` : '—'} / {slaMs}ms
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-black/40 overflow-hidden border border-white/[0.06]">
                          <div
                            className={`h-full rounded-full transition-all ${
                              cand.p95 != null && cand.p95 <= slaMs ? 'bg-emerald-500' : 'bg-rose-500'
                            }`}
                            style={{ width: `${cand.p95 != null ? Math.min(100, (cand.p95 / maxLatency) * 100) : 0}%` }}
                          />
                        </div>
                      </div>

                      {/* Plain-English Verdict (3 cols) */}
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
                            <span>Feasible alternative</span>
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
        {/* TAB 3: TECHNICAL PROOF & BENCHMARKS (Progressive Disclosure)             */}
        {/* ========================================================================= */}
        {activeTab === 'technical' && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
              <div>
                <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                  Technical Proof & Simulation Data
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Auditable verification proofs, queueing simulations, and empirical component regression models
                </p>
              </div>

              {/* Sub-Tabs for Technical Deep Dive */}
              <div className="flex items-center gap-2 bg-black/40 p-1 rounded-xl border border-white/[0.08]">
                {[
                  { id: 'trace', label: 'Agent Investigation', icon: Bot },
                  { id: 'evidence', label: 'Evidence & Assumptions', icon: ShieldCheck },
                  { id: 'registry', label: 'Model Registry (24)', icon: Database },
                ].map((st) => {
                  const Icon = st.icon;
                  const isCurrent = techSubTab === st.id;
                  return (
                    <button
                      key={st.id}
                      type="button"
                      onClick={() => setTechSubTab(st.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all ${
                        isCurrent
                          ? 'bg-indigo-600 text-white shadow-sm'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{st.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Deep-Dive Sub-Panels */}
            {techSubTab === 'trace' && <InvestigationTrace />}
            {techSubTab === 'evidence' && <EvidenceDisclosure />}
            {techSubTab === 'registry' && <ModelRegistryBrowser />}
          </div>
        )}
      </div>
    </main>
  );
}
