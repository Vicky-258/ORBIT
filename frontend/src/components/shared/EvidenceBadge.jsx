import React from 'react';

/**
 * Honest Evidence Provenance Badge
 * Distinguishes: Measured, Simulation-derived, Model-derived, Estimated, Assumed, Not modelled
 * Polished for modern developer SaaS (sentence case, soft pill, glowing dot)
 */
export default function EvidenceBadge({ provenance, className = '' }) {
  if (!provenance) return null;

  const normalized = String(provenance).toUpperCase();

  let label = 'Simulated';
  let badgeStyle = 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20';
  let dotColor = 'bg-indigo-400';

  if (normalized.includes('MEASURED') || normalized === 'EMPIRICAL_MEASURED') {
    label = 'Measured';
    badgeStyle = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20';
    dotColor = 'bg-emerald-400';
  } else if (normalized.includes('SIMPY') || normalized.includes('SIMULAT')) {
    label = 'Simulation-derived';
    badgeStyle = 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20';
    dotColor = 'bg-indigo-400';
  } else if (normalized.includes('MODEL') || normalized === 'ESTIMATED') {
    label = 'Model-derived';
    badgeStyle = 'bg-sky-500/10 text-sky-300 border-sky-500/20';
    dotColor = 'bg-sky-400';
  } else if (normalized.includes('ASSUM')) {
    label = 'Assumption-based';
    badgeStyle = 'bg-amber-500/10 text-amber-300 border-amber-500/20';
    dotColor = 'bg-amber-400';
  } else if (normalized.includes('NOT_MODELLED') || normalized.includes('UNAVAILABLE')) {
    label = 'Not modelled';
    badgeStyle = 'bg-slate-500/10 text-slate-300 border-slate-500/20';
    dotColor = 'bg-slate-400';
  } else {
    label = provenance;
    badgeStyle = 'bg-white/[0.05] text-slate-300 border-white/[0.08]';
    dotColor = 'bg-slate-400';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 py-0.5 px-2 rounded-full border text-[10px] font-medium tracking-normal backdrop-blur-xs ${badgeStyle} ${className}`}
      title={`Epistemic Origin: ${label}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </span>
  );
}
