import React from 'react';
import EvidenceBadge from '../shared/EvidenceBadge';

export default function MetricCard({
  title,
  value,
  unit = '',
  provenance,
  targetComparison,
  uncertaintyRange,
  statusColor = 'text-slate-900',
  progressPercent = null,
  progressColor = 'bg-emerald-500',
}) {
  return (
    <div className="saas-card p-5 flex flex-col justify-between space-y-3 relative overflow-hidden">
      {/* Card Header: Title & Honest Provenance Badge */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-slate-500 font-medium tracking-tight">
          {title}
        </span>
        <EvidenceBadge provenance={provenance} />
      </div>

      {/* Main Metric Value */}
      <div className="space-y-1.5">
        <div className="flex items-baseline gap-1.5">
          <span className={`text-2xl sm:text-3xl font-bold font-sans tracking-tight ${statusColor}`}>
            {value}
          </span>
          {unit && (
            <span className="text-sm text-slate-500 font-sans font-medium">{unit}</span>
          )}
        </div>

        {/* Visual Progress / Comparison Bar */}
        {progressPercent != null && (
          <div className="w-full h-1.5 rounded-full bg-slate-100 overflow-hidden mt-2">
            <div
              className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
              style={{ width: `${Math.min(100, Math.max(5, progressPercent))}%` }}
            />
          </div>
        )}
      </div>

      {/* Card Footer: Target Comparison & Uncertainty Bounds */}
      <div className="pt-2.5 border-t border-slate-100 space-y-1 text-xs">
        {targetComparison && (
          <div className="text-slate-700 font-medium flex items-center justify-between">
            <span>{targetComparison}</span>
          </div>
        )}

        {uncertaintyRange && (
          <div className="text-[11px] text-slate-400" title="Heuristic simulation bounds">
            {uncertaintyRange}
          </div>
        )}
      </div>
    </div>
  );
}
