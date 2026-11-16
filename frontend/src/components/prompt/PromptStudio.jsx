import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
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
  RefreshCw
} from 'lucide-react';

export default function PromptStudio() {
  const {
    prompt,
    setPrompt,
    workloadInputs,
    updateWorkloadField,
    selectedPresetId,
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
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 flex flex-col font-sans selection:bg-indigo-500/30">
      {/* Top Bar */}
      <header className="h-14 border-b border-white/[0.08] px-6 flex items-center justify-between shrink-0 bg-[#0d121c]">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
            <Layers className="w-3.5 h-3.5 stroke-[2.5]" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-white">AADS</span>
            <span className="text-[11px] font-medium text-slate-400 border-l border-white/10 pl-2">
              Architecture Copilot
            </span>
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {/* Backend Status */}
          <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.06] text-[11px] text-slate-400">
            <span className={`w-1.5 h-1.5 rounded-full ${backendConnected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            <span>{backendConnected ? 'Engine Ready' : 'Local Mode'}</span>
          </div>

          <button
            type="button"
            onClick={() => setIsFeatureManagerOpen(true)}
            className="p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors text-xs font-medium flex items-center gap-1 cursor-pointer"
            title="Configure Features & Flags"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span className="hidden md:inline text-[11px]">Flags</span>
          </button>

          {response && (
            <button
              type="button"
              onClick={goToResults}
              className="btn btn-secondary text-xs py-1 px-2.5 h-7.5 flex items-center gap-1.5 text-slate-200 hover:text-white"
            >
              <span>View Current Blueprint</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </header>

      {/* Main Centered Studio Canvas */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-10 flex flex-col items-center">
        <div className="w-full max-w-3xl space-y-8 my-auto">
          {/* Hero Heading */}
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-1">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Developer-First Architecture Copilot</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              What backend are you building?
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto leading-relaxed">
              Describe your workload requirements to simulate candidate topologies, evaluate latency &amp; cost trade-offs, and generate implementation blueprints.
            </p>
          </div>

          {/* Primary Prompt Input Card */}
          <div className="bg-[#111622] rounded-xl border border-white/[0.08] shadow-lg shadow-black/20 p-4 sm:p-5 space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="prompt-input" className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Workload Description &amp; Architecture Intent</span>
                <span className="text-[11px] text-slate-500 font-mono">⌘ + Enter to simulate</span>
              </label>

              <div className="relative">
                <textarea
                  id="prompt-input"
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="e.g. An e-commerce backend expecting 500 requests/sec, 90% reads, p95 latency under 100ms, and monthly infrastructure budget under $250..."
                  className="w-full bg-[#0b0f17] border border-white/10 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all font-sans leading-relaxed resize-y min-h-[96px]"
                />
              </div>
            </div>

            {/* Quick 1-Click Scenario Chips */}
            <div className="space-y-2 pt-1 border-t border-white/[0.05]">
              <div className="text-[11px] font-medium text-slate-400">
                Or select a realistic starting workload:
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {CANONICAL_PRESETS.map((preset) => {
                  const isSelected = selectedPresetId === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => loadPreset(preset)}
                      className={`p-2.5 rounded-lg border text-left transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'bg-indigo-950/40 border-indigo-500/50 text-white shadow-xs'
                          : 'bg-[#0d121c] border-white/[0.06] hover:border-white/15 text-slate-300 hover:text-white'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="text-xs font-semibold tracking-tight">
                          {preset.title.replace(/Scenario \d+: /, '')}
                        </span>
                        {isSelected && (
                          <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                        )}
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                        <span>{preset.qps}</span>
                        <span>{preset.sla}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Workload Specifications (Directly Visible, Clean & Low Friction) */}
          <div className="bg-[#111622] rounded-xl border border-white/[0.08] p-4 sm:p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.05] pb-3">
              <div>
                <h3 className="text-xs font-semibold text-white tracking-tight flex items-center gap-2">
                  <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Workload Parameters &amp; Target Constraints</span>
                </h3>
                <p className="text-[11px] text-slate-400">
                  Explicit simulation parameters derived from your requirements
                </p>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">
                {workloadInputs.qps} RPS · {workloadInputs.p95_sla_ms}ms SLA
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* 1. Target RPS */}
              <div className="bg-[#0b0f17] border border-white/[0.06] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <Zap className="w-3 h-3 text-amber-400" />
                    <span>Throughput (RPS)</span>
                  </label>
                  <span className="text-xs font-mono font-semibold text-white">
                    {workloadInputs.qps} req/s
                  </span>
                </div>
                <input
                  type="number"
                  min="10"
                  max="5000"
                  step="25"
                  value={workloadInputs.qps}
                  onChange={(e) => updateWorkloadField('qps', parseFloat(e.target.value) || 100)}
                  className="w-full bg-[#111622] border border-white/10 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                />
                <div className="flex items-center gap-1 pt-1">
                  {[100, 300, 500, 1000].map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => updateWorkloadField('qps', val)}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                        workloadInputs.qps === val
                          ? 'bg-indigo-600/30 border-indigo-500/50 text-indigo-300'
                          : 'bg-white/[0.03] border-white/[0.06] text-slate-400 hover:text-white'
                      }`}
                    >
                      {val}
                    </button>
                  ))}
                </div>
              </div>

              {/* 2. Latency SLA */}
              <div className="bg-[#0b0f17] border border-white/[0.06] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-sky-400" />
                    <span>p95 Latency SLA</span>
                  </label>
                  <span className="text-xs font-mono font-semibold text-white">
                    &lt; {workloadInputs.p95_sla_ms} ms
                  </span>
                </div>
                <input
                  type="number"
                  min="10"
                  max="2000"
                  step="10"
                  value={workloadInputs.p95_sla_ms}
                  onChange={(e) => updateWorkloadField('p95_sla_ms', parseFloat(e.target.value) || 100)}
                  className="w-full bg-[#111622] border border-white/10 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                />
                <div className="flex items-center gap-1 pt-1">
                  {[50, 100, 150, 300].map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => updateWorkloadField('p95_sla_ms', val)}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                        workloadInputs.p95_sla_ms === val
                          ? 'bg-sky-600/30 border-sky-500/50 text-sky-300'
                          : 'bg-white/[0.03] border-white/[0.06] text-slate-400 hover:text-white'
                      }`}
                    >
                      {val}ms
                    </button>
                  ))}
                </div>
              </div>

              {/* 3. Read / Write Split */}
              <div className="bg-[#0b0f17] border border-white/[0.06] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <BarChart3 className="w-3 h-3 text-emerald-400" />
                    <span>Read / Write Ratio</span>
                  </label>
                  <span className="text-xs font-mono font-semibold text-white">
                    {Math.round(workloadInputs.read_ratio * 100)}% Read / {Math.round(workloadInputs.write_ratio * 100)}% Write
                  </span>
                </div>

                {/* Split Visual Indicator */}
                <div className="h-2 w-full rounded-full overflow-hidden flex bg-slate-800">
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
                      onClick={() => updateWorkloadField('read_ratio', preset.read)}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                        Math.abs(workloadInputs.read_ratio - preset.read) < 0.02
                          ? 'bg-emerald-600/30 border-emerald-500/50 text-emerald-300'
                          : 'bg-white/[0.03] border-white/[0.06] text-slate-400 hover:text-white'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 4. Monthly Budget */}
              <div className="bg-[#0b0f17] border border-white/[0.06] rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <DollarSign className="w-3 h-3 text-purple-400" />
                    <span>Monthly Budget Limit</span>
                  </label>
                  <span className="text-xs font-mono font-semibold text-white">
                    ${workloadInputs.budget_usd} / mo
                  </span>
                </div>
                <input
                  type="number"
                  min="50"
                  max="5000"
                  step="50"
                  value={workloadInputs.budget_usd}
                  onChange={(e) => updateWorkloadField('budget_usd', parseFloat(e.target.value) || 250)}
                  className="w-full bg-[#111622] border border-white/10 rounded px-2.5 py-1.5 text-xs text-white font-mono"
                />
                <div className="flex items-center gap-1 pt-1">
                  {[100, 250, 500, 1000].map((val) => (
                    <button
                      key={val}
                      type="button"
                      onClick={() => updateWorkloadField('budget_usd', val)}
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors cursor-pointer ${
                        workloadInputs.budget_usd === val
                          ? 'bg-purple-600/30 border-purple-500/50 text-purple-300'
                          : 'bg-white/[0.03] border-white/[0.06] text-slate-400 hover:text-white'
                      }`}
                    >
                      ${val}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Progressive Disclosure: Advanced Simulation Settings Accordion */}
            <div className="pt-2 border-t border-white/[0.05]">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center justify-between w-full text-left text-xs font-medium text-slate-400 hover:text-slate-200 py-1 cursor-pointer transition-colors"
              >
                <span className="flex items-center gap-1.5">
                  <Cpu className="w-3.5 h-3.5 text-slate-500" />
                  <span>Advanced Simulation Parameters</span>
                </span>
                {showAdvanced ? (
                  <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                )}
              </button>

              {showAdvanced && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 mt-2 border-t border-white/[0.05]">
                  <div>
                    <label className="text-[11px] font-medium text-slate-400 block mb-1">
                      SimPy Duration (s)
                    </label>
                    <input
                      type="number"
                      min="1.0"
                      max="30.0"
                      step="0.5"
                      value={options.simulation_duration_seconds}
                      onChange={(e) => handleOptionChange('simulation_duration_seconds', parseFloat(e.target.value) || 5.0)}
                      className="w-full bg-[#0b0f17] border border-white/10 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-medium text-slate-400 block mb-1">
                      Investigation Rounds
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="5"
                      value={options.max_investigation_rounds}
                      onChange={(e) => handleOptionChange('max_investigation_rounds', parseInt(e.target.value) || 3)}
                      className="w-full bg-[#0b0f17] border border-white/10 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-medium text-slate-400 block mb-1">
                      Random Seed
                    </label>
                    <input
                      type="number"
                      value={options.random_seed}
                      onChange={(e) => handleOptionChange('random_seed', parseInt(e.target.value) || 42)}
                      className="w-full bg-[#0b0f17] border border-white/10 rounded px-2 py-1 text-xs text-white font-mono"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Primary Action Button */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              <span>Ready to evaluate 3 candidate architectures against your SLA.</span>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={() => handleRunWorkflow()}
              className="w-full sm:w-auto btn btn-primary px-6 py-2.5 text-sm font-semibold rounded-lg flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-white/5 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
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
