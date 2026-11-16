import React from 'react';

/**
 * Honest Evidence Provenance Badge
 * Distinguishes: Measured, Simulation-derived, Model-derived, Estimated, Assumed, Not modelled
 */
export default function EvidenceBadge({ provenance, className = '' }) {
  if (!provenance) return null;

  const normalized = String(provenance).toUpperCase();

  let label = 'Simulated';
  let badgeClass = 'badge-indigo';

  if (normalized.includes('MEASURED') || normalized === 'EMPIRICAL_MEASURED') {
    label = 'Measured';
    badgeClass = 'badge-emerald';
  } else if (normalized.includes('SIMPY') || normalized.includes('SIMULAT')) {
    label = 'Simulation-derived';
    badgeClass = 'badge-indigo';
  } else if (normalized.includes('MODEL') || normalized === 'ESTIMATED') {
    label = 'Model-derived';
    badgeClass = 'badge-zinc';
  } else if (normalized.includes('ASSUM')) {
    label = 'Assumption-based';
    badgeClass = 'badge-zinc';
  } else if (normalized.includes('NOT_MODELLED') || normalized.includes('UNAVAILABLE')) {
    label = 'Not modelled';
    badgeClass = 'badge-amber';
  } else {
    label = provenance;
    badgeClass = 'badge-zinc';
  }

  return (
    <span
      className={`badge ${badgeClass} text-[9px] font-mono py-0.5 px-2 tracking-wide uppercase ${className}`}
      title={`Epistemic Origin: ${label}`}
    >
      {label}
    </span>
  );
}
