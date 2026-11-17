import React, { useState, useMemo, useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
import { inferWorkloadFromPrompt } from '../../utils/workloadInference';
import {
  Layers,
  Sparkles,
  ArrowRight,
  Sliders,
  ChevronDown,
  ChevronUp,
  Cpu,
  Clock,
  DollarSign,
  BarChart3,
  Server,
  Zap,
  CheckCircle2,
  RefreshCw,
  HelpCircle,
  Wand2,
  Info,
  Check
} from 'lucide-react';

export default function PromptStudio() {
  const {
    prompt,
    setPrompt,
    workloadInputs,
    setWorkloadInputs,
    updateWorkloadField,
    selectedPresetId,
    setSelectedPresetId,
    loadPreset,
    handleRunWorkflow,
    loading,
    response,
    goToResults,
    backendConnected,
    setIsFeatureManagerOpen,
    options,
    setOptions,
  } = useApp();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showManualTuning, setShowManualTuning] = useState(false);
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(true);

  // Compute smart inference from prompt
  const inferred = useMemo(() => {
    return inferWorkloadFromPrompt(prompt);
  }, [prompt]);

  // When prompt changes, if auto-sync is enabled, automatically update workload inputs
  useEffect(() => {
    if (autoSyncEnabled && inferred && selectedPresetId === 'custom') {
      setWorkloadInputs((prev) => ({
        ...prev,
        qps: inferred.qps,
        p95_sla_ms: inferred.p95_sla_ms,
        read_ratio: inferred.read_ratio,
        write_ratio: inferred.write_ratio,
        budget_usd: inferred.budget_usd,
      }));
    }
  }, [prompt, autoSyncEnabled, inferred, selectedPresetId, setWorkloadInputs]);

  const handlePromptChange = (e) => {
    const val = e.target.value;
    setPrompt(val);
    if (selectedPresetId !== 'custom') {
      setSelectedPresetId('custom');
    }
  };

  const handleApplyInference = () => {
    if (inferred) {
      setWorkloadInputs({
        qps: inferred.qps,
        p95_sla_ms: inferred.p95_sla_ms,
        read_ratio: inferred.read_ratio,
        write_ratio: inferred.write_ratio,
        budget_usd: inferred.budget_usd,
      });
      setAutoSyncEnabled(true);
    }
  };

  const handleManualFieldChange = (field, val) => {
    setAutoSyncEnabled(false);
    updateWorkloadField(field, val);
  };

  const handleKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      handleRunWorkflow();
    }
  };

  const handleOptionChange = (key, value) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col font-sans selection:bg-zinc-700 selection:text-white">
      {/* Top Header */}
      <header className="h-16 border-b border-white/[0.08] px-6 sm:px-10 lg:px-12 flex items-center justify-between shrink-0 bg-[#09090b]/80 backdrop-blur-md sticky top-0 z-30">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-zinc-100 flex items-center justify-center text-zinc-950 shadow-sm">
            <Layers className="w-4 h-4 stroke-[2.5]" />
          </div>
          <div className="flex items-center gap-2.5">
            <span className="font-bold text-base tracking-tight text-white">ORBIT</span>
            <span className="text-xs font-medium text-zinc-400 border-l border-white/10 pl-2.5">
              Architecture Copilot
            </span>
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {/* Backend Status */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-400">
            <span className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' : 'bg-amber-400'}`} />
            <span>{backendConnected ? 'Simulation Engine Online' : 'Local Verification'}</span>
          </div>

          <button
            type="button"
            onClick={() => setIsFeatureManagerOpen(true)}
            className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800/60 transition-colors text-xs font-medium flex items-center gap-1.5 cursor-pointer border border-transparent hover:border-zinc-700"
            title="Configure Features & Flags"
          >
            <Sliders className="w-4 h-4" />
            <span className="hidden md:inline text-xs">Flags</span>
          </button>

          {response && (
            <button
              type="button"
              onClick={goToResults}
              className="btn btn-secondary text-xs py-1.5 px-3.5 h-8 flex items-center gap-2 text-zinc-200 hover:text-white"
            >
              <span>View Active Blueprint</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </header>

      {/* Main Expansive Studio Canvas */}
      <main className="flex-1 overflow-y-auto px-6 sm:px-10 lg:px-12 py-10 sm:py-14 flex flex-col items-center">
        <div className="w-full max-w-5xl space-y-8">
          {/* Hero Section */}
          <div className="text-center space-y-3.5 max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-300 text-xs font-medium">
              <Sparkles className="w-3.5 h-3.5 text-zinc-400" />
              <span>Developer-First Architecture Copilot</span>
            </div>
            <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-white leading-tight">
              What backend are you building?
            </h1>
            <p className="text-sm sm:text-base text-zinc-400 max-w-2xl mx-auto leading-relaxed">
              Describe what you want to build in plain English. ORBIT automatically infers your traffic load, latency SLAs, and access patterns to design the optimal backend architecture.
            </p>
          </div>

          {/* Primary Prompt Input Card */}
          <div className="bg-[#121215] rounded-2xl border border-white/[0.08] shadow-2xl p-6 sm:p-8 space-y-5">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label htmlFor="prompt-input" className="text-xs sm:text-sm font-medium text-zinc-300 flex items-center gap-2">
                  <span>Describe your application, target users, or key features:</span>
                </label>
                <span className="text-xs text-zinc-500 font-mono hidden sm:inline">
                  Press ⌘ + Enter to simulate
                </span>
              </div>

              <div className="relative">
                <textarea
                  id="prompt-input"
                  rows={4}
                  value={prompt}
                  onChange={handlePromptChange}
                  onKeyDown={handleKeyDown}
                  placeholder="e.g. I want a backend for a photo sharing app with 100K daily active users, where people share photos, scroll feeds, like, and comment..."
                  className="w-full bg-[#09090b] border border-zinc-800 rounded-xl p-4 sm:p-5 text-sm sm:text-base text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 focus:ring-1 focus:ring-zinc-500 transition-all font-sans leading-relaxed resize-y min-h-[110px]"
                />
              </div>
            </div>

            {/* Quick 1-Click Scenario Starting Points */}
            <div className="space-y-2 pt-2 border-t border-white/[0.06]">
              <div className="text-xs font-medium text-zinc-400">
                Or start from a validated scenario baseline:
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {CANONICAL_PRESETS.map((preset) => {
                  const isSelected = selectedPresetId === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        loadPreset(preset);
                        setAutoSyncEnabled(false);
                      }}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'bg-zinc-800/90 border-zinc-600 text-white shadow-md'
                          : 'bg-[#09090b] border-zinc-800/80 hover:border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-900/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1.5 mb-1">
                        <span className="text-xs font-semibold tracking-tight">
                          {preset.title.replace(/Scenario \d+: /, '')}
                        </span>
                        {isSelected && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-400 line-clamp-1 mb-1.5 font-sans">
                        {preset.description}
                      </p>
                      <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono pt-1.5 border-t border-white/[0.06]">
                        <span>{preset.qps}</span>
                        <span>{preset.sla}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Intelligent Architecture Inferences (Translating natural language into plain-English architecture facts) */}
          {inferred && (
            <div className="bg-[#121215] rounded-2xl border border-zinc-800 p-6 sm:p-7 space-y-4 shadow-xl relative overflow-hidden">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                    <Wand2 className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm sm:text-base font-semibold text-white tracking-tight flex items-center gap-2">
                      <span>Architecture Inferences from Prompt</span>
                      <span className="badge-saas bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                        Auto-Derived
                      </span>
                    </h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      ORBIT interpreted your requirements into concrete distributed systems specifications:
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleApplyInference}
                    className="btn btn-secondary text-xs py-1.5 px-3 rounded-lg flex items-center gap-1.5 text-zinc-300 hover:text-white"
                    title="Re-synchronize simulation parameters from prompt"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Re-infer</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowManualTuning(!showManualTuning)}
                    className="btn btn-secondary text-xs py-1.5 px-3 rounded-lg flex items-center gap-1.5 text-zinc-300 hover:text-white"
                  >
                    <Sliders className="w-3.5 h-3.5" />
                    <span>{showManualTuning ? 'Hide Technical Knobs' : 'Tune Knobs Manually'}</span>
                  </button>
                </div>
              </div>

              {/* Inferred Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                {/* 1. Inferred Load */}
                <div className="p-3.5 rounded-xl bg-[#09090b] border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-400" />
                      <span>Traffic Target</span>
                    </span>
                    <span className="font-mono font-bold text-white text-sm">
                      ~{workloadInputs.qps} req/s
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">
                    {inferred.explanations.qps}
                  </p>
                </div>

                {/* 2. Inferred Latency */}
                <div className="p-3.5 rounded-xl bg-[#09090b] border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-zinc-300" />
                      <span>Speed Requirement</span>
                    </span>
                    <span className="font-mono font-bold text-white text-sm">
                      &lt; {workloadInputs.p95_sla_ms} ms
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">
                    {inferred.explanations.p95_sla_ms}
                  </p>
                </div>

                {/* 3. Inferred Access Pattern */}
                <div className="p-3.5 rounded-xl bg-[#09090b] border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium flex items-center gap-1.5">
                      <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Access Pattern</span>
                    </span>
                    <span className="font-mono font-bold text-white text-sm">
                      {Math.round(workloadInputs.read_ratio * 100)}% R / {Math.round(workloadInputs.write_ratio * 100)}% W
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">
                    {inferred.explanations.read_ratio}
                  </p>
                </div>

                {/* 4. Inferred Budget */}
                <div className="p-3.5 rounded-xl bg-[#09090b] border border-zinc-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400 font-medium flex items-center gap-1.5">
                      <DollarSign className="w-3.5 h-3.5 text-zinc-300" />
                      <span>Budget Limit</span>
                    </span>
                    <span className="font-mono font-bold text-white text-sm">
                      ${workloadInputs.budget_usd} / mo
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-snug">
                    {inferred.explanations.budget_usd}
                  </p>
                </div>
              </div>

              {/* Informative reassurance for non-technical users */}
              <div className="p-3 rounded-xl bg-zinc-900/80 border border-zinc-800/80 text-xs text-zinc-300 flex items-start gap-2.5">
                <Info className="w-4 h-4 text-zinc-400 shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-medium text-white">No technical setup required:</span>
                  <p className="text-zinc-400 text-xs">
                    You can click <strong className="text-white">Simulate &amp; Generate Blueprint</strong> immediately. ORBIT will test candidate topologies against this inferred load and prove which architecture works best for your app.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Manual Parameter Tuning (Revealed if user wants to tweak or when showManualTuning is true) */}
          {showManualTuning && (
            <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-6 sm:p-8 space-y-6 shadow-xl animate-in fade-in duration-200">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.06] pb-4">
                <div>
                  <h3 className="text-sm sm:text-base font-semibold text-white tracking-tight flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-zinc-300" />
                    <span>Manual Workload Configuration &amp; SLA Tuning</span>
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Adjust numeric parameters directly if you have specific hardware or SLA constraints:
                  </p>
                </div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 font-mono">
                  <span>{workloadInputs.qps} RPS</span>
                  <span className="text-zinc-600">•</span>
                  <span>{workloadInputs.p95_sla_ms}ms SLA</span>
                  <span className="text-zinc-600">•</span>
                  <span>${workloadInputs.budget_usd}/mo</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
                {/* 1. Target RPS */}
                <div className="bg-[#09090b] border border-zinc-800 rounded-xl p-4 space-y-2.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5 text-amber-400" />
                        <span>Traffic Volume (RPS)</span>
                      </label>
                      <span className="text-xs font-mono font-bold text-white">
                        {workloadInputs.qps} req/s
                      </span>
                    </div>
                    <input
                      type="number"
                      min="10"
                      max="5000"
                      step="25"
                      value={workloadInputs.qps}
                      onChange={(e) => handleManualFieldChange('qps', parseFloat(e.target.value) || 100)}
                      className="w-full bg-[#121215] border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-zinc-500"
                    />
                    <span className="text-[10px] text-zinc-500 mt-1 block">
                      Rule of thumb: 10K DAU ≈ 25 RPS · 100K DAU ≈ 240 RPS
                    </span>
                  </div>
                  <div className="flex items-center gap-1 pt-1">
                    {[100, 240, 500, 1000].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => handleManualFieldChange('qps', val)}
                        className={`flex-1 text-[11px] font-mono py-1 rounded border transition-colors cursor-pointer text-center ${
                          workloadInputs.qps === val
                            ? 'bg-zinc-800 border-zinc-500 text-white font-semibold'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 2. Latency SLA */}
                <div className="bg-[#09090b] border border-zinc-800 rounded-xl p-4 space-y-2.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-zinc-300" />
                        <span>p95 Latency SLA</span>
                      </label>
                      <span className="text-xs font-mono font-bold text-white">
                        &lt; {workloadInputs.p95_sla_ms} ms
                      </span>
                    </div>
                    <input
                      type="number"
                      min="10"
                      max="2000"
                      step="10"
                      value={workloadInputs.p95_sla_ms}
                      onChange={(e) => handleManualFieldChange('p95_sla_ms', parseFloat(e.target.value) || 100)}
                      className="w-full bg-[#121215] border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-zinc-500"
                    />
                    <span className="text-[10px] text-zinc-500 mt-1 block">
                      &lt; 100ms keeps mobile feed browsing smooth
                    </span>
                  </div>
                  <div className="flex items-center gap-1 pt-1">
                    {[50, 100, 150, 300].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => handleManualFieldChange('p95_sla_ms', val)}
                        className={`flex-1 text-[11px] font-mono py-1 rounded border transition-colors cursor-pointer text-center ${
                          workloadInputs.p95_sla_ms === val
                            ? 'bg-zinc-800 border-zinc-500 text-white font-semibold'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                        }`}
                      >
                        {val}ms
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Read / Write Split */}
                <div className="bg-[#09090b] border border-zinc-800 rounded-xl p-4 space-y-2.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                        <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Read / Write Ratio</span>
                      </label>
                      <span className="text-xs font-mono font-bold text-white">
                        {Math.round(workloadInputs.read_ratio * 100)}% R / {Math.round(workloadInputs.write_ratio * 100)}% W
                      </span>
                    </div>

                    {/* Dual color split indicator */}
                    <div className="h-2 w-full rounded-full overflow-hidden flex bg-zinc-800 my-2">
                      <div
                        className="bg-emerald-500 transition-all duration-200"
                        style={{ width: `${workloadInputs.read_ratio * 100}%` }}
                        title={`Read: ${Math.round(workloadInputs.read_ratio * 100)}%`}
                      />
                      <div
                        className="bg-amber-500 transition-all duration-200"
                        style={{ width: `${workloadInputs.write_ratio * 100}%` }}
                        title={`Write: ${Math.round(workloadInputs.write_ratio * 100)}%`}
                      />
                    </div>
                    <span className="text-[10px] text-zinc-500 mt-1 block">
                      Social/photo is 90/10; Transactional is 40/60
                    </span>
                  </div>

                  <div className="flex items-center gap-1 pt-1">
                    {[
                      { label: '90/10', read: 0.90 },
                      { label: '70/30', read: 0.70 },
                      { label: '50/50', read: 0.50 },
                      { label: '10/90', read: 0.10 },
                    ].map((preset) => (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => handleManualFieldChange('read_ratio', preset.read)}
                        className={`flex-1 text-[11px] font-mono py-1 rounded border transition-colors cursor-pointer text-center ${
                          Math.abs(workloadInputs.read_ratio - preset.read) < 0.02
                            ? 'bg-zinc-800 border-zinc-500 text-white font-semibold'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 4. Monthly Budget */}
                <div className="bg-[#09090b] border border-zinc-800 rounded-xl p-4 space-y-2.5 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
                        <DollarSign className="w-3.5 h-3.5 text-zinc-300" />
                        <span>Monthly Budget</span>
                      </label>
                      <span className="text-xs font-mono font-bold text-white">
                        ${workloadInputs.budget_usd} / mo
                      </span>
                    </div>
                    <input
                      type="number"
                      min="50"
                      max="5000"
                      step="50"
                      value={workloadInputs.budget_usd}
                      onChange={(e) => handleManualFieldChange('budget_usd', parseFloat(e.target.value) || 250)}
                      className="w-full bg-[#121215] border border-zinc-800 rounded-lg px-3 py-2 text-xs font-mono text-white focus:border-zinc-500"
                    />
                    <span className="text-[10px] text-zinc-500 mt-1 block">
                      $250 covers managed Redis + PostgreSQL tier
                    </span>
                  </div>
                  <div className="flex items-center gap-1 pt-1">
                    {[100, 250, 500, 1000].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => handleManualFieldChange('budget_usd', val)}
                        className={`flex-1 text-[11px] font-mono py-1 rounded border transition-colors cursor-pointer text-center ${
                          workloadInputs.budget_usd === val
                            ? 'bg-zinc-800 border-zinc-500 text-white font-semibold'
                            : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                        }`}
                      >
                        ${val}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Progressive Disclosure: Advanced Simulation Settings Accordion */}
              <div className="pt-2 border-t border-white/[0.06]">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center justify-between w-full text-left text-xs font-medium text-zinc-400 hover:text-zinc-200 py-1.5 cursor-pointer transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-zinc-500" />
                    <span>Advanced Simulation Parameters (SimPy queue duration, seeds, rounds)</span>
                  </span>
                  {showAdvanced ? (
                    <ChevronUp className="w-4 h-4 text-zinc-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-zinc-500" />
                  )}
                </button>

                {showAdvanced && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 mt-2 border-t border-white/[0.06]">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-zinc-400 block">
                        SimPy Duration (s)
                      </label>
                      <input
                        type="number"
                        min="1.0"
                        max="30.0"
                        step="0.5"
                        value={options.simulation_duration_seconds}
                        onChange={(e) => handleOptionChange('simulation_duration_seconds', parseFloat(e.target.value) || 5.0)}
                        className="w-full bg-[#09090b] border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-zinc-400 block">
                        Max Investigation Rounds
                      </label>
                      <input
                        type="number"
                        min="1"
                        max="5"
                        value={options.max_investigation_rounds}
                        onChange={(e) => handleOptionChange('max_investigation_rounds', parseInt(e.target.value) || 3)}
                        className="w-full bg-[#09090b] border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-zinc-400 block">
                        Simulation Random Seed
                      </label>
                      <input
                        type="number"
                        value={options.random_seed}
                        onChange={(e) => handleOptionChange('random_seed', parseInt(e.target.value) || 42)}
                        className="w-full bg-[#09090b] border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white font-mono"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Primary Action Button Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
            <div className="text-xs sm:text-sm text-zinc-400 flex items-center gap-2">
              <span>Ready to simulate and evaluate 3 candidate architectures against your requirements.</span>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={() => handleRunWorkflow()}
              className="w-full sm:w-auto btn btn-primary px-8 py-3.5 text-sm sm:text-base font-semibold rounded-xl flex items-center justify-center gap-2.5 cursor-pointer shadow-lg hover:shadow-xl disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-zinc-950" />
                  <span>Simulating Discrete Events...</span>
                </>
              ) : (
                <>
                  <span>Simulate &amp; Generate Blueprint</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
