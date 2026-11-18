import React, { useState } from 'react';
import { useApp } from '../../context/AppContext';
import CandidateCard from './CandidateCard';
import ArchitectureComparisonTable from './ArchitectureComparisonTable';
import CandidateDetails from './CandidateDetails';
import { Layers, Sliders, CheckCircle2, Table, LayoutGrid } from 'lucide-react';

export default function CompareOptions() {
  const { response } = useApp();
  const [selectedCandidateId, setSelectedCandidateId] = useState(null);
  const [viewMode, setViewMode] = useState('both'); // 'both' | 'cards' | 'table'

  const decisionResult = response?.decision_result || response?.decisionResult;
  const workload = decisionResult?.workload || response?.workload || {};
  const candidates = response?.candidates || [];
  const recommendation = response?.recommendation || {};
  const winnerId = recommendation.winner_id || recommendation.winner?.id || candidates[1]?.id || candidates[0]?.id;

  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;
  const qps = workload.qps || workload.request_rate_rps || 500;

  const activeCandidate = candidates.find(c => c.id === (selectedCandidateId || winnerId)) || candidates[0];

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* 1. Header & Metric Constraint Overview */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            Architecture Candidates Comparison Matrix
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            SimPy discrete-event simulation under offered load of <strong className="text-zinc-200">{qps} requests/sec</strong> with a <strong className="text-zinc-200">&lt; {slaMs} ms</strong> p95 SLA ceiling.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="px-3 py-1.5 rounded-lg bg-[#141417] border border-white/[0.08] text-xs font-mono text-zinc-300">
            <span>Evaluating {candidates.length} Archetypes</span>
          </div>
        </div>
      </div>

      {/* 2. Visual Candidate Cards Grid (Prominent Side-by-Side Presentation) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Generated System Archetypes ({candidates.length})
          </span>
          <span className="text-xs text-zinc-500">
            Select an archetype to expand simulation proofs below
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {candidates.map((cand) => (
            <CandidateCard
              key={cand.id}
              candidate={cand}
              isWinner={cand.id === winnerId}
              slaMs={slaMs}
              budgetUsd={budgetUsd}
              isSelected={cand.id === (selectedCandidateId || winnerId)}
              onSelectCandidate={() => setSelectedCandidateId(cand.id)}
            />
          ))}
        </div>
      </div>

      {/* 3. Detailed Side-by-Side Comparison Table */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Full Metrics &amp; Constraints Table
          </span>
          <span className="text-xs text-zinc-400 font-mono">
            Derived directly from SimPy physics engine
          </span>
        </div>

        <ArchitectureComparisonTable
          candidates={candidates}
          winnerId={winnerId}
          slaMs={slaMs}
          budgetUsd={budgetUsd}
        />
      </div>

      {/* 4. Candidate Deep-Dive & Constraint Proofs Accordion */}
      <div className="space-y-4 pt-4 border-t border-white/[0.08]">
        <div>
          <h3 className="text-sm font-bold text-white tracking-tight">
            Individual Candidate Deep-Dive &amp; Constraint Proofs
          </h3>
          <p className="text-xs text-zinc-400 mt-0.5">
            Examine the exact bottleneck components, queue wait times, and failure boundaries for each candidate.
          </p>
        </div>

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
