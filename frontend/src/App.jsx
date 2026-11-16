import React from 'react';
import { useApp } from './context/AppContext';
import { getRegisteredFeatures } from './features/registry';
import FeatureManager from './features/FeatureManager';
import {
  Sparkles,
  Sliders,
  Layers,
  LayoutGrid,
  ListFilter,
  CheckCircle2,
  AlertCircle,
  Database,
  ArrowRight,
  ExternalLink,
  Award,
} from 'lucide-react';

export default function App() {
  const {
    activeTab,
    setActiveTab,
    viewMode,
    setViewMode,
    featureStates,
    backendConnected,
    setIsFeatureManagerOpen,
    response,
  } = useApp();

  const allFeatures = getRegisteredFeatures();
  const enabledFeatures = allFeatures.filter((f) => featureStates[f.id] !== false);

  const handleTabClick = (featId) => {
    setActiveTab(featId);
    if (viewMode === 'flow') {
      const el = document.getElementById(featId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  const winner = response?.section_d_recommendation?.winner;

  return (
    <div className="min-h-screen flex flex-col bg-[#09090b] text-[#f4f4f5]">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-[#27272a]/60 bg-[#09090b]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-15 flex items-center justify-between gap-4">
          {/* Logo & Platform Info */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-md shadow-indigo-600/30">
              <span className="text-white font-bold text-sm">⚡</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base tracking-tight text-white">AADS</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">v5.0</span>
              </div>
              <p className="text-[11px] text-zinc-400 hidden sm:block leading-none mt-0.5">
                Agentic Architecture Design & Simulation
              </p>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            {/* Backend Connectivity Status */}
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800 text-xs text-zinc-400">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`}
              />
              <span className="hidden sm:inline">
                {backendConnected ? 'API Ready (8000)' : 'Connecting...'}
              </span>
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center rounded-lg bg-zinc-900 border border-zinc-800 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('tabbed')}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                  viewMode === 'tabbed'
                    ? 'bg-zinc-800 text-white font-medium'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <ListFilter className="w-3.5 h-3.5" />
                <span>Tabs</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('flow')}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                  viewMode === 'flow'
                    ? 'bg-zinc-800 text-white font-medium'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>Flow</span>
              </button>
            </div>

            {/* Feature Manager Button */}
            <button
              type="button"
              onClick={() => setIsFeatureManagerOpen(true)}
              className="btn btn-secondary text-xs flex items-center gap-1.5 py-1 px-2.5"
            >
              <Sliders className="w-3.5 h-3.5 text-zinc-400" />
              <span>Features ({enabledFeatures.length}/{allFeatures.length})</span>
            </button>
          </div>
        </div>

        {/* Clean Segmented Tab Bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 border-t border-zinc-800/40 flex items-center gap-1 overflow-x-auto py-2">
          {enabledFeatures.map((feat) => {
            const IconComp = feat.icon;
            const isActive = activeTab === feat.id;

            return (
              <button
                key={feat.id}
                type="button"
                onClick={() => handleTabClick(feat.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-zinc-800 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/60'
                }`}
              >
                {IconComp && <IconComp className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-zinc-500'}`} />}
                <span>{feat.title}</span>
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Recommendation Notification Banner if winner is selected */}
        {winner && (
          <div className="p-4 rounded-xl bg-zinc-900 border border-emerald-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-lg">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 shrink-0">
                <Award className="w-5 h-5" />
              </div>
              <div>
                <div className="text-xs font-semibold text-emerald-400">
                  Recommendation Ready
                </div>
                <div className="text-sm font-semibold text-white mt-0.5">
                  Winning Architecture: <span className="text-emerald-300">{winner.name || winner.id}</span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setActiveTab('recommendation')}
              className="btn btn-primary text-xs px-3.5 py-1.5 self-start sm:self-auto"
            >
              <span>View Recommendation</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {viewMode === 'flow' ? (
          /* Flow Mode: Render all enabled features in order */
          <div className="space-y-8">
            {enabledFeatures.map((feat) => {
              const FeatureComponent = feat.component;
              return (
                <section key={feat.id} id={feat.id} className="scroll-mt-24">
                  <FeatureComponent />
                </section>
              );
            })}
          </div>
        ) : (
          /* Tabbed Mode: Render only active tab component */
          <div>
            {(() => {
              const activeFeature = enabledFeatures.find((f) => f.id === activeTab) || enabledFeatures[0];
              if (!activeFeature) {
                return (
                  <div className="panel p-8 text-center text-zinc-400">
                    No active feature selected. Use the Feature Manager to enable features.
                  </div>
                );
              }
              const ActiveComponent = activeFeature.component;
              return <ActiveComponent />;
            })()}
          </div>
        )}
      </main>

      {/* Feature Manager Modal */}
      <FeatureManager />

      {/* Footer */}
      <footer className="border-t border-zinc-800/60 bg-[#09090b] py-5 text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            <span>AADS Empirical Architecture Platform</span>
            <span>•</span>
            <span className="font-mono text-zinc-400 text-[11px]">
              Manifest: 69d3e068...77a6 (Frozen)
            </span>
          </div>
          <div className="flex items-center gap-4 text-zinc-400">
            <span>FastAPI: <code className="text-zinc-300 font-mono">localhost:8000</code></span>
            <span>•</span>
            <span>React: <code className="text-zinc-300 font-mono">localhost:3000</code></span>
          </div>
        </div>
      </footer>
    </div>
  );
}
