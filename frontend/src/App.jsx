import React, { useEffect } from 'react';
import { useApp } from './context/AppContext';

import PromptStudio from './components/prompt/PromptStudio';
import ResultsHeader from './components/layout/ResultsHeader';

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
    viewMode,
    goToPrompt,
    activeTab,
    loading,
    error,
    response,
    handleRunWorkflow,
  } = useApp();

  // Keyboard shortcut: Esc returns to Prompt Studio if on results page
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && viewMode === 'results') {
        goToPrompt();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewMode, goToPrompt]);

  // Stage 1: Prompt-Focused Studio
  if (viewMode === 'prompt') {
    return (
      <div className="h-screen w-screen flex flex-col bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
        <PromptStudio />
        <ImplementationPromptModal />
        <FeatureManager />
      </div>
    );
  }

  // Stage 2: Architecture Blueprint & Results
  return (
    <div className="h-screen w-screen flex flex-col bg-[#09090b] text-zinc-100 overflow-hidden font-sans">
      {/* 1. Results Navigation & Context Header */}
      <ResultsHeader />

      {/* 2. Main Scrollable Content Canvas */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 min-h-0 bg-[#09090b]">
        <div className="max-w-6xl mx-auto">
          {loading ? (
            <LoadingState message="Simulating Candidate Topologies & Evaluating Constraints..." />
          ) : error ? (
            <ErrorState error={error} onRetry={() => handleRunWorkflow()} />
          ) : !response ? (
            <EmptyState onGoToPrompt={goToPrompt} />
          ) : (
            <>
              {activeTab === 'blueprint' && <ArchitectureBlueprint />}
              {activeTab === 'compare' && <CompareOptions />}
              {activeTab === 'technical' && <TechnicalProof />}
            </>
          )}
        </div>
      </main>

      {/* 3. Global Drawers and Modals */}
      <WorkloadDrawer />
      <ImplementationPromptModal />
      <FeatureManager />
    </div>
  );
}
