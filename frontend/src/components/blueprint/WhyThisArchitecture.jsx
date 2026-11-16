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
      <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.06]">
        <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shadow-sm">
          <CheckCircle2 className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-100 tracking-tight">
            Senior Architect Rationale
          </h2>
          <p className="text-[11px] text-slate-400">
            Why this topology wins under your latency and cost constraints
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {/* Accordion 1: Why This Architecture Fits */}
        <div className="rounded-xl border border-white/[0.08] bg-slate-900/50 overflow-hidden hover:border-white/[0.14] transition-all shadow-sm">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
              <span className="text-sm">1. Why this architecture fits your workload</span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="p-4 pt-1 border-t border-white/[0.04] text-xs text-slate-300 space-y-2.5 leading-relaxed bg-black/20">
              {rationale.map((r, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-slate-300">
                  <div className="w-4 h-4 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                    <Check className="w-2.5 h-2.5" />
                  </div>
                  <span className="text-slate-200 leading-normal">{r}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 2: Trade-Offs Introduced */}
        <div className="rounded-xl border border-white/[0.08] bg-slate-900/50 overflow-hidden hover:border-white/[0.14] transition-all shadow-sm">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'tradeoffs' ? null : 'tradeoffs')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]" />
              <span className="text-sm">2. What trade-offs does it introduce?</span>
            </div>
            {openSection === 'tradeoffs' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-500" />
            )}
          </button>

          {openSection === 'tradeoffs' && (
            <div className="p-4 pt-1 border-t border-white/[0.04] text-xs text-slate-300 space-y-2.5 leading-relaxed bg-black/20">
              {tradeOffs.map((t, idx) => (
                <div key={idx} className="flex items-start gap-2.5 text-slate-300">
                  <div className="w-4 h-4 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shrink-0 mt-0.5">
                    <AlertCircle className="w-2.5 h-2.5" />
                  </div>
                  <span className="text-slate-200 leading-normal">{t}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Alternatives Considered */}
        <div className="rounded-xl border border-white/[0.06] bg-black/20 overflow-hidden hover:border-white/[0.12] transition-colors">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-slate-100 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-indigo-400 shadow-[0_0_8px_rgba(129,140,248,0.6)]" />
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
                  <div key={idx} className="p-3 rounded-lg bg-black/40 border border-white/[0.04] space-y-1">
                    <div className="font-semibold text-slate-200 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-slate-400" />
                      <span>{alt.name || alt.architecture_name}</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-normal pl-5">
                      {alt.reason || alt.trade_off || alt.trade_off_vs_winner}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-slate-400 text-xs">
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
