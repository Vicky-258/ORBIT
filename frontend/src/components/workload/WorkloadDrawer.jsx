import React, { useEffect } from 'react';
import { useApp } from '../../context/AppContext';
import { X, Play, Sliders } from 'lucide-react';
import WorkloadPresets from './WorkloadPresets';
import AdvancedSettings from './AdvancedSettings';

export default function WorkloadDrawer() {
  const {
    isWorkloadDrawerOpen,
    setIsWorkloadDrawerOpen,
    prompt,
    setPrompt,
    workloadInputs,
    updateWorkloadField,
    handleRunWorkflow,
    loading,
  } = useApp();

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isWorkloadDrawerOpen) {
        setIsWorkloadDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isWorkloadDrawerOpen, setIsWorkloadDrawerOpen]);

  if (!isWorkloadDrawerOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    handleRunWorkflow();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
        onClick={() => setIsWorkloadDrawerOpen(false)}
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-xl bg-[#0c101a] border-l border-white/[0.08] h-full shadow-2xl flex flex-col z-10 overflow-hidden">
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#090d16]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100 tracking-tight">
                Configure Workload Requirements
              </h2>
              <p className="text-[11px] text-slate-400">
                Adjust traffic, latency SLA, and budget to evaluate architectures
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsWorkloadDrawerOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Body (Scrollable) */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 1. Presets */}
          <WorkloadPresets />

          {/* 2. Numeric Workload Inputs */}
          <div className="space-y-4 pt-2 border-t border-white/[0.06]">
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Core Performance & SLA Inputs
            </label>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-300 block mb-1.5">
                  Expected Traffic (RPS)
                </label>
                <input
                  type="number"
                  min="10"
                  max="5000"
                  step="10"
                  value={workloadInputs.qps}
                  onChange={(e) => updateWorkloadField('qps', parseFloat(e.target.value) || 100)}
                  className="font-mono text-xs"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">Offered requests per second</span>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-300 block mb-1.5">
                  Max Response Time (p95 ms)
                </label>
                <input
                  type="number"
                  min="5"
                  max="1000"
                  step="5"
                  value={workloadInputs.p95_sla_ms}
                  onChange={(e) => updateWorkloadField('p95_sla_ms', parseFloat(e.target.value) || 100)}
                  className="font-mono text-xs"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">Maximum acceptable SLA tail latency</span>
              </div>
            </div>

            {/* Traffic Mix Slider */}
            <div className="p-3.5 rounded-xl bg-black/30 border border-white/[0.06] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">Traffic Mix (Reads vs. Writes):</span>
                <span className="font-mono font-semibold text-slate-100">
                  {Math.round((workloadInputs.read_ratio ?? 0.85) * 100)}% Read / {Math.round((workloadInputs.write_ratio ?? 0.15) * 100)}% Write
                </span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.95"
                step="0.05"
                value={workloadInputs.read_ratio ?? 0.85}
                onChange={(e) => updateWorkloadField('read_ratio', parseFloat(e.target.value))}
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                <span>Write-Heavy (OLTP)</span>
                <span>Balanced</span>
                <span>Read-Heavy (Catalog)</span>
              </div>
            </div>

            {/* Budget */}
            <div>
              <label className="text-xs font-medium text-slate-300 block mb-1.5">
                Maximum Monthly Cloud Budget ($/mo)
              </label>
              <input
                type="number"
                min="20"
                max="5000"
                step="10"
                value={workloadInputs.budget_usd || 250}
                onChange={(e) => updateWorkloadField('budget_usd', parseFloat(e.target.value) || 250)}
                className="font-mono text-xs"
              />
              <span className="text-[10px] text-slate-500 mt-1 block">Infrastructure hosting spending ceiling</span>
            </div>
          </div>

          {/* 3. Natural Language Workload Description */}
          <div className="space-y-2 pt-2 border-t border-white/[0.06]">
            <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Natural Language Description
            </label>
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Design a backend for an e-commerce API expecting approximately 500 requests per second with p95 latency under 100 ms..."
              className="text-xs bg-black/40 border border-white/[0.08] focus:border-indigo-500 rounded-lg p-3 text-slate-100 placeholder:text-slate-600 transition-all resize-none w-full"
            />
            <span className="text-[10px] text-slate-500 block">
              Parsed by AADS into structured traffic and constraint parameters.
            </span>
          </div>

          {/* 4. Advanced Simulation Settings */}
          <AdvancedSettings />
        </form>

        {/* Drawer Footer */}
        <div className="p-4 px-6 border-t border-white/[0.08] bg-[#090d16] flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setIsWorkloadDrawerOpen(false)}
            className="btn btn-ghost text-xs py-2 px-4 text-slate-400 hover:text-slate-200"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            disabled={loading}
            className="btn btn-primary text-xs py-2 px-5 flex items-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Simulating...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Save &amp; Run Simulation</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
