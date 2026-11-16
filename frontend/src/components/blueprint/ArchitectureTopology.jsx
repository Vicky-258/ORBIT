import React from 'react';
import { Server, Zap, Database, Layers, Cpu, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function ArchitectureTopology({ nodes = [], topologyStr = '' }) {
  const displayNodes = nodes.length > 0 ? nodes : deriveNodes(topologyStr);

  return (
    <div className="p-5 sm:p-6 rounded-xl bg-slate-50/70 border border-slate-200/80 bg-dot-grid relative overflow-hidden shadow-2xs">
      <div className="relative z-10 flex items-center justify-between gap-3 sm:gap-4 flex-wrap lg:flex-nowrap">
        {displayNodes.map((node, idx) => {
          const isLast = idx === displayNodes.length - 1;
          const config = getNodeConfig(node.type);

          return (
            <React.Fragment key={idx}>
              {/* Node Card */}
              <div
                className="flex-1 min-w-[170px] p-4 rounded-xl bg-white border border-slate-200 shadow-xs hover:border-slate-300 hover:shadow-sm transition-all"
              >
                {/* Top Node Header: Icon + Type Badge */}
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div className={`w-8 h-8 rounded-lg ${config.iconBg} flex items-center justify-center ${config.iconColor} border ${config.iconBorder} shadow-2xs`}>
                    {config.icon}
                  </div>
                  <span className={`text-[10px] font-medium tracking-tight px-2.5 py-0.5 rounded-full ${config.badgeBg} ${config.badgeColor} border ${config.badgeBorder}`}>
                    {config.roleLabel}
                  </span>
                </div>

                {/* Node Name & Description */}
                <div className="space-y-1">
                  <div className="font-bold text-sm text-slate-900 tracking-tight flex items-center gap-1.5">
                    <span>{node.name}</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-500" title="Active & Calibrated" />
                  </div>
                  <div className="text-xs text-slate-500 leading-snug">
                    {node.note || config.defaultNote}
                  </div>
                </div>
              </div>

              {/* Connector between Nodes */}
              {!isLast && (
                <div className="flex flex-col items-center justify-center px-1 shrink-0">
                  <div className="flex items-center gap-1">
                    <div className="w-4 sm:w-6 h-px bg-slate-300" />
                    <div className="w-5 h-5 rounded-full bg-white border border-slate-300 flex items-center justify-center text-slate-600 shadow-2xs">
                      <ArrowRight className="w-3 h-3 text-slate-600 shrink-0" />
                    </div>
                    <div className="w-4 sm:w-6 h-px bg-slate-300" />
                  </div>
                  <span className="text-[10px] text-slate-500 mt-1.5 font-medium tracking-normal">
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
        iconBg: 'bg-cyan-50',
        iconColor: 'text-cyan-700',
        iconBorder: 'border-cyan-200',
        badgeBg: 'bg-cyan-50',
        badgeColor: 'text-cyan-700',
        badgeBorder: 'border-cyan-200',
        roleLabel: 'In-Memory Cache',
        defaultNote: 'Sub-millisecond Read Shield',
      };
    case 'database':
      return {
        icon: <Database className="w-3.5 h-3.5 fill-current" />,
        iconBg: 'bg-blue-50',
        iconColor: 'text-blue-700',
        iconBorder: 'border-blue-200',
        badgeBg: 'bg-blue-50',
        badgeColor: 'text-blue-700',
        badgeBorder: 'border-blue-200',
        roleLabel: 'Primary Database',
        defaultNote: 'ACID Persistence Store',
      };
    case 'queue':
      return {
        icon: <Layers className="w-3.5 h-3.5" />,
        iconBg: 'bg-amber-50',
        iconColor: 'text-amber-700',
        iconBorder: 'border-amber-200',
        badgeBg: 'bg-amber-50',
        badgeColor: 'text-amber-700',
        badgeBorder: 'border-amber-200',
        roleLabel: 'Message Queue',
        defaultNote: 'Bursty Ingestion Buffer',
      };
    case 'worker':
      return {
        icon: <Cpu className="w-3.5 h-3.5" />,
        iconBg: 'bg-emerald-50',
        iconColor: 'text-emerald-700',
        iconBorder: 'border-emerald-200',
        badgeBg: 'bg-emerald-50',
        badgeColor: 'text-emerald-700',
        badgeBorder: 'border-emerald-200',
        roleLabel: 'Async Worker Pool',
        defaultNote: 'Batch Persistence Worker',
      };
    case 'ingress':
    default:
      return {
        icon: <Server className="w-3.5 h-3.5" />,
        iconBg: 'bg-slate-100',
        iconColor: 'text-slate-700',
        iconBorder: 'border-slate-200',
        badgeBg: 'bg-slate-100',
        badgeColor: 'text-slate-700',
        badgeBorder: 'border-slate-200',
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
