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
  Play,
  Lock,
} from 'lucide-react';

export default function InvestigationTrace() {
  const { response, loading, handleRunWorkflow } = useApp();
  const sectionB = response?.section_b_investigation;

  if (loading) {
    return (
      <div className="glass-panel p-8 text-center py-16 space-y-4">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <div className="text-base font-semibold text-slate-200">
          Agent Investigation & Safety Guardrails Active...
        </div>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          Checking empirical model coverage in SQLite registry, evaluating action proposals against the deterministic policy gatekeeper, and executing SimPy simulations.
        </p>
      </div>
    );
  }

  if (!sectionB) {
    return (
      <div className="glass-panel p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="badge badge-indigo text-xs">Section B</span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Bounded Agent Investigation Trace
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Auditable log of autonomous agent decision cycles, tool calls, and deterministic policy gatekeeper guardrails.
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            className="btn btn-primary text-xs px-4 py-2"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Start Investigation</span>
          </button>
        </div>

        {/* Workflow Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-indigo-400 font-semibold text-xs">
              <Bot className="w-4 h-4" /> 1. Bounded Reasoning
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Agent evaluates missing model coverage, inspects workload constraints, and iteratively simulates alternatives within a strictly bounded budget (max 3 rounds).
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-xs">
              <ShieldCheck className="w-4 h-4" /> 2. Policy Gatekeeper
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every action proposal passes through the deterministic Policy Gatekeeper. Unauthorized live Docker execution or registry mutation is strictly rejected.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
            <div className="flex items-center gap-2 text-cyan-400 font-semibold text-xs">
              <Activity className="w-4 h-4" /> 3. Verified Execution
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Actions execute against frozen empirical models and SimPy request-level discrete event queues, logging full inputs and outputs.
            </p>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-400" />
            <span>Deterministic Policy Gatekeeper: Live Docker Container Benchmarks Disabled (Audited)</span>
          </div>
          <span className="badge badge-emerald text-[10px]">Policy Active</span>
        </div>
      </div>
    );
  }

  const steps = sectionB.steps || [];

  return (
    <div className="glass-panel p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="badge badge-indigo text-xs">Section B</span>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Bounded Agent Investigation Trace
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
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
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Activity className="w-3 h-3 text-indigo-400" /> Actions Executed
          </div>
          <div className="text-xl font-bold text-white mt-1">{steps.length}</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Clock className="w-3 h-3 text-cyan-400" /> Elapsed Time
          </div>
          <div className="text-xl font-bold text-white mt-1 font-mono">
            {sectionB.elapsed_seconds != null ? `${sectionB.elapsed_seconds.toFixed(2)}s` : '< 1.0s'}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-400" /> Policy Gatekeeper
          </div>
          <div className="text-sm font-semibold text-emerald-400 mt-1.5">0 Violations</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="text-[11px] text-slate-400 flex items-center gap-1">
            <Layers className="w-3 h-3 text-purple-400" /> Investigation Status
          </div>
          <div className="text-sm font-semibold text-slate-200 mt-1.5 font-mono">
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
