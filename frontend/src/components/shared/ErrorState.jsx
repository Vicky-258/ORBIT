import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
        <AlertCircle className="w-6 h-6" />
      </div>
      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold text-slate-100">Simulation Failed</h3>
        <p className="text-xs text-rose-300/90 font-mono bg-rose-950/40 p-3 rounded-lg border border-rose-900/40 text-left overflow-x-auto">
          {error}
        </p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="btn btn-secondary text-xs py-2 px-4 flex items-center gap-1.5 mt-2"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Retry Simulation</span>
        </button>
      )}
    </div>
  );
}
