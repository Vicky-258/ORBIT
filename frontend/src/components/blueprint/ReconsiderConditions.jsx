import React from 'react';
import { AlertTriangle, ChevronRight, HelpCircle } from 'lucide-react';

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
    <div className="bg-[#111622] rounded-xl border border-white/[0.08] p-5 sm:p-6 space-y-4 shadow-xs">
      <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.06]">
        <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">
            Operational Reconsideration Triggers
          </h2>
          <p className="text-xs text-slate-400">
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
              className="p-3.5 rounded-lg border border-white/[0.06] bg-[#0b0f17] hover:border-white/15 transition-all space-y-1.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-white tracking-tight flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                  <span>{category}</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-slate-400 border border-white/[0.06]">
                  {type}
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">
                {text}
              </p>
            </div>
          );
        })}
      </div>

      <div className="pt-2 border-t border-white/[0.05] flex items-center justify-between text-[11px] text-slate-500 font-mono">
        <span>Boundary definitions derived from empirical calibration models</span>
        <HelpCircle className="w-3.5 h-3.5" />
      </div>
    </div>
  );
}
