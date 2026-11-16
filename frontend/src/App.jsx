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
    <div className="min-h-screen flex flex-col bg-[#080c14] text-slate-100 font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#080c14]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Logo & Platform Info */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/30 flex items-center justify-center">
              <span className="text-white font-black text-lg select-none">⚡</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold text-base tracking-tight text-white">AADS</h1>
                <span className="badge badge-indigo text-[10px] font-mono">React v5.0</span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Agentic Architecture Design & Simulation
              </p>
            </div>
          </div>

          {/* Navigation Controls & Action Buttons */}
          <div className="flex items-center gap-3">
            {/* Backend Connectivity Status Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-[11px]">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`}
              />
              <span className="text-slate-300 hidden md:inline">
                {backendConnected ? 'FastAPI Connected (8000)' : 'Connecting to API...'}
              </span>
            </div>

            {/* View Mode Toggle: Flow vs Tabbed */}
            <div className="flex items-center rounded-xl bg-slate-900 border border-slate-800 p-1 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('tabbed')}
                className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                  viewMode === 'tabbed'
                    ? 'bg-indigo-600 text-white font-medium shadow-md shadow-indigo-600/30'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Tabbed Navigation"
              >
                <ListFilter className="w-3.5 h-3.5" />
                <span>Tabs</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('flow')}
                className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 ${
                  viewMode === 'flow'
                    ? 'bg-indigo-600 text-white font-medium shadow-md shadow-indigo-600/30'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Full Continuous Flow"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>Flow</span>
              </button>
            </div>

            {/* Feature Manager Button */}
            <button
              type="button"
              onClick={() => setIsFeatureManagerOpen(true)}
              className="btn btn-secondary text-xs flex items-center gap-1.5 border-indigo-500/30 hover:border-indigo-500/60 px-3 py-1.5"
            >
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Features ({enabledFeatures.length}/{allFeatures.length})</span>
            </button>
          </div>
        </div>

        {/* Global Tab Navigation Bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto py-2.5">
          {enabledFeatures.map((feat) => {
            const IconComp = feat.icon;
            const isActive = activeTab === feat.id;

            return (
              <button
                key={feat.id}
                type="button"
                onClick={() => handleTabClick(feat.id)}
                className={`btn text-xs py-2 px-3.5 shrink-0 flex items-center gap-2 rounded-xl transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white font-semibold shadow-lg shadow-indigo-600/30'
                    : 'bg-slate-900/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-slate-800'
                }`}
              >
                {IconComp && <IconComp className="w-3.5 h-3.5" />}
                <span>{feat.title}</span>
                {feat.badge && (
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${
                      isActive ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {feat.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Recommendation Alert Banner if run completed */}
        {winner && (
          <div className="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/40 via-slate-900 to-indigo-950/40 border border-emerald-500/40 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-emerald-500/20 text-emerald-400 shrink-0">
                <Award className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    Recommendation Synthesized
                  </span>
                  <span className="badge badge-emerald text-[10px]">Optimal Topology</span>
                </div>
                <div className="text-sm font-semibold text-white mt-0.5">
                  Winner: <span className="text-emerald-300 font-bold">{winner.name || winner.id}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setActiveTab('recommendation')}
                className="btn btn-primary text-xs px-4 py-2 flex items-center gap-1.5"
              >
                <span>View Full Recommendation & Trade-Offs</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {viewMode === 'flow' ? (
          /* Flow Mode: Render all enabled features in order */
          <div className="space-y-8">
            {enabledFeatures.map((feat) => {
              const FeatureComponent = feat.component;
              return (
                <section key={feat.id} id={feat.id} className="scroll-mt-28">
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
                  <div className="glass-panel p-8 text-center text-slate-400">
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
      <footer className="border-t border-slate-800/80 bg-[#080c14]/80 py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            <span>AADS Empirical Architecture Platform</span>
            <span>•</span>
            <span className="font-mono text-slate-400">
              SHA-256: 69d3e068...77a6 (Frozen)
            </span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>FastAPI: <code className="text-indigo-400 font-mono">http://localhost:8000</code></span>
            <span>•</span>
            <span>React: <code className="text-cyan-400 font-mono">http://localhost:3000</code></span>
          </div>
        </div>
      </footer>
    </div>
  );
}
