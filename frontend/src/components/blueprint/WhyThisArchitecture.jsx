import React, { useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Layers, Scale } from 'lucide-react';

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
    <div className="rounded-2xl bg-[#0c101a] border border-white/[0.08] p-6 space-y-4">
      <div className="flex items-center gap-2 pb-3 border-b border-white/[0.06]">
        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
          Architecture Evaluation &amp; Trade-Offs
        </h2>
      </div>

      <div className="space-y-3">
        {/* Accordion 1: Why This Architecture Fits */}
        <div className="rounded-xl border border-white/[0.06] bg-black/25 overflow-hidden">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-3.5 px-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>1. Why this architecture fits your workload</span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="p-4 pt-1 border-t border-white/[0.04] text-xs text-slate-300 space-y-2 leading-relaxed">
              {rationale.map((r, idx) => (
                <div key={idx} className="flex items-start gap-2 text-slate-300">
                  <span className="text-emerald-400 font-bold shrink-0 mt-0.5">•</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 2: Trade-Offs Introduced */}
        <div className="rounded-xl border border-white/[0.06] bg-black/25 overflow-hidden">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'tradeoffs' ? null : 'tradeoffs')}
            className="w-full p-3.5 px-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
              <span>2. What trade-offs does it introduce?</span>
            </div>
            {openSection === 'tradeoffs' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {openSection === 'tradeoffs' && (
            <div className="p-4 pt-1 border-t border-white/[0.04] text-xs text-slate-300 space-y-2 leading-relaxed">
              {tradeOffs.map((t, idx) => (
                <div key={idx} className="flex items-start gap-2 text-slate-300">
                  <span className="text-amber-400 font-bold shrink-0 mt-0.5">•</span>
                  <span>{t}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Alternatives Considered */}
        <div className="rounded-xl border border-white/[0.06] bg-black/25 overflow-hidden">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
            className="w-full p-3.5 px-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              <span>3. What alternatives were evaluated?</span>
            </div>
            {openSection === 'alternatives' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {openSection === 'alternatives' && (
            <div className="p-4 pt-1 border-t border-white/[0.04] text-xs text-slate-300 space-y-3 leading-relaxed">
              {alternatives.length > 0 ? (
                alternatives.map((alt, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-black/30 border border-white/[0.04] space-y-1">
                    <div className="font-semibold text-slate-200">
                      {alt.name || alt.architecture_name}
                    </div>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      {alt.reason || alt.trade_off || alt.trade_off_vs_winner}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 text-xs">
                  Candidate alternatives (direct relational and asynchronous pipelines) were evaluated against hard SLA constraints and multi-objective Pareto scoring.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
