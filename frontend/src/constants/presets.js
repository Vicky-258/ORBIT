export const CANONICAL_PRESETS = [
  {
    id: 'ecommerce',
    title: 'Scenario 1: E-commerce Catalog',
    badge: 'Read-Heavy',
    badgeColor: 'badge-emerald',
    description: '2000 QPS, 15% writes, p95 < 50ms, $800 budget. Tests read-replica and caching superiority.',
    prompt:
      "I am building an e-commerce catalog API that must handle 2000 QPS with p95 latency under 50ms and 15% write ratio. Monthly budget is $800. What architecture should I use?",
    expectedWinner: 'Architecture B (PostgreSQL + Redis Cache)',
  },
  {
    id: 'transactional',
    title: 'Scenario 2: High-Contention OLTP',
    badge: 'Write-Heavy',
    badgeColor: 'badge-amber',
    description: '400 QPS, 75% writes, p95 < 80ms, $400 budget. Cache is invalid; tests primary relational scaling.',
    prompt:
      "We are designing a high-contention financial ledger and order execution engine handling 400 QPS with 75% writes. Latency p95 must be under 80ms and budget is $400/month. Recommender must evaluate consistency trade-offs.",
    expectedWinner: 'Architecture A (Direct PostgreSQL)',
  },
  {
    id: 'analytics',
    title: 'Scenario 3: Async Analytics Pipeline',
    badge: 'Bursty Event Stream',
    badgeColor: 'badge-cyan',
    description: '3500 QPS bursts, 90% writes, $1200 budget. Synchronous DB fails; tests Kafka decoupling.',
    prompt:
      "We need an analytics event ingestion pipeline receiving 3500 QPS bursty tracking data with 90% writes. Monthly budget is $1200. Background persistence can be asynchronous. Suggest the best decoupled architecture.",
    expectedWinner: 'Architecture C (Async Event Pipeline with Kafka)',
  },
];

export const DEFAULT_PROMPT =
  "I am building an e-commerce catalog API that must handle 2000 QPS with p95 latency under 50ms and 15% write ratio. Monthly budget is $800. What architecture should I use?";
