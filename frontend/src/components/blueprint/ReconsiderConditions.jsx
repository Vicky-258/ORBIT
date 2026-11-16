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
      <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
        <div className="w-7 h-7 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700 shadow-2xs">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            Operational Reconsideration Triggers
          </h2>
          <p className="text-xs text-slate-500">
            Concrete scale or traffic shifts that would require modifying this design
          </p>
        </div>
      </div>

      <p className="text-xs text-slate-600 leading-relaxed">
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
              className="p-4 rounded-xl bg-slate-50/70 border border-slate-200 hover:border-slate-300 transition-all space-y-2 shadow-2xs"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-slate-900 text-xs flex items-center gap-1.5">
                  <ChevronRight className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>{category}</span>
                </div>
                {type && (
                  <span className="badge-saas badge-zinc text-[10px]">
                    {type}
                  </span>
                )}
              </div>
              <p className="text-slate-600 text-xs leading-relaxed pl-5">
                {text}
              </p>
            </div>
          );
        })}
      </div>

      {/* Extrapolation Warning Banner */}
      <div className="p-3.5 rounded-xl bg-amber-50/60 border border-amber-200 flex items-start gap-2.5 text-xs text-amber-900">
        <HelpCircle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <span className="leading-relaxed text-xs">
          <strong className="text-amber-950 font-semibold">Validation Boundary Notice:</strong> Performance figures represent discrete-event queueing simulation (SimPy). Traffic beyond validated ranges should be empirically benchmarked before relying on this design at higher scale.
        </span>
      </div>
    </div>
  );
}
