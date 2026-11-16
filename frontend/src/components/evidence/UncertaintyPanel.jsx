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
      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 space-y-1">
        <span className="font-semibold text-slate-900">Scientific Uncertainty &amp; Limitation Disclosures</span>
        <p className="text-slate-600 leading-relaxed">
          In alignment with AADS empirical integrity guidelines, all heuristic bounds and model limitations are disclosed openly to prevent overconfident architectural conclusions.
        </p>
      </div>

      <div className="space-y-3">
        {uncertaintyItems.map((item, idx) => (
          <div
            key={idx}
            className="p-4 rounded-xl bg-white border border-slate-200 shadow-2xs space-y-2 text-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-slate-900 flex items-center gap-2">
                <Info className="w-4 h-4 text-slate-500 shrink-0" />
                <span>{item.title}</span>
              </span>
              <span className="badge-saas badge-zinc text-[10px] shrink-0">
                {item.badge}
              </span>
            </div>
            <p className="text-slate-600 leading-relaxed pl-6">
              {item.description}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
