# AADS Phase 5.1: Developer-First Architecture Copilot
## Implementation Prompt & Technical Specification

> **Target Audience**: AI Coding Agents & System Implementers  
> **Mission**: Transform AADS from an academic research simulator into an intuitive, production-grade Architecture Copilot for builders without compromising scientific rigor or empirical integrity.

---

### Core Directive: Reuse Existing Backend (Do Not Manufacture Results)
Do **not** manufacture, mock, or hardcode demo results in the frontend. All candidate metrics, feasibility flags, trade-offs, and breaking points must be consumed directly from the AADS backend API (`POST /api/agent/run` and `POST /api/workflow/run`) via the canonical decision schema.

---

## 1. Canonical Backend Object: `ArchitectureDecisionResult`

To eliminate desynchronization between the Blueprint Hero card, Candidate Comparison table, and AI Prompt Generator, all features must consume a single structured object:

```typescript
interface ArchitectureDecisionResult {
  // 1. What the developer wants to build
  workload: {
    app_type: string;
    request_rate_rps: number;
    read_ratio: number;
    write_ratio: number;
    p95_latency_target_ms: number;
    max_monthly_budget_usd?: number;
    user_facts: Record<string, any>;
    agent_assumptions: string[];
  };

  // 2. All generated architecture topologies
  candidates: Array<{
    id: string;
    name: string;
    topology: string;
    components: string[];
    is_winner: boolean;
    sla_result: "SATISFIED" | "BORDERLINE" | "VIOLATED";
    feasibility_status: "FEASIBLE" | "UNCERTAIN" | "INFEASIBLE";
  }>;

  // 3. Quantitative simulation metrics & evidence provenance
  simulations: Record<string, {
    throughput_achieved_rps: number;
    throughput_provenance: "MEASURED" | "SIMULATED" | "ESTIMATED";
    p95_latency_ms: number;
    latency_provenance: "MEASURED" | "SIMULATED_SIMPY" | "REGRESSION_MODEL";
    uncertainty_bounds_p95_ms?: [number, number];
    cpu_utilization_pct?: number;
    cpu_provenance?: "MEASURED" | "ESTIMATED" | "NOT_MODELLED";
    estimated_monthly_cost_usd?: number;
    cost_provenance?: "MODELLED" | "NOT_MODELLED";
    cache_hit_rate?: number;
    bottleneck_component: string;
  }>;

  // 4. Recommendation & Selection
  recommendation: {
    winner_architecture_id: string | null;
    is_conclusive: boolean;
    executive_summary: string;
  };

  // 5. Senior Architect Explanation & Trade-Offs (Objective Tone)
  explanation: {
    why_winner_chosen: string[];
    when_direct_db_insufficient: string;
    when_async_unnecessary: string;
    reconsideration_triggers: string[]; // Breaking points
    rejected_alternatives: Array<{
      architecture_id: string;
      technical_disqualification: string;
    }>;
  };

  // 6. Validated inputs for AI Implementation Prompt Generator
  implementation_boundaries: {
    caching_rules?: {
      strategy: "CACHE_ASIDE" | "WRITE_THROUGH" | "NONE";
      ttl_seconds: number;
      invalidation_events: string[];
    };
    connection_pool: {
      max_connections: number;
      pool_timeout_seconds: number;
    };
    timeouts_and_retries: {
      downstream_timeout_ms: number;
      max_retries: number;
      circuit_breaker_enabled: boolean;
    };
    explicit_non_goals: string[];
    developer_checkpoints: string[];
  };

  // 7. Audit & Provenance Verification
  evidence_audit: {
    registry_models_used: string[];
    manifest_sha256: string;
    policy_violations_prevented: number;
  };
}
```

---

## 2. Six Mandatory Architectural Corrections

### Correction A: Honest KPIs — Zero Hardcoding
- Every metric rendered in the UI must bind strictly to `ArchitectureDecisionResult.simulations`.
- If a metric is not modelled by the backend (e.g. cost), render explicitly:
  ```jsx
  <div className="text-slate-400">Estimated Monthly Cost: <span className="italic">Not modelled</span></div>
  ```
- **Never** invent a dollar figure or latency number to make the UI look complete.

### Correction B: Explicit Evidence Provenance (No Misleading "Capacity" Claims)
- Replace unqualified labels like `"Capacity"` and `"100% Sustained"` with:
  - `Simulated Throughput: 501.6 req/sec [Simulated]`
  - `p95 Response Time: ~7.25 ms [SimPy Queue]`
- Next to **every** key metric on the Blueprint card, display a subtle provenance tag:
  - `[Simulated]` (SimPy discrete-event queueing)
  - `[Modelled]` (SQLite calibrated regression)
  - `[Measured]` (Physical benchmark trial)
  - `[Not modelled]` (Metric outside scope)

