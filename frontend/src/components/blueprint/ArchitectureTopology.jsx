import React from 'react';
import { Server, Zap, Database, Layers, Cpu, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function ArchitectureTopology({ nodes = [], topologyStr = '' }) {
  const displayNodes = nodes.length > 0 ? nodes : deriveNodes(topologyStr);

  return (
    <div className="p-5 sm:p-6 rounded-2xl bg-[#090d18]/80 border border-white/[0.08] bg-dot-grid relative overflow-hidden shadow-inner">
      {/* Ambient Canvas Lighting */}
      <div className="absolute inset-0 bg-radial from-indigo-500/[0.05] via-transparent to-cyan-500/[0.03] pointer-events-none" />

      <div className="relative z-10 flex items-center justify-between gap-3 sm:gap-4 flex-wrap lg:flex-nowrap">
        {displayNodes.map((node, idx) => {
          const isLast = idx === displayNodes.length - 1;
          const config = getNodeConfig(node.type);

          return (
            <React.Fragment key={idx}>
              {/* Node Card */}
              <div
                className={`flex-1 min-w-[170px] p-4 rounded-xl bg-gradient-to-b from-[#18233c]/90 to-[#0f172a]/95 backdrop-blur-md border ${config.borderColor} shadow-xl shadow-black/50 relative group hover:border-white/25 transition-all`}
              >
                {/* Top Node Header: Icon + Type Badge */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className={`w-8 h-8 rounded-lg ${config.iconBg} flex items-center justify-center ${config.iconColor} border ${config.iconBorder} shadow-sm`}>
                    {config.icon}
                  </div>
                  <span className={`text-[10px] font-medium tracking-tight px-2.5 py-0.5 rounded-full ${config.badgeBg} ${config.badgeColor} border ${config.badgeBorder}`}>
                    {config.roleLabel}
                  </span>
                </div>

                {/* Node Name & Description */}
                <div className="space-y-1">
                  <div className="font-bold text-sm text-white tracking-tight flex items-center gap-1.5">
                    <span>{node.name}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" title="Active & Calibrated" />
                  </div>
                  <div className="text-xs text-slate-400 leading-snug">
                    {node.note || config.defaultNote}
                  </div>
                </div>
              </div>

              {/* Connector between Nodes */}
              {!isLast && (
                <div className="flex flex-col items-center justify-center px-1 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <div className="w-4 sm:w-7 h-px bg-gradient-to-r from-white/20 via-indigo-400/60 to-white/20" />
                    <div className="w-5 h-5 rounded-full bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.3)]">
                      <ArrowRight className="w-3 h-3 text-indigo-300 shrink-0" />
                    </div>
                    <div className="w-4 sm:w-7 h-px bg-gradient-to-r from-white/20 via-indigo-400/60 to-white/20" />
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1.5 font-medium tracking-normal">
                    {idx === 0 ? 'sub-ms read' : 'sync fallback'}
                  </span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function getNodeConfig(type) {
  switch (type) {
    case 'cache':
      return {
        icon: <Zap className="w-3.5 h-3.5 fill-current" />,
        iconBg: 'bg-cyan-500/10',
        iconColor: 'text-cyan-400',
        iconBorder: 'border-cyan-500/30',
        borderColor: 'border-cyan-500/30 shadow-[0_0_15px_-3px_rgba(6,182,212,0.15)]',
        badgeBg: 'bg-cyan-500/10',
        badgeColor: 'text-cyan-300',
        badgeBorder: 'border-cyan-500/20',
        roleLabel: 'In-Memory Cache',
        defaultNote: 'Sub-millisecond Read Shield',
      };
    case 'database':
      return {
        icon: <Database className="w-3.5 h-3.5 fill-current" />,
        iconBg: 'bg-indigo-500/10',
        iconColor: 'text-indigo-400',
        iconBorder: 'border-indigo-500/30',
        borderColor: 'border-indigo-500/30 shadow-[0_0_15px_-3px_rgba(99,102,241,0.15)]',
        badgeBg: 'bg-indigo-500/10',
        badgeColor: 'text-indigo-300',
        badgeBorder: 'border-indigo-500/20',
        roleLabel: 'Primary Database',
        defaultNote: 'ACID Persistence Store',
      };
    case 'queue':
      return {
        icon: <Layers className="w-3.5 h-3.5" />,
        iconBg: 'bg-amber-500/10',
        iconColor: 'text-amber-400',
        iconBorder: 'border-amber-500/30',
        borderColor: 'border-amber-500/30 shadow-[0_0_15px_-3px_rgba(245,158,11,0.15)]',
        badgeBg: 'bg-amber-500/10',
        badgeColor: 'text-amber-300',
        badgeBorder: 'border-amber-500/20',
        roleLabel: 'Message Queue',
        defaultNote: 'Bursty Ingestion Buffer',
      };
    case 'worker':
      return {
        icon: <Cpu className="w-3.5 h-3.5" />,
        iconBg: 'bg-emerald-500/10',
        iconColor: 'text-emerald-400',
        iconBorder: 'border-emerald-500/30',
        borderColor: 'border-emerald-500/30 shadow-[0_0_15px_-3px_rgba(16,185,129,0.15)]',
        badgeBg: 'bg-emerald-500/10',
        badgeColor: 'text-emerald-300',
        badgeBorder: 'border-emerald-500/20',
        roleLabel: 'Async Worker Pool',
        defaultNote: 'Batch Persistence Worker',
      };
    case 'ingress':
    default:
      return {
        icon: <Server className="w-3.5 h-3.5" />,
        iconBg: 'bg-purple-500/10',
        iconColor: 'text-purple-400',
        iconBorder: 'border-purple-500/30',
        borderColor: 'border-white/10 shadow-[0_0_15px_-3px_rgba(168,85,247,0.1)]',
        badgeBg: 'bg-purple-500/10',
        badgeColor: 'text-purple-300',
        badgeBorder: 'border-purple-500/20',
        roleLabel: 'API Ingress',
        defaultNote: 'HTTP Router & Controller',
      };
  }
}

function deriveNodes(str = '') {
  const lower = str.toLowerCase();
  if (lower.includes('redis') || lower.includes('cache')) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go Controller' },
      { name: 'Redis 7.2', type: 'cache', note: '84.8% Cache Read Shield' },
      { name: 'PostgreSQL 16', type: 'database', note: 'Transactional Writes & Misses' },
    ];
  }
  if (lower.includes('kafka') || lower.includes('queue') || lower.includes('worker')) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'Immediate HTTP 202 Ack' },
      { name: 'Kafka Queue', type: 'queue', note: 'Partitioned Event Log' },
      { name: 'Async Worker', type: 'worker', note: 'Batch Persistence' },
      { name: 'PostgreSQL 16', type: 'database', note: 'Durable Database Store' },
    ];
  }
  return [
    { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go Controller' },
    { name: 'PostgreSQL 16', type: 'database', note: 'Direct Relational Queries' },
  ];
}
