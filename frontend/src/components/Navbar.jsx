import React from 'react';
import { useApp } from '../context/AppContext';
import {
  Sparkles,
  Sliders,
  RotateCcw,
  Zap,
  Activity,
  Layers,
  ShieldCheck,
} from 'lucide-react';
import canonicalScenarios from '../constants/canonicalScenarios.json';
import { normalizeResponse } from '../api/normalizer';
import { CANONICAL_PRESETS } from '../constants/presets';

export default function Navbar() {
  const {
    backendConnected,
    setIsFeatureManagerOpen,
    featureStates,
    selectedPresetId,
    loadPreset,
    setResponse,
  } = useApp();

  const enabledCount = Object.values(featureStates).filter(Boolean).length;
  const currentPreset = CANONICAL_PRESETS.find((p) => p.id === selectedPresetId) || CANONICAL_PRESETS[0];

  const handleReset = () => {
    loadPreset(CANONICAL_PRESETS[0]);
  };

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#09090e] px-4 sm:px-6 flex items-center justify-between shrink-0 z-20">
      {/* Brand & Studio Status */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
          <Zap className="w-4 h-4 text-white fill-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-white tracking-tight">AADS</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
              STUDIO v5.0
            </span>
          </div>
        </div>
        <div className="h-4 w-px bg-zinc-800 mx-1 hidden sm:block" />
        <span className="text-xs text-zinc-400 hidden lg:inline">
          Agentic Architecture Design & Discrete-Event Simulation
        </span>
      </div>

      {/* Active Workload Pill (Center) */}
      <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-900/80 border border-zinc-800 text-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
        <span className="text-zinc-400">Active Scenario:</span>
        <span className="font-semibold text-white">{currentPreset.title}</span>
        <span className={`badge ${currentPreset.badgeColor} text-[9px] py-0 px-1.5`}>
          {currentPreset.badge}
        </span>
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Status */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300">
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
            }`}
          />
          <span className="hidden sm:inline">
            {backendConnected ? 'FastAPI 8000 Ready' : 'Backend Offline'}
          </span>
        </div>

        {/* Feature Manager Drawer Button */}
        <button
          type="button"
          onClick={() => setIsFeatureManagerOpen(true)}
          className="btn btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5 border-zinc-800 bg-zinc-900/90 hover:bg-zinc-800"
        >
          <Sliders className="w-3.5 h-3.5 text-zinc-400" />
          <span>Features ({enabledCount}/7)</span>
        </button>

        {/* Reset to Canonical Default */}
        <button
          type="button"
          onClick={handleReset}
          className="btn btn-ghost text-xs py-1.5 px-2 text-zinc-400 hover:text-zinc-200"
          title="Reset to Scenario 1"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Reset</span>
        </button>
      </div>
    </header>
  );
}
