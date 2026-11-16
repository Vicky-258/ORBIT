import React from 'react';

export default function LoadingState({ message = 'Simulating Candidate Architectures...' }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center space-y-4">
      <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-slate-100">{message}</h3>
        <p className="text-xs text-slate-400 max-w-md">
          Executing discrete-event queueing simulations with SimPy, calculating p95 latencies, and evaluating constraints.
        </p>
      </div>
    </div>
  );
}
