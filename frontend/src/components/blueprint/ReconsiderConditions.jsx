import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function ReconsiderConditions({ conditions = [] }) {
  const defaultConditions = [
    {
      category: 'Workload Shift',
      text: 'If write ratio rises above 40%, cache invalidation overhead increases and direct relational routing becomes more cost-effective.',
      component: 'Redis In-Memory Cache',
      adjustment: 'Switch to write-through buffer or direct partitioned database'
    },
    {
      category: 'Traffic Scale',
      text: 'If traffic exceeds 650 RPS, direct database execution reaches saturation limits; horizontal read replicas or asynchronous ingestion will be needed.',
      component: 'PostgreSQL Primary Instance',
      adjustment: 'Deploy read replicas with connection pooling (PgBouncer)'
    },
    {
      category: 'Budget Constraints',
      text: 'If monthly infrastructure budget is capped below $150/mo, dedicated cache tiers are disqualified in favor of direct database hosting.',
      component: 'Cloud Hosting Quota',
      adjustment: 'Scale down to single combined compute/database instance'
    },
  ];

  const displayConditions = conditions.length > 0 ? conditions : defaultConditions;

  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-6 space-y-5 shadow-xl">
      <div>
        <h2 className="text-base font-bold text-white tracking-tight">
          Operational Boundaries
        </h2>
        <p className="text-xs text-zinc-400 mt-0.5">
          Scale or traffic shifts that require reassessing this topology
        </p>
      </div>

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
              className="p-4 rounded-xl border border-white/[0.06] bg-[#09090b] space-y-2 text-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-zinc-100 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
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
                  <span className="text-zinc-500 font-medium">Action:</span>
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
