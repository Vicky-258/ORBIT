import React from 'react';
import { useApp } from '../../context/AppContext';
import ArchitectureComparisonTable from './ArchitectureComparisonTable';
import CandidateDetails from './CandidateDetails';

export default function CompareOptions() {
  const { response } = useApp();

  const decisionResult = response?.decision_result || response?.decisionResult;
  const workload = decisionResult?.workload || response?.workload || {};
  const candidates = response?.candidates || [];
  const recommendation = response?.recommendation || {};
  const winnerId = recommendation.winner_id || recommendation.winner?.id || candidates[0]?.id;

  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;
  const qps = workload.qps || workload.request_rate_rps || 500;

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header Description */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-1 border-b border-white/[0.06]">
        <div>
          <h2 className="text-lg font-bold text-slate-100 tracking-tight">
            Architecture Candidates Comparison Matrix
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Side-by-side evaluation under {qps} requests/sec offered load and {slaMs} ms SLA threshold
          </p>
        </div>

        <div className="text-xs text-slate-400 font-mono">
          <span>Target SLA: &lt; {slaMs} ms</span>
          {budgetUsd && <span> • Budget: &lt; ${budgetUsd}/mo</span>}
        </div>
      </div>

      {/* Primary Interface: Comparison Table */}
      <ArchitectureComparisonTable
        candidates={candidates}
        winnerId={winnerId}
        slaMs={slaMs}
        budgetUsd={budgetUsd}
      />

      {/* Secondary Detailed Breakdown */}
      <div className="space-y-3 pt-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          Individual Candidate Deep-Dive &amp; Constraint Proofs
        </h3>
        <div className="space-y-3">
          {candidates.map((cand) => (
            <CandidateDetails
              key={cand.id}
              candidate={cand}
              isWinner={cand.id === winnerId}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
