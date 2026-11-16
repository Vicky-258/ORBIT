import React from 'react';
import { useApp } from '../../context/AppContext';
import { RotateCcw, ChevronDown, Sparkles, Check } from 'lucide-react';
import { CANONICAL_PRESETS } from '../../constants/presets';

export default function AppHeader() {
  const {
    backendConnected,
    selectedPresetId,
    loadPreset,
    resetToDefault,
  } = useApp();

  return (
    <header className="h-14 border-b border-white/[0.06] bg-[#080b12]/90 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-20">
      {/* Brand: Logo & Product Title */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 flex items-center justify-center font-bold text-white text-xs shadow-[0_0_12px_rgba(99,102,241,0.4)] border border-white/20">
          <Sparkles className="w-3.5 h-3.5 fill-white text-white" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-white tracking-tight">AADS</span>
          <span className="text-[11px] font-medium text-slate-400 border-l border-white/[0.1] pl-2">
            Architecture Copilot
          </span>
        </div>
      </div>

      {/* Center: Scenario Quick Switcher */}
      <div className="flex items-center gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
        {CANONICAL_PRESETS.map((p) => {
          const isSelected = selectedPresetId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => loadPreset(p)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                isSelected
                  ? 'bg-white/10 text-white shadow-sm border border-white/10'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
              }`}
            >
              {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />}
              <span>{p.title.replace(/Scenario \d+: /, '')}</span>
            </button>
          );
        })}
      </div>

      {/* Right: Backend Status & Reset */}
      <div className="flex items-center gap-3">
        {/* Backend readiness indicator */}
        <div
          className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.06] text-xs"
          title={backendConnected ? 'FastAPI Backend Ready' : 'Backend Offline'}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected
                ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]'
                : 'bg-rose-400'
            }`}
          />
          <span className="hidden md:inline text-[11px] font-medium text-slate-400 font-mono">
            {backendConnected ? 'API Ready' : 'Offline'}
          </span>
        </div>

        <div className="h-4 w-px bg-white/[0.08]" />

        {/* Reset Action */}
        <button
          type="button"
          onClick={resetToDefault}
          className="btn-saas-secondary text-xs py-1 px-2.5 rounded-lg flex items-center gap-1.5 text-slate-400 hover:text-white"
          title="Reset to default baseline"
        >
          <RotateCcw className="w-3 h-3" />
          <span className="hidden sm:inline text-xs">Reset</span>
        </button>
      </div>
    </header>
  );
}
