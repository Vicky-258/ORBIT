import React from 'react';
import { useApp } from '../../context/AppContext';
import { RotateCcw, ChevronDown } from 'lucide-react';
import { CANONICAL_PRESETS } from '../../constants/presets';

export default function AppHeader() {
  const {
    backendConnected,
    selectedPresetId,
    loadPreset,
    resetToDefault,
  } = useApp();

  return (
    <header className="h-13 border-b border-white/[0.08] bg-[#0c101a] px-5 sm:px-6 flex items-center justify-between shrink-0 z-20">
      {/* Brand: Logo & Product Title */}
      <div className="flex items-center gap-3">
        <div className="w-6 h-6 rounded-md bg-indigo-600 flex items-center justify-center font-bold text-white text-xs shadow-sm">
          A
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-semibold text-sm text-slate-100 tracking-tight">AADS</span>
          <span className="text-xs text-slate-400 font-normal">
            Architecture Copilot
          </span>
        </div>
      </div>

      {/* Center: Compact Scenario Selector */}
      <div className="flex items-center gap-2">
        <div className="relative inline-block text-left">
          <select
            value={selectedPresetId || 'custom'}
            onChange={(e) => {
              const matched = CANONICAL_PRESETS.find((p) => p.id === e.target.value);
              if (matched) loadPreset(matched);
            }}
            className="text-xs font-medium bg-[#141b2d] border border-white/[0.1] hover:border-white/[0.2] text-slate-200 rounded-lg px-3 py-1.5 cursor-pointer appearance-none pr-8 transition-all"
          >
            {CANONICAL_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} ({p.badge})
              </option>
            ))}
            {!selectedPresetId && (
              <option value="custom">Custom Workload Specification</option>
            )}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
            <ChevronDown className="w-3.5 h-3.5" />
          </div>
        </div>
      </div>

      {/* Right: Backend Status & Reset */}
      <div className="flex items-center gap-3">
        {/* Backend readiness indicator */}
        <div className="flex items-center gap-1.5 text-xs text-slate-400" title={backendConnected ? 'FastAPI Backend Connected' : 'Backend Disconnected'}>
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]' : 'bg-rose-400'
            }`}
          />
          <span className="hidden md:inline text-[11px] font-medium text-slate-400">
            {backendConnected ? 'Ready' : 'Offline'}
          </span>
        </div>

        <div className="h-3.5 w-px bg-white/[0.08]" />

        {/* Reset Action */}
        <button
          type="button"
          onClick={resetToDefault}
          className="btn btn-ghost text-xs py-1 px-2 text-slate-400 hover:text-slate-200"
          title="Reset to default baseline"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline text-xs">Reset</span>
        </button>
      </div>
    </header>
  );
}
