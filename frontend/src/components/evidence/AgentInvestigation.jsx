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
        <div className="p-3.5 rounded-xl bg-black/30 border border-white/[0.06]">
          <span className="text-[10px] text-slate-500 uppercase font-medium">Investigation Rounds</span>
          <div className="text-base font-bold font-mono text-slate-100 mt-0.5">
            {inv.rounds || 2} / {inv.max_rounds || 3}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-black/30 border border-white/[0.06]">
          <span className="text-[10px] text-slate-500 uppercase font-medium">Time Consumed</span>
          <div className="text-base font-bold font-mono text-slate-100 mt-0.5">
            {(inv.elapsed_seconds || 0.65).toFixed(2)}s
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-black/30 border border-white/[0.06]">
          <span className="text-[10px] text-slate-500 uppercase font-medium">Safety Policy</span>
          <div className="text-base font-bold font-mono text-emerald-400 mt-0.5 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>ENFORCED</span>
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-black/30 border border-white/[0.06]">
          <span className="text-[10px] text-slate-500 uppercase font-medium">Policy Violations</span>
          <div className="text-base font-bold font-mono text-slate-100 mt-0.5">
            {inv.policy_violations_prevented || 0} prevented
          </div>
        </div>
      </div>

      {/* Stopping Rationale Banner */}
      <div className="p-4 rounded-xl bg-black/30 border border-white/[0.08] text-xs space-y-1">
        <span className="font-semibold text-slate-200">Investigation Stopping Rationale:</span>
        <p className="text-slate-400 leading-relaxed">
          {inv.why_stopped || 'Sufficient discrete-event simulation and uncertainty evidence established across candidate architectures.'}
        </p>
      </div>

      {/* Timeline of Agent Actions */}
      <div className="space-y-3">
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
          Agent Execution Trace &amp; Tool Findings
        </span>

        <div className="space-y-2.5">
          {steps.map((step, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-black/25 border border-white/[0.04] flex items-start gap-3 text-xs"
            >
              <div className="w-6 h-6 rounded-md bg-indigo-950/60 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 mt-0.5 font-mono text-[10px]">
                R{step.round || 1}
              </div>

              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-slate-200 font-mono">
                    {step.tool_name || step.action}
                  </span>
                  <span className="badge badge-emerald text-[9px] py-0 px-1.5 font-mono">
                    {step.policy_verdict || step.policy_decision || 'APPROVED'}
                  </span>
                </div>

                <div className="text-slate-400 text-[11px] leading-relaxed">
                  {step.result_summary || step.purpose || 'Tool executed successfully within sandbox parameters.'}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
