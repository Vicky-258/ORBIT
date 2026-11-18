import React from 'react';
import EvidenceBadge from '../shared/EvidenceBadge';

export default function MetricCard({
  title,
  value,
  unit = '',
  provenance,
  targetComparison,
  statusColor = 'text-white',
  progressPercent = null,
  progressColor = 'bg-emerald-500',
  isPrimary = false
}) {
  return (
    <div className={`rounded-xl border p-4 sm:p-5 flex flex-col justify-between transition-all duration-200 ${
      isPrimary
        ? 'bg-[#151a17] border-emerald-500/30 shadow-md ring-1 ring-emerald-500/10'
        : 'bg-[#121215] border-white/[0.06] hover:border-white/[0.12]'
    }`}>
      {/* Header: Title & subtle provenance */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
          {title}
        </span>
        <EvidenceBadge provenance={provenance} />
      </div>

      {/* Main Metric Value */}
      <div className="my-1">
        <div className="flex items-baseline gap-1.5">
          <span className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight ${statusColor}`}>
            {value}
          </span>
          {unit && (
            <span className="text-xs text-zinc-400 font-mono">{unit}</span>
          )}
        </div>

        {/* Progress Bar */}
        {progressPercent != null && (
          <div className="w-full h-1 rounded-full bg-white/[0.06] overflow-hidden mt-3">
            <div
              className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
              style={{ width: `${Math.min(100, Math.max(5, progressPercent))}%` }}
            />
          </div>
        )}
      </div>

      {/* Target Comparison Footer */}
      {targetComparison && (
        <div className="pt-2.5 mt-2 border-t border-white/[0.04] text-[11px] text-zinc-400 font-mono">
          {targetComparison}
        </div>
      )}
    </div>
  );
}
