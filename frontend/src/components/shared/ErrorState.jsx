import React from 'react';
import { AlertCircle, RotateCcw } from 'lucide-react';

export default function ErrorState({ error, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center space-y-4">
      <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center text-rose-700 shadow-2xs">
        <AlertCircle className="w-6 h-6" />
      </div>
      <div className="space-y-1.5 max-w-md">
        <h3 className="text-base font-semibold text-slate-900">Simulation Failed</h3>
        <p className="text-xs text-rose-800 font-mono bg-rose-50 p-3 rounded-lg border border-rose-200 text-left overflow-x-auto">
          {error}
        </p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="btn-saas-secondary text-xs py-2 px-4 flex items-center gap-1.5 mt-2"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span>Retry Simulation</span>
        </button>
      )}
    </div>
  );
}
