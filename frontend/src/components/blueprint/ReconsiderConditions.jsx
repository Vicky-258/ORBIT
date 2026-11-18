import React from 'react';
import { AlertTriangle, TrendingUp, DollarSign, Activity } from 'lucide-react';

export default function ReconsiderConditions({ conditions = [] }) {
  const defaultConditions = [
    {
      category: 'Workload Shift',
      text: 'If write ratio rises above 40%, cache invalidation overhead increases and direct relational routing becomes more cost-effective.',
      component: 'Redis In-Memory Cache',
      impact: 'Cache invalidation stampedes',
      adjustment: 'Switch to write-through buffer or direct partitioned database'
    },
    {
      category: 'Traffic Scale',
      text: 'If traffic exceeds 650 RPS, direct database execution reaches saturation limits; horizontal read replicas or asynchronous ingestion will be needed.',
      component: 'PostgreSQL Primary Instance',
      impact: 'Connection exhaustion & queuing delay',
      adjustment: 'Deploy read replicas with connection pooling (PgBouncer)'
    },
    {
      category: 'Budget Constraints',
      text: 'If monthly infrastructure budget is capped below $150/mo, dedicated cache tiers are disqualified in favor of direct database hosting.',
      component: 'Cloud Hosting Quota',
      impact: 'Budget violation warning',
      adjustment: 'Scale down to single combined compute/database instance'
    },
  ];

  const displayConditions = conditions.length > 0 ? conditions : defaultConditions;

  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-5 sm:p-6 space-y-4 shadow-xl">
      <div className="flex items-center gap-3 pb-3 border-b border-white/[0.06]">
        <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">
            Operational Reconsideration Triggers
          </h2>
          <p className="text-xs text-zinc-400">
            Concrete scale or traffic shifts that would require modifying this design
          </p>
        </div>
      </div>

      <p className="text-xs text-zinc-400 leading-relaxed">
        Architectural choices are bound to workload assumptions. Reassess this blueprint if the following operational boundaries are approached:
      </p>

      <div className="space-y-3">
        {displayConditions.map((item, idx) => {
          const isObj = typeof item === 'object' && item !== null;
          const text = isObj ? item.text || item.condition : item;
          const category = isObj ? item.category : `Boundary #${idx + 1}`;
          const component = isObj ? item.component : 'System Primitive';
          const adjustment = isObj ? item.adjustment : 'Re-run simulation with adjusted constraints';

          return (
            <div
              key={idx}
              className="p-4 rounded-xl border border-white/[0.08] bg-[#09090b] hover:border-zinc-700 transition-all space-y-2 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-zinc-200 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                  <span>{category}</span>
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                  {component}
                </span>
              </div>

              <p className="text-zinc-300 leading-relaxed">
                {text}
              </p>

              {adjustment && (
                <div className="pt-2 border-t border-white/[0.04] flex items-center justify-between text-[11px] text-zinc-400">
                  <span className="text-zinc-500 font-medium">Recommended action:</span>
                  <span className="text-zinc-300 font-medium">{adjustment}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
