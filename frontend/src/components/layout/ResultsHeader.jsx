import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  ArrowLeft,
  Layers,
  Award,
  ShieldCheck,
  Terminal,
  Activity,
  Sliders,
  AlertTriangle,
  RotateCcw
} from 'lucide-react';

export default function ResultsHeader() {
  const {
    goToChat,
    goToPrompt,
    activeTab,
    setActiveTab,
    response,
    workloadInputs,
    isStale,
    handleRunWorkflow,
    loading,
    setIsPromptModalOpen,
  } = useApp();

  const candidatesCount = response?.candidates?.length || response?.decision_result?.candidates?.length || 3;
  const decisionWorkload = response?.decision_result?.workload || response?.workload || {};

  const qps = workloadInputs.qps || decisionWorkload.request_rate_rps || 500;
  const slaMs = workloadInputs.p95_sla_ms || decisionWorkload.p95_latency_target_ms || 100;
  const readPct = Math.round((workloadInputs.read_ratio ?? decisionWorkload.read_ratio ?? 0.85) * 100);
  const writePct = Math.round((workloadInputs.write_ratio ?? decisionWorkload.write_ratio ?? 0.15) * 100);

  const NAV_ITEMS = [
    { id: 'blueprint', label: 'Architecture Blueprint', num: '01', icon: Award },
    { id: 'compare', label: `Compare Options (${candidatesCount})`, num: '02', icon: Layers },
    { id: 'technical', label: 'Technical Proof', num: '03', icon: ShieldCheck },
  ];

  return (
    <header className="border-b border-white/[0.08] bg-[#0c0c0e]/95 backdrop-blur-md px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3 shrink-0 z-20">
      {/* Left: Back to Chat + Breadcrumb */}
      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={goToChat}
          className="h-8 px-3 rounded-lg border border-white/[0.1] bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/[0.18] text-xs font-medium text-zinc-300 hover:text-white transition-all cursor-pointer flex items-center gap-1.5 shadow-xs"
          title="Return to conversational chat (Esc)"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Chat</span>
        </button>

        <button
          type="button"
          onClick={goToPrompt}
          className="h-8 px-2.5 rounded-lg border border-white/[0.06] hover:border-white/[0.12] bg-transparent hover:bg-white/[0.03] text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-all cursor-pointer flex items-center gap-1.5"
          title="Open manual tuning studio"
        >
          <Sliders className="w-3 h-3 text-zinc-500" />
          <span className="hidden sm:inline">Manual Tuning</span>
        </button>

        <div className="hidden md:flex items-center gap-2 pl-2.5 border-l border-white/[0.08]">
          <span className="font-semibold text-xs tracking-tight text-white">ORBIT</span>
          <span className="text-[11px] text-zinc-400 font-mono">/ Architecture Workspace</span>
        </div>
      </div>

      {/* Center: Premium Tab Switcher */}
      <nav className="inline-flex items-center gap-1 bg-[#141417] p-1 rounded-xl border border-white/[0.08] shadow-inner">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all cursor-pointer ${
                isActive
                  ? 'bg-zinc-100 text-zinc-950 font-semibold shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04]'
              }`}
            >
              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${isActive ? 'bg-zinc-200 text-zinc-900 font-bold' : 'bg-white/[0.04] text-zinc-400'}`}>
                {item.num}
              </span>
              <Icon className="w-3.5 h-3.5" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Right: Workload Parameters & Implementation Prompt CTA */}
      <div className="flex items-center gap-2.5">
        {/* Workload Parameter Pill */}
        <div
          onClick={goToPrompt}
          className="hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#141417] border border-white/[0.08] text-xs text-zinc-300 font-mono hover:border-zinc-500 cursor-pointer transition-colors shadow-xs"
          title="Operational constraints evaluated in SimPy. Click to modify."
        >
          <Activity className="w-3.5 h-3.5 text-zinc-400" />
          <span>{qps} RPS</span>
          <span className="text-zinc-600">·</span>
          <span>&lt;{slaMs}ms</span>
          <span className="text-zinc-600">·</span>
          <span>{readPct}R/{writePct}W</span>
        </div>

        {/* Stale Badge if inputs changed */}
        {isStale && (
          <div
            onClick={goToPrompt}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-medium cursor-pointer"
            title="Inputs modified. Click to view or re-run."
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Modified</span>
          </div>
        )}

        {/* Generate Implementation Prompt CTA */}
        <button
          type="button"
          onClick={() => setIsPromptModalOpen(true)}
          className="h-8 px-3.5 rounded-lg bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm cursor-pointer active:scale-95"
          title="Generate Cursor / Copilot Implementation Prompt"
        >
          <Terminal className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">AI Prompt</span>
        </button>
      </div>
    </header>
  );
}
