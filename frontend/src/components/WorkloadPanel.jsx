import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { CANONICAL_PRESETS } from '../constants/presets';
import {
  Play,
  RotateCcw,
  Sliders,
  Check,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  Clock,
  DollarSign,
  Cpu,
  Layers,
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

  const sectionA = response?.section_a_workload;

  return (
    <div className="w-full lg:w-[420px] xl:w-[460px] bg-[#0c0c10] border-r border-zinc-800/80 flex flex-col shrink-0 h-full overflow-y-auto">
      <div className="p-5 space-y-6 flex-1">
        {/* Step 1: Scenario Selector */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
              1. Choose a Workload
            </span>
            <span className="text-[11px] text-zinc-500">1-click benchmark presets</span>
          </div>

          <div className="space-y-2.5">
            {CANONICAL_PRESETS.map((preset) => {
              const isSelected = selectedPresetId === preset.id;
              const icon = SCENARIO_ICONS[preset.id] || '📦';

              return (
                <div
                  key={preset.id}
                  onClick={() => loadPreset(preset)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-zinc-900 border-indigo-500 ring-1 ring-indigo-500 shadow-md shadow-indigo-500/10'
                      : 'bg-zinc-900/40 border-zinc-800 hover:border-zinc-700 hover:bg-zinc-900/80'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-base select-none">{icon}</span>
                      <div>
                        <div className="text-xs font-bold text-white flex items-center gap-1.5">
                          <span>{preset.title.split(': ')[1] || preset.title}</span>
                          <span className={`badge ${preset.badgeColor} text-[9px] py-0 px-1.5`}>
                            {preset.badge}
                          </span>
                        </div>
                      </div>
                    </div>
                    {isSelected && (
                      <span className="w-4 h-4 rounded-full bg-indigo-600 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5 text-white" />
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                    {preset.description}
                  </p>

                  <div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[11px]">
                    <span className="text-zinc-500">Target Winner:</span>
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      {preset.expectedWinner.split(' ')[1]}
                      <ArrowRight className="w-3 h-3 text-emerald-500" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Step 2: Prompt Input */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
              2. Workload Description
            </span>
            <span className="text-[11px] text-zinc-500">Natural language input</span>
          </div>

          <textarea
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your workload, target QPS, p95 latency requirements, write percentage, and budget..."
            className="text-xs font-sans bg-[#09090c] border border-zinc-800 focus:border-indigo-500 rounded-lg p-3 text-white placeholder:text-zinc-600 transition-all resize-none w-full"
          />
        </div>

        {/* Step 3: Simulation Parameters Toggle */}
        <div className="border border-zinc-800/80 rounded-xl overflow-hidden bg-zinc-900/30">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full p-3 flex items-center justify-between text-xs font-medium text-zinc-300 hover:text-white transition-colors"
          >
            <div className="flex items-center gap-2">
              <Sliders className="w-3.5 h-3.5 text-zinc-400" />
              <span>Simulation Controls</span>
            </div>
            {showAdvanced ? (
              <ChevronUp className="w-4 h-4 text-zinc-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {showAdvanced && (
            <div className="p-4 border-t border-zinc-800 space-y-4 bg-zinc-950/60">
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>SimPy Duration</span>
                  <span className="font-mono text-zinc-200">{options.simulation_duration_seconds}s</span>
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

              <div className="space-y-1">
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>Max Investigation Rounds</span>
                  <span className="font-mono text-zinc-200">{options.max_investigation_rounds} rounds</span>
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

              <div className="space-y-1">
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>Investigation Budget</span>
                  <span className="font-mono text-zinc-200">{options.investigation_budget_seconds}s</span>
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

        {/* Extracted Parameters Strip if available */}
        {sectionA && (
          <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2.5">
            <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider">
              Parsed Specifications
            </span>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-zinc-950 p-2 rounded border border-zinc-800/80">
                <div className="text-[10px] text-zinc-500">Target QPS</div>
                <div className="font-bold text-white font-mono">
                  {sectionA.target_qps ? `${sectionA.target_qps.toLocaleString()}` : '—'}
                </div>
              </div>
              <div className="bg-zinc-950 p-2 rounded border border-zinc-800/80">
                <div className="text-[10px] text-zinc-500">p95 SLA</div>
                <div className="font-bold text-cyan-400 font-mono">
                  {sectionA.p95_latency_ms ? `${sectionA.p95_latency_ms} ms` : '—'}
                </div>
              </div>
              <div className="bg-zinc-950 p-2 rounded border border-zinc-800/80">
                <div className="text-[10px] text-zinc-500">Write Ratio</div>
                <div className="font-bold text-amber-400 font-mono">
                  {sectionA.write_ratio != null ? `${Math.round(sectionA.write_ratio * 100)}%` : '—'}
                </div>
              </div>
              <div className="bg-zinc-950 p-2 rounded border border-zinc-800/80">
                <div className="text-[10px] text-zinc-500">Budget Cap</div>
                <div className="font-bold text-emerald-400 font-mono">
                  {sectionA.max_monthly_budget ? `$${sectionA.max_monthly_budget}` : '—'}
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Sticky Bottom Run Action Bar */}
      <div className="p-5 border-t border-zinc-800 bg-[#0c0c10] space-y-2.5 shrink-0">
        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading || !prompt.trim()}
          className="btn btn-primary w-full py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30"
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

        <div className="flex items-center justify-center gap-1.5 text-[11px] text-zinc-500">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Policy Gatekeeper: Live Docker Disabled</span>
        </div>
      </div>
    </div>
  );
}
