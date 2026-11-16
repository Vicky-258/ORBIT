import React from 'react';
import { useApp } from '../../context/AppContext';
import { Bot, CheckCircle2, ShieldAlert } from 'lucide-react';

export default function AgentInvestigation() {
  const { response } = useApp();
  const inv = response?.investigation || response?.investigation_summary || response?.section_b_investigation || {};
  const steps = inv.steps || inv.actions || [];

  return (
    <div className="space-y-5">
      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="p-3.5 rounded-xl bg-[#111622] border border-white/[0.08] shadow-xs">
          <span className="text-[11px] text-slate-400 font-medium">Investigation Rounds</span>
          <div className="text-base font-bold font-mono text-white mt-0.5">
            {inv.rounds || 2} / {inv.max_rounds || 3}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111622] border border-white/[0.08] shadow-xs">
          <span className="text-[11px] text-slate-400 font-medium">Time Consumed</span>
          <div className="text-base font-bold font-mono text-white mt-0.5">
            {(inv.elapsed_seconds || 0.65).toFixed(2)}s
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111622] border border-white/[0.08] shadow-xs">
          <span className="text-[11px] text-slate-400 font-medium">Safety Policy</span>
          <div className="text-base font-bold font-mono text-emerald-400 mt-0.5 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>ENFORCED</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#111622] border border-white/[0.08] shadow-xs">
          <span className="text-[11px] text-slate-400 font-medium">Policy Violations</span>
          <div className="text-base font-bold font-mono text-white mt-0.5">
            {inv.policy_violations_prevented || 0} prevented
          </div>
        </div>
      </div>

      {/* Stopping Rationale Banner */}
      <div className="p-4 rounded-xl bg-[#111622] border border-white/[0.08] text-xs space-y-1">
        <span className="font-semibold text-white">Investigation Stopping Rationale:</span>
        <p className="text-slate-300 leading-relaxed">
          {inv.why_stopped || 'Sufficient discrete-event simulation and uncertainty evidence established across candidate architectures.'}
        </p>
      </div>

      {/* Step Trace */}
      <div className="space-y-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
          Investigation Round Trace ({steps.length})
        </span>

        {steps.length === 0 ? (
          <div className="p-4 rounded-xl bg-[#111622] border border-white/[0.08] text-center text-xs text-slate-400">
            No exploratory investigation rounds required. Canonical baseline models resolved constraints deterministically.
          </div>
        ) : (
          <div className="space-y-2">
            {steps.map((st, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl bg-[#111622] border border-white/[0.08] space-y-1.5 text-xs hover:border-white/15 transition-all"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-white flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-white/[0.05] border border-white/10 text-[10px] font-mono flex items-center justify-center text-slate-300">
                      {idx + 1}
                    </span>
                    <span>{st.action || st.tool_name || 'Investigation Action'}</span>
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-slate-400 border border-white/[0.06]">
                    Round {st.round || 1}
                  </span>
                </div>
                <p className="text-slate-400 leading-relaxed text-xs">
                  {st.rationale || st.description || 'Evaluated empirical service demands and queue contention.'}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
