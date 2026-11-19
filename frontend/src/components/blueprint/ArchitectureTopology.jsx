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
    <div className="w-full rounded-xl bg-[#111317] border border-[#1e222b] overflow-hidden">
      {/* Continuous Technical Pipeline Nodes */}
      <div className="flex flex-col md:flex-row items-stretch border-b border-[#1e222b] overflow-x-auto divide-y md:divide-y-0 md:divide-x divide-[#1e222b]">
        {displayNodes.map((node, idx) => {
          const config = getNodeConfig(node.type, node.name);

          return (
            <div
              key={idx}
              className={`flex-1 min-w-[200px] p-5 bg-[#16181f] flex flex-col justify-between transition-colors ${config.borderAccent}`}
            >
              <div>
                {/* Node Sub-Header: Role + Latency Class */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className={`text-[10px] font-mono font-bold tracking-wider uppercase ${config.roleColor}`}>
                    {config.roleLabel}
                  </span>
                  <span className="text-[10px] font-mono text-slate-500">
                    {config.latencyClass}
                  </span>
                </div>

                {/* Node Name */}
                <div className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>{node.name}</span>
                </div>

                <div className="text-xs text-slate-400 mt-1 leading-snug">
                  {node.note || config.defaultNote}
                </div>
              </div>

              {/* Technical Spec Rows */}
              <div className="mt-4 pt-3 border-t border-[#1e222b] font-mono text-[11px] space-y-1">
                <div className="flex justify-between text-slate-500">
                  <span>Component</span>
                  <span className="text-slate-300 font-medium">{config.techFamily}</span>
                </div>
                <div className="flex justify-between text-slate-500">
                  <span>Access Mode</span>
                  <span className="text-slate-400">{config.accessMode}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pipeline Dataflow Summary Bar */}
      <div className="px-5 py-3 bg-[#111317] flex items-center justify-between text-[11px] font-mono text-slate-400">
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#34d399]" />
          <span>Continuous verified data path</span>
        </span>
        <span className="text-slate-500">Protocol: HTTP/3 Edge ➔ Low-Latency Sync</span>
      </div>
    </div>
  );
}

function getNodeConfig(type, name = '') {
  const lower = (name || '').toLowerCase();

  if (type === 'cache' || lower.includes('redis') || lower.includes('memcached')) {
    return {
      borderAccent: 'border-t-2 border-t-[#fef08a]',
      roleColor: 'text-[#fef08a]',
      roleLabel: 'Memory Cache Tier',
      defaultNote: 'Sub-millisecond Read Shield',
      techFamily: 'Redis 7.2 Cluster',
      latencyClass: '< 1.2ms p95',
      accessMode: 'In-Memory Volatile-LRU'
    };
  }

  if (type === 'database' || lower.includes('postgres') || lower.includes('mysql') || lower.includes('db')) {
    return {
      borderAccent: 'border-t-2 border-t-[#ffffff]',
      roleColor: 'text-[#ffffff]',
      roleLabel: 'Persistence Tier',
      defaultNote: 'ACID Relational Storage',
      techFamily: 'PostgreSQL 16',
      latencyClass: '~10-15ms p95',
      accessMode: 'Read Committed'
    };
  }

  if (type === 'queue' || lower.includes('kafka') || lower.includes('rabbitmq') || lower.includes('queue')) {
    return {
      borderAccent: 'border-t-2 border-t-[#c084fc]',
      roleColor: 'text-[#c084fc]',
      roleLabel: 'Message Queue Tier',
      defaultNote: 'Bursty Ingestion Buffer',
      techFamily: 'Apache Kafka / SQS',
      latencyClass: '~3ms enqueue',
      accessMode: 'Distributed Log'
    };
  }

  if (type === 'worker' || lower.includes('worker') || lower.includes('consumer')) {
    return {
      borderAccent: 'border-t-2 border-t-[#34d399]',
      roleColor: 'text-[#34d399]',
      roleLabel: 'Async Worker Pool',
      defaultNote: 'Decoupled Batch Processing',
      techFamily: 'Go / Python Workers',
      latencyClass: 'Decoupled Async',
      accessMode: 'Event Consumers'
    };
  }

  return {
    borderAccent: 'border-t-2 border-t-slate-500',
    roleColor: 'text-slate-400',
    roleLabel: 'Edge Ingress Tier',
    defaultNote: 'Traffic Routing & Rate Limiting',
    techFamily: 'Envoy / Cloudflare',
    latencyClass: '< 3ms p95',
    accessMode: 'Anycast Edge L7'
  };
}

function deriveNodes(topologyStr = '') {
  if (!topologyStr) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'Edge Envoy Controller' },
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
