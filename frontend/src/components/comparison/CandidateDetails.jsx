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
          ? 'bg-emerald-50/40 border-emerald-300 shadow-xs'
          : 'bg-white border-slate-200 hover:border-slate-300 shadow-2xs'
      }`}
    >
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between text-left cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600">
            <Layers className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-900">{candidate.name}</span>
              {isWinner && (
                <span className="badge badge-emerald text-[9px] py-0 px-1.5 font-semibold">
                  Recommended
                </span>
              )}
            </div>
            <span className="text-xs text-slate-500 font-normal">
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
            <ChevronUp className="w-4 h-4 text-slate-600" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="p-4 pt-1 border-t border-slate-100 space-y-4 text-xs">
          {/* Feasibility Checks */}
          {checks.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-700 block">
                Feasibility Constraint Checks
              </span>
              <div className="space-y-1.5">
                {checks.map((fc, idx) => {
                  const passed = fc.status === 'FEASIBLE' || fc.status === 'SATISFIED' || fc.status === 'PASS';
                  return (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {passed ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                        )}
                        <span className="text-slate-800 capitalize font-medium">{fc.criterion?.replace('_', ' ')}</span>
                      </div>

                      <div className="flex items-center gap-3 text-slate-600">
                        <span>Predicted: <strong className="text-slate-900">{fc.predicted_value}</strong></span>
                        <span>Target: <strong className="text-slate-900">&lt;= {fc.target_value}</strong></span>
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
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs space-y-1">
              <span className="font-semibold flex items-center gap-1.5 text-rose-700">
                <AlertTriangle className="w-3.5 h-3.5" /> Constraint Violations:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-xs text-rose-800/90 pl-1">
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
