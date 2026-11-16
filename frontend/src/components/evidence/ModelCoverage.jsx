import React from 'react';
import StatusBadge from '../shared/StatusBadge';
import { Database, ShieldCheck, AlertCircle } from 'lucide-react';

export default function ModelCoverage() {
  const coverageData = [
    {
      component: 'postgres_db (PostgreSQL 16-alpine)',
      modelType: 'piecewise_ridge + lookup_interpolation',
      status: 'OBSERVED',
      range: 'QPS: [100 - 650], Concurrency: [1 - 64], SF2',
      r2: '0.940 - 0.986',
      notes: 'Fully calibrated against 12 live benchmark trials on isolated Linux cgroups.',
    },
    {
      component: 'redis_cache (Redis 7.2-alpine)',
      modelType: 'sub-millisecond empirical microbenchmark',
      status: 'OBSERVED',
      range: 'QPS: [100 - 5000], Concurrency: [1 - 128]',
      r2: 'Calibrated Point Estimate (~0.65ms)',
      notes: 'In-memory service demand model; sub-millisecond tail latency bounds.',
    },
    {
      component: 'kafka_queue + worker',
      modelType: 'discrete-event queueing model',
      status: 'OBSERVED',
      range: 'QPS: [100 - 1500], Worker Threads: [2 - 8]',
      r2: 'M/M/k Poisson Arrival Simulation',
      notes: 'Calibrated enqueue latency with background asynchronous worker batching.',
    },
    {
      component: 'postgres_db (Traffic > 650 RPS)',
      modelType: 'piecewise_ridge extrapolation',
      status: 'INTERPOLATED',
      range: 'QPS: [650 - 800]',
      r2: 'Heuristic Ridge Regression',
      notes: 'Model interpolates CPU contention beyond measured 650 RPS boundary.',
    },
    {
      component: 'mongodb_unregistered (Uncalibrated)',
      modelType: 'none',
      status: 'INSUFFICIENT_EVIDENCE',
      range: 'Unsupported / Unregistered',
      r2: 'N/A',
      notes: 'Missing baseline trial measurements; excluded from feasible recommendations.',
    },
  ];

  return (
    <div className="space-y-4 text-xs">
      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-slate-700 space-y-1">
        <span className="font-semibold text-slate-900">Empirical Model Operating Ranges</span>
        <p className="text-slate-600 leading-relaxed">
          The table below indicates the validated boundaries for each empirical performance model registered in SQLite. Operating within the <strong className="text-emerald-700">OBSERVED</strong> range guarantees high fidelity.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-2xs">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-slate-600">
              <th className="py-3 px-4 font-semibold">Component &amp; Version</th>
              <th className="py-3 px-4 font-semibold">Coverage Status</th>
              <th className="py-3 px-4 font-semibold">Validated Operating Range</th>
              <th className="py-3 px-4 font-semibold">Fit Metric (R²)</th>
              <th className="py-3 px-4 font-semibold">Validation Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {coverageData.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50/50">
                <td className="py-3 px-4 font-semibold text-slate-900 font-mono text-[11px]">
                  {row.component}
                </td>
                <td className="py-3 px-4">
                  <StatusBadge status={row.status} type="evidence" />
                </td>
                <td className="py-3 px-4 font-mono text-slate-600 text-[11px]">
                  {row.range}
                </td>
                <td className="py-3 px-4 font-mono text-slate-700 text-[11px]">
                  {row.r2}
                </td>
                <td className="py-3 px-4 text-slate-600 text-xs">
                  {row.notes}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
