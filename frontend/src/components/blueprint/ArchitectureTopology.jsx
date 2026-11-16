import React from 'react';
import { Server, Zap, Database, Layers, Cpu, ArrowRight } from 'lucide-react';

export default function ArchitectureTopology({ nodes = [], topologyStr = '' }) {
  // If no explicit nodes provided, derive standard nodes from topology string or candidate id
  const displayNodes = nodes.length > 0 ? nodes : deriveNodes(topologyStr);

  return (
    <div className="flex items-center gap-2 flex-wrap py-2">
      {displayNodes.map((node, idx) => {
        const isLast = idx === displayNodes.length - 1;

        return (
          <React.Fragment key={idx}>
            <div className="px-3 py-2 rounded-xl bg-black/40 border border-white/[0.08] flex items-center gap-2 text-xs">
              <NodeIcon type={node.type} />
              <div className="flex flex-col">
                <span className="font-semibold text-slate-100">{node.name}</span>
                {node.note && (
                  <span className="text-[10px] text-slate-400 font-mono">{node.note}</span>
                )}
              </div>
            </div>

            {!isLast && (
              <div className="flex items-center justify-center text-slate-500 px-0.5">
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function NodeIcon({ type }) {
  switch (type) {
    case 'cache':
      return <Zap className="w-4 h-4 text-cyan-400 shrink-0" />;
    case 'database':
      return <Database className="w-4 h-4 text-indigo-400 shrink-0" />;
    case 'queue':
      return <Layers className="w-4 h-4 text-amber-400 shrink-0" />;
    case 'worker':
      return <Cpu className="w-4 h-4 text-emerald-400 shrink-0" />;
    case 'ingress':
    default:
      return <Server className="w-4 h-4 text-slate-400 shrink-0" />;
  }
}

function deriveNodes(str = '') {
  const lower = str.toLowerCase();
  if (lower.includes('redis') || lower.includes('cache')) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go' },
      { name: 'Redis 7.2', type: 'cache', note: 'Read Cache Shield' },
      { name: 'PostgreSQL 16', type: 'database', note: 'Relational Store' },
    ];
  }
  if (lower.includes('kafka') || lower.includes('queue') || lower.includes('worker')) {
    return [
      { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go' },
      { name: 'Kafka Queue', type: 'queue', note: 'Event Ingestion' },
      { name: 'Async Worker', type: 'worker', note: 'Background Ingestion' },
      { name: 'PostgreSQL 16', type: 'database', note: 'Persistence Store' },
    ];
  }
  return [
    { name: 'API Gateway', type: 'ingress', note: 'FastAPI / Go' },
    { name: 'PostgreSQL 16', type: 'database', note: 'Direct Queries' },
  ];
}
