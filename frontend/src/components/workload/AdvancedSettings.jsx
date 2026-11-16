import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { ChevronDown, ChevronUp, Sliders } from 'lucide-react';

export default function AdvancedSettings() {
  const { options, setOptions } = useApp();
  const [isOpen, setIsOpen] = useState(false);

  const updateOption = (key, value) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-slate-50/50">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-xs text-slate-600 hover:text-slate-900 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Sliders className="w-3.5 h-3.5 text-slate-500" />
          <span className="font-medium">Advanced Simulation Settings</span>
        </div>
        {isOpen ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {isOpen && (
        <div className="p-4 pt-1 border-t border-slate-200 bg-white space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-slate-600 block mb-1">
                SimPy Duration (seconds)
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={options.simulation_duration_seconds}
                onChange={(e) => updateOption('simulation_duration_seconds', parseFloat(e.target.value) || 5.0)}
                className="font-mono text-xs"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-600 block mb-1">
                Random Seed
              </label>
              <input
                type="number"
                value={options.random_seed}
                onChange={(e) => updateOption('random_seed', parseInt(e.target.value, 10) || 42)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-slate-600 block mb-1">
                Investigation Rounds Cap
              </label>
              <input
                type="number"
                min="1"
                max="5"
                value={options.max_investigation_rounds}
                onChange={(e) => updateOption('max_investigation_rounds', parseInt(e.target.value, 10) || 3)}
                className="font-mono text-xs"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-600 block mb-1">
                Agent Time Budget (sec)
              </label>
              <input
                type="number"
                min="10"
                max="120"
                value={options.investigation_budget_seconds}
                onChange={(e) => updateOption('investigation_budget_seconds', parseFloat(e.target.value) || 60.0)}
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-1 text-slate-600">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={options.include_async}
                onChange={(e) => updateOption('include_async', e.target.checked)}
                className="rounded border-slate-300 text-slate-900 focus:ring-0"
              />
              <span>Include Async Queues</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
