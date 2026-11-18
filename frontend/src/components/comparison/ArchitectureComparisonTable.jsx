import React from 'react';
import StatusBadge from '../shared/StatusBadge';
import EvidenceBadge from '../shared/EvidenceBadge';
import { Award, Zap, Layers, Cpu, Database, Check } from 'lucide-react';

export default function ArchitectureComparisonTable({
  candidates = [],
  winnerId,
  slaMs = 100,
  budgetUsd = 250,
}) {
  return (
    <div className="bg-[#121215] rounded-2xl border border-white/[0.08] overflow-hidden shadow-xl">
      <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-zinc-700">
        <table className="w-full text-left border-collapse min-w-[680px]">
          <thead>
            <tr className="border-b border-white/[0.08] bg-[#09090b]">
              <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-zinc-400 w-1/4">
                Architecture Candidate
              </th>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                return (
                  <th
                    key={cand.id}
                    className={`py-4 px-6 text-xs ${
                      isWinner
                        ? 'bg-emerald-950/20 border-x border-emerald-500/20'
                        : 'text-white'
                    }`}
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {isWinner ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-semibold">
                            <Award className="w-3 h-3 text-emerald-400" />
                            <span>Recommended Winner</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.08] text-[10px] font-mono">
                            Alternative
                          </span>
                        )}
                      </div>
                      <div className="font-bold text-sm text-white tracking-tight">
                        {cand.name}
                      </div>
                      <div className="text-xs text-zinc-400 font-mono">
                        {cand.topology || cand.topology_summary}
                      </div>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-white/[0.05] text-xs">
            {/* Row 1: Response Time (p95) */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Response Latency (p95)</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">SLA Target: &lt; {slaMs} ms</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const p95 = cand.p95 ?? cand.p95_latency_ms;
                const isSlaMet = p95 != null && p95 <= slaMs;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-mono ${isSlaMet ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}`}>
                        {p95 != null ? `${p95} ms` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.latency_provenance || 'SIMULATED_SIMPY'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 2: Throughput Achieved */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Simulated Throughput</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">Tested under offered load</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const throughput = cand.throughput ?? cand.throughput_achieved_rps;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-semibold text-white">
                        {throughput != null ? `${Math.round(throughput)} req/s` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.throughput_provenance || 'SIMULATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 3: Estimated Monthly Cost */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Estimated Monthly Cost</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">Budget cap: {budgetUsd ? `$${budgetUsd}/mo` : 'None'}</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const cost = cand.cost ?? cand.estimated_monthly_cost_usd;
                const isOverBudget = cost != null && budgetUsd && cost > budgetUsd;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-mono font-semibold ${isOverBudget ? 'text-rose-400' : 'text-zinc-200'}`}>
                        {cost != null ? `$${cost}/mo` : 'Not modelled'}
                      </span>
                      <EvidenceBadge provenance={cand.cost_provenance || (cost != null ? 'ASSUMED' : 'NOT_MODELLED')} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 4: Database CPU Load */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Database CPU Load</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">Hardware resource headroom</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const cpu = cand.cpu ?? cand.cpu_utilization_pct;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-zinc-300">
                        {cpu != null ? `${cpu}%` : 'Not modelled'}
                      </span>
                      <EvidenceBadge provenance={cand.cpu_provenance || (cpu != null ? 'ESTIMATED' : 'NOT_MODELLED')} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 5: Constraint Outcome */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Constraint Outcome</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">SLA &amp; budget compliance</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const p95 = cand.p95 ?? cand.p95_latency_ms;
                const isSlaMet = p95 != null && p95 <= slaMs;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20' : ''
                    }`}
                  >
                    <StatusBadge
                      status={isSlaMet ? 'FEASIBLE' : 'INFEASIBLE'}
                      type="constraint"
                    />
                  </td>
                );
              })}
            </tr>

            {/* Row 6: Primary Trade-Off */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-zinc-300">
                <div className="font-semibold text-white">Primary Trade-Off</div>
                <div className="text-[10px] text-zinc-400 font-mono mt-0.5">Operational considerations</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const isSimple = cand.id?.includes('simple');
                const isCached = cand.id?.includes('cached');
                const isAsync = cand.id?.includes('async');
                const tradeOffText = isCached
                  ? 'Cache synchronization & memory management'
                  : isAsync
                  ? 'Higher asynchronous latency for immediate read queries'
                  : 'Database thread exhaustion under concurrency spikes';

                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 text-zinc-400 leading-relaxed ${
                      isWinner ? 'bg-emerald-950/10 border-x border-emerald-500/20 text-zinc-300' : ''
                    }`}
                  >
                    {tradeOffText}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
