import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { CANONICAL_PRESETS } from '../constants/presets';
import {
  Play,
  Sliders,
  Check,
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

const SCENARIO_ICONS = {
  ecommerce: '🛒',
  transactional: '💳',
  analytics: '⚡',
};

export default function WorkloadPanel() {
  const {
    prompt,
    setPrompt,
    options,
    setOptions,
    loading,
    error,
    handleRunWorkflow,
    loadPreset,
    selectedPresetId,
    response,
  } = useApp();

  const [showAdvanced, setShowAdvanced] = useState(false);
  const workload = response?.workload || response?.section_a_workload;

  return (
    <aside className="w-full lg:w-[380px] xl:w-[400px] bg-[#0c101a] border-r border-white/[0.08] flex flex-col shrink-0 h-full overflow-y-auto">
      <div className="p-5 space-y-6 flex-1">
        {/* Step 1: Scenarios */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              1. Select a Scenario
            </span>
            <span className="text-[11px] text-slate-500">1-click presets</span>
          </div>

          <div className="space-y-2.5">
            {CANONICAL_PRESETS.map((preset) => {
              const isSelected = selectedPresetId === preset.id;
              const icon = SCENARIO_ICONS[preset.id] || '📦';

              return (
                <div
                  key={preset.id}
                  onClick={() => loadPreset(preset)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all duration-150 ${
                    isSelected
                      ? 'bg-indigo-950/20 border-indigo-500/60 ring-1 ring-indigo-500/40 shadow-sm'
                      : 'bg-white/[0.02] border-white/[0.06] hover:border-white/[0.14] hover:bg-white/[0.04]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-base select-none">{icon}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-100">
                          {preset.title.split(': ')[1] || preset.title}
                        </span>
                        <span className={`badge ${preset.badgeColor} text-[10px] py-0 px-2 font-medium`}>
                          {preset.badge}
                        </span>
                      </div>
                    </div>
                    {isSelected && (
                      <span className="w-4 h-4 rounded-full bg-indigo-600 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-white" />
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    {preset.description}
                  </p>

                  {/* Specs line */}
                  <div className="mt-3 pt-2.5 border-t border-white/[0.06] flex items-center justify-between text-[11px]">
                    <span className="text-slate-400 font-mono text-[11px]">
                      {preset.qps} • {preset.sla} • {preset.budget}
                    </span>
                    <span className="text-emerald-400 font-medium text-[11px] flex items-center gap-1">
                      {preset.expectedWinner.split(' ')[1]}
                      <ArrowRight className="w-3 h-3 text-emerald-500" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Step 2: Workload Description */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              2. Workload Description
            </span>
            <span className="text-[11px] text-slate-500 font-mono">{prompt.length} chars</span>
          </div>

          <textarea
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your workload, target QPS, p95 latency requirements, and budget..."
            className="text-xs font-sans bg-white/[0.03] border border-white/[0.08] focus:border-indigo-500 rounded-lg p-3 text-slate-100 placeholder:text-slate-600 transition-all resize-none w-full"
          />
          <div className="text-[11px] text-slate-500 flex items-center justify-between">
            <span>Natural language parsed with deterministic fallback</span>
          </div>
        </div>

        {/* Step 3: Simulation Parameters Collapsible */}
        <div className="border border-white/[0.08] rounded-xl overflow-hidden bg-white/[0.02]">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full p-3 flex items-center justify-between text-xs font-medium text-slate-300 hover:text-white transition-colors"
          >
            <div className="flex items-center gap-2">
              <Sliders className="w-3.5 h-3.5 text-slate-400" />
              <span>Simulation Controls</span>
            </div>
            {showAdvanced ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {showAdvanced && (
            <div className="p-4 border-t border-white/[0.08] space-y-4 bg-black/20">
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>SimPy Duration</span>
                  <span className="font-mono text-slate-200">{options.simulation_duration_seconds}s</span>
                </div>
                <input
                  type="range"
                  min="2.0"
                  max="20.0"
                  step="1.0"
                  value={options.simulation_duration_seconds}
                  onChange={(e) =>
                    setOptions({ ...options, simulation_duration_seconds: parseFloat(e.target.value) })
                  }
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>Max Investigation Rounds</span>
                  <span className="font-mono text-slate-200">{options.max_investigation_rounds} rounds</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={options.max_investigation_rounds}
                  onChange={(e) =>
                    setOptions({ ...options, max_investigation_rounds: parseInt(e.target.value, 10) })
                  }
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>Investigation Budget</span>
                  <span className="font-mono text-slate-200">{options.investigation_budget_seconds}s</span>
                </div>
                <input
                  type="range"
                  min="10.0"
                  max="120.0"
                  step="10.0"
                  value={options.investigation_budget_seconds}
                  onChange={(e) =>
                    setOptions({ ...options, investigation_budget_seconds: parseFloat(e.target.value) })
                  }
                />
              </div>
            </div>
          )}
        </div>

        {/* Extracted Specifications */}
        {workload && (
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06] space-y-2.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Parsed Specifications
            </span>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-white/[0.03] p-2.5 rounded-lg border border-white/[0.06]">
                <div className="text-[10px] text-slate-500 font-medium">Target QPS</div>
                <div className="font-semibold text-slate-200 font-mono mt-0.5">
                  {workload.qps ? `${workload.qps.toLocaleString()} RPS` : '—'}
                </div>
              </div>
              <div className="bg-white/[0.03] p-2.5 rounded-lg border border-white/[0.06]">
                <div className="text-[10px] text-slate-500 font-medium">p95 SLA Target</div>
                <div className="font-semibold text-slate-200 font-mono mt-0.5">
                  {workload.p95_sla_ms ? `${workload.p95_sla_ms} ms` : '—'}
                </div>
              </div>
              <div className="bg-white/[0.03] p-2.5 rounded-lg border border-white/[0.06]">
                <div className="text-[10px] text-slate-500 font-medium">Traffic Mix</div>
                <div className="font-semibold text-slate-200 font-mono mt-0.5">
                  {workload.read_ratio != null ? `${Math.round(workload.read_ratio * 100)}% R / ${Math.round(workload.write_ratio * 100)}% W` : '—'}
                </div>
              </div>
              <div className="bg-white/[0.03] p-2.5 rounded-lg border border-white/[0.06]">
                <div className="text-[10px] text-slate-500 font-medium">Monthly Budget</div>
                <div className="font-semibold text-slate-200 font-mono mt-0.5">
                  {workload.budget_usd ? `$${workload.budget_usd}/mo` : '—'}
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="p-5 border-t border-white/[0.08] bg-[#0c101a] space-y-2.5 shrink-0">
        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading || !prompt.trim()}
          className="btn btn-primary w-full py-2.5 text-xs sm:text-sm font-semibold flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Simulating Architectures...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Run AADS Agent Simulation</span>
            </>
          )}
        </button>

        <div className="flex items-center justify-center gap-1.5 text-[11px] text-slate-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Policy Gatekeeper: Live Docker Disabled</span>
        </div>
      </div>
    </aside>
  );
}
