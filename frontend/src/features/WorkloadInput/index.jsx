import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
import {
  Sparkles,
  Play,
  RotateCcw,
  Sliders,
  CheckCircle2,
  HelpCircle,
  TrendingUp,
  Clock,
  DollarSign,
  Cpu,
  ArrowRight,
  ShieldCheck,
  Check,
} from 'lucide-react';

export default function WorkloadInput() {
  const {
    prompt,
    setPrompt,
    options,
    setOptions,
    response,
    loading,
    error,
    handleRunWorkflow,
    loadPreset,
    selectedPresetId,
  } = useApp();

  const [showAdvanced, setShowAdvanced] = useState(false);

  const sectionA = response?.section_a_workload;

  return (
    <div className="glass-panel p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="badge badge-indigo text-xs">Section A</span>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Workload Specification & Presets
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Describe your backend workload in natural language or choose a canonical benchmark scenario.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`btn text-xs px-3 py-2 ${
              showAdvanced ? 'btn-primary' : 'btn-secondary'
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>{showAdvanced ? 'Hide Simulation Controls' : 'Fine-Tune Simulation'}</span>
          </button>
        </div>
      </div>

      {/* 1-Click Canonical Presets */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Canonical Benchmark Scenarios
          </label>
          <span className="text-[11px] text-slate-500 font-mono">Select a preset to load parameters</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {CANONICAL_PRESETS.map((preset) => {
            const isSelected = selectedPresetId === preset.id;

            return (
              <div
                key={preset.id}
                onClick={() => loadPreset(preset)}
                className={`relative p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between select-none ${
                  isSelected
                    ? 'bg-slate-900 border-indigo-500 ring-2 ring-indigo-500/30 shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-900/60 border-slate-800 hover:border-slate-700 hover:bg-slate-900/90'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`badge ${preset.badgeColor} text-[10px]`}>
                      {preset.badge}
                    </span>
                    {isSelected && (
                      <span className="flex items-center gap-1 text-[11px] text-indigo-400 font-medium">
                        <Check className="w-3.5 h-3.5" /> Active
                      </span>
                    )}
                  </div>

                  <h3 className="font-semibold text-sm text-slate-100 mb-1.5">
                    {preset.title}
                  </h3>
                  <p className="text-xs text-slate-400 leading-relaxed mb-3">
                    {preset.description}
                  </p>
                </div>

                <div className="pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Expected Winner:</span>
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

      {/* Natural Language Prompt Box */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Natural Language Workload Description
          </label>
          <span className="text-[11px] text-slate-500">Natural language parsed via LangChain / Regex</span>
        </div>
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your workload, QPS, latency requirements, write percentage, and budget..."
          className="text-sm font-sans bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl p-3.5 text-slate-100 placeholder:text-slate-600 transition-all resize-y"
        />
      </div>

      {/* Advanced Simulation Controls */}
      {showAdvanced && (
        <div className="p-4 sm:p-5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              Agent & SimPy Simulation Parameters
            </span>
            <button
              type="button"
              onClick={() =>
                setOptions({
                  auto_benchmark_missing: true,
                  force_synthetic: true,
                  simulation_duration_seconds: 5.0,
                  random_seed: 42,
                  include_async: true,
                  include_unsupported: false,
                  max_investigation_rounds: 3,
                  investigation_budget_seconds: 60.0,
                })
              }
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" /> Reset Defaults
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                <span>SimPy Duration</span>
                <span className="font-mono text-indigo-400">{options.simulation_duration_seconds}s</span>
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
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                <span>Max Investigation Rounds</span>
                <span className="font-mono text-cyan-400">{options.max_investigation_rounds} rounds</span>
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
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                <span>Investigation Budget</span>
                <span className="font-mono text-amber-400">{options.investigation_budget_seconds}s</span>
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
        </div>
      )}

      {/* Action Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-800/80">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Policy Gatekeeper: <strong className="text-slate-300">Live Docker Disabled (Audited)</strong></span>
        </div>

        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading || !prompt.trim()}
          className="btn btn-primary w-full sm:w-auto px-6 py-2.5 text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>Investigating & Simulating Architectures...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Run AADS Agent Investigation</span>
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
          <strong>Error executing agent workflow:</strong> {error}
        </div>
      )}

      {/* Extracted Specifications & Provenance (Section A Results) */}
      {sectionA && (
        <div className="mt-4 pt-5 border-t border-slate-800/80 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Extracted Workload Parameters
            </span>
            <span className="badge badge-emerald">Extracted by LangChain / Deterministic Fallback</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5 text-indigo-400" /> Target Throughput
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {sectionA.target_qps ? `${sectionA.target_qps.toLocaleString()} QPS` : '—'}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-cyan-400" /> p95 Latency SLA
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {sectionA.p95_latency_ms ? `${sectionA.p95_latency_ms} ms` : '—'}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-amber-400" /> Write Ratio
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {sectionA.write_ratio != null ? `${Math.round(sectionA.write_ratio * 100)}%` : '—'}
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Monthly Budget
              </div>
              <div className="text-lg font-bold text-white mt-1">
                {sectionA.max_monthly_budget ? `$${sectionA.max_monthly_budget}/mo` : '—'}
              </div>
            </div>
          </div>

          {/* Epistemic Badges: Facts vs Assumptions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
            <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800/80">
              <div className="text-xs font-semibold text-emerald-400 mb-2.5 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Explicit User Facts ({sectionA.facts?.length || 0})
              </div>
              {sectionA.facts && sectionA.facts.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {sectionA.facts.map((fact, idx) => (
                    <span key={idx} className="badge badge-emerald text-[11px]">
                      {fact.key}: {String(fact.value)}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No explicit constraints parsed.</p>
              )}
            </div>

            <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800/80">
              <div className="text-xs font-semibold text-amber-400 mb-2.5 flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5" /> Agent Assumptions ({sectionA.assumptions?.length || 0})
              </div>
              {sectionA.assumptions && sectionA.assumptions.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {sectionA.assumptions.map((assump, idx) => (
                    <span key={idx} className="badge badge-amber text-[11px]" title={assump.rationale || ''}>
                      {assump.key}: {String(assump.value)}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">All parameters were provided as facts.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
