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
    <div className="h-screen w-screen flex flex-col bg-[#f8fafc] text-slate-900 overflow-hidden font-sans">
      {/* 1. Global Application Header */}
      <AppHeader />

      {/* 2. Compact Workload Summary Bar */}
      <WorkloadSummary />

      {/* 3. Main Navigation (01 Blueprint, 02 Compare, 03 Technical) */}
      <MainNavigation />

      {/* 4. Main Scrollable Content Canvas */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 min-h-0 bg-[#f8fafc]">
        <div className="max-w-6xl mx-auto">
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
