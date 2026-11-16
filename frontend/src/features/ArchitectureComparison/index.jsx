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
  Play,
  ArrowRight,
  Server,
} from 'lucide-react';

const CANDIDATE_PORTFOLIO = [
  {
    id: 'arch_a_simple',
    name: 'Architecture A — Simple Direct',
    path: 'API → PostgreSQL 16',
    cost: '~$133/mo [Assumed]',
    type: 'Relational Baseline',
    desc: 'Lowest cost and zero cache complexity. Best suited for balanced/write-heavy low-to-medium QPS.',
    color: 'border-slate-800 hover:border-slate-700',
  },
  {
    id: 'arch_b_cached',
    name: 'Architecture B — Cached Reads',
    path: 'API → Redis Cache → PostgreSQL 16',
    cost: '~$176/mo [Assumed]',
    type: 'In-Memory Cache Shield',
    desc: 'Shields primary database with high read-hit ratios. Best suited for catalog & read-heavy traffic.',
    color: 'border-indigo-500/30 hover:border-indigo-500/60',
  },
  {
    id: 'arch_c_async',
    name: 'Architecture C — Async Pipeline',
    path: 'API → Kafka Queue → Worker → PostgreSQL 16',
    cost: '~$216/mo [Assumed]',
    type: 'Decoupled Event Stream',
    desc: 'Immediate HTTP 202 ack; absorbs high-burst write spikes with background persistence workers.',
    color: 'border-cyan-500/30 hover:border-cyan-500/60',
  },
];

export default function ArchitectureComparison() {
  const { response, loading, handleRunWorkflow } = useApp();
  const sectionC = response?.section_c_comparison;
  const sectionD = response?.section_d_recommendation;

  if (loading) {
    return (
      <div className="glass-panel p-8 text-center py-16 space-y-4">
        <div className="w-10 h-10 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        <div className="text-base font-semibold text-slate-200">
          Simulating Candidate Architectures under Workload...
        </div>
        <p className="text-xs text-slate-400 max-w-md mx-auto">
          SimPy is simulating connection pool contention, physical CPU core queueing, and cache hit distributions.
        </p>
      </div>
    );
  }

  // Pre-run candidate portfolio preview
  if (!sectionC) {
    return (
      <div className="glass-panel p-6 sm:p-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="badge badge-indigo text-xs">Section C</span>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                Candidate Architecture Simulation Matrix
              </h2>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              SimPy discrete-event simulation evaluates candidate topologies under identical synthetic offered loads.
            </p>
          </div>
          <button
            type="button"
            onClick={() => handleRunWorkflow()}
            className="btn btn-primary text-xs px-4 py-2"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            <span>Run Simulation Now</span>
          </button>
        </div>

        <div className="space-y-3">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300">
            Available Candidate Architecture Portfolio
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {CANDIDATE_PORTFOLIO.map((cand) => (
              <div
                key={cand.id}
                className={`p-4 rounded-xl border bg-slate-900/60 transition-all ${cand.color} flex flex-col justify-between`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="badge badge-slate text-[10px]">{cand.type}</span>
                    <span className="font-mono text-xs text-emerald-400 font-semibold">{cand.cost}</span>
                  </div>
                  <h3 className="font-bold text-sm text-slate-100 mb-1">{cand.name}</h3>
                  <div className="text-[11px] font-mono text-indigo-300 mb-2">{cand.path}</div>
                  <p className="text-xs text-slate-400 leading-relaxed">{cand.desc}</p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                  <span>SimPy Evaluated:</span>
                  <span className="text-slate-300">p50, p95, p99, QPS, CPU</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
            <span>Deterministic SimPy Request-Level Engine ready for execution.</span>
          </div>
          <span className="font-mono text-slate-500">Zero synthetic data substituted for empirical measurements</span>
        </div>
      </div>
    );
  }

  const candidates = sectionC.candidates || [];
  const winnerId = sectionD?.winner?.id || sectionD?.winner_id;

  return (
    <div className="glass-panel p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="badge badge-indigo text-xs">Section C</span>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Candidate Architecture Simulation Matrix
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Deterministic SimPy discrete-event simulation results across all candidate topologies under identical workloads.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge badge-cyan font-mono text-xs">
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
                  className={isWinner ? 'bg-indigo-950/30 font-medium' : ''}
                >
                  <td>
                    <div className="flex items-center gap-2.5">
                      {isWinner && (
                        <Award className="w-4 h-4 text-emerald-400 shrink-0" />
                      )}
                      <div>
                        <div className="font-semibold text-slate-100 text-xs flex items-center gap-2">
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
        <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-900/50 space-y-2">
          <div className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> Hard Constraint Filtering Audit
          </div>
          <ul className="text-xs text-slate-400 space-y-1.5 list-disc pl-4">
            {candidates
              .filter((c) => !c.feasible && c.disqualification_reason)
              .map((c) => (
                <li key={c.id}>
                  <strong className="text-slate-200">{c.name || c.id}:</strong> {c.disqualification_reason}
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
