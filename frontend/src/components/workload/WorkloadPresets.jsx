import React from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
import { Check, Sparkles } from 'lucide-react';

export default function WorkloadPresets() {
  const { selectedPresetId, loadPreset } = useApp();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
          Workload Presets
        </label>
        <span className="text-[11px] text-slate-500 font-mono">1-Click Configuration</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {CANONICAL_PRESETS.map((preset) => {
          const isSelected = selectedPresetId === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => loadPreset(preset)}
              className={`p-4 rounded-xl border text-left transition-all flex flex-col justify-between cursor-pointer relative group ${
                isSelected
                  ? 'bg-gradient-to-b from-indigo-950/60 to-slate-900/90 border-indigo-500/60 shadow-lg shadow-indigo-950/50 ring-1 ring-indigo-400/40'
                  : 'bg-slate-900/60 border-white/[0.08] hover:border-white/[0.16] hover:bg-slate-900/80 shadow-xs'
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1">
                  <span className={`badge-saas ${preset.badgeColor} text-[10px] py-0 px-2 font-mono`}>
                    {preset.badge}
                  </span>
                  {isSelected && (
                    <div className="w-4 h-4 rounded-full bg-indigo-500 flex items-center justify-center text-white">
                      <Check className="w-2.5 h-2.5 stroke-[3]" />
                    </div>
                  )}
                </div>

                <div className="text-xs font-bold text-white tracking-tight mt-1">
                  {preset.title.replace(/Scenario \d+: /, '')}
                </div>

                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed font-sans">
                  {preset.description}
                </p>
              </div>

              <div className="text-[10px] font-mono text-slate-400 mt-3 pt-2.5 border-t border-white/[0.04] flex items-center justify-between">
                <span className="font-semibold text-slate-300">{preset.qps}</span>
                <span className="text-slate-500">{preset.sla}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
