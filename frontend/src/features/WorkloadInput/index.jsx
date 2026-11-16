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
  Server,
  Layers,
  Zap,
} from 'lucide-react';

const PRESET_METRICS = {
  ecommerce: [
    { label: 'Offered Load', val: '2,000 QPS', color: 'text-indigo-400' },
    { label: 'Traffic Mix', val: '85% Read / 15% Write', color: 'text-emerald-400' },
    { label: 'p95 SLA', val: '< 50 ms', color: 'text-cyan-400' },
    { label: 'Budget Cap', val: '$800/mo', color: 'text-amber-400' },
  ],
  transactional: [
    { label: 'Offered Load', val: '400 QPS', color: 'text-indigo-400' },
    { label: 'Traffic Mix', val: '25% Read / 75% Write', color: 'text-amber-400' },
    { label: 'p95 SLA', val: '< 80 ms', color: 'text-cyan-400' },
    { label: 'Budget Cap', val: '$400/mo', color: 'text-emerald-400' },
  ],
  analytics: [
    { label: 'Offered Load', val: '3,500 QPS', color: 'text-indigo-400' },
    { label: 'Traffic Mix', val: '10% Read / 90% Write', color: 'text-rose-400' },
    { label: 'p95 SLA', val: '< 100 ms', color: 'text-cyan-400' },
    { label: 'Budget Cap', val: '$1,200/mo', color: 'text-purple-400' },
  ],
};

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
    setActiveTab,
  } = useApp();

  const [showAdvanced, setShowAdvanced] = useState(false);

  const sectionA = response?.section_a_workload;

  return (
    <div className="space-y-6">
      {/* Main Workload Card */}
      <div className="glass-panel p-6 sm:p-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="badge badge-indigo text-xs">Section A</span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Workload Specification & Presets
              </h2>
            </div>
            <p className="text-sm text-slate-300 mt-1">
              Select a canonical benchmark scenario or enter custom requirements in natural language.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className={`btn text-xs px-3.5 py-2 ${
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
            <label className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Canonical Benchmark Scenarios
            </label>
            <span className="text-xs text-slate-400 font-mono">1-click to load parameters</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {CANONICAL_PRESETS.map((preset) => {
              const isSelected = selectedPresetId === preset.id;
              const metrics = PRESET_METRICS[preset.id] || [];

              return (
                <div
                  key={preset.id}
                  onClick={() => loadPreset(preset)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                    isSelected
                      ? 'bg-slate-900 border-indigo-500 ring-2 ring-indigo-500/40 shadow-xl shadow-indigo-500/10'
                      : 'bg-slate-900/80 border-slate-700/80 hover:border-slate-500 hover:bg-slate-900'
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between mb-2.5">
                      <span className={`badge ${preset.badgeColor} text-[10px]`}>
                        {preset.badge}
                      </span>
                      {isSelected ? (
                        <span className="badge badge-indigo text-[10px] flex items-center gap-1 font-bold">
                          <Check className="w-3 h-3" /> Selected
                        </span>
                      ) : (
                        <span className="text-[11px] text-slate-400 font-mono">Click to load</span>
                      )}
                    </div>

                    <h3 className="font-bold text-sm text-white mb-1.5">
                      {preset.title}
                    </h3>
                    <p className="text-xs text-slate-300 leading-relaxed mb-3">
                      {preset.description}
                    </p>

                    {/* Metric Pills Grid */}
                    <div className="grid grid-cols-2 gap-1.5 py-2 border-t border-slate-800">
                      {metrics.map((m, idx) => (
                        <div key={idx} className="bg-slate-950/70 rounded px-2 py-1 border border-slate-800/80">
                          <div className="text-[10px] text-slate-400">{m.label}</div>
                          <div className={`text-xs font-bold font-mono ${m.color}`}>{m.val}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="pt-2.5 border-t border-slate-800 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Target Winner:</span>
                    <span className="text-emerald-400 font-bold flex items-center gap-1">
                      {preset.expectedWinner.split(' ')[1]}
                      <ArrowRight className="w-3 h-3 text-emerald-400" />
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
            <label className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Natural Language Workload Description
            </label>
            <span className="text-xs text-slate-400">Parsed via LangChain with deterministic fallback</span>
          </div>
          <textarea
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe your workload, QPS, latency requirements, write percentage, and budget..."
            className="text-sm font-sans bg-slate-950 border border-slate-700 focus:border-indigo-400 rounded-xl p-3.5 text-white placeholder:text-slate-500 transition-all resize-y"
          />
        </div>

        {/* Advanced Simulation Controls */}
        {showAdvanced && (
          <div className="p-5 rounded-xl bg-slate-950/90 border border-slate-700/80 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <Sliders className="w-4 h-4 text-indigo-400" />
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
                className="text-xs text-slate-300 hover:text-white flex items-center gap-1 font-medium"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Reset Defaults
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
              <div>
                <div className="flex justify-between text-xs text-slate-300 mb-1.5 font-medium">
                  <span>SimPy Duration</span>
                  <span className="font-mono text-indigo-400 font-bold">{options.simulation_duration_seconds}s</span>
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
                <div className="flex justify-between text-xs text-slate-300 mb-1.5 font-medium">
                  <span>Investigation Rounds</span>
                  <span className="font-mono text-cyan-400 font-bold">{options.max_investigation_rounds} rounds</span>
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
                <div className="flex justify-between text-xs text-slate-300 mb-1.5 font-medium">
                  <span>Investigation Budget</span>
                  <span className="font-mono text-amber-400 font-bold">{options.investigation_budget_seconds}s</span>
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
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-800">
          <div className="flex items-center gap-2 text-xs text-slate-300">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Policy Gatekeeper: <strong className="text-white">Live Docker Disabled (Audited Policy)</strong></span>
          </div>

          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            disabled={loading || !prompt.trim()}
            className="btn btn-primary w-full sm:w-auto px-7 py-3 text-sm shadow-xl shadow-indigo-500/30 flex items-center justify-center gap-2 font-bold"
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
          <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-700 text-rose-200 text-xs">
            <strong>Error executing agent workflow:</strong> {error}
          </div>
        )}

        {/* Extracted Specifications & Provenance (Section A Results) */}
        {sectionA && (
          <div className="mt-4 pt-5 border-t border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                Extracted Workload Parameters
              </span>
              <span className="badge badge-emerald">Extracted by LangChain / Deterministic Fallback</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-300 flex items-center gap-1 font-medium">
                  <TrendingUp className="w-3.5 h-3.5 text-indigo-400" /> Target Throughput
                </div>
                <div className="text-xl font-bold text-white mt-1">
                  {sectionA.target_qps ? `${sectionA.target_qps.toLocaleString()} QPS` : '—'}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-300 flex items-center gap-1 font-medium">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" /> p95 Latency SLA
                </div>
                <div className="text-xl font-bold text-white mt-1">
                  {sectionA.p95_latency_ms ? `${sectionA.p95_latency_ms} ms` : '—'}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-300 flex items-center gap-1 font-medium">
                  <Cpu className="w-3.5 h-3.5 text-amber-400" /> Write Ratio
                </div>
                <div className="text-xl font-bold text-white mt-1">
                  {sectionA.write_ratio != null ? `${Math.round(sectionA.write_ratio * 100)}%` : '—'}
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-300 flex items-center gap-1 font-medium">
                  <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Monthly Budget
                </div>
                <div className="text-xl font-bold text-white mt-1">
                  {sectionA.max_monthly_budget ? `$${sectionA.max_monthly_budget}/mo` : '—'}
                </div>
              </div>
            </div>

            {/* Epistemic Badges: Facts vs Assumptions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-xs font-bold text-emerald-400 mb-2.5 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" /> Explicit User Facts ({sectionA.facts?.length || 0})
                </div>
                {sectionA.facts && sectionA.facts.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {sectionA.facts.map((fact, idx) => (
                      <span key={idx} className="badge badge-emerald text-xs">
                        {fact.key}: {String(fact.value)}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">No explicit constraints parsed.</p>
                )}
              </div>

              <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800">
                <div className="text-xs font-bold text-amber-400 mb-2.5 flex items-center gap-1.5">
                  <HelpCircle className="w-4 h-4" /> Agent Assumptions ({sectionA.assumptions?.length || 0})
                </div>
                {sectionA.assumptions && sectionA.assumptions.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {sectionA.assumptions.map((assump, idx) => (
                      <span key={idx} className="badge badge-amber text-xs" title={assump.rationale || ''}>
                        {assump.key}: {String(assump.value)}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 italic">All parameters were provided as facts.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Workspace System Capabilities Panel (Fills the view so there is no empty void) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-5 space-y-2 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Server className="w-4 h-4 text-indigo-400" />
              Candidate Topologies
            </span>
            <span className="badge badge-slate text-[10px]">3 Active</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Evaluates Direct PostgreSQL 16 (Arch A), Cached Reads with Redis (Arch B), and Async Kafka Pipeline (Arch C).
          </p>
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">Simulation Engine:</span>
            <span className="text-indigo-400 font-mono font-semibold">SimPy 4.1</span>
          </div>
        </div>

        <div className="glass-panel p-5 space-y-2 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-emerald-400" />
              Decision Policy
            </span>
            <span className="badge badge-emerald text-[10px]">Audited</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            Stage 1 hard feasibility filter eliminates SLA violators; Stage 2 multi-objective Pareto ranking selects the winner.
          </p>
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">Gatekeeper Status:</span>
            <span className="text-emerald-400 font-mono font-semibold">Strict Pass</span>
          </div>
        </div>

        <div className="glass-panel p-5 space-y-2 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-cyan-400" />
              Empirical Baselines
            </span>
            <span className="badge badge-cyan text-[10px]">Frozen</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            PostgreSQL 16 empirical performance model grounded in reconciled Phase 4F.4.5 live benchmark pilot (24 models).
          </p>
          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">Manifest SHA-256:</span>
            <span className="text-cyan-400 font-mono text-[11px] truncate max-w-[140px]" title="69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6">
              69d3e068...77a6
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
