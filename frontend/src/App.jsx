import React from 'react';
import Navbar from './components/Navbar';
import WorkloadPanel from './components/WorkloadPanel';
import ResultsPanel from './components/ResultsPanel';
import FeatureManager from './features/FeatureManager';

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-[#09090b] text-[#f4f4f5] overflow-hidden font-sans">
      {/* Top Navigation */}
      <Navbar />

      {/* Main Two-Column Studio Workspace */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left: Workload & Scenario Controls */}
        <WorkloadPanel />

        {/* Right: Simulation Canvas & Results */}
        <ResultsPanel />
      </div>

      {/* Dynamic Feature Slot Manager Modal */}
      <FeatureManager />
    </div>
  );
}
