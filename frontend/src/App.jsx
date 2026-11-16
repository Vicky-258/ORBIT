import React from 'react';
import { useApp } from './context/AppContext';

import AppHeader from './components/layout/AppHeader';
import WorkloadSummary from './components/layout/WorkloadSummary';
import MainNavigation from './components/layout/MainNavigation';

import WorkloadDrawer from './components/workload/WorkloadDrawer';
import ImplementationPromptModal from './components/blueprint/ImplementationPromptModal';

import ArchitectureBlueprint from './components/blueprint/ArchitectureBlueprint';
import CompareOptions from './components/comparison/CompareOptions';
import TechnicalProof from './components/evidence/TechnicalProof';

import LoadingState from './components/shared/LoadingState';
import ErrorState from './components/shared/ErrorState';
import EmptyState from './components/shared/EmptyState';
import FeatureManager from './features/FeatureManager';

export default function App() {
  const {
    activeTab,
    loading,
    error,
    response,
    handleRunWorkflow,
    loadPreset,
  } = useApp();

  return (
    <div className="h-screen w-screen flex flex-col bg-[#080c16] text-slate-100 overflow-hidden font-sans">
      {/* 1. Global Application Header */}
      <AppHeader />

      {/* 2. Compact Workload Summary Bar */}
      <WorkloadSummary />

      {/* 3. Main Navigation (01 Blueprint, 02 Compare, 03 Technical) */}
      <MainNavigation />

      {/* 4. Main Scrollable Content Canvas with SaaS Ambient Light */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 min-h-0 bg-[#080c16] relative">
        {/* Subtle Ambient SaaS Spotlight */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1100px] h-[400px] bg-radial from-indigo-500/[0.12] via-violet-500/[0.04] to-transparent rounded-full blur-3xl pointer-events-none -mt-36" />

        <div className="relative z-10">
          {loading ? (
            <LoadingState message="Simulating Architectures & Evaluating Constraints..." />
          ) : error ? (
            <ErrorState error={error} onRetry={() => handleRunWorkflow()} />
          ) : !response ? (
            <EmptyState />
          ) : (
            <>
              {activeTab === 'blueprint' && <ArchitectureBlueprint />}
              {activeTab === 'compare' && <CompareOptions />}
              {activeTab === 'technical' && <TechnicalProof />}
            </>
          )}
        </div>
      </main>

      {/* 5. Drawers and Modals */}
      <WorkloadDrawer />
      <ImplementationPromptModal />
      <FeatureManager />
    </div>
  );
}
