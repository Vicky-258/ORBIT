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
          ? 'bg-emerald-950/20 border-emerald-500/30'
          : 'bg-[#121215] border-white/[0.08] hover:border-zinc-700'
      }`}
    >
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between text-left cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300">
            <Layers className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-white">{candidate.name}</span>
              {isWinner && (
                <span className="badge-saas bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] py-0 px-1.5 font-semibold">
                  Recommended
                </span>
              )}
            </div>
            <span className="text-xs text-zinc-400 font-normal">
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
            <ChevronUp className="w-4 h-4 text-zinc-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="p-4 pt-1 border-t border-white/[0.05] space-y-4 text-xs">
          {/* Feasibility Checks */}
          {checks.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-zinc-300 block">
                Feasibility Constraint Checks
              </span>
              <div className="space-y-1.5">
                {checks.map((fc, idx) => {
                  const passed = fc.status === 'FEASIBLE' || fc.status === 'SATISFIED' || fc.status === 'PASS';
                  return (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-[#09090b] border border-zinc-800 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {passed ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                        )}
                        <span className="text-zinc-200 capitalize font-medium">{fc.criterion?.replace('_', ' ')}</span>
                      </div>

                      <div className="flex items-center gap-3 text-zinc-400 font-mono">
                        <span>Predicted: <strong className="text-white">{fc.predicted_value}</strong></span>
                        <span>Target: <strong className="text-white">&lt;= {fc.target_value}</strong></span>
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
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs space-y-1">
              <span className="font-semibold flex items-center gap-1.5 text-rose-400">
                <AlertTriangle className="w-3.5 h-3.5" /> Constraint Violations:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-xs text-rose-300/90 pl-1">
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
