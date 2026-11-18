import React from 'react';
import { useApp } from '../../context/AppContext';
import RecommendationHero from './RecommendationHero';
import MetricGrid from './MetricGrid';
import WhyThisArchitecture from './WhyThisArchitecture';
import ReconsiderConditions from './ReconsiderConditions';

export default function ArchitectureBlueprint() {
  const { response } = useApp();

  const decisionResult = response?.decision_result || response?.decisionResult;
  const workload = decisionResult?.workload || response?.workload || {};
  const candidates = response?.candidates || [];
  const recommendation = response?.recommendation || {};
  const explanation = decisionResult?.explanation || {};

  const winner = recommendation.winner || candidates.find((c) => c.id === recommendation.winner_id) || candidates[1] || candidates[0];

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* 1. Hero: Architecture Identity & Connected Topology */}
      <RecommendationHero winner={winner} recommendation={recommendation} />

      {/* 2. Key Metrics Grid: Clear Visual Accent on p95 Latency SLA */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Simulated System Performance
          </span>
          <span className="text-xs text-zinc-400 font-mono">
            Calibrated under 500 RPS offered load
          </span>
        </div>
        <MetricGrid winner={winner} workload={workload} />
      </div>

      {/* 3. Deep Dive: Architect Rationale & Operational Boundaries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <WhyThisArchitecture recommendation={recommendation} candidates={candidates} />
        <ReconsiderConditions
          conditions={explanation.conditions_for_reconsideration || recommendation.conditions_for_change}
        />
      </div>
    </div>
  );
}
