import React from 'react';
import {
  Server,
  Zap,
  Database,
  Layers,
  Cpu,
  ArrowRight
} from 'lucide-react';

export default function ArchitectureTopology({ nodes = [], topologyStr = '' }) {
  const displayNodes = nodes.length > 0 ? nodes : deriveNodes(topologyStr);

  return (
    <div className="w-full rounded-xl bg-[#09090b] border border-white/[0.06] p-4 sm:p-5">
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 sm:gap-4 relative">
        {displayNodes.map((node, idx) => {
          const isLast = idx === displayNodes.length - 1;
          const config = getNodeConfig(node.type, node.name);

          return (
            <React.Fragment key={idx}>
              {/* Component Node Card */}
              <div className="flex-1 min-w-[200px] p-4 rounded-xl bg-[#141417] border border-white/[0.06] hover:border-zinc-600 transition-all duration-150 shadow-sm">
                {/* Header: Icon + Category Badge */}
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <div className={`w-8 h-8 rounded-lg ${config.iconBg} border ${config.iconBorder} flex items-center justify-center ${config.iconColor}`}>
                    {config.icon}
                  </div>
                  <span className={`text-[10px] font-mono tracking-tight px-2 py-0.5 rounded-full ${config.badgeBg} ${config.badgeColor} border ${config.badgeBorder}`}>
                    {config.roleLabel}
                  </span>
                </div>

                {/* Node Title & Description */}
                <div>
                  <div className="font-bold text-sm text-zinc-100 flex items-center gap-1.5">
                    <span>{node.name}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5 leading-snug">
                    {node.note || config.defaultNote}
                  </div>
                </div>

                {/* Bottom spec pill */}
                <div className="mt-3 pt-2 border-t border-white/[0.04] flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                  <span>{config.techFamily}</span>
                  <span className="text-zinc-400">{config.latencyClass}</span>
                </div>
              </div>

              {/* Data Flow Connector between Nodes */}
              {!isLast && (
                <div className="flex md:flex-col items-center justify-center px-1 py-1 md:py-0 shrink-0">
                  <div className="flex items-center gap-1">
                    <div className="w-3 sm:w-5 h-px bg-zinc-700 hidden md:block" />
                    <div className="w-6 h-6 rounded-full bg-[#18181c] border border-zinc-700 flex items-center justify-center text-zinc-400 shadow-xs">
                      <ArrowRight className="w-3.5 h-3.5 text-zinc-300" />
                    </div>
                    <div className="w-3 sm:w-5 h-px bg-zinc-700 hidden md:block" />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1 font-mono tracking-tight text-center">
                    {idx === 0 ? 'sync call' : idx === 1 && displayNodes.length > 2 ? 'persist write' : 'data flow'}
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

function getNodeConfig(type, name = '') {
  const lower = (name || '').toLowerCase();

  if (type === 'cache' || lower.includes('redis') || lower.includes('memcached')) {
    return {
      icon: <Zap className="w-4 h-4 fill-amber-400/20 text-amber-400" />,
      iconBg: 'bg-amber-500/10',
      iconBorder: 'border-amber-500/20',
      iconColor: 'text-amber-400',
      badgeBg: 'bg-amber-500/10',
      badgeBorder: 'border-amber-500/20',
      badgeColor: 'text-amber-300',
      roleLabel: 'In-Memory Cache',
      defaultNote: 'Sub-millisecond Read Shield',
      techFamily: 'Redis 7.2',
      latencyClass: '< 1ms p95'
    };
  }

  if (type === 'database' || lower.includes('postgres') || lower.includes('mysql') || lower.includes('db')) {
    return {
      icon: <Database className="w-4 h-4 text-sky-400" />,
      iconBg: 'bg-sky-500/10',
      iconBorder: 'border-sky-500/20',
      iconColor: 'text-sky-400',
      badgeBg: 'bg-sky-500/10',
      badgeBorder: 'border-sky-500/20',
      badgeColor: 'text-sky-300',
      roleLabel: 'Primary Database',
      defaultNote: 'ACID Relational Persistence',
      techFamily: 'PostgreSQL 16',
      latencyClass: '~10-15ms p95'
    };
  }

  if (type === 'queue' || lower.includes('kafka') || lower.includes('rabbitmq') || lower.includes('queue')) {
    return {
      icon: <Layers className="w-4 h-4 text-purple-400" />,
      iconBg: 'bg-purple-500/10',
      iconBorder: 'border-purple-500/20',
      iconColor: 'text-purple-400',
      badgeBg: 'bg-purple-500/10',
      badgeBorder: 'border-purple-500/20',
      badgeColor: 'text-purple-300',
      roleLabel: 'Message Queue',
      defaultNote: 'Bursty Ingestion Buffer',
      techFamily: 'Kafka / SQS',
      latencyClass: '~3ms enqueue'
    };
  }

  if (type === 'worker' || lower.includes('worker') || lower.includes('consumer')) {
    return {
      icon: <Cpu className="w-4 h-4 text-emerald-400" />,
      iconBg: 'bg-emerald-500/10',
      iconBorder: 'border-emerald-500/20',
      iconColor: 'text-emerald-400',
      badgeBg: 'bg-emerald-500/10',
      badgeBorder: 'border-emerald-500/20',
      badgeColor: 'text-emerald-300',
      roleLabel: 'Async Worker Pool',
      defaultNote: 'Decoupled Batch Execution',
      techFamily: 'Python / Go Workers',
      latencyClass: 'Decoupled'
    };
  }

  return {
    icon: <Server className="w-4 h-4 text-zinc-300" />,
    iconBg: 'bg-zinc-800',
    iconBorder: 'border-zinc-700',
    iconColor: 'text-zinc-200',
    badgeBg: 'bg-zinc-800',
    badgeBorder: 'border-zinc-700',
    badgeColor: 'text-zinc-300',
    roleLabel: 'API Gateway',
    defaultNote: 'Edge Routing & Rate Limiting',
    techFamily: 'FastAPI / Envoy',
    latencyClass: '< 3ms p95'
  };
}

function deriveNodes(topologyStr = '') {
  if (!topologyStr) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go Controller' },
      { name: 'PostgreSQL 16', type: 'database', note: 'Direct Relational Queries' }
    ];
  }

  const parts = topologyStr.split(/➔|->|→/).map((p) => p.trim());
  return parts.map((part) => {
    const lower = part.toLowerCase();
    let type = 'ingress';
    let note = 'Traffic Routing';

    if (lower.includes('redis') || lower.includes('cache')) {
      type = 'cache';
      note = 'Sub-millisecond Read Shield';
    } else if (lower.includes('postgres') || lower.includes('mysql') || lower.includes('database') || lower.includes('db')) {
      type = 'database';
      note = 'Relational Persistence';
    } else if (lower.includes('kafka') || lower.includes('queue') || lower.includes('mq') || lower.includes('rabbit')) {
      type = 'queue';
      note = 'Asynchronous Buffering';
    } else if (lower.includes('worker') || lower.includes('batch')) {
      type = 'worker';
      note = 'Background Processing';
    } else if (lower.includes('api') || lower.includes('gateway') || lower.includes('sync')) {
      type = 'ingress';
      note = 'Ingress Controller';
    }

    return { name: part, type, note };
  });
}
