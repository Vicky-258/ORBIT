import React from 'react';
import EvidenceBadge from '../shared/EvidenceBadge';
import { Award, Zap, Layers, Server, Database, CheckCircle2, XCircle, ArrowRight } from 'lucide-react';

export default function CandidateCard({
  candidate,
  isWinner,
  slaMs = 100,
  budgetUsd = 250,
  onSelectCandidate,
  isSelected
}) {
  const p95 = candidate.p95 ?? candidate.p95_latency_ms;
  const throughput = candidate.throughput ?? candidate.throughput_achieved_rps;
  const cost = candidate.cost ?? candidate.estimated_monthly_cost_usd;
  const cpu = candidate.cpu ?? candidate.cpu_utilization_pct;

  const isSlaMet = p95 != null ? p95 <= slaMs : true;
  const isBudgetMet = cost != null && budgetUsd ? cost <= budgetUsd : true;

  // Derive primary advantage & trade-off
  const isSimple = candidate.id?.includes('simple');
  const isCached = candidate.id?.includes('cached');
  const isAsync = candidate.id?.includes('async');

  const advantage = isCached
    ? 'Sub-millisecond read latency via in-memory caching'
    : isAsync
    ? 'Absorbs peak write bursts with zero request drops'
    : 'Minimal operational overhead with single database';

  const tradeoff = isCached
    ? 'Requires cache invalidation synchronization'
    : isAsync
    ? 'Higher latency for synchronous read requests'
    : 'Database connection exhaustion under high concurrency';

  return (
    <div
      onClick={onSelectCandidate}
      className={`rounded-2xl border p-5 sm:p-6 transition-all duration-200 cursor-pointer relative shadow-lg flex flex-col justify-between ${
        isWinner
          ? 'bg-[#151a18] border-emerald-500/40 hover:border-emerald-500/60 ring-1 ring-emerald-500/20'
          : isSelected
          ? 'bg-[#181820] border-zinc-400 ring-1 ring-zinc-500/30'
          : 'bg-[#121215] border-white/[0.08] hover:border-zinc-600 hover:bg-[#151519]'
      }`}
    >
      <div>
        {/* Top Header Badge Row */}
        <div className="flex items-center justify-between gap-2 mb-3">
          {isWinner ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
              <Award className="w-3.5 h-3.5 text-emerald-400" />
              <span>Recommended Winner</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white/[0.04] text-zinc-400 border border-white/[0.08] text-[11px] font-medium font-mono">
              Alternative Candidate
            </span>
          )}

          <div className="flex items-center gap-1 text-[11px] font-mono">
            {isSlaMet ? (
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> SLA Met
              </span>
            ) : (
              <span className="text-rose-400 flex items-center gap-1">
                <XCircle className="w-3 h-3" /> SLA Violated
              </span>
            )}
          </div>
        </div>

        {/* Candidate Title & Topology Summary */}
        <h3 className="text-base font-bold text-white tracking-tight leading-snug mb-1">
          {candidate.name}
        </h3>
        <p className="text-xs text-zinc-400 font-mono mb-4 leading-relaxed line-clamp-1">
          {candidate.topology || candidate.topology_summary}
        </p>

        {/* Metric Triad Box */}
        <div className="grid grid-cols-3 gap-2 p-3 rounded-xl bg-[#09090b] border border-white/[0.06] mb-4 text-center">
          <div>
            <div className="text-[10px] text-zinc-400 font-medium">p95 Latency</div>
            <div className={`text-sm font-bold font-mono mt-0.5 ${isSlaMet ? 'text-emerald-400' : 'text-rose-400'}`}>
              {p95 != null ? `${p95}ms` : '—'}
            </div>
            <div className="text-[9px] text-zinc-400 font-mono">&lt;{slaMs}ms</div>
          </div>

          <div>
            <div className="text-[10px] text-zinc-400 font-medium">Throughput</div>
            <div className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
              {throughput != null ? Math.round(throughput) : '—'}
            </div>
            <div className="text-[9px] text-zinc-400 font-mono">RPS verified</div>
          </div>

          <div>
            <div className="text-[10px] text-zinc-400 font-medium">Est. Cost</div>
            <div className="text-sm font-bold font-mono text-zinc-100 mt-0.5">
              {cost != null ? `$${cost}` : '—'}
            </div>
            <div className="text-[9px] text-zinc-400 font-mono">/month</div>
          </div>
        </div>

        {/* Key Trade-offs Section */}
        <div className="space-y-2 text-xs">
          <div className="flex items-start gap-2">
            <span className="text-emerald-400 font-bold shrink-0">+</span>
            <span className="text-zinc-300 leading-snug">{advantage}</span>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-amber-400 font-bold shrink-0">−</span>
            <span className="text-zinc-400 leading-snug">{tradeoff}</span>
          </div>
        </div>
      </div>

      {/* Footer Details Prompt */}
      <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
        <span className="font-mono text-[11px] text-zinc-400">ID: {candidate.id}</span>
        <div className="flex items-center gap-1 text-zinc-300 font-medium group-hover:text-white transition-colors">
          <span>Inspect Deep-Dive</span>
          <ArrowRight className="w-3 h-3 text-zinc-400 group-hover:translate-x-0.5 transition-transform" />
        </div>
      </div>
    </div>
  );
}
