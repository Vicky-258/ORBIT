import React from 'react';
import { AlertTriangle, ChevronRight, HelpCircle, ShieldAlert } from 'lucide-react';

export default function ReconsiderConditions({ conditions = [] }) {
  const defaultConditions = [
    {
      category: 'Workload Shift',
      text: 'If write ratio rises above 40%, cache invalidation overhead increases and direct relational routing becomes more cost-effective.',
      type: 'Observed boundary',
    },
    {
      category: 'Traffic Scale',
      text: 'If traffic exceeds 650 RPS, direct database execution reaches saturation limits; horizontal read replicas or asynchronous ingestion will be needed.',
      type: 'Model-supported boundary',
    },
    {
      category: 'Budget Constraints',
      text: 'If monthly infrastructure budget is capped below $150/mo, dedicated cache tiers are disqualified in favor of direct database hosting.',
      type: 'Constraint boundary',
    },
  ];

  const displayConditions = conditions.length > 0 ? conditions : defaultConditions;

  return (
    <div className="saas-card p-6 space-y-4">
      <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.06]">
        <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-sm">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-100 tracking-tight">
            Operational Reconsideration Triggers
          </h2>
          <p className="text-[11px] text-slate-400">
            Concrete scale or traffic shifts that would require modifying this design
          </p>
        </div>
      </div>

      <p className="text-xs text-slate-400 leading-relaxed">
        Architectural choices are bound to workload assumptions. Reassess this blueprint if the following operational boundaries are approached:
      </p>

      <div className="space-y-3">
        {displayConditions.map((item, idx) => {
          const isObj = typeof item === 'object' && item !== null;
          const text = isObj ? item.text || item.condition : item;
          const category = isObj ? item.category : `Boundary #${idx + 1}`;
          const type = isObj ? item.type : 'Model-supported boundary';

          return (
            <div
              key={idx}
              className="p-4 rounded-xl bg-slate-900/50 border border-white/[0.08] hover:border-white/[0.14] transition-all space-y-2 shadow-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-slate-200 text-xs flex items-center gap-1.5">
                  <ChevronRight className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>{category}</span>
                </div>
                {type && (
                  <span className="badge-saas bg-white/[0.04] text-slate-300 border border-white/[0.08] text-[10px]">
                    {type}
                  </span>
                )}
              </div>
              <p className="text-slate-300 text-xs leading-relaxed pl-5">
                {text}
              </p>
            </div>
          );
        })}
      </div>

      {/* Extrapolation Warning Banner */}
      <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] flex items-start gap-2.5 text-xs text-slate-400">
        <HelpCircle className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
        <span className="leading-relaxed text-[11px]">
          <strong className="text-slate-300">Validation Boundary Notice:</strong> Performance figures represent discrete-event queueing simulation (SimPy). Traffic beyond validated ranges should be empirically benchmarked before relying on this design at higher scale.
        </span>
      </div>
    </div>
  );
}
