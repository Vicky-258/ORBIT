import React from 'react';
import {
  Cpu,
  Layers,
  Sparkles,
  CheckCircle2,
  Loader2,
  Activity,
  Server,
  Zap,
  BarChart3
} from 'lucide-react';

export const EXECUTION_STEPS = [
  { id: 'domain', label: 'Understanding application requirements & entities', icon: Sparkles },
  { id: 'workloads', label: 'Decomposing independent operational workloads', icon: Layers },
  { id: 'archetypes', label: 'Classifying workloads into system archetypes', icon: Cpu },
  { id: 'composition', label: 'Composing infrastructure topology & routing', icon: Server },
  { id: 'validation', label: 'Validating architecture acyclicity & interface rules', icon: CheckCircle2 },
  { id: 'simulation', label: 'Running SimPy discrete-event queueing simulation', icon: Activity },
  { id: 'recommendation', label: 'Synthesizing performance trade-offs & report', icon: BarChart3 },
];

export default function AgentStatusIndicator({ currentStepIndex = 0, isComplete = false }) {
  return (
    <div className="my-3 p-4 rounded-xl border border-white/[0.1] bg-[#121215] shadow-sm max-w-xl">
      <div className="flex items-center gap-2 mb-3">
        {!isComplete ? (
          <Loader2 className="w-4 h-4 text-zinc-300 animate-spin" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        )}
        <span className="text-xs font-semibold text-zinc-200">
          {!isComplete ? 'ORBIT Architecture Intelligence in progress...' : 'Analysis & Simulation Complete'}
        </span>
      </div>

      <div className="space-y-2">
        {EXECUTION_STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isPast = idx < currentStepIndex || isComplete;
          const isCurrent = idx === currentStepIndex && !isComplete;
          const isPending = idx > currentStepIndex && !isComplete;

          return (
            <div
              key={step.id}
              className={`flex items-center gap-2.5 text-xs transition-opacity duration-200 ${
                isPast
                  ? 'text-zinc-400'
                  : isCurrent
                  ? 'text-zinc-100 font-medium'
                  : 'text-zinc-600 opacity-60'
              }`}
            >
              <div className="w-4 flex justify-center shrink-0">
                {isPast ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                ) : isCurrent ? (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-zinc-300 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
                  </span>
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
                )}
              </div>
              <span className="truncate">{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
