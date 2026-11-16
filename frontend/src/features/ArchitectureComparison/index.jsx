import React from 'react';
import { useApp } from '../../context/AppContext';
import {
  Layers,
  CheckCircle2,
  XCircle,
  Award,
  TrendingUp,
  Clock,
  DollarSign,
  AlertTriangle,
} from 'lucide-react';

export default function ArchitectureComparison() {
  const { response, loading } = useApp();
  const sectionC = response?.section_c_comparison;
  const sectionD = response?.section_d_recommendation;

  if (!sectionC && !loading) {
    return (
      <div className="glass-panel p-6 text-center py-10 space-y-3">
        <Layers className="w-10 h-10 text-slate-600 mx-auto" />
        <h3 className="text-base font-semibold text-slate-300">No Candidate Simulation Results</h3>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          Run an investigation in Section A to simulate candidate architectures under the specified workload with SimPy.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass-panel p-6 text-center py-12 space-y-3">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <div className="text-sm font-semibold text-slate-300">Simulating Candidate Architectures...</div>
      </div>
    );
  }

  const candidates = sectionC.candidates || [];
  const winnerId = sectionD?.winner?.id || sectionD?.winner_id;

  return (
    <div className="glass-panel p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="badge badge-indigo">Section C</span>
            <h2 className="text-xl font-bold tracking-tight text-white">Candidate Architecture Simulation Matrix</h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic SimPy discrete-event simulation results across all candidate architectures under identical synthetic workloads.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge badge-cyan font-mono">
            {candidates.length} Architectures Evaluated
          </span>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Architecture Candidate</th>
              <th>Feasibility Filter</th>
              <th>p95 Latency</th>
              <th>p50 Latency</th>
              <th>Throughput</th>
              <th>CPU Load</th>
              <th>Monthly Cost</th>
              <th>Overall Rank</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((cand) => {
              const isWinner = cand.id === winnerId;
              const p95 = cand.metrics?.p95_latency_ms ?? cand.p95_latency_ms;
              const p50 = cand.metrics?.p50_latency_ms ?? cand.p50_latency_ms;
              const qps = cand.metrics?.throughput_qps ?? cand.throughput_qps;
              const cpu = cand.metrics?.cpu_utilization ?? cand.cpu_utilization;
              const cost = cand.cost_monthly ?? cand.estimated_cost_monthly;
              const slaMet = cand.sla_met ?? cand.hard_constraint_met;
              const isFeasible = cand.feasible ?? (cand.status === 'FEASIBLE');

              return (
                <tr
                  key={cand.id}
                  className={isWinner ? 'bg-indigo-950/20 font-medium' : ''}
                >
                  <td>
                    <div className="flex items-center gap-2">
                      {isWinner && (
                        <Award className="w-4 h-4 text-emerald-400 shrink-0" />
                      )}
                      <div>
                        <div className="font-semibold text-slate-200 text-xs flex items-center gap-2">
                          <span>{cand.name || cand.id}</span>
                          {isWinner && <span className="badge badge-emerald text-[9px]">Winner</span>}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                          {cand.description || cand.components?.join(' + ') || cand.id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {isFeasible ? (
                      <span className="badge badge-emerald text-[10px]">
                        <CheckCircle2 className="w-3 h-3" /> Feasible
                      </span>
                    ) : (
                      <span className="badge badge-rose text-[10px]" title={cand.disqualification_reason || ''}>
                        <XCircle className="w-3 h-3" /> Disqualified
                      </span>
                    )}
                  </td>
                  <td>
                    <div className="flex items-center gap-1.5 font-mono text-xs">
                      <span className={slaMet ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                        {p95 != null ? `${p95.toFixed(1)} ms` : '—'}
                      </span>
                      {slaMet ? (
                        <span className="text-[10px] text-emerald-500">✓ SLA</span>
                      ) : (
                        <span className="text-[10px] text-rose-500">✗ Exceeds</span>
                      )}
                    </div>
                  </td>
                  <td className="font-mono text-xs text-slate-300">
                    {p50 != null ? `${p50.toFixed(1)} ms` : '—'}
                  </td>
                  <td className="font-mono text-xs text-slate-300">
                    {qps != null ? `${Math.round(qps)} QPS` : '—'}
                  </td>
                  <td className="font-mono text-xs text-slate-300">
                    {cpu != null ? (
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              cpu > 0.8 ? 'bg-rose-500' : cpu > 0.6 ? 'bg-amber-500' : 'bg-indigo-500'
                            }`}
                            style={{ width: `${Math.min(100, Math.round(cpu * 100))}%` }}
                          />
                        </div>
                        <span>{Math.round(cpu * 100)}%</span>
                      </div>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="font-mono text-xs text-slate-200">
                    {cost != null ? `$${Math.round(cost)}/mo` : '—'}
                  </td>
                  <td>
                    <span
                      className={`badge text-[10px] ${
                        isWinner
                          ? 'badge-emerald'
                          : isFeasible
                          ? 'badge-slate'
                          : 'badge-rose'
                      }`}
                    >
                      {isWinner ? '#1 Ranked' : isFeasible ? 'Alternative' : 'Infeasible'}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Disqualification / Infeasibility Callout if any */}
      {candidates.some((c) => !c.feasible && c.disqualification_reason) && (
        <div className="p-3.5 rounded-lg bg-amber-950/30 border border-amber-900/50 space-y-1.5">
          <div className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Hard Constraint Filtering Audit
          </div>
          <ul className="text-xs text-slate-400 space-y-1 list-disc pl-4">
            {candidates
              .filter((c) => !c.feasible && c.disqualification_reason)
              .map((c) => (
                <li key={c.id}>
                  <strong className="text-slate-300">{c.name || c.id}:</strong> {c.disqualification_reason}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
