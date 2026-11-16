import React, { useState } from 'react';
import { useApp, CANONICAL_PRESETS } from '../../context/AppContext';
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
  } = useApp();

  const [showAdvanced, setShowAdvanced] = useState(false);

  const sectionA = response?.section_a_workload;

  return (
    <div className="glass-panel p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge badge-indigo">Section A</span>
            <h2 className="text-xl font-bold tracking-tight text-white">Workload Specification & Presets</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Describe your backend workload in natural language or choose a canonical benchmark scenario.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="btn btn-secondary text-xs"
          >
            <Sliders className="w-3.5 h-3.5" />
            {showAdvanced ? 'Hide Simulation Controls' : 'Fine-Tune Simulation'}
          </button>
        </div>
      </div>

      {/* 1-Click Canonical Presets */}
      <div>
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
          Canonical Benchmark Scenarios
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {CANONICAL_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              onClick={() => loadPreset(preset)}
              className="text-left p-3.5 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-slate-800/80 hover:border-indigo-500/50 transition-all flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className={`badge ${preset.badgeColor}`}>{preset.badge}</span>
                  <span className="text-[11px] text-slate-500 font-mono">1-click</span>
                </div>
                <h3 className="font-semibold text-sm text-slate-200 group-hover:text-indigo-300 transition-colors">
                  {preset.title}
                </h3>
                <p className="text-xs text-slate-400 mt-1 leading-relaxed">{preset.description}</p>
              </div>
              <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-400">
                <span>Target:</span>
                <span className="text-emerald-400 font-medium">{preset.expectedWinner.split(' ')[1]}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Natural Language Prompt Box */}
      <div className="space-y-2">
        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
          Natural Language Workload Description
        </label>
        <textarea
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe your workload, QPS, latency requirements, write percentage, and budget..."
          className="text-sm font-sans"
        />
      </div>

      {/* Advanced Simulation Controls */}
      {showAdvanced && (
        <div className="p-4 rounded-lg bg-slate-950/70 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Agent & SimPy Parameters
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

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">
                SimPy Duration ({options.simulation_duration_seconds}s)
              </label>
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
              <label className="block text-xs text-slate-400 mb-1">
                Investigation Rounds ({options.max_investigation_rounds})
              </label>
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
              <label className="block text-xs text-slate-400 mb-1">
                Investigation Budget ({options.investigation_budget_seconds}s)
              </label>
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
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
        <div className="text-xs text-slate-400 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
          Policy Gatekeeper: <strong className="text-slate-300">Live Docker Disabled (Audited)</strong>
        </div>

        <button
          type="button"
          onClick={() => handleRunWorkflow()}
          disabled={loading || !prompt.trim()}
          className="btn btn-primary w-full sm:w-auto px-6 py-2.5 text-sm shadow-lg shadow-indigo-500/20"
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
        <div className="p-3.5 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300 text-xs">
          <strong>Error executing agent workflow:</strong> {error}
        </div>
      )}

      {/* Extracted Specifications & Provenance (Section A Results) */}
      {sectionA && (
        <div className="mt-4 pt-4 border-t border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Extracted Workload Parameters
            </span>
            <span className="badge badge-emerald">Extracted by LangChain / Deterministic Fallback</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-indigo-400" /> Target Throughput
              </div>
              <div className="text-lg font-bold text-white mt-0.5">
                {sectionA.target_qps ? `${sectionA.target_qps.toLocaleString()} QPS` : '—'}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <Clock className="w-3 h-3 text-cyan-400" /> p95 Latency SLA
              </div>
              <div className="text-lg font-bold text-white mt-0.5">
                {sectionA.p95_latency_ms ? `${sectionA.p95_latency_ms} ms` : '—'}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <Cpu className="w-3 h-3 text-amber-400" /> Write Ratio
              </div>
              <div className="text-lg font-bold text-white mt-0.5">
                {sectionA.write_ratio != null ? `${Math.round(sectionA.write_ratio * 100)}%` : '—'}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <div className="text-[11px] text-slate-400 flex items-center gap-1">
                <DollarSign className="w-3 h-3 text-emerald-400" /> Monthly Budget
              </div>
              <div className="text-lg font-bold text-white mt-0.5">
                {sectionA.max_monthly_budget ? `$${sectionA.max_monthly_budget}/mo` : '—'}
              </div>
            </div>
          </div>

          {/* Epistemic Badges: Facts vs Assumptions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="p-3 rounded-lg bg-slate-900/40 border border-slate-800/80">
              <div className="text-xs font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
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

            <div className="p-3 rounded-lg bg-slate-900/40 border border-slate-800/80">
              <div className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
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
