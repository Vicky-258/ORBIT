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
    <div className="bg-[#121215] rounded-xl border border-white/[0.08] p-5 sm:p-6 space-y-4 shadow-xs">
      <div className="flex items-center gap-2.5 pb-3 border-b border-white/[0.06]">
        <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
          <CheckCircle2 className="w-4 h-4" />
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
        <div className="rounded-xl border border-zinc-800 bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'why' ? null : 'why')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-sm font-semibold text-white">1. Why this architecture fits your workload</span>
            </div>
            {openSection === 'why' ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {openSection === 'why' && (
            <div className="px-4 pb-4 pt-1 border-t border-zinc-800 space-y-2 text-xs text-zinc-300 leading-relaxed">
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

        {/* Accordion 2: Trade-offs & Operational Risks */}
        <div className="rounded-xl border border-zinc-800 bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
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
            <div className="px-4 pb-4 pt-1 border-t border-zinc-800 space-y-2 text-xs text-zinc-300 leading-relaxed">
              {tradeOffs.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2.5">
                  <div className="w-4 h-4 rounded-full bg-amber-500/10 flex items-center justify-center shrink-0 mt-0.5 border border-amber-500/20">
                    <span className="text-[10px] font-bold text-amber-400">!</span>
                  </div>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Accordion 3: Architectural Alternatives Comparison */}
        <div className="rounded-xl border border-zinc-800 bg-[#09090b] overflow-hidden hover:border-zinc-700 transition-all">
          <button
            type="button"
            onClick={() => setOpenSection(openSection === 'alternatives' ? null : 'alternatives')}
            className="w-full p-4 flex items-center justify-between text-left text-xs font-semibold text-zinc-200 hover:text-white transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2.5">
              <span className="w-2 h-2 rounded-full bg-zinc-500" />
              <span className="text-sm font-semibold text-white">3. When alternatives are appropriate</span>
            </div>
            {openSection === 'alternatives' ? (
              <ChevronUp className="w-4 h-4 text-zinc-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-zinc-500" />
            )}
          </button>

          {openSection === 'alternatives' && (
            <div className="px-4 pb-4 pt-1 border-t border-zinc-800 space-y-3 text-xs text-zinc-300 leading-relaxed">
              {alternatives.length > 0 ? (
                alternatives.map((alt, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 space-y-1">
                    <div className="font-semibold text-zinc-200 flex items-center justify-between">
                      <span>{alt.name || alt.candidate_id}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                        {alt.status || 'Evaluated'}
                      </span>
                    </div>
                    <p className="text-zinc-400 text-xs">
                      {alt.reason_not_chosen || alt.why_not_selected || alt.summary}
                    </p>
                  </div>
                ))
              ) : (
                <div className="space-y-2">
                  <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 space-y-1">
                    <div className="font-semibold text-zinc-200">
                      When direct PostgreSQL stops being sufficient:
                    </div>
                    <p className="text-zinc-400">
                      Direct PostgreSQL is operationally simpler and cost-effective under 150 RPS. Above 300 RPS read traffic, connection pool exhaustion and disk IOPS latency degrade p95 response times beyond the 100ms threshold.
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-800 space-y-1">
                    <div className="font-semibold text-zinc-200">
                      When asynchronous queue processing is unnecessary:
                    </div>
                    <p className="text-zinc-400">
                      Kafka or RabbitMQ event buffers excel for write-heavy burst absorption (read ratio &lt; 20%), but introduce eventual consistency and unnecessary worker fleet complexity for read-heavy OLTP APIs.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
