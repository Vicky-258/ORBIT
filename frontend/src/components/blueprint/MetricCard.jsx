import React from 'react';
import EvidenceBadge from '../shared/EvidenceBadge';

export default function MetricCard({
  title,
  value,
  unit = '',
  provenance,
  targetComparison,
  uncertaintyRange,
  statusColor = 'text-white',
  progressPercent = null,
  progressColor = 'bg-emerald-500',
}) {
  return (
    <div className="bg-[#121215] rounded-xl border border-white/[0.08] p-4 sm:p-5 flex flex-col justify-between space-y-3 relative overflow-hidden shadow-xs hover:border-zinc-700 transition-all">
      {/* Card Header: Title & Honest Provenance Badge */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-zinc-400 font-medium tracking-tight">
          {title}
        </span>
        <EvidenceBadge provenance={provenance} />
      </div>

      {/* Main Metric Value */}
      <div className="space-y-1.5">
        <div className="flex items-baseline gap-1.5">
          <span className={`text-2xl sm:text-3xl font-bold font-mono tracking-tight ${statusColor}`}>
            {value}
          </span>
          {unit && (
            <span className="text-xs text-zinc-400 font-mono font-medium">{unit}</span>
          )}
        </div>

        {/* Visual Progress / Comparison Bar */}
        {progressPercent != null && (
          <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden mt-2">
            <div
              className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
              style={{ width: `${Math.min(100, Math.max(5, progressPercent))}%` }}
            />
          </div>
        )}
      </div>

      {/* Card Footer: Target Comparison & Uncertainty Bounds */}
      <div className="pt-2 border-t border-white/[0.05] space-y-1 text-xs">
        {targetComparison && (
          <div className="text-zinc-300 font-medium flex items-center justify-between">
            <span>{targetComparison}</span>
          </div>
        )}

        {uncertaintyRange && (
          <div className="text-[11px] text-zinc-500 font-mono" title="Heuristic simulation bounds">
            {uncertaintyRange}
          </div>
        )}
      </div>
    </div>
  );
}
