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
    <div className="saas-card overflow-hidden shadow-xs border border-slate-200">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="py-4 px-6 text-xs font-semibold uppercase tracking-wider text-slate-500 w-1/4">
                Architecture Candidate
              </th>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                return (
                  <th
                    key={cand.id}
                    className={`py-4 px-6 text-xs ${
                      isWinner
                        ? 'bg-emerald-50/70 border-x border-emerald-200'
                        : 'text-slate-800'
                    }`}
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {isWinner ? (
                          <span className="badge-saas badge-emerald text-[9px] font-semibold flex items-center gap-1 shadow-2xs">
                            <Award className="w-3 h-3 text-emerald-700" />
                            <span>Recommended Winner</span>
                          </span>
                        ) : (
                          <span className="badge-saas badge-zinc text-[9px]">
                            Alternative
                          </span>
                        )}
                      </div>
                      <div className="font-bold text-sm text-slate-900 tracking-tight">
                        {cand.name}
                      </div>
                      <div className="text-xs text-slate-500 font-normal">
                        {cand.topology || cand.topology_summary}
                      </div>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 text-xs">
            {/* Row 1: Response Time (p95) */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Response Latency (p95)</div>
                <div className="text-[10px] text-slate-400 mt-0.5">SLA Target: &lt; {slaMs} ms</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const isSlaMet = cand.p95 != null && cand.p95 <= slaMs;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm ${isSlaMet ? 'text-emerald-700 font-bold' : 'text-rose-700 font-bold'}`}>
                        {cand.p95 != null ? `${cand.p95} ms` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.latency_provenance || 'SIMULATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 2: Throughput Achieved */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Simulated Throughput</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Tested under offered load</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-900 font-bold text-sm">
                        {cand.throughput != null ? `${cand.throughput} RPS` : '—'}
                      </span>
                      <EvidenceBadge provenance={cand.throughput_provenance || 'SIMULATED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 3: Estimated Monthly Cost */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Estimated Monthly Cost</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Budget cap: {budgetUsd ? `< $${budgetUsd}/mo` : 'None'}</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const isOverBudget = cand.cost != null && budgetUsd != null && cand.cost > budgetUsd;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`text-sm ${isOverBudget ? 'text-rose-700 font-bold' : 'text-slate-900 font-bold'}`}>
                        {cand.cost != null ? `$${cand.cost}/mo` : 'Not modelled'}
                      </span>
                      <EvidenceBadge provenance={cand.cost != null ? (cand.cost_provenance || 'ASSUMED') : 'NOT_MODELLED'} />
                    </div>
                  </td>
                );
              })}
            </tr>

            {/* Row 4: Database CPU Utilization */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Database CPU Load</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Hardware resource headroom</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const cpuVal = cand.cpu;
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50 font-bold' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm font-bold ${
                          cpuVal != null
                            ? cpuVal < 60
                              ? 'text-emerald-700'
                              : cpuVal < 85
                              ? 'text-amber-700'
                              : 'text-rose-700'
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
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Constraint Outcome</div>
                <div className="text-[10px] text-slate-400 mt-0.5">SLA &amp; budget compliance</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const status = cand.slaMet && cand.feasible ? 'PASS' : !cand.feasible ? 'FAIL' : 'UNCERTAIN';
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50' : ''
                    }`}
                  >
                    <StatusBadge status={status} type="constraint" />
                  </td>
                );
              })}
            </tr>

            {/* Row 6: Evidence Coverage Status */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Evidence Coverage</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Empirical model support</div>
              </td>
              {candidates.map((cand) => {
                const isWinner = cand.id === winnerId;
                const evStatus = cand.evidence_status || 'OBSERVED';
                return (
                  <td
                    key={cand.id}
                    className={`py-3.5 px-6 ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50' : ''
                    }`}
                  >
                    <StatusBadge status={evStatus} type="evidence" />
                  </td>
                );
              })}
            </tr>

            {/* Row 7: Architecture Trade-Off */}
            <tr className="hover:bg-slate-50/50 transition-colors">
              <td className="py-3.5 px-6 font-medium text-slate-700">
                <div className="font-semibold text-slate-800">Primary Trade-Off</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Operational considerations</div>
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
                    className={`py-3.5 px-6 text-slate-600 text-xs leading-relaxed ${
                      isWinner ? 'bg-emerald-50/20 border-x border-emerald-200/50 text-slate-800 font-medium' : ''
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
