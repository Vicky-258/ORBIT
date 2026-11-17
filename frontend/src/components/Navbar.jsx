import React from 'react';
import { useApp } from '../context/AppContext';
import {
  Sliders,
  RotateCcw,
  Zap,
} from 'lucide-react';
import { CANONICAL_PRESETS } from '../constants/presets';

export default function Navbar() {
  const {
    backendConnected,
    setIsFeatureManagerOpen,
    featureStates,
    selectedPresetId,
    loadPreset,
  } = useApp();

  const enabledCount = Object.values(featureStates).filter(Boolean).length;
  const currentPreset = CANONICAL_PRESETS.find((p) => p.id === selectedPresetId) || CANONICAL_PRESETS[0];

  const handleReset = () => {
    loadPreset(CANONICAL_PRESETS[0]);
  };

  return (
    <header className="h-14 border-b border-white/[0.08] bg-[#0a0d14] px-5 sm:px-6 flex items-center justify-between shrink-0 z-20">
      {/* Brand & Studio Status */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shadow-sm">
          <Zap className="w-4 h-4 text-white fill-white" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-semibold text-sm text-slate-100 tracking-tight">ORBIT</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-400 font-mono">
            v5.3
          </span>
        </div>
        <div className="h-4 w-px bg-white/[0.08] mx-1 hidden sm:block" />
        <span className="text-xs text-slate-400 hidden lg:inline font-normal">
          Orchestrated Reasoning and Benchmarking for Infrastructure Testing
        </span>
      </div>

      {/* Active Workload Pill (Center) */}
      <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs">
        <span className="text-slate-400">Scenario:</span>
        <span className="font-medium text-slate-200">{currentPreset.title}</span>
        <span className={`badge ${currentPreset.badgeColor} text-[10px] py-0 px-2`}>
          {currentPreset.badge}
        </span>
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-2.5">
        {/* Backend Status Indicator */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-xs text-slate-300">
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' : 'bg-rose-400'
            }`}
          />
          <span className="hidden sm:inline text-[11px] font-medium">
            {backendConnected ? 'FastAPI 8000 Ready' : 'Backend Offline'}
          </span>
        </div>

        {/* Feature Manager Drawer Button */}
        <button
          type="button"
          onClick={() => setIsFeatureManagerOpen(true)}
          className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5 text-slate-300 hover:text-white"
        >
          <Sliders className="w-3.5 h-3.5 text-slate-400" />
          <span>Features ({enabledCount}/7)</span>
        </button>

        {/* Reset to Canonical Default */}
        <button
          type="button"
          onClick={handleReset}
          className="btn btn-ghost text-xs py-1.5 px-2 text-slate-400 hover:text-slate-200"
          title="Reset to Scenario 1"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline text-xs">Reset</span>
        </button>
      </div>
    </header>
  );
}
