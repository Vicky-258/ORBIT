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
  RefreshCw,
  AlertTriangle
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
    setIsFeatureManagerOpen,
    backendConnected,
    selectedPresetId,
  } = useApp();

  const candidatesCount = response?.candidates?.length || response?.decision_result?.candidates?.length || 3;
  const decisionWorkload = response?.decision_result?.workload || response?.workload || {};

  const qps = workloadInputs.qps || decisionWorkload.request_rate_rps || 500;
  const slaMs = workloadInputs.p95_sla_ms || decisionWorkload.p95_latency_target_ms || 100;
  const readPct = Math.round((workloadInputs.read_ratio ?? 0.85) * 100);
  const writePct = Math.round((workloadInputs.write_ratio ?? 0.15) * 100);

  const NAV_ITEMS = [
    { id: 'blueprint', label: 'Architecture Blueprint', num: '01', icon: Award },
    { id: 'compare', label: `Compare Options (${candidatesCount})`, num: '02', icon: Layers },
    { id: 'technical', label: 'Technical Proof', num: '03', icon: ShieldCheck },
  ];

  return (
    <header className="border-b border-white/[0.08] bg-[#121215] px-4 sm:px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 shrink-0 z-20">
      {/* Left: Back to Chat / Prompt + Brand */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={goToChat}
          className="btn btn-secondary text-xs py-1.5 px-3 h-8 flex items-center gap-1.5 text-zinc-300 hover:text-white border-zinc-700 hover:border-zinc-500 transition-all cursor-pointer"
          title="Return to conversational chat (Esc)"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span className="font-medium">Back to Chat</span>
        </button>

        <button
          type="button"
          onClick={goToPrompt}
          className="text-xs py-1.5 px-2.5 h-8 flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
          title="Open manual tuning studio"
        >
          <Sliders className="w-3 h-3" />
          <span className="hidden sm:inline">Manual Tuning</span>
        </button>

        <div className="hidden md:flex items-center gap-2 pl-2 border-l border-white/[0.08]">
          <span className="font-bold text-sm tracking-tight text-white">ORBIT</span>
          <span className="text-[11px] text-zinc-400 font-mono">/ Copilot</span>
        </div>
      </div>

      {/* Center: Clean Main Tabs (Blueprint, Compare, Technical) */}
      <div className="inline-flex items-center gap-1 bg-[#09090b] p-1 rounded-lg border border-white/[0.08]">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveTab(item.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
                isActive
                  ? 'bg-white text-zinc-950 font-semibold shadow-xs'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-850'
              }`}
            >
              <span className={`text-[10px] font-mono px-1 py-0.2 rounded ${isActive ? 'bg-zinc-200 text-zinc-900' : 'text-zinc-500'}`}>
                {item.num}
              </span>
              <Icon className="w-3.5 h-3.5" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Right: Active Workload Pill, AI Prompt CTA, Status */}
      <div className="flex items-center gap-2.5">
        {/* Workload Parameter Pill */}
        <div
          onClick={goToPrompt}
          className="hidden xl:flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#09090b] border border-zinc-800 text-xs text-zinc-300 font-mono hover:border-zinc-600 cursor-pointer transition-colors"
          title="Click to modify parameters"
        >
          <Activity className="w-3 h-3 text-zinc-400" />
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
            className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[11px] font-medium cursor-pointer"
            title="Inputs modified. Click to view or re-run."
          >
            <AlertTriangle className="w-3 h-3" />
            <span className="hidden sm:inline">Modified</span>
          </div>
        )}

        {/* Generate Implementation Prompt CTA */}
        <button
          type="button"
          onClick={() => setIsPromptModalOpen(true)}
          className="btn btn-primary text-xs py-1.5 px-3 h-8 flex items-center gap-1.5"
          title="Generate Cursor / Copilot Implementation Prompt"
        >
          <Terminal className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">AI Prompt</span>
        </button>

        {/* Re-simulate Button */}
        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading}
          className="p-1.5 rounded-md text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
          title="Re-run Simulation"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-zinc-200' : ''}`} />
        </button>
      </div>
    </header>
  );
}
