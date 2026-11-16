import React from 'react';
import { CheckCircle2, XCircle, AlertTriangle, HelpCircle } from 'lucide-react';

export default function StatusBadge({ status, type = 'constraint', className = '' }) {
  if (!status) return null;

  const normalized = String(status).toUpperCase();

  if (type === 'constraint') {
    if (normalized === 'PASS' || normalized === 'SATISFIED' || normalized === 'FEASIBLE') {
      return (
        <span className={`badge badge-emerald text-[10px] font-semibold py-0.5 px-2 flex items-center gap-1 shadow-2xs ${className}`}>
          <CheckCircle2 className="w-3 h-3 text-emerald-700" />
          <span>PASS</span>
        </span>
      );
    }
    if (normalized === 'FAIL' || normalized === 'VIOLATED' || normalized === 'INFEASIBLE') {
      return (
        <span className={`badge badge-rose text-[10px] font-semibold py-0.5 px-2 flex items-center gap-1 shadow-2xs ${className}`}>
          <XCircle className="w-3 h-3 text-rose-700" />
          <span>FAIL</span>
        </span>
      );
    }
    if (normalized === 'UNCERTAIN' || normalized === 'BORDERLINE') {
      return (
        <span className={`badge badge-amber text-[10px] font-semibold py-0.5 px-2 flex items-center gap-1 shadow-2xs ${className}`}>
          <AlertTriangle className="w-3 h-3 text-amber-700" />
          <span>UNCERTAIN</span>
        </span>
      );
    }
    return (
      <span className={`badge badge-zinc text-[10px] font-medium py-0.5 px-2 flex items-center gap-1 shadow-2xs ${className}`}>
        <HelpCircle className="w-3 h-3 text-slate-500" />
        <span>NOT EVALUATED</span>
      </span>
    );
  }

  // Evidence coverage type
  if (normalized === 'OBSERVED') {
    return (
      <span className={`badge badge-emerald text-[10px] font-mono py-0.5 px-2 ${className}`}>
        OBSERVED
      </span>
    );
  }
  if (normalized === 'INTERPOLATED') {
    return (
      <span className={`badge badge-cyan text-[10px] font-mono py-0.5 px-2 ${className}`}>
        INTERPOLATED
      </span>
    );
  }
  if (normalized === 'OUT_OF_RANGE') {
    return (
      <span className={`badge badge-amber text-[10px] font-mono py-0.5 px-2 ${className}`}>
        OUT OF RANGE
      </span>
    );
  }
  return (
    <span className={`badge badge-rose text-[10px] font-mono py-0.5 px-2 ${className}`}>
      INSUFFICIENT EVIDENCE
    </span>
  );
}