### Correction C: Objective Architect Tone (No Calling Alternatives "Traps")
Adopt the objective, respectful tone of a principal systems architect. Replace adversarial phrasing:
- ❌ *"Why direct DB fails"* ➔ ✅ **"When direct PostgreSQL stops being sufficient"**
- ❌ *"Why Kafka is overkill"* ➔ ✅ **"When asynchronous processing is unnecessary"**
- ❌ *"When this breaks"* ➔ ✅ **"When should you reconsider this architecture?"**

### Correction D: Strict Boundaries for the AI Prompt Generator
The AI Prompt Generator must prevent both infrastructure hallucination and developer complacency. It must output:
1. **Target Topology & Versions**: e.g., `API Gateway ➔ Redis 7.2 ➔ PostgreSQL 16`.
2. **Caching Strategy**: Cache-Aside with specific TTLs and cache invalidation hooks on mutations.
3. **Database Guardrails**: Connection pool sizing, query timeout limits.
4. **Resilience & Fault Tolerance**: Retry budgets, backoff, circuit breaking.
5. **Observability Requirements**: Health check probes, p95 latency tracing, cache hit/miss metric counters.
6. **Explicit Non-Goals (What NOT to build)**:
   - *Do not implement Kafka or distributed message brokers.*
   - *Do not split into microservices.*
   - *Do not implement multi-region replication.*
7. **Developer Confirmation Checkpoints**: Areas where the AI must pause and ask the developer for confirmation.

### Correction E: Evidence In Plain Sight
Keep the 3-tab layout, but do not force users to switch tabs to check metric reliability:
- Show small inline evidence pills next to every KPI on the default Blueprint.
- Clicking any evidence pill smoothly links or expands the relevant section in the **Technical Proof** tab.

### Correction F: Unified Single Source of Truth
All three tabs and the AI prompt generator must read from `ArchitectureDecisionResult`. The frontend normalizer (`frontend/src/api/normalizer.js`) must map backend responses into this single canonical contract so that the Hero card, Alternative cards, and Prompt Generator are mathematically guaranteed to stay in sync.

---

## 3. Product View Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│ HEADER: AADS Architecture Copilot                                      │
│ Active Scenario: E-commerce API (500 req/sec • 90% Read • SLA < 100ms) │
├────────────────────────────────────────────────────────────────────────┤
│ TABS: [ ⭐ Architecture Blueprint ] [ 📊 Compare Options ] [ 🔬 Proof ]│
├────────────────────────────────────────────────────────────────────────┤
│ TAB 1: ARCHITECTURE BLUEPRINT (Default View)                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ RECOMMENDED BLUEPRINT: Cached Reads                                │ │
│ │ Topology: API Gateway ➔ Redis 7.2 In-Memory Cache ➔ PostgreSQL 16   │ │
│ │                                                                    │ │
│ │ [ Response Time ]  [ Monthly Cost ]  [ Simulated Load ] [ DB CPU ] │ │
│ │    ~7.25 ms          Not modelled       501.6 req/sec     27.5%    │ │
│ │   (Simulated)       (Not modelled)       (Simulated)   (Estimated) │ │
│ │                                                                    │ │
│ │ [ 📋 Copy AI System Prompt ]       [ Compare All 3 Options ➔ ]     │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ ┌──────────────────────────────────┐ ┌───────────────────────────────┐ │
│ │ WHY THIS ARCHITECTURE?           │ │ WHEN TO RECONSIDER IT?        │ │
│ │ - Redis absorbs 85% of queries   │ │ - If writes rise above 40%    │ │
│ │ - Protects DB connection pool    │ │ - If traffic exceeds 650 RPS  │ │
│ │ - Minimizes operational overhead │ │ - If budget capped < $150/mo  │ │
│ └──────────────────────────────────┘ └───────────────────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ TAB 2: COMPARE OPTIONS (Architecture A, B, C Side-by-Side Breakdown)  │
├────────────────────────────────────────────────────────────────────────┤
│ TAB 3: TECHNICAL PROOF & BENCHMARKS (SimPy Queues, Models, Evidence)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Verification & Testing Gates
1. **Pytest Suite**: All 337 unit and integration tests must pass (`.venv/bin/pytest tests/ -k "not live_llm"`).
2. **Scientific Freeze Preservation**:
   - `data/registry.db` must remain at exactly 24 active empirical models.
   - `artifacts/phase_4f5/candidates/` must remain frozen.
   - SHA-256 manifest hash `69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6` must match.
3. **Frontend Bundle**: `cd frontend && yarn build` must compile with zero errors in under 3 seconds.
4. **Browser DevTools Audit**: 0 console errors, 0 network drops on `http://localhost:3000`.
