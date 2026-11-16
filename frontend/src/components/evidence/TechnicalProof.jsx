import React, { useState } from 'react';
import AgentInvestigation from './AgentInvestigation';
import BenchmarkEvidence from './BenchmarkEvidence';
import ModelCoverage from './ModelCoverage';
import UncertaintyPanel from './UncertaintyPanel';
import ModelRegistryBrowser from '../../features/ModelRegistryBrowser';
import { Bot, ShieldCheck, Database, HelpCircle, HardDrive } from 'lucide-react';

export default function TechnicalProof() {
  const [subTab, setSubTab] = useState('investigation');

  const SUB_TABS = [
    { id: 'investigation', label: 'Agent Investigation', icon: Bot },
    { id: 'benchmark', label: 'Benchmark Evidence', icon: ShieldCheck },
    { id: 'coverage', label: 'Model Coverage', icon: HardDrive },
    { id: 'uncertainty', label: 'Uncertainty & Limits', icon: HelpCircle },
    { id: 'registry', label: 'Model Registry (24)', icon: Database },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto pb-12">
      {/* Header and Sub-Tab Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
        <div>
          <h2 className="text-lg font-bold text-slate-100 tracking-tight">
            Technical Proof, Evidence &amp; Model Calibration
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Empirical measurements, discrete-event queueing traces, and model coverage bounds
          </p>
        </div>

        {/* Sub-tab pills */}
        <div className="flex items-center gap-1.5 bg-black/40 p-1 rounded-xl border border-white/[0.08] overflow-x-auto shrink-0">
          {SUB_TABS.map((tab) => {
            const Icon = tab.icon;
            const isCurrent = subTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSubTab(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
                  isCurrent
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active Sub-Tab View */}
      {subTab === 'investigation' && <AgentInvestigation />}
      {subTab === 'benchmark' && <BenchmarkEvidence />}
      {subTab === 'coverage' && <ModelCoverage />}
      {subTab === 'uncertainty' && <UncertaintyPanel />}
      {subTab === 'registry' && <ModelRegistryBrowser />}
    </div>
  );
}
