import React from 'react';
import { useApp } from '../../context/AppContext';
import { getRegisteredFeatures } from '../registry';
import {
  X,
  Sliders,
  RotateCcw,
  Check,
  PlusCircle,
  HelpCircle,
  Sparkles,
} from 'lucide-react';

export default function FeatureManager() {
  const {
    isFeatureManagerOpen,
    setIsFeatureManagerOpen,
    featureStates,
    toggleFeature,
    resetFeatures,
  } = useApp();

  if (!isFeatureManagerOpen) return null;

  const features = getRegisteredFeatures();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="glass-panel w-full max-w-2xl bg-slate-900 border border-slate-700 shadow-2xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Feature & Modular Slot Manager</h2>
              <p className="text-xs text-slate-400">
                Easily toggle, enable, or disable features in your AADS workspace in real-time.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsFeatureManagerOpen(false)}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feature List */}
        <div className="p-5 overflow-y-auto space-y-3 divide-y divide-slate-800/60">
          {features.map((feat) => {
            const isEnabled = featureStates[feat.id] !== false;
            const IconComp = feat.icon;

            return (
              <div key={feat.id} className="pt-3 first:pt-0 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg mt-0.5 ${isEnabled ? 'bg-indigo-500/20 text-indigo-300' : 'bg-slate-800 text-slate-500'}`}>
                    {IconComp ? <IconComp className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-200">{feat.title}</span>
                      {feat.badge && (
                        <span className="badge badge-slate text-[10px]">{feat.badge}</span>
                      )}
                      {feat.required && (
                        <span className="badge badge-indigo text-[10px]">Required</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{feat.description}</p>
                    <span className="text-[10px] font-mono text-slate-500">Category: {feat.category}</span>
                  </div>
                </div>

                <div className="shrink-0 pt-1">
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      disabled={feat.required}
                      onChange={() => toggleFeature(feat.id)}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>
            );
          })}
        </div>

        {/* Developer Guide Snippet: How to add new features */}
        <div className="p-4 bg-slate-950/80 border-t border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-indigo-300 flex items-center gap-1.5">
              <PlusCircle className="w-3.5 h-3.5" /> How to Add a New Feature
            </span>
            <span className="text-slate-500 font-mono text-[10px]">Modular Feature Architecture</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Drop your component into <code className="text-indigo-300 font-mono">src/features/YourFeature/index.jsx</code> and add 1 line to <code className="text-indigo-300 font-mono">src/features/registry.js</code>. It will automatically mount, register in the state tree, and appear in this manager!
          </p>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between">
          <button
            type="button"
            onClick={resetFeatures}
            className="btn btn-ghost text-xs flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset Defaults
          </button>
          <button
            type="button"
            onClick={() => setIsFeatureManagerOpen(false)}
            className="btn btn-primary text-xs px-5"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
