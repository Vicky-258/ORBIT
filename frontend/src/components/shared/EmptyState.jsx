import React from 'react';
import { Layers } from 'lucide-react';

export default function EmptyState({ onSelectPreset }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
        <Layers className="w-6 h-6" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-slate-100">No Simulation Active</h3>
        <p className="text-xs text-slate-400 max-w-md">
          Select a workload scenario or configure your requirements above to view architecture recommendations.
        </p>
      </div>
    </div>
  );
}
