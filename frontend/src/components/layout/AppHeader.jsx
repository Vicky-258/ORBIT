import React from 'react';
import { useApp } from '../../context/AppContext';
import { RotateCcw, Layers } from 'lucide-react';
import { CANONICAL_PRESETS } from '../../constants/presets';

export default function AppHeader() {
  const {
    backendConnected,
    selectedPresetId,
    loadPreset,
    resetToDefault,
  } = useApp();

  return (
    <header className="h-14 border-b border-slate-200 bg-white px-6 flex items-center justify-between shrink-0 z-20 shadow-2xs">
      {/* Brand: Logo & Product Title */}
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center text-white text-xs shadow-xs">
          <Layers className="w-3.5 h-3.5 stroke-[2.5]" />
        </div>
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-slate-900 tracking-tight">ORBIT</span>
          <span className="text-xs font-normal text-slate-400 border-l border-slate-200 pl-2">
            Architecture Copilot
          </span>
        </div>
      </div>

      {/* Center: Scenario Quick Switcher */}
      <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-100 border border-slate-200/60">
        {CANONICAL_PRESETS.map((p) => {
          const isSelected = selectedPresetId === p.id;
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => loadPreset(p)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                isSelected
                  ? 'bg-white text-slate-900 shadow-xs border border-slate-200/80 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-slate-900" />}
              <span>{p.title.replace(/Scenario \d+: /, '')}</span>
            </button>
          );
        })}
      </div>

      {/* Right: Backend Status & Reset */}
      <div className="flex items-center gap-3">
        {/* Backend readiness indicator */}
        <div
          className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs"
          title={backendConnected ? 'FastAPI Backend Ready' : 'Backend Offline'}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              backendConnected
                ? 'bg-emerald-500'
                : 'bg-rose-500'
            }`}
          />
          <span className="hidden md:inline text-[11px] font-medium text-slate-600">
            {backendConnected ? 'API Connected' : 'Offline'}
          </span>
        </div>

        <div className="h-4 w-px bg-slate-200" />

        {/* Reset Action */}
        <button
          type="button"
          onClick={resetToDefault}
          className="btn-saas-secondary text-xs py-1 px-2.5 rounded-md flex items-center gap-1.5 text-slate-600 hover:text-slate-900"
          title="Reset to default baseline"
        >
          <RotateCcw className="w-3 h-3" />
          <span className="hidden sm:inline text-xs">Reset</span>
        </button>
      </div>
    </header>
  );
}
