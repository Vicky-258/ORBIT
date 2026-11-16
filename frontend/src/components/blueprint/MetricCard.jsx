import React from 'react';
import EvidenceBadge from '../shared/EvidenceBadge';

export default function MetricCard({
  title,
  value,
  unit = '',
  provenance,
  targetComparison,
  uncertaintyRange,
  statusColor = 'text-slate-100',
}) {
  return (
    <div className="p-4 rounded-xl bg-black/30 border border-white/[0.08] flex flex-col justify-between space-y-2">
      <div className="flex items-center justify-between gap-1.5">
        <span className="text-[11px] text-slate-400 uppercase font-medium tracking-wider">
          {title}
        </span>
        <EvidenceBadge provenance={provenance} />
      </div>

      <div>
        <div className="flex items-baseline gap-1">
          <span className={`text-xl lg:text-2xl font-bold font-mono tracking-tight ${statusColor}`}>
            {value}
          </span>
          {unit && (
            <span className="text-xs text-slate-400 font-mono">{unit}</span>
          )}
        </div>

        {targetComparison && (
          <div className="text-[11px] text-slate-400 mt-1 font-medium flex items-center gap-1">
            <span>{targetComparison}</span>
          </div>
        )}

        {uncertaintyRange && (
          <div className="text-[10px] text-slate-500 font-mono mt-0.5" title="Heuristic simulation bounds">
            {uncertaintyRange}
          </div>
        )}
      </div>
    </div>
  );
}
