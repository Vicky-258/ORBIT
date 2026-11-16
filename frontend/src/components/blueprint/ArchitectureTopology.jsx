import React from 'react';
import { Server, Zap, Database, Layers, Cpu, ArrowRight } from 'lucide-react';

export default function ArchitectureTopology({ nodes = [], topologyStr = '' }) {
  const displayNodes = nodes.length > 0 ? nodes : deriveNodes(topologyStr);

  return (
    <div className="p-4 sm:p-5 rounded-xl bg-[#09090b] border border-zinc-800 relative overflow-hidden">
      <div className="relative z-10 flex items-center justify-between gap-3 sm:gap-4 flex-wrap lg:flex-nowrap">
        {displayNodes.map((node, idx) => {
          const isLast = idx === displayNodes.length - 1;
          const config = getNodeConfig(node.type);

          return (
            <React.Fragment key={idx}>
              {/* Node Card */}
              <div
                className="flex-1 min-w-[170px] p-3.5 sm:p-4 rounded-xl bg-[#141417] border border-zinc-800 hover:border-zinc-700 transition-all shadow-xs"
              >
                {/* Top Node Header: Icon + Type Badge */}
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <div className={`w-7 h-7 rounded-lg ${config.iconBg} flex items-center justify-center ${config.iconColor} border ${config.iconBorder}`}>
                    {config.icon}
                  </div>
                  <span className={`text-[10px] font-medium tracking-tight px-2 py-0.5 rounded-full ${config.badgeBg} ${config.badgeColor} border ${config.badgeBorder}`}>
                    {config.roleLabel}
                  </span>
                </div>

                {/* Node Name & Description */}
                <div className="space-y-1">
                  <div className="font-semibold text-sm text-white tracking-tight flex items-center gap-1.5">
                    <span>{node.name}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" title="Active & Calibrated" />
                  </div>
                  <div className="text-xs text-zinc-400 leading-snug">
                    {node.note || config.defaultNote}
                  </div>
                </div>
              </div>

              {/* Connector between Nodes */}
              {!isLast && (
                <div className="flex flex-col items-center justify-center px-1 shrink-0">
                  <div className="flex items-center gap-1">
                    <div className="w-3 sm:w-5 h-px bg-zinc-800" />
                    <div className="w-5 h-5 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400">
                      <ArrowRight className="w-3 h-3 text-zinc-400 shrink-0" />
                    </div>
                    <div className="w-3 sm:w-5 h-px bg-zinc-800" />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1 font-mono">
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
        iconBg: 'bg-zinc-800',
        iconColor: 'text-zinc-200',
        iconBorder: 'border-zinc-700',
        badgeBg: 'bg-zinc-800',
        badgeColor: 'text-zinc-300',
        badgeBorder: 'border-zinc-700',
        roleLabel: 'In-Memory Cache',
        defaultNote: 'Sub-millisecond Read Shield',
      };
    case 'database':
      return {
        icon: <Database className="w-3.5 h-3.5 fill-current" />,
        iconBg: 'bg-zinc-800',
        iconColor: 'text-zinc-200',
        iconBorder: 'border-zinc-700',
        badgeBg: 'bg-zinc-800',
        badgeColor: 'text-zinc-300',
        badgeBorder: 'border-zinc-700',
        roleLabel: 'Primary Database',
        defaultNote: 'ACID Persistence Store',
      };
    case 'queue':
      return {
        icon: <Layers className="w-3.5 h-3.5" />,
        iconBg: 'bg-zinc-800',
        iconColor: 'text-zinc-200',
        iconBorder: 'border-zinc-700',
        badgeBg: 'bg-zinc-800',
        badgeColor: 'text-zinc-300',
        badgeBorder: 'border-zinc-700',
        roleLabel: 'Message Queue',
        defaultNote: 'Bursty Ingestion Buffer',
      };
    case 'worker':
      return {
        icon: <Cpu className="w-3.5 h-3.5" />,
        iconBg: 'bg-emerald-500/10',
        iconColor: 'text-emerald-400',
        iconBorder: 'border-emerald-500/20',
        badgeBg: 'bg-emerald-500/10',
        badgeColor: 'text-emerald-400',
        badgeBorder: 'border-emerald-500/20',
        roleLabel: 'Async Worker Pool',
        defaultNote: 'Batch Persistence Worker',
      };
    case 'ingress':
    default:
      return {
        icon: <Server className="w-3.5 h-3.5" />,
        iconBg: 'bg-zinc-800',
        iconColor: 'text-zinc-300',
        iconBorder: 'border-zinc-700',
        badgeBg: 'bg-zinc-800',
        badgeColor: 'text-zinc-300',
        badgeBorder: 'border-zinc-700',
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
