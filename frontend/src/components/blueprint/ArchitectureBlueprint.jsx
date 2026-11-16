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

  const winner = recommendation.winner || candidates.find((c) => c.id === recommendation.winner_id) || candidates[0];

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Section A: Recommendation Hero */}
      <RecommendationHero winner={winner} recommendation={recommendation} />

      {/* Section B: Key Performance Indicators */}
      <MetricGrid winner={winner} workload={workload} />

      {/* Two Column Layout for Section C & Section D */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Section C: Why This Architecture? */}
        <WhyThisArchitecture recommendation={recommendation} candidates={candidates} />

        {/* Section D: When Should You Reconsider? */}
        <ReconsiderConditions
          conditions={explanation.conditions_for_reconsideration || recommendation.conditions_for_change}
        />
      </div>
    </div>
  );
}
