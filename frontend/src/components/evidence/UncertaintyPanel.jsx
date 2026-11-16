import React from 'react';
import { AlertTriangle, HelpCircle, Shield, Info } from 'lucide-react';

export default function UncertaintyPanel() {
  const uncertaintyItems = [
    {
      title: 'Heuristic Prediction Uncertainty vs. Statistical Confidence Intervals',
      badge: 'Uncertainty Modeling',
      description:
        'AADS outputs heuristic prediction intervals based on piecewise regression residual errors. These are heuristic uncertainty bounds, not formal frequentist 95% confidence intervals, and should be interpreted as operational risk boundaries.',
    },
    {
      title: 'Container Isolation vs. Production Hypervisor Contention',
      badge: 'Environmental Caveat',
      description:
        'Benchmarks were executed inside cgroups v2 pinned CPU containers. Multi-tenant hypervisor noise, shared noisy-neighbor disk I/O, and cross-AZ cloud network transit jitter are not modeled in local discrete-event simulation.',
    },
    {
      title: 'Monthly Cloud Infrastructure Cost Approximation',
      badge: 'Cost Model Assumption',
      description:
        'Hosting prices reflect standard AWS/GCP list container and database VM pricing (730 continuous running hours per month). Dynamic autoscaling, spot instance discounts, data egress fees, and IOPS provisioned costs are not included.',
    },
    {
      title: 'Extrapolation Beyond 650 RPS Operating Range',
      badge: 'Extrapolation Limitation',
      description:
        'PostgreSQL regression models were trained up to 650 RPS under SF2 pgbench conditions. Traffic inputs beyond 650 RPS rely on ridge regularized slope continuation and require physical verification before deploying.',
    },
  ];

  return (
    <div className="space-y-4 text-xs">
      <div className="p-4 rounded-xl bg-[#121215] border border-white/[0.08] text-zinc-300 space-y-1">
        <span className="font-semibold text-white">Scientific Uncertainty &amp; Limitation Disclosures</span>
        <p className="text-zinc-400 leading-relaxed">
          In alignment with AADS empirical integrity guidelines, all heuristic bounds and model limitations are disclosed openly to prevent overconfident architectural conclusions.
        </p>
      </div>

      <div className="space-y-3">
        {uncertaintyItems.map((item, idx) => (
          <div
            key={idx}
            className="p-4 rounded-xl bg-[#121215] border border-white/[0.08] shadow-xs space-y-2 text-xs hover:border-zinc-700 transition-all"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-white flex items-center gap-2">
                <Info className="w-4 h-4 text-zinc-400 shrink-0" />
                <span>{item.title}</span>
              </span>
              <span className="badge-saas bg-zinc-800 text-zinc-300 border border-zinc-700 text-[10px] shrink-0">
                {item.badge}
              </span>
            </div>
            <p className="text-zinc-400 leading-relaxed pl-6">
              {item.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
