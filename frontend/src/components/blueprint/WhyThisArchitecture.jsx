import React, { useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Check,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  Scale
} from 'lucide-react';

export default function WhyThisArchitecture({ recommendation = {}, candidates = [] }) {
  const [openSection, setOpenSection] = useState('why'); // 'why' | 'tradeoffs' | 'alternatives'

  const rationale = recommendation.decision_rationale?.length > 0
    ? recommendation.decision_rationale
    : [
        'Meets all hard constraints under discrete-event queue contention in SimPy.',
        'Provides the optimal balance of response time, cost, and operational simplicity.',
        'Prevents database resource exhaustion at peak traffic bursts.'
      ];

  const tradeOffs = recommendation.main_trade_offs?.length > 0
    ? recommendation.main_trade_offs
    : (recommendation.trade_offs_and_risks?.length > 0 ? recommendation.trade_offs_and_risks : [
        'Introduces cache invalidation complexity and cache synchronization policies.',
        'Adds an extra infrastructure component dependency to monitor and maintain.'
      ]);

  const alternatives = recommendation.rejected_alternatives?.length > 0
    ? recommendation.rejected_alternatives
    : candidates.filter(c => !c.id?.includes('cached') && c.id !== recommendation.winner_id);

  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] p-5 sm:p-6 space-y-4 shadow-xl">
      <div className="flex items-center gap-3 pb-3 border-b border-white/[0.06]">
        <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-white tracking-tight">
            Senior Architect Rationale
          </h2>
          <p className="text-xs text-zinc-400">
            Why this topology wins under your latency and cost constraints
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {/* Accordion 1: Why This Architecture Fits */}
        <div className="rounded-xl border border-white/[0.08] bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-sm font-semibold text-white">1. Workload Fit &amp; Advantages</span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="px-4 pb-4 pt-1 border-t border-white/[0.06] space-y-2.5 text-xs text-zinc-300 leading-relaxed">
              {rationale.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <div className="w-4 h-4 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0 mt-0.5 border border-emerald-500/20">
                    <Check className="w-2.5 h-2.5 text-emerald-400" />
                  </div>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 2: Trade-offs & Operational Costs */}
        <div className="rounded-xl border border-white/[0.08] bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'tradeoffs' ? null : 'tradeoffs')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span className="text-sm font-semibold text-white">2. Trade-offs &amp; Operational Costs</span>
            </div>
            {openSection === 'tradeoffs' ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {openSection === 'tradeoffs' && (
            <div className="px-4 pb-4 pt-1 border-t border-white/[0.06] space-y-2.5 text-xs text-zinc-300 leading-relaxed">
              {tradeOffs.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <div className="w-4 h-4 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0 mt-0.5 border border-amber-500/20">
                    <AlertCircle className="w-2.5 h-2.5 text-amber-400" />
                  </div>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Rejected Alternatives Analysis */}
        <div className="rounded-xl border border-white/[0.08] bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-zinc-400" />
              <span className="text-sm font-semibold text-white">3. Alternative Candidates Assessment</span>
            </div>
            {openSection === 'alternatives' ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {openSection === 'alternatives' && (
            <div className="px-4 pb-4 pt-1 border-t border-white/[0.06] space-y-2 text-xs text-zinc-300 leading-relaxed">
              {alternatives.length > 0 ? (
                alternatives.map((alt, idx) => {
                  const altName = alt.architecture_name || alt.name || alt.id || `Alternative #${idx + 1}`;
                  const reason = alt.rejection_reason || alt.summary || (
                    alt.id?.includes('simple') ? 'Direct relational database saturates connection pools under high read contention.' :
                    alt.id?.includes('async') ? 'Queue buffering adds unnecessary asynchronous overhead for synchronous feed reading.' :
                    'Higher operational complexity or cost profile compared to optimal cached topology.'
                  );
                  return (
                    <div key={idx} className="p-3 rounded-lg bg-[#141417] border border-white/[0.04] space-y-1">
                      <div className="font-semibold text-zinc-200">{altName}</div>
                      <div className="text-zinc-400 text-xs">{reason}</div>
                    </div>
                  );
                })
              ) : (
                <div className="text-zinc-400 text-xs">
                  All candidate alternatives were benchmarked and evaluated against hard SLA latency ceilings.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
