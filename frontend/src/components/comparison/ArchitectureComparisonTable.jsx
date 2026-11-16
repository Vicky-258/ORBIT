import React from 'react';
import StatusBadge from '../shared/StatusBadge';
import EvidenceBadge from '../shared/EvidenceBadge';
import { Award, Server, Zap, Layers, Cpu, Database, Check } from 'lucide-react';

export default function ArchitectureComparisonTable({
  candidates = [],
  winnerId,
  slaMs = 100,
  budgetUsd = 250,
}) {
  return (
    <div className="saas-card overflow-hidden shadow-xl border border-white/[0.08]">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/[0.08] bg-[#090d16]/80 backdrop-blur-md">
              <th className="py-4 px-6 text-xs font-bold uppercase tracking-wider text-slate-400 w-1/4">
                Architecture Candidate
              </th>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                return (
                  <th
                    key={cand.id}
                    className={`py-4 px-6 text-xs ${
                      isWinner
                        ? 'bg-gradient-to-b from-indigo-500/15 via-indigo-950/20 to-transparent border-x border-indigo-500/30'
                        : 'text-slate-200'
                    }`}
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {isWinner ? (
                          <span className="badge-saas bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[9px] font-semibold flex items-center gap-1">
                            <Award className="w-3 h-3 text-emerald-400" />
                            <span>Recommended Winner</span>
                          </span>
                        ) : (
                          <span className="badge-saas bg-white/[0.04] text-slate-400 border border-white/[0.08] text-[9px]">
                            Alternative
                          </span>
                        )}
                      </div>
                      <div className="font-bold text-sm text-white tracking-tight">
                        {cand.name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono font-normal">
                        {cand.topology || cand.topology_summary}
                      </div>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-white/[0.04] text-xs">
            {/* Row 1: Response Time (p95) */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Response Latency (p95)</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">SLA Target: &lt; {slaMs} ms</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const isSlaMet = cand.p95 != null && cand.p95 <= slaMs;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 font-mono ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm ${isSlaMet ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}`}>
                        {cand.p95 != null ? `${cand.p95} ms` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.latency_provenance || 'SIMULATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 2: Throughput Achieved */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Simulated Throughput</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Tested under offered load</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 font-mono ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-100 font-bold text-sm">
                        {cand.throughput != null ? `${cand.throughput} RPS` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.throughput_provenance || 'SIMULATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 3: Estimated Monthly Cost */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Estimated Monthly Cost</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Budget cap: {budgetUsd ? `< $${budgetUsd}/mo` : 'None'}</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const isOverBudget = cand.cost != null && budgetUsd != null && cand.cost > budgetUsd;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 font-mono ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm ${isOverBudget ? 'text-rose-400 font-bold' : 'text-slate-100 font-bold'}`}>
                        {cand.cost != null ? `$${cand.cost}/mo` : 'Not modelled'}
                      </span>
                      <EvidenceBadge provenance={cand.cost != null ? (cand.cost_provenance || 'ASSUMED') : 'NOT_MODELLED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 4: Database CPU Utilization */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Database CPU Load</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Hardware resource headroom</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const cpuVal = cand.cpu;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 font-mono ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm font-bold ${
                          cpuVal != null
                            ? cpuVal < 60
                              ? 'text-emerald-400'
                              : cpuVal < 85
                              ? 'text-amber-400'
                              : 'text-rose-400'
                            : 'text-slate-400'
                        }`}
                      >
                        {cpuVal != null ? `${cpuVal}%` : 'Not modelled'}
                      </span>
                      <EvidenceBadge provenance={cand.cpu_provenance || 'ESTIMATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 5: Hard Constraint Status */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Constraint Outcome</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">SLA &amp; budget compliance</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const status = cand.slaMet && cand.feasible ? 'PASS' : !cand.feasible ? 'FAIL' : 'UNCERTAIN';
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20' : ''
                    }`}
                  >
                    <StatusBadge status={status} type="constraint" />
                  </td>
                );
              })}
            </tr>

            {/* Row 6: Evidence Coverage Status */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Evidence Coverage</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Empirical model support</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const evStatus = cand.evidence_status || 'OBSERVED';
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20' : ''
                    }`}
                  >
                    <StatusBadge status={evStatus} type="evidence" />
                  </td>
                );
              })}
            </tr>

            {/* Row 7: Architecture Trade-Off */}
            <tr className="hover:bg-white/[0.02] transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-300">
                <div className="font-semibold text-slate-200">Primary Trade-Off</div>
                <div className="text-[10px] text-slate-500 font-mono mt-0.5">Operational considerations</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                let tradeOffSummary = '';
                if (cand.id.includes('simple')) {
                  tradeOffSummary = 'Zero caching dependencies; simpler operations but higher direct DB CPU under heavy read load.';
                } else if (cand.id.includes('cached')) {
                  tradeOffSummary = 'High read hit rate shields database; introduces Redis cache invalidation overhead.';
                } else {
                  tradeOffSummary = 'Immediate enqueue response; introduces message queue infrastructure and eventual consistency.';
                }

                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 text-slate-400 text-xs leading-relaxed ${
                      isWinner ? 'bg-indigo-500/[0.03] border-x border-indigo-500/20 text-slate-300 font-medium' : ''
                    }`}
                  >
                    {tradeOffSummary}
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
