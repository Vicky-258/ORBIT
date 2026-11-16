import React from 'react';
import { Layers, ArrowRight } from 'lucide-react';

export default function EmptyState({ onGoToPrompt }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-[#111622] border border-white/[0.08] flex items-center justify-center text-slate-400 shadow-sm">
        <Layers className="w-6 h-6" />
      </div>
      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold text-white">No Simulation Results Yet</h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          Describe your application requirements in the prompt studio to simulate candidates, evaluate constraints, and view architecture blueprints.
        </p>
      </div>
      {onGoToPrompt && (
        <button
          type="button"
          onClick={onGoToPrompt}
          className="btn btn-primary text-xs py-2 px-4 rounded-lg flex items-center gap-2 mt-2"
        >
          <span>Open Prompt Studio</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
