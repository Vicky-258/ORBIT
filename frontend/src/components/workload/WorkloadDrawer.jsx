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
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={() => setIsWorkloadDrawerOpen(false)}
      />

      {/* Slide-over Drawer Panel */}
      <div className="relative w-full max-w-xl bg-white border-l border-slate-200 h-full shadow-2xl flex flex-col z-10 overflow-hidden">
        {/* Drawer Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between shrink-0 bg-white">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 shadow-2xs">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 tracking-tight">
                Configure Workload Requirements
              </h2>
              <p className="text-xs text-slate-500">
                Adjust traffic, latency SLA, and budget to evaluate architectures
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsWorkloadDrawerOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Drawer Body (Scrollable) */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* 1. Presets */}
          <WorkloadPresets />

          {/* 2. Numeric Workload Inputs */}
          <div className="space-y-4 pt-2 border-t border-slate-100">
            <label className="text-xs font-semibold text-slate-700 block">
              Core Performance &amp; SLA Inputs
            </label>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-700 block mb-1.5">
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
                <span className="text-[11px] text-slate-500 mt-1 block">Offered requests per second</span>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-700 block mb-1.5">
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
                <span className="text-[11px] text-slate-500 mt-1 block">Maximum acceptable SLA tail latency</span>
              </div>
            </div>

            {/* Traffic Mix Slider */}
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-700 font-medium">Traffic Mix (Reads vs. Writes):</span>
                <span className="font-mono font-semibold text-slate-900">
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
              <div className="flex justify-between text-[11px] text-slate-500 font-sans">
                <span>Write-Heavy (OLTP)</span>
                <span>Balanced</span>
                <span>Read-Heavy (Catalog)</span>
              </div>
            </div>

            {/* Budget */}
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1.5">
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
              <span className="text-[11px] text-slate-500 mt-1 block">Infrastructure hosting spending ceiling</span>
            </div>
          </div>

          {/* 3. Natural Language Workload Description */}
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <label className="text-xs font-semibold text-slate-700 block">
              Natural Language Description
            </label>
            <textarea
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Design a backend for an e-commerce API expecting approximately 500 requests per second with p95 latency under 100 ms..."
              className="text-xs bg-white border border-slate-300 focus:border-slate-500 rounded-lg p-3 text-slate-900 placeholder:text-slate-400 transition-all resize-none w-full"
            />
            <span className="text-[11px] text-slate-500 block">
              Parsed by ORBIT into structured traffic and constraint parameters.
            </span>
          </div>

          {/* 4. Advanced Simulation Settings */}
          <AdvancedSettings />
        </form>

        {/* Drawer Footer */}
        <div className="p-4 px-6 border-t border-slate-200 bg-slate-50 flex items-center justify-between gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setIsWorkloadDrawerOpen(false)}
            className="btn-saas-secondary text-xs py-2 px-4"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            disabled={loading}
            className="btn-saas-primary text-xs py-2 px-5 flex items-center gap-2"
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
