import React from 'react';
import { useApp } from '../../context/AppContext';
import { CANONICAL_PRESETS } from '../../constants/presets';
import { Check, Sparkles } from 'lucide-react';

export default function WorkloadPresets() {
  const { selectedPresetId, loadPreset } = useApp();

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-slate-700 block">
          Workload Presets
        </label>
        <span className="text-xs text-slate-500 font-sans">1-Click Scenarios</span>
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
                  ? 'bg-slate-900 text-white border-slate-900 shadow-sm'
                  : 'bg-slate-50 border-slate-200 hover:border-slate-300 hover:bg-white text-slate-800 shadow-2xs'
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1">
                  <span className={`badge-saas ${isSelected ? 'bg-white/20 text-white border-white/30' : 'bg-white text-slate-700 border-slate-200 shadow-2xs'} text-[10px] py-0 px-2`}>
                    {preset.badge}
                  </span>
                  {isSelected && (
                    <div className="w-4 h-4 rounded-full bg-white flex items-center justify-center text-slate-900">
                      <Check className="w-2.5 h-2.5 stroke-[3]" />
                    </div>
                  )}
                </div>

                <div className={`text-xs font-bold ${isSelected ? 'text-white' : 'text-slate-900'} tracking-tight mt-1`}>
                  {preset.title.replace(/Scenario \d+: /, '')}
                </div>

                <p className={`text-xs ${isSelected ? 'text-slate-300' : 'text-slate-500'} line-clamp-2 leading-relaxed font-sans`}>
                  {preset.description}
                </p>
              </div>

              <div className={`text-[11px] ${isSelected ? 'text-slate-300 border-white/10' : 'text-slate-500 border-slate-200'} mt-3 pt-2.5 border-t flex items-center justify-between font-medium`}>
                <span className={isSelected ? 'text-white' : 'text-slate-800'}>{preset.qps}</span>
                <span>{preset.sla}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
