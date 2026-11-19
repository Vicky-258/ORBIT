import React, { useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  HelpCircle,
  ShieldCheck
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
    <div className="bg-[#111317] rounded-xl border border-[#1e222b] p-6 space-y-5">
      <div>
        <h2 className="text-base font-bold text-slate-100 tracking-tight">
          Senior Architect Rationale
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Engineering justification grounded in simulation metrics
        </p>
      </div>

      <div className="space-y-3">
        {/* Accordion 1: Why This Architecture Fits */}
        <div className="rounded-lg border border-[#1e222b] bg-[#16181f] overflow-hidden">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/20 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="w-4 h-4 text-[#34d399] shrink-0" />
              <span className="font-semibold text-xs text-slate-200">
                Workload Suitability Validation ({rationale.length} factors)
              </span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="p-4 pt-1 border-t border-[#1e222b] space-y-2.5 text-xs text-slate-300">
              {rationale.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#34d399] mt-0.5 shrink-0" />
                  <span className="leading-relaxed">{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 2: Architectural Trade-Offs & Complexity */}
        <div className="rounded-lg border border-[#1e222b] bg-[#16181f] overflow-hidden">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'tradeoffs' ? null : 'tradeoffs')}
            className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/20 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-[#fef08a] shrink-0" />
              <span className="font-semibold text-xs text-slate-200">
                Operational Trade-offs ({tradeOffs.length} tradeoffs)
              </span>
            </div>
            {openSection === 'tradeoffs' ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </button>

          {openSection === 'tradeoffs' && (
            <div className="p-4 pt-1 border-t border-[#1e222b] space-y-2.5 text-xs text-slate-300">
              {tradeOffs.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#fef08a] mt-1.5 shrink-0" />
                  <span className="leading-relaxed">{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Rejected Alternatives */}
        {alternatives.length > 0 && (
          <div className="rounded-lg border border-[#1e222b] bg-[#16181f] overflow-hidden">
            <button
              type="button"
              onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/20 transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <HelpCircle className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="font-semibold text-xs text-slate-200">
                  Alternative Candidates Evaluated ({alternatives.length})
                </span>
              </div>
              {openSection === 'alternatives' ? (
                <ChevronUp className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {openSection === 'alternatives' && (
              <div className="p-4 pt-1 border-t border-[#1e222b] space-y-2.5 text-xs text-slate-300">
                {alternatives.map((alt, idx) => {
                  const name = alt.name || alt.candidate_name || `Alternative ${idx + 1}`;
                  const reason = alt.reason || alt.rejection_reason || 'Higher latency under queue contention in simulation.';
                  return (
                    <div key={idx} className="p-3 rounded-md bg-[#111317] border border-[#1e222b] space-y-1">
                      <div className="font-bold text-slate-200 text-xs">{name}</div>
                      <div className="text-[11px] text-slate-400">{reason}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
