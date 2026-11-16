export const CANONICAL_PRESETS = [
  {
    id: 'ecommerce',
    scenarioKey: 'scenario_1_ecommerce',
    title: 'Scenario 1: E-commerce API',
    badge: 'Read-Heavy',
    badgeColor: 'badge-emerald',
    qps: '500 RPS',
    sla: 'p95 < 100ms',
    budget: '$250/mo',
    mix: '85% Read / 15% Write',
    description: 'High catalog reads with occasional cart writes. In-memory caching shields relational database.',
    prompt:
      'Design a backend for an e-commerce API expecting approximately 500 requests per second. The p95 latency must remain below 100 ms, the monthly infrastructure budget is $250, and the system should support read-heavy traffic with occasional writes.',
    expectedWinner: 'Architecture B (Redis Cache)',
    expectedWinnerId: 'arch_b_cached',
  },
  {
    id: 'transactional',
    scenarioKey: 'scenario_2_transactional',
    title: 'Scenario 2: High-Contention OLTP',
    badge: 'Write-Heavy',
    badgeColor: 'badge-amber',
    qps: '150 RPS',
    sla: 'p95 < 150ms',
    budget: '$300/mo',
    mix: '40% Read / 60% Write',
    description: 'Strict transactional ledger with frequent database writes. Cache invalidation overhead makes direct DB optimal.',
    prompt:
      'Write-heavy transactional workload with 150 RPS, 40% reads and 60% writes, p95 latency under 150 ms, monthly budget $300',
    expectedWinner: 'Architecture A (Direct PostgreSQL)',
    expectedWinnerId: 'arch_a_simple',
  },
  {
    id: 'analytics',
    scenarioKey: 'scenario_3_background_worker',
    title: 'Scenario 3: Async Event Stream',
    badge: 'Bursty Event Stream',
    badgeColor: 'badge-cyan',
    qps: '300 RPS',
    sla: 'p95 < 100ms',
    budget: '$350/mo',
    mix: '10% Read / 90% Write',
    description: 'Bursty event tracking. Asynchronous message queue decouples client HTTP responses from database persistence.',
    prompt:
      'Background processing workload: 300 RPS incoming, background tasks can be processed asynchronously, p95 API response target 100 ms, budget $350/month',
    expectedWinner: 'Architecture C (Async Pipeline)',
    expectedWinnerId: 'arch_c_async',
  },
];

export const DEFAULT_PROMPT = CANONICAL_PRESETS[0].prompt;
