import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import {
  TrendingUp,
  DollarSign,
  Cpu,
  BarChart3,
  Sliders,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

export default function CostSensitivityAnalyzer() {
  const { response } = useApp();
  const [scaleFactor, setScaleFactor] = useState(1.0);
  const [costMultiplier, setCostMultiplier] = useState(1.0);

  const candidates = response?.section_c_comparison?.candidates || [
    { id: 'arch_a', name: 'Direct PostgreSQL', cost_monthly: 220, p95_latency_ms: 18.5 },
    { id: 'arch_b', name: 'PostgreSQL + Redis Cache', cost_monthly: 380, p95_latency_ms: 8.2 },
    { id: 'arch_c', name: 'Kafka Async Pipeline', cost_monthly: 650, p95_latency_ms: 5.1 },
  ];

  return (
    <div className="glass-panel p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge badge-cyan">Plugin / Extension</span>
            <h2 className="text-xl font-bold tracking-tight text-white">Cost & Scale Sensitivity Analyzer</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Example modular plugin: analyze how candidate architecture operational costs scale under 0.5x to 5.0x traffic growth.
          </p>
        </div>
        <div>
          <span className="badge badge-indigo text-xs">
            <Sparkles className="w-3.5 h-3.5" /> Dynamic Plugin Slot
          </span>
        </div>
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-semibold text-slate-300">
              Traffic Scale Factor ({scaleFactor.toFixed(1)}x)
            </label>
            <span className="text-[11px] font-mono text-cyan-400">{Math.round(scaleFactor * 100)}% load</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="5.0"
            step="0.1"
            value={scaleFactor}
            onChange={(e) => setScaleFactor(parseFloat(e.target.value))}
          />
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-semibold text-slate-300">
              Cloud Infrastructure Price Multiplier ({costMultiplier.toFixed(1)}x)
            </label>
            <span className="text-[11px] font-mono text-emerald-400">AWS / GCP baseline</span>
          </div>
          <input
            type="range"
            min="0.8"
            max="2.0"
            step="0.1"
            value={costMultiplier}
            onChange={(e) => setCostMultiplier(parseFloat(e.target.value))}
          />
        </div>
      </div>

      {/* Scaled Projections Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {candidates.map((cand) => {
          const baseCost = cand.cost_monthly ?? cand.estimated_cost_monthly ?? 250;
          const projectedCost = Math.round(baseCost * (1 + (scaleFactor - 1) * 0.65) * costMultiplier);
          const baseLatency = cand.p95_latency_ms ?? cand.metrics?.p95_latency_ms ?? 12.0;
          const projectedLatency = (baseLatency * (1 + (scaleFactor - 1) * 0.25)).toFixed(1);

          return (
            <div key={cand.id} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-slate-200">{cand.name || cand.id}</span>
                <span className="badge badge-slate text-[10px] font-mono">{cand.id}</span>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center gap-1">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Projected Cost:
                  </span>
                  <span className="font-bold text-white font-mono">${projectedCost}/mo</span>
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center gap-1">
                    <TrendingUp className="w-3.5 h-3.5 text-indigo-400" /> Est. p95 Latency:
                  </span>
                  <span className="font-mono text-slate-300">{projectedLatency} ms</span>
                </div>
              </div>

              {/* Mini visual bar */}
              <div className="pt-2 border-t border-slate-800/80">
                <div className="text-[10px] text-slate-500 mb-1">Scale headroom</div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{ width: `${Math.min(100, Math.round((projectedCost / 1200) * 100))}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
