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
  ExternalLink,
  Github,
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
  } = useApp();

  const allFeatures = getRegisteredFeatures();
  const enabledFeatures = allFeatures.filter((f) => featureStates[f.id] !== false);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 font-sans">
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
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
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px]">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`}
              />
              <span className="text-slate-300 hidden md:inline">
                {backendConnected ? 'FastAPI Connected' : 'Connecting to API...'}
              </span>
            </div>

            {/* View Mode Toggle: Flow vs Tabbed */}
            <div className="flex items-center rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setViewMode('flow')}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                  viewMode === 'flow'
                    ? 'bg-indigo-600 text-white font-medium shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Full Dashboard Flow"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Flow</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('tabbed')}
                className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                  viewMode === 'tabbed'
                    ? 'bg-indigo-600 text-white font-medium shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
                title="Tabbed Navigation"
              >
                <ListFilter className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Tabs</span>
              </button>
            </div>

            {/* Feature Manager Button */}
            <button
              type="button"
              onClick={() => setIsFeatureManagerOpen(true)}
              className="btn btn-secondary text-xs flex items-center gap-1.5 border-indigo-500/30 hover:border-indigo-500/60"
            >
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Features ({enabledFeatures.length}/{allFeatures.length})</span>
            </button>
          </div>
        </div>

        {/* Tab Navigation (Visible in Tabbed Mode or as quick anchors) */}
        {viewMode === 'tabbed' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto py-2">
            {enabledFeatures.map((feat) => {
              const IconComp = feat.icon;
              const isActive = activeTab === feat.id;

              return (
                <button
                  key={feat.id}
                  type="button"
                  onClick={() => setActiveTab(feat.id)}
                  className={`btn text-xs py-1.5 px-3 shrink-0 flex items-center gap-2 rounded-lg transition-all ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                      : 'bg-slate-900/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {IconComp && <IconComp className="w-3.5 h-3.5" />}
                  <span>{feat.title}</span>
                  {feat.badge && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800/80 font-mono text-slate-300">
                      {feat.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {viewMode === 'flow' ? (
          /* Flow Mode: Render all enabled features in order */
          <div className="space-y-8">
            {enabledFeatures.map((feat) => {
              const FeatureComponent = feat.component;
              return (
                <section key={feat.id} id={feat.id} className="scroll-mt-20">
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
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-xs text-slate-500">
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
