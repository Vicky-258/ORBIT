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
  let badgeStyle = 'bg-blue-50 text-blue-800 border-blue-200';
  let dotColor = 'bg-blue-600';

  if (normalized.includes('MEASURED') || normalized === 'EMPIRICAL_MEASURED') {
    label = 'Measured';
    badgeStyle = 'bg-emerald-50 text-emerald-800 border-emerald-200';
    dotColor = 'bg-emerald-600';
  } else if (normalized.includes('SIMPY') || normalized.includes('SIMULAT')) {
    label = 'Simulation-derived';
    badgeStyle = 'bg-blue-50 text-blue-800 border-blue-200';
    dotColor = 'bg-blue-600';
  } else if (normalized.includes('MODEL') || normalized === 'ESTIMATED') {
    label = 'Model-derived';
    badgeStyle = 'bg-slate-100 text-slate-700 border-slate-200';
    dotColor = 'bg-slate-500';
  } else if (normalized.includes('ASSUM')) {
    label = 'Assumption-based';
    badgeStyle = 'bg-amber-50 text-amber-800 border-amber-200';
    dotColor = 'bg-amber-600';
  } else if (normalized.includes('NOT_MODELLED') || normalized.includes('UNAVAILABLE')) {
    label = 'Not modelled';
    badgeStyle = 'bg-slate-100 text-slate-500 border-slate-200';
    dotColor = 'bg-slate-400';
  } else {
    label = provenance;
    badgeStyle = 'bg-slate-100 text-slate-700 border-slate-200';
    dotColor = 'bg-slate-400';
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 py-0.5 px-2 rounded-full border text-[10px] font-medium tracking-normal shadow-2xs ${badgeStyle} ${className}`}
      title={`Epistemic Origin: ${label}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </span>
  );
}
