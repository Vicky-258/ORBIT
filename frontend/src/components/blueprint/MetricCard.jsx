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
    <div
      className={`rounded-lg border p-4 sm:p-5 flex flex-col justify-between transition-all ${
        isPrimary
          ? 'bg-[#16181f] border-[#1e222b] border-l-4 border-l-[#34d399]'
          : 'bg-[#16181f] border-[#1e222b]'
      }`}
    >
      {/* Header: Title & Provenance */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[11px] font-mono font-medium text-slate-400 uppercase tracking-wider">
          {title}
        </span>
        <EvidenceBadge provenance={provenance} />
      </div>

      {/* Main Metric Value */}
      <div className="my-1">
        <div className="flex items-baseline gap-1.5">
          <span className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight ${isPrimary ? 'text-[#34d399]' : statusColor}`}>
            {value}
          </span>
          {unit && (
            <span className="text-xs text-slate-400 font-mono">{unit}</span>
          )}
        </div>

        {/* Progress Bar */}
        {progressPercent != null && (
          <div className="w-full h-1 rounded-full bg-slate-800 overflow-hidden mt-3">
            <div
              className={`h-full rounded-full transition-all duration-500 ${isPrimary ? 'bg-[#34d399]' : progressColor}`}
              style={{ width: `${Math.min(100, Math.max(5, progressPercent))}%` }}
            />
          </div>
        )}
      </div>

      {/* Target Comparison Footer */}
      {targetComparison && (
        <div className="text-[11px] text-slate-500 font-mono mt-3 pt-2 border-t border-[#1e222b]">
          {targetComparison}
        </div>
      )}
    </div>
  );
}
