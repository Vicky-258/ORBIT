import React, { useState } from 'react';
import StatusBadge from '../shared/StatusBadge';
import { ChevronDown, ChevronUp, Layers, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

export default function CandidateDetails({ candidate, isWinner }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const checks = candidate.feasibility_checks || candidate.checks || [];

  return (
    <div
      className={`rounded-xl border transition-all ${
        isWinner
          ? 'bg-[#0f172a]/60 border-emerald-500/40 shadow-sm'
          : 'bg-[#0c101a] border-white/[0.08] hover:border-white/[0.14]'
      }`}
    >
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between text-left cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-black/40 border border-white/[0.08] flex items-center justify-center text-slate-400">
            <Layers className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-100">{candidate.name}</span>
              {isWinner && (
                <span className="badge badge-emerald text-[9px] py-0 px-1.5 font-semibold">
                  Recommended
                </span>
              )}
            </div>
            <span className="text-[11px] text-slate-400 font-mono">
              {candidate.topology || candidate.topology_summary}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge
            status={candidate.slaMet && candidate.feasible ? 'PASS' : !candidate.feasible ? 'FAIL' : 'UNCERTAIN'}
            type="constraint"
          />
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-500" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="p-4 pt-1 border-t border-white/[0.04] space-y-4 text-xs">
          {/* Feasibility Checks */}
          {checks.length > 0 && (
            <div className="space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                Feasibility Constraint Checks
              </span>
              <div className="space-y-1.5">
                {checks.map((fc, idx) => {
                  const passed = fc.status === 'FEASIBLE' || fc.status === 'SATISFIED' || fc.status === 'PASS';
                  return (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-black/30 border border-white/[0.04] flex items-center justify-between gap-3 font-mono text-[11px]"
                    >
                      <div className="flex items-center gap-2">
                        {passed ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                        )}
                        <span className="text-slate-200 capitalize font-sans">{fc.criterion?.replace('_', ' ')}</span>
                      </div>

                      <div className="flex items-center gap-3 text-slate-400">
                        <span>Predicted: <strong className="text-slate-200">{fc.predicted_value}</strong></span>
                        <span>Target: <strong className="text-slate-200">&lt;= {fc.target_value}</strong></span>
                        <StatusBadge status={fc.status} type="constraint" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Rejection / Trade-off reasons */}
          {candidate.rejectionReasons && candidate.rejectionReasons.length > 0 && (
            <div className="p-3 rounded-lg bg-rose-950/20 border border-rose-900/40 text-rose-300 text-xs space-y-1">
              <span className="font-semibold flex items-center gap-1.5 text-rose-400">
                <AlertTriangle className="w-3.5 h-3.5" /> Constraint Violations:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-rose-300/90 pl-1">
                {candidate.rejectionReasons.map((r, rIdx) => (
                  <li key={rIdx}>{r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
