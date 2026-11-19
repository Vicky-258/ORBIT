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
    <div className="bg-[#111317] rounded-xl border border-[#1e222b] p-6 space-y-5">
      <div>
        <h2 className="text-base font-bold text-slate-100 tracking-tight">
          Operational Boundaries
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
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
              className="p-4 rounded-lg border border-[#1e222b] bg-[#16181f] space-y-2 text-xs border-l-4 border-l-[#f87171]"
            >
              {/* Category + Affected Component */}
              <div className="flex items-center justify-between gap-2 flex-wrap font-mono">
                <span className="font-bold text-slate-200">
                  {category}
                </span>
                <span className="text-[10px] text-slate-400">
                  Target: {component}
                </span>
              </div>

              {/* Concrete Trigger Text */}
              <div className="text-slate-300 leading-relaxed font-sans">
                {text}
              </div>

              {/* Recommended Action */}
              <div className="pt-2 border-t border-[#1e222b] flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span className="text-[#f87171] font-semibold">Recommended Action:</span>
                <span className="text-slate-300">{adjustment}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
