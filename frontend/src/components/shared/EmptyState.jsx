import React from 'react';
import { Layers } from 'lucide-react';

export default function EmptyState({ onSelectPreset }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 shadow-2xs">
        <Layers className="w-6 h-6" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-slate-900">No Simulation Active</h3>
        <p className="text-xs text-slate-500 max-w-md">
          Select a workload scenario or configure your requirements above to view architecture recommendations.
        </p>
      </div>
    </div>
  );
}
