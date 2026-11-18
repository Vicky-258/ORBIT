import React from 'react';
import MetricCard from './MetricCard';

export default function MetricGrid({ winner, workload = {} }) {
  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;

  const bounds = winner?.uncertainty_bounds_p95 || winner?.uncertainty_bounds_p95_ms;
  const uncertaintyText = bounds && bounds[0] != null && bounds[1] != null
    ? `[${bounds[0].toFixed(1)}, ${bounds[1].toFixed(1)} ms] 95% CI`
    : null;

  // Latency calculation
  const p95Val = winner?.p95 ?? winner?.p95_latency_ms;
  const latencyProgress = p95Val != null && slaMs ? Math.min(100, (p95Val / slaMs) * 100) : null;
  const isSlaMet = p95Val != null && slaMs ? p95Val <= slaMs : true;

  // Throughput calculation
  const throughputVal = winner?.throughput ?? winner?.throughput_achieved_rps;

  // Cost calculation
  const costVal = winner?.cost ?? winner?.estimated_monthly_cost_usd;
  const costProgress = costVal != null && budgetUsd ? Math.min(100, (costVal / budgetUsd) * 100) : null;
  const isBudgetMet = costVal != null && budgetUsd ? costVal <= budgetUsd : true;

  // CPU calculation
  const cpuVal = winner?.cpu ?? winner?.cpu_utilization_pct;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Metric 1: p95 Latency */}
      <MetricCard
        title="Predicted p95 Latency"
        value={p95Val != null ? `~${p95Val}` : '—'}
        unit="ms"
        provenance={winner?.latency_provenance || 'SIMULATED_SIMPY'}
        targetComparison={slaMs ? `Target: < ${slaMs} ms` : null}
        uncertaintyRange={uncertaintyText}
        statusColor={isSlaMet ? 'text-emerald-400' : 'text-rose-400'}
        progressPercent={latencyProgress}
        progressColor={isSlaMet ? 'bg-emerald-500' : 'bg-rose-500'}
      />

      {/* Metric 2: Simulated Throughput */}
      <MetricCard
        title="Simulated Throughput"
        value={throughputVal != null ? throughputVal : '—'}
        unit="req/sec"
        provenance={winner?.throughput_provenance || 'SIMULATED'}
        targetComparison="Offered load verified in SimPy"
        statusColor="text-white"
        progressPercent={100}
        progressColor="bg-sky-500"
      />

      {/* Metric 3: Estimated Monthly Cost */}
      <MetricCard
        title="Estimated Monthly Cost"
        value={costVal != null ? `$${costVal}` : 'Cost not modelled'}
        unit={costVal != null ? '/mo' : ''}
        provenance={costVal != null ? (winner?.cost_provenance || 'ASSUMED') : 'NOT_MODELLED'}
        targetComparison={
          costVal != null && budgetUsd
            ? costVal <= budgetUsd
              ? `$${budgetUsd - costVal} under budget`
              : `$${costVal - budgetUsd} over budget`
            : budgetUsd
            ? `Budget cap: < $${budgetUsd}/mo`
            : 'Unconstrained'
        }
        statusColor={
          costVal != null
            ? budgetUsd && costVal > budgetUsd
              ? 'text-rose-400'
              : 'text-white'
            : 'text-zinc-500'
        }
        progressPercent={costProgress}
        progressColor={isBudgetMet ? 'bg-zinc-500' : 'bg-rose-500'}
      />

      {/* Metric 4: Database CPU Load */}
      <MetricCard
        title="Database CPU Utilization"
        value={cpuVal != null ? `${cpuVal}%` : 'Not modelled'}
        unit=""
        provenance={cpuVal != null ? 'ESTIMATED' : 'NOT_MODELLED'}
        targetComparison={cpuVal != null ? 'Headroom: > 20% free' : 'Hardware model pending'}
        statusColor={cpuVal != null && cpuVal > 80 ? 'text-amber-400' : 'text-zinc-200'}
        progressPercent={cpuVal != null ? Math.min(100, cpuVal) : null}
        progressColor={cpuVal != null && cpuVal > 80 ? 'bg-amber-500' : 'bg-sky-500'}
      />
    </div>
  );
}
