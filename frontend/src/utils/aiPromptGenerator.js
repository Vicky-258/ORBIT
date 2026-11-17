/**
 * Generates a production-grade infrastructure and architecture prompt
 * that developers can paste directly into AI coding assistants (Cursor, Claude Code, Copilot, ChatGPT)
 * to prevent architectural drift and ensure backend code conforms to simulated SLA boundaries.
 *
 * Implements Correction D: Strict Boundaries, Non-Goals, and Evidence Disclosures.
 */

export function generateAIPrompt(winner, workload = {}, recommendation = {}, decisionResult = null) {
  const impl = decisionResult?.implementation || {};
  const winnerName = winner?.name || decisionResult?.recommendation?.winner_name || 'Recommended Architecture';
  const topology = winner?.topology || winner?.topology_summary || impl.recommended_topology || 'API Gateway ➔ Redis 7.2 ➔ PostgreSQL 16';
  
  const qps = workload.qps || workload.request_rate_rps || 500;
  const readRatio = Math.round((workload.read_ratio ?? 0.85) * 100);
  const writeRatio = Math.round((workload.write_ratio ?? 0.15) * 100);
  const slaMs = workload.p95_sla_ms || workload.p95_latency_target_ms || 100;
  const budgetUsd = workload.budget_usd || workload.max_monthly_budget_usd;

  const costDisplay = winner?.cost != null ? `$${winner.cost}/mo (Assumed pricing)` : 'Not modelled';
  const p95Display = winner?.p95 != null ? `~${winner.p95} ms (Simulated via SimPy)` : 'Not modelled';

  const isCached = winnerName.toLowerCase().includes('cached') || topology.toLowerCase().includes('redis');
  const isAsync = winnerName.toLowerCase().includes('async') || topology.toLowerCase().includes('kafka') || topology.toLowerCase().includes('queue');

  // 1. Specific topology guidance
  let specificRequirements = '';
  if (isCached) {
    specificRequirements = `
### 1. Cache-Aside Strategy & Invalidation Requirements
- **Cache-Aside Pattern**: On read, check Redis first. On miss, read from PostgreSQL and write to Redis with TTL.
- **TTL & Jitter**: Set default TTL to 300 seconds (5 min) with +/- 10% random jitter to avoid synchronized cache stampedes.
- **Cache Invalidation**: On write/mutation endpoints, synchronously evict or invalidate associated Redis keys. Never allow stale caches after a state mutation.
- **Fallback**: On Redis downtime or lookup timeout, gracefully degrade by querying PostgreSQL directly. Do NOT throw a 500 server error to the client.`;
  } else if (isAsync) {
    specificRequirements = `
### 1. Asynchronous Event Pipeline Requirements
- **Immediate Acknowledgment**: Write/event endpoints must validate schema and immediately enqueue events, returning HTTP 202 Accepted.
- **Worker Concurrency**: Implement background worker pool consuming batches from queue to insert into PostgreSQL.
- **Failure & Poison Pills**: Implement Dead-Letter Queue (DLQ) with exponential backoff retries (max 3 attempts).`;
  } else {
    specificRequirements = `
### 1. Direct Relational Database Requirements
- **Direct Execution**: No caching tier or message queue overhead.
- **Covering Indexes**: Ensure composite indexes exist for primary query filters to avoid full table scans.`;
  }

  // 2. Component Versions & Configuration Assumptions
  const componentVersions = impl.component_versions || {
    postgres: 'postgres:16-alpine',
    redis: isCached ? 'redis:7.2-alpine' : 'N/A',
    kafka: isAsync ? 'kafka:3.6-alpine' : 'N/A',
  };

  // 3. Connection Pooling
  const connectionPooling = impl.connection_pooling || {
    max_pool_size: 25,
    min_idle: 5,
    acquire_timeout_seconds: 2.0,
  };

  // 4. Timeouts & Retries
  const timeouts = impl.timeouts_and_retries || {
    database_query_timeout_ms: 500,
    cache_lookup_timeout_ms: 50,
    max_query_retries: 2,
    backoff_policy: 'exponential_jitter',
  };

  // 5. Observability
  const observability = impl.observability_requirements || [
    'Emit p95 and p99 response latency metrics per route.',
    'Track Redis cache hit/miss ratio gauge (target > 80%).',
    'Monitor PostgreSQL connection pool saturation and queue depth.',
  ];

  // 6. Security Considerations
  const security = impl.security_considerations || [
    'Enforce TLS in transit for all database and cache connections.',
    'Use parameterized queries / ORM prepared statements to eliminate SQL injection.',
    'Store all credentials in environment variables or cloud secret manager; never commit credentials.',
  ];

  // 7. Explicit Non-Goals (What NOT to implement)
  const nonGoals = impl.explicit_non_goals || [
    'DO NOT implement Kafka or message queues unless asynchronous architecture is chosen.',
    'DO NOT implement multi-region distributed cache clustering before single-node limits are exceeded.',
    'DO NOT introduce microservice decomposition or distributed sagas for this service.',
  ];

  // 8. Evidence Limitations & Developer Decisions
  const evidenceLimitations = impl.evidence_limitations || [
    'Performance metrics are derived from SimPy discrete-event queueing simulation, not live real-world benchmarks.',
    'Cost figures reflect standard cloud provider approximations and assume continuous 730 hr/mo usage without auto-scaling.',
  ];

  const confirmations = impl.decisions_requiring_confirmation || [
    'Confirm cache eviction policy (volatile-lru recommended for catalog items).',
    'Confirm read replica provisioning trigger if read traffic expands beyond 650 RPS.',
  ];

  return `# SYSTEM ARCHITECTURE & IMPLEMENTATION SPECIFICATION
# Generated by ORBIT Architecture Copilot

I am building the backend for this application. Please write the architecture, database models, and API endpoints following this validated infrastructure specification.

## 1. Workload Context & Target SLAs
- **Architecture**: ${winnerName}
- **Topology**: ${topology}
- **Offered Load**: ${qps} requests/sec (${readRatio}% Read / ${writeRatio}% Write)
- **Target SLA**: p95 latency < ${slaMs} ms [Evidence: ${p95Display}]
- **Monthly Cloud Budget**: ${budgetUsd ? `< $${budgetUsd}/mo` : 'Unconstrained'} [Evidence: ${costDisplay}]

## 2. Component Versions & Infrastructure Configuration
- **Database**: ${componentVersions.postgres || 'PostgreSQL 16-alpine'}
- **Cache**: ${componentVersions.redis || (isCached ? 'Redis 7.2-alpine' : 'None')}
- **Database Connection Pooling**: Max pool size: ${connectionPooling.max_pool_size || 25}, Min idle: ${connectionPooling.min_idle || 5}, Acquire timeout: ${connectionPooling.acquire_timeout_seconds || 2}s.
${specificRequirements}

## 3. Timeouts, Retries & Failure Handling
- **Query Timeout**: ${timeouts.database_query_timeout_ms || 500} ms.
- **Cache Lookup Timeout**: ${timeouts.cache_lookup_timeout_ms || 50} ms.
- **Retry Policy**: Max ${timeouts.max_query_retries || 2} retries with exponential backoff and jitter on transient connection loss.
- **Degradation**: If cache fails or times out, bypass cache and query primary database directly without returning 500 to client.

## 4. Observability & Telemetry
${observability.map((item) => `- ${item}`).join('\n')}

## 5. Security & Isolation
${security.map((item) => `- ${item}`).join('\n')}

## 6. EXPLICIT NON-GOALS (DO NOT IMPLEMENT)
${nonGoals.map((item) => `- ${item}`).join('\n')}

## 7. Scaling Boundaries & When to Reconsider
${(recommendation.conditions_for_change || [
  'When direct PostgreSQL stops being sufficient: If traffic exceeds 650 RPS or read ratio exceeds 80%.',
  'When asynchronous processing is unnecessary: When write traffic remains below 35% and client APIs require synchronous consistency.',
  'When should you reconsider this architecture? If write traffic increases substantially, cache invalidation becomes harder, or cache hit rate falls below 60%.',
]).map((c) => `- ${c}`).join('\n')}

## 8. Evidence Limitations & Required Developer Confirmation
- **Evidence Caveat**: ${evidenceLimitations.join(' ')}
- **Developer Confirmation Required**:
${confirmations.map((item) => `  - [ ] ${item}`).join('\n')}

Please generate clean, idiomatic backend code adhering strictly to these boundaries. Do not invent unneeded infrastructure tiers.`;
}
