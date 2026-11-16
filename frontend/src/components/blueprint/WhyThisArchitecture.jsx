import React, { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Check, Layers, AlertCircle } from 'lucide-react';

export default function WhyThisArchitecture({ recommendation = {}, candidates = [] }) {
  const [openSection, setOpenSection] = useState('why'); // 'why' | 'tradeoffs' | 'alternatives'

  const rationale = recommendation.decision_rationale || [
    'Meets all hard constraints under discrete-event queue contention.',
    'Provides the optimal balance of response time, cost, and operational simplicity.',
  ];

  const tradeOffs = recommendation.main_trade_offs || recommendation.trade_offs_and_risks || [
    'Introduces cache invalidation complexity and cache synchronization policies.',
    'Adds an extra infrastructure dependency to provision and monitor.',
  ];

  const alternatives = recommendation.rejected_alternatives || [];

  return (
    <div className="saas-card p-6 space-y-4">
      <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
        <div className="w-7 h-7 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 shadow-2xs">
          <CheckCircle2 className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            Senior Architect Rationale
          </h2>
          <p className="text-xs text-slate-500">
            Why this topology wins under your latency and cost constraints
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {/* Accordion 1: Why This Architecture Fits */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 overflow-hidden hover:border-slate-300 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-800 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-sm font-semibold">1. Why this architecture fits your workload</span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="p-4 pt-1 border-t border-slate-200/60 text-xs text-slate-700 space-y-2.5 leading-relaxed bg-white">
              {rationale.map((r, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-slate-700">
                  <div className="w-4 h-4 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-700 shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5" />
                  </div>
                  <span className="text-slate-700 leading-normal">{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 2: Trade-Offs Introduced */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 overflow-hidden hover:border-slate-300 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'tradeoffs' ? null : 'tradeoffs')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-800 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-sm font-semibold">2. What trade-offs does it introduce?</span>
            </div>
            {openSection === 'tradeoffs' ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {openSection === 'tradeoffs' && (
            <div className="p-4 pt-1 border-t border-slate-200/60 text-xs text-slate-700 space-y-2.5 leading-relaxed bg-white">
              {tradeOffs.map((t, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-slate-700">
                  <div className="w-4 h-4 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700 shrink-0 mt-0.5">
                    <AlertCircle className="w-2.5 h-2.5" />
                  </div>
                  <span className="text-slate-700 leading-normal">{t}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Alternatives Considered */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 overflow-hidden hover:border-slate-300 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-800 hover:text-slate-900 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              <span className="text-sm font-semibold">3. What alternatives were evaluated?</span>
            </div>
            {openSection === 'alternatives' ? (
              <ChevronUp className="w-4 h-4 text-slate-500" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {openSection === 'alternatives' && (
            <div className="p-4 pt-1 border-t border-slate-200/60 text-xs text-slate-700 space-y-3 leading-relaxed bg-white">
              {alternatives.length > 0 ? (
                alternatives.map((alt, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-slate-500" />
                      <span>{alt.name || alt.architecture_name}</span>
                    </div>
                    <p className="text-xs text-slate-600 leading-normal pl-5">
                      {alt.reason || alt.trade_off || alt.trade_off_vs_winner}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-slate-500 text-xs">
                  Candidate alternatives were evaluated against hard SLA constraints and multi-objective Pareto scoring.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
