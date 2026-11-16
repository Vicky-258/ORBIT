import React from 'react';
import MetricCard from './MetricCard';

export default function MetricGrid({ winner, workload = {} }) {
  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;

  const bounds = winner?.uncertainty_bounds_p95 || winner?.uncertainty_bounds_p95_ms;
  const uncertaintyText = bounds && bounds[0] != null && bounds[1] != null
    ? `[${bounds[0].toFixed(1)}, ${bounds[1].toFixed(1)} ms] heuristic range`
    : null;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {/* Metric 1: p95 Latency */}
      <MetricCard
        title="Predicted p95 Latency"
        value={winner?.p95 != null ? `~${winner.p95}` : '—'}
        unit="ms"
        provenance={winner?.latency_provenance || 'SIMULATED'}
        targetComparison={slaMs ? `Target: < ${slaMs} ms` : null}
        uncertaintyRange={uncertaintyText}
        statusColor={winner?.p95 != null && winner.p95 <= slaMs ? 'text-emerald-400' : 'text-rose-400'}
      />

      {/* Metric 2: Simulated Throughput */}
      <MetricCard
        title="Simulated Throughput"
        value={winner?.throughput != null ? winner.throughput : '—'}
        unit="req/sec"
        provenance={winner?.throughput_provenance || 'SIMULATED'}
        targetComparison="Offered load tested"
        statusColor="text-slate-100"
      />

      {/* Metric 3: Estimated Monthly Cost */}
      <MetricCard
        title="Estimated Monthly Cost"
        value={winner?.cost != null ? `$${winner.cost}` : 'Cost not modelled'}
        unit={winner?.cost != null ? '/mo' : ''}
        provenance={winner?.cost != null ? (winner.cost_provenance || 'ASSUMED') : 'NOT_MODELLED'}
        targetComparison={
          winner?.cost != null && budgetUsd
            ? winner.cost <= budgetUsd
              ? `$${budgetUsd - winner.cost} under budget`
              : `$${winner.cost - budgetUsd} over budget`
            : budgetUsd
            ? `Budget cap: < $${budgetUsd}/mo`
            : 'Unconstrained'
        }
        statusColor={
          winner?.cost != null
            ? budgetUsd && winner.cost > budgetUsd
              ? 'text-rose-400'
              : 'text-slate-100'
            : 'text-slate-400'
        }
      />

      {/* Metric 4: Database CPU Load */}
      <MetricCard
        title="Database CPU Load"
        value={winner?.cpu != null ? `${winner.cpu}%` : 'Not modelled'}
        unit={winner?.cpu != null ? 'CPU' : ''}
        provenance={winner?.cpu != null ? (winner.cpu_provenance || 'ESTIMATED') : 'NOT_MODELLED'}
        targetComparison={
          winner?.cpu != null
            ? winner.cpu < 60
              ? 'Safe headroom (<60%)'
              : winner.cpu < 85
              ? 'Moderate load'
              : 'High contention risk'
            : 'Hardware model pending'
        }
        statusColor={
          winner?.cpu != null
            ? winner.cpu < 60
              ? 'text-emerald-400'
              : winner.cpu < 85
              ? 'text-amber-400'
              : 'text-rose-400'
            : 'text-slate-400'
        }
      />
    </div>
  );
}
