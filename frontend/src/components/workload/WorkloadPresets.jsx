import React from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
import { Check } from 'lucide-react';

export default function WorkloadPresets() {
  const { selectedPresetId, loadPreset } = useApp();

  return (
    <div className="space-y-2.5">
      <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
        Choose a Baseline Workload Preset
      </label>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
        {CANONICAL_PRESETS.map((preset) => {
          const isSelected = selectedPresetId === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => loadPreset(preset)}
              className={`p-3 rounded-xl border text-left transition-all flex flex-col justify-between ${
                isSelected
                  ? 'bg-indigo-950/40 border-indigo-500/60 shadow-sm'
                  : 'bg-black/30 border-white/[0.08] hover:border-white/[0.16]'
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-1">
                  <span className={`badge ${preset.badgeColor} text-[10px] py-0 px-1.5 font-mono`}>
                    {preset.badge}
                  </span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-indigo-400" />}
                </div>
                <div className="text-xs font-semibold text-slate-100 mt-1">
                  {preset.title.replace(/Scenario \d+: /, '')}
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                  {preset.description}
                </p>
              </div>

              <div className="text-[10px] font-mono text-slate-400 mt-2.5 pt-2 border-t border-white/[0.04] flex items-center justify-between">
                <span>{preset.qps}</span>
                <span>{preset.sla}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
