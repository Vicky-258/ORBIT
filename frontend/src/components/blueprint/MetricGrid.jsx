import React from 'react';
import MetricCard from './MetricCard';

export default function MetricGrid({ winner, workload = {} }) {
  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;

  const bounds = winner?.uncertainty_bounds_p95 || winner?.uncertainty_bounds_p95_ms;
  const uncertaintyText = bounds && bounds[0] != null && bounds[1] != null
    ? `[${bounds[0].toFixed(1)}, ${bounds[1].toFixed(1)} ms] heuristic range`
    : null;

  // Latency calculation
  const p95Val = winner?.p95;
  const latencyProgress = p95Val != null && slaMs ? Math.min(100, (p95Val / slaMs) * 100) : null;
  const isSlaMet = p95Val != null && slaMs ? p95Val <= slaMs : true;

  // Cost calculation
  const costVal = winner?.cost;
  const costProgress = costVal != null && budgetUsd ? Math.min(100, (costVal / budgetUsd) * 100) : null;
  const isBudgetMet = costVal != null && budgetUsd ? costVal <= budgetUsd : true;

  // CPU calculation
  const cpuVal = winner?.cpu;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Metric 1: p95 Latency */}
      <MetricCard
        title="Predicted p95 Latency"
        value={p95Val != null ? `~${p95Val}` : '—'}
        unit="ms"
        provenance={winner?.latency_provenance || 'SIMULATED'}
        targetComparison={slaMs ? `Target: < ${slaMs} ms` : null}
        uncertaintyRange={uncertaintyText}
        statusColor={isSlaMet ? 'text-emerald-400' : 'text-rose-400'}
        progressPercent={latencyProgress}
        progressColor={isSlaMet ? 'bg-emerald-500' : 'bg-rose-500'}
      />

      {/* Metric 2: Simulated Throughput */}
      <MetricCard
        title="Simulated Throughput"
        value={winner?.throughput != null ? winner.throughput : '—'}
        unit="req/sec"
        provenance={winner?.throughput_provenance || 'SIMULATED'}
        targetComparison="Offered load tested"
        statusColor="text-white"
        progressPercent={100}
        progressColor="bg-indigo-500"
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
            : 'text-slate-500'
        }
        progressPercent={costProgress}
        progressColor={isBudgetMet ? 'bg-slate-600' : 'bg-rose-500'}
      />

      {/* Metric 4: Database CPU Load */}
      <MetricCard
        title="Database CPU Load"
        value={cpuVal != null ? `${cpuVal}%` : 'Not modelled'}
        unit={cpuVal != null ? 'CPU' : ''}
        provenance={cpuVal != null ? (winner?.cpu_provenance || 'ESTIMATED') : 'NOT_MODELLED'}
        targetComparison={
          cpuVal != null
            ? cpuVal < 60
              ? 'Safe headroom (<60%)'
              : cpuVal < 85
              ? 'Moderate load'
              : 'High contention risk'
            : 'Hardware model pending'
        }
        statusColor={
          cpuVal != null
            ? cpuVal < 60
              ? 'text-emerald-400'
              : cpuVal < 85
              ? 'text-amber-400'
              : 'text-rose-400'
            : 'text-slate-500'
        }
        progressPercent={cpuVal != null ? cpuVal : null}
        progressColor={
          cpuVal != null && cpuVal < 60
            ? 'bg-emerald-500'
            : cpuVal != null && cpuVal < 85
            ? 'bg-amber-500'
            : 'bg-rose-500'
        }
      />
    </div>
  );
}
