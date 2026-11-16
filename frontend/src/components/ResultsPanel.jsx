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
  HelpCircle,
} from 'lucide-react';

import InvestigationTrace from '../features/InvestigationTrace';
import ArchitectureComparison from '../features/ArchitectureComparison';
import RecommendationView from '../features/RecommendationView';
import EvidenceDisclosure from '../features/EvidenceDisclosure';
import ModelRegistryBrowser from '../features/ModelRegistryBrowser';

export default function ResultsPanel() {
  const { response, loading, handleRunWorkflow } = useApp();
  const [activeTab, setActiveTab] = useState('recommendation');

  const winner = response?.section_d_recommendation?.winner;
  const sectionC = response?.section_c_comparison;
  const sectionD = response?.section_d_recommendation;
  const candidates = sectionC?.candidates || [];

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 p-8 flex flex-col items-center justify-center text-center space-y-4 bg-[#09090b]">
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

  // Pre-run welcome canvas
  if (!response) {
    return (
      <div className="flex-1 p-6 sm:p-8 flex flex-col justify-between bg-[#09090b] overflow-y-auto">
        <div className="max-w-4xl mx-auto w-full space-y-6">
          {/* Header */}
          <div className="space-y-1.5 border-b border-zinc-800 pb-5">
            <div className="flex items-center gap-2">
              <span className="badge badge-indigo">Simulator Canvas</span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Architecture Design & Simulation Studio
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-zinc-400">
              Select a benchmark scenario on the left and run the investigation to generate evidence-backed architectural recommendations.
            </p>
          </div>

          {/* Three Candidate Architectures Overview */}
          <div className="space-y-3">
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
              Candidate Architectures in Play
            </span>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="panel p-4 space-y-2 border-zinc-800 bg-zinc-900/40">
                <div className="flex items-center justify-between">
                  <span className="badge badge-zinc">Baseline Relational</span>
                  <span className="font-mono text-xs text-emerald-400 font-semibold">$133/mo</span>
                </div>
                <h4 className="font-bold text-sm text-white">Architecture A: Simple Direct</h4>
                <div className="text-[11px] font-mono text-zinc-400">API → PostgreSQL 16</div>
                <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                  Zero cache complexity. Best suited for balanced low-to-medium throughput where database CPU stays under 60%.
                </p>
              </div>

              <div className="panel p-4 space-y-2 border-indigo-500/30 bg-zinc-900/40">
                <div className="flex items-center justify-between">
                  <span className="badge badge-indigo">In-Memory Shield</span>
                  <span className="font-mono text-xs text-emerald-400 font-semibold">$176/mo</span>
                </div>
                <h4 className="font-bold text-sm text-white">Architecture B: Cached Reads</h4>
                <div className="text-[11px] font-mono text-indigo-300">API → Redis Cache → PostgreSQL</div>
                <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                  Sub-10ms reads. In-memory cache absorbs 85%+ read spikes, preventing database saturation on catalog reads.
                </p>
              </div>

              <div className="panel p-4 space-y-2 border-cyan-500/30 bg-zinc-900/40">
                <div className="flex items-center justify-between">
                  <span className="badge badge-cyan">Decoupled Queue</span>
                  <span className="font-mono text-xs text-emerald-400 font-semibold">$216/mo</span>
                </div>
                <h4 className="font-bold text-sm text-white">Architecture C: Async Pipeline</h4>
                <div className="text-[11px] font-mono text-cyan-300">API → Kafka → Worker → PostgreSQL</div>
                <p className="text-xs text-zinc-400 leading-relaxed pt-1">
                  Immediate HTTP 202 ack. Background workers absorb massive write spikes with asynchronous persistence.
                </p>
              </div>
            </div>
          </div>

          {/* How It Works 3-Step Banner */}
          <div className="panel p-5 space-y-3 bg-[#0d0d12]">
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
              Autonomous Verification Process
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-zinc-400">
              <div className="space-y-1">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <Bot className="w-3.5 h-3.5 text-indigo-400" /> 1. Model Discovery
                </div>
                <p className="leading-relaxed">
                  Checks operating bounds in the SQLite registry (24 active empirical models).
                </p>
              </div>
              <div className="space-y-1">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-emerald-400" /> 2. SimPy Simulation
                </div>
                <p className="leading-relaxed">
                  Simulates request queueing, database connection limits, and CPU cores.
                </p>
              </div>
              <div className="space-y-1">
                <div className="font-semibold text-white flex items-center gap-1.5">
                  <Award className="w-3.5 h-3.5 text-amber-400" /> 3. Decision Engine
                </div>
                <p className="leading-relaxed">
                  Two-stage filtering eliminates SLA violators and ranks optimal Pareto efficiency.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom CTA */}
        <div className="pt-6 border-t border-zinc-800/80 flex items-center justify-between text-xs text-zinc-500">
          <span>Deterministic & Auditable Simulation Pipeline</span>
          <span className="font-mono text-[11px]">Manifest: 69d3e068...77a6</span>
        </div>
      </div>
    );
  }

  // Active Results View
  return (
    <div className="flex-1 bg-[#09090b] flex flex-col h-full overflow-y-auto">
      {/* Top Results Navigation */}
      <div className="border-b border-zinc-800 bg-[#0c0c10] px-6 py-2.5 flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-white">Results & Inspection:</span>
          {winner && (
            <span className="badge badge-emerald text-[10px]">
              <Award className="w-3 h-3" /> Winner: {winner.name?.split('—')[0] || winner.id}
            </span>
          )}
        </div>

        {/* Tab Controls */}
        <div className="flex items-center gap-1 text-xs">
          {[
            { id: 'recommendation', label: 'Recommendation', icon: Award },
            { id: 'comparison', label: 'Simulations', icon: Layers },
            { id: 'trace', label: 'Agent Trace', icon: Bot },
            { id: 'evidence', label: 'Evidence & Epistemics', icon: ShieldCheck },
            { id: 'registry', label: 'Model Registry', icon: Database },
          ].map((t) => {
            const IconComp = t.icon;
            const isTabActive = activeTab === t.id;

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-all font-medium ${
                  isTabActive
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                }`}
              >
                <IconComp className={`w-3.5 h-3.5 ${isTabActive ? 'text-indigo-400' : 'text-zinc-500'}`} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Results Body */}
      <div className="p-6 space-y-6 flex-1">
        {/* Winner Hero Card (Always visible on results canvas) */}
        {winner && (
          <div className="winner-hero p-5 rounded-2xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="badge badge-emerald text-[10px] font-bold">
                  Recommended Architecture
                </span>
                <h3 className="text-xl font-bold text-white mt-1">
                  {winner.name || winner.id}
                </h3>
                <p className="text-xs text-zinc-300 mt-0.5 font-mono">
                  {winner.topology_summary || winner.components?.join(' → ')}
                </p>
              </div>

              {/* KPI Stat Badges */}
              <div className="flex items-center gap-2.5 shrink-0">
                <div className="px-3 py-2 rounded-lg bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 uppercase font-semibold flex items-center justify-center gap-1">
                    <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.metrics?.p95_latency_ms != null ? `${winner.metrics.p95_latency_ms.toFixed(1)}ms` : '—'}
                  </div>
                </div>

                <div className="px-3 py-2 rounded-lg bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 uppercase font-semibold flex items-center justify-center gap-1">
                    <TrendingUp className="w-3 h-3 text-emerald-400" /> Throughput
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.metrics?.throughput_qps != null ? `${Math.round(winner.metrics.throughput_qps)} QPS` : '—'}
                  </div>
                </div>

                <div className="px-3 py-2 rounded-lg bg-zinc-950/80 border border-zinc-800 text-center">
                  <div className="text-[10px] text-zinc-400 uppercase font-semibold flex items-center justify-center gap-1">
                    <DollarSign className="w-3 h-3 text-amber-400" /> Monthly Cost
                  </div>
                  <div className="text-base font-bold text-white font-mono mt-0.5">
                    {winner.estimated_cost_monthly != null ? `$${Math.round(winner.estimated_cost_monthly)}` : '—'}
                  </div>
                </div>
              </div>
            </div>

            {/* Why It Won Bullets */}
            {sectionD?.why_it_won && sectionD.why_it_won.length > 0 && (
              <div className="pt-3 border-t border-emerald-500/20 text-xs text-zinc-200 space-y-1.5">
                <div className="font-semibold text-emerald-400 flex items-center gap-1 text-[11px] uppercase tracking-wider">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Key Rationale
                </div>
                {sectionD.why_it_won.map((r, idx) => (
                  <div key={idx} className="flex items-start gap-2 text-zinc-300">
                    <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Selected View Tab Content */}
        <div>
          {activeTab === 'recommendation' && <RecommendationView />}
          {activeTab === 'comparison' && <ArchitectureComparison />}
          {activeTab === 'trace' && <InvestigationTrace />}
          {activeTab === 'evidence' && <EvidenceDisclosure />}
          {activeTab === 'registry' && <ModelRegistryBrowser />}
        </div>
      </div>
    </div>
  );
}
