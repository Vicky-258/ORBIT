import React from 'react';
import { useApp } from '../context/AppContext';
import {
  Sparkles,
  Sliders,
  RotateCcw,
  Zap,
  Activity,
  Layers,
} from 'lucide-react';

export default function Navbar() {
  const {
    backendConnected,
    setIsFeatureManagerOpen,
    featureStates,
    response,
    setResponse,
  } = useApp();

  const enabledCount = Object.values(featureStates).filter(Boolean).length;

  return (
    <header className="h-14 border-b border-zinc-800 bg-[#09090b] px-4 sm:px-6 flex items-center justify-between shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-md bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
          <Zap className="w-4 h-4 text-white fill-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-white tracking-tight">AADS</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 font-mono">
              Studio v5.0
            </span>
          </div>
        </div>
        <div className="h-4 w-px bg-zinc-800 mx-1 hidden sm:block" />
        <span className="text-xs text-zinc-400 hidden sm:inline">
          Agentic Architecture Design & Discrete-Event Simulation
        </span>
      </div>

      {/* Header Actions */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Status */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs text-zinc-300">
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
            }`}
          />
          <span className="hidden md:inline">
            {backendConnected ? 'FastAPI 8000 Ready' : 'Backend Offline'}
          </span>
        </div>

        {/* Feature Manager Drawer Button */}
        <button
          type="button"
          onClick={() => setIsFeatureManagerOpen(true)}
          className="btn btn-secondary text-xs py-1 px-2.5 flex items-center gap-1.5"
        >
          <Sliders className="w-3.5 h-3.5 text-zinc-400" />
          <span>Features ({enabledCount})</span>
        </button>

        {/* Clear Results if any */}
        {response && (
          <button
            type="button"
            onClick={() => setResponse(null)}
            className="btn btn-ghost text-xs py-1 px-2 text-zinc-400 hover:text-zinc-200"
            title="Clear current results"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        )}
      </div>
    </header>
  );
}
