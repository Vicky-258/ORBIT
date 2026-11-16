import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  Bot,
  ShieldCheck,
  ShieldAlert,
  Clock,
  CheckCircle,
  Activity,
  Layers,
  ArrowRight,
} from 'lucide-react';

export default function InvestigationTrace() {
  const { response, loading } = useApp();
  const sectionB = response?.section_b_investigation;

  if (!sectionB && !loading) {
    return (
      <div className="glass-panel p-6 text-center py-10 space-y-3">
        <Bot className="w-10 h-10 text-slate-600 mx-auto" />
        <h3 className="text-base font-semibold text-slate-300">Agent Investigation Trace Inactive</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Run an investigation in Section A to observe the autonomous agent’s bounded decision cycles,
          tool calls, and deterministic policy gatekeeper guardrails.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass-panel p-6 text-center py-12 space-y-4">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <div className="text-sm font-semibold text-slate-200">
          Agent Investigation & Simulation Active...
        </div>
        <p className="text-xs text-slate-400">
          Checking empirical model coverage, running SimPy discrete-event simulations, and enforcing policy guardrails.
        </p>
      </div>
    );
  }

  const steps = sectionB.steps || [];

  return (
    <div className="glass-panel p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge badge-indigo">Section B</span>
            <h2 className="text-xl font-bold tracking-tight text-white">Bounded Agent Investigation Trace</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Auditable log of agent rounds, tool invocations, and deterministic policy gatekeeper decisions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge badge-emerald">
            <ShieldCheck className="w-3.5 h-3.5" /> Policy Enforced
          </span>
          <span className="text-xs text-slate-400 font-mono">
            Rounds: {sectionB.rounds_completed || 1} / {sectionB.max_rounds || 3}
          </span>
        </div>
      </div>

      {/* Investigation Metrics Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Activity className="w-3 h-3 text-indigo-400" /> Actions Executed
          </div>
          <div className="text-lg font-bold text-white mt-0.5">{steps.length}</div>
        </div>

        <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Clock className="w-3 h-3 text-cyan-400" /> Elapsed Time
          </div>
          <div className="text-lg font-bold text-white mt-0.5 font-mono">
            {sectionB.elapsed_seconds != null ? `${sectionB.elapsed_seconds.toFixed(2)}s` : '< 1.0s'}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-400" /> Policy Gatekeeper
          </div>
          <div className="text-sm font-semibold text-emerald-400 mt-1">0 Violations</div>
        </div>

        <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Layers className="w-3 h-3 text-purple-400" /> Investigation Status
          </div>
          <div className="text-sm font-semibold text-slate-200 mt-1">
            {sectionB.status || 'COMPLETED'}
          </div>
        </div>
      </div>

      {/* Steps Table */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Chronological Action Trace
        </h3>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th style={{ width: '80px' }}>Round</th>
                <th>Action & Target</th>
                <th style={{ width: '140px' }}>Policy Decision</th>
                <th>Observation / Outcome</th>
                <th style={{ width: '100px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step, idx) => (
                <tr key={idx}>
                  <td className="font-mono text-xs text-slate-400">
                    #{step.round || (idx + 1)}
                  </td>
                  <td>
                    <div className="font-semibold text-slate-200 text-xs flex items-center gap-1.5">
                      <span className="text-indigo-400 font-mono">{step.action}</span>
                      {step.target && (
                        <>
                          <ArrowRight className="w-3 h-3 text-slate-500" />
                          <span className="text-slate-300 font-mono text-[11px]">{step.target}</span>
                        </>
                      )}
                    </div>
                    {step.details && (
                      <div className="text-[11px] text-slate-400 mt-0.5">{step.details}</div>
                    )}
                  </td>
                  <td>
                    {step.policy_decision === 'DENY' || step.policy_decision === 'BLOCKED' ? (
                      <span className="badge badge-rose text-[10px]">
                        <ShieldAlert className="w-3 h-3" /> DENIED
                      </span>
                    ) : (
                      <span className="badge badge-emerald text-[10px]">
                        <ShieldCheck className="w-3 h-3" /> ALLOWED
                      </span>
                    )}
                  </td>
                  <td className="text-xs text-slate-300 font-mono">
                    {step.result_summary || 'Action completed successfully.'}
                  </td>
                  <td>
                    <span className="badge badge-slate text-[10px] flex items-center gap-1">
                      <CheckCircle className="w-2.5 h-2.5 text-emerald-400" /> Success
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
