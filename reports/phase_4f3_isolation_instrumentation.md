# AADS Phase 4F.3 — Experimental Isolation & Instrumentation Report

**Document ID:** `PHASE-4F.3-ISOLATION-INSTRUMENTATION`  
**Execution Date:** November 2, 2026  
**Git Branch:** `feat/phase-4f3-isolation-instrumentation`  
**Baseline Commit:** `d9e9adb` (Phase 4F.2 reviewed state)  
**Execution Mode:** Engineering Implementation & Offline Validation (Strictly Non-Destructive)  
**Machine-Readable Summary:** [`artifacts/audits/phase_4f3_implementation_summary.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/audits/phase_4f3_implementation_summary.json)

---

## Executive Summary

Phase 4F.3 resolves the critical experimental methodology weaknesses identified during the Phase 4F.2 evidence audit before scaling PostgreSQL empirical benchmarks to $\text{SF}=20$ or $\text{SF}=100$. 

In previous phases (Phase 4F.1), 36 trials ran sequentially in a single long-lived container without table resets, PostgreSQL internal engine metrics were unobserved, storage metrics were conflated with logical WAL writes, CFS throttling was sampled at too coarse an interval (500ms) to resolve 100ms periods, and causal claims were occasionally asserted without supporting telemetry.

Phase 4F.3 establishes six production-grade workstreams that eliminate these weaknesses:
1. **Independent Trial Isolation:** Per-trial fresh container lifecycle, timed dataset initialization, and baseline state verification ($100,000 \times \text{SF}$ accounts, $\text{SF}$ branches, $10 \times \text{SF}$ tellers, exactly $0$ history rows) with immediate fail-closed error handling.
2. **PostgreSQL Engine Observability:** Pre- and post-trial differential snapshots and $100\text{ms}$ periodic lock/wait sampling across `pg_stat_wal`, `pg_stat_checkpointer`, `pg_stat_bgwriter`, `pg_stat_database`, `pg_stat_user_tables`, `pg_stat_io`, `pg_stat_activity`, and `pg_locks`.
3. **Storage I/O Observability:** Synchronized collection of container cgroup v2 `io.stat` and host `/proc/diskstats`, with formal rules separating logical WAL generation from physical disk saturation.
4. **Fine-Grained CFS Correlation:** $10\text{–}20\text{ms}$ cgroup v2 `cpu.stat` continuous sampling and an offline microsecond-resolution analyzer (`CFSCorrelationAnalyzer`) classifying temporal associations across four distinct epistemological tiers while strictly prohibiting client-count division fallacies.
5. **Evidence Classification Taxonomy & Guardrails:** Pydantic validation guardrails enforcing strict boundaries across five categories (`OBSERVED`, `DERIVED`, `CORRELATED`, `HYPOTHESIS`, `VALIDATED`), accompanied by a catalog of standardized corrections for historical Phase 4F.1 findings.
6. **Offline Validation & Compatibility:** A dedicated 23-test test suite verifying baseline state rejection, container lifecycle cleanup, metric delta computations, bottleneck detection, and guardrail enforcement, with $214/214$ total tests passing across the repository.

---

## Safety and Scope Verification

In strict accordance with the Phase 4F.3 authorization directive:
- **No live benchmark campaign was launched.** All empirical trials for $\text{SF}=20$ or $\text{SF}=100$ remain deferred pending explicit operator sign-off.
- **Model Registry Intact:** Zero models were calibrated, promoted, or overwritten. All 24 active production models in [`data/registry.db`](file:///home/vicky/v_drive/Codes/AADS/data/registry.db) remain preserved in their reviewed states.
- **Provenance & Evidence Separation:** Synthetic tests, offline mocks, and empirical evidence artifacts remain strictly partitioned.
- **Host System Safety:** No host OS caches were flushed, no host kernel settings were modified, and no non-benchmark containers or databases were touched.

---

## Workstream 1 — Independent Trial Isolation & Baseline Verification

### 1.1 Methodology Weakness Addressed
In Phase 4F.1, all 36 trials ran inside one persistent container. Write-heavy workloads (`balanced_oltp_tpcb` and `simple_write_ingest`) accumulated rows in `pgbench_history` and dirtied table pages. `VACUUM ANALYZE` does not reset table bloat, index bloat, or history rows, meaning subsequent trials ran against contaminated state.

### 1.2 Implementation Details ([`aads/benchmark/trial_isolation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/trial_isolation.py))
- **`TrialIsolationManager`:**
  - Manages isolated ephemeral container lifecycles per trial.
  - Pinned Docker image digest and resource constraints (`--cpus`, `--memory`).
  - Measures initialization duration separately from benchmark measurement duration (`init_duration_seconds`).
  - Guarantees forceful container destruction (`docker rm -f`) in a `finally:` block regardless of whether execution succeeds, fails, or times out.
- **`DatabaseStateSnapshot` & Pre-condition Verification:**
  - Queries exact row counts and relation byte sizes before benchmark execution.
  - **Baseline Acceptance Rule:**
    $$\text{accounts} == 100,000 \times \text{SF}$$
    $$\text{branches} == 1 \times \text{SF}$$
    $$\text{tellers} == 10 \times \text{SF}$$
    $$\text{history} == 0$$
  - **Fail-Closed Policy:** If `history > 0` or row counts mismatch, execution aborts immediately with `TrialIsolationError`.
  - Captures post-trial state and computes relation growth deltas (`delta_history_rows`, `delta_database_size_bytes`).

---

## Workstream 2 — PostgreSQL Engine Observability

### 2.1 Methodology Weakness Addressed
Phase 4F.1 relied entirely on external client observations from `pgbench`. Crucial engine behaviors—such as WAL sync duration, checkpoint flushing, buffer hit rates, and lock queues—were unobserved.

### 2.2 Implementation Details ([`aads/benchmark/postgres_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/postgres_instrumentation.py))
- **`PostgresSnapshot` & `PostgresMetricsCollector`:**
  - Captures internal database views at trial boundaries:
    - `pg_stat_wal`: `wal_records`, `wal_fpi`, `wal_bytes`, `wal_write`, `wal_sync`, `wal_write_time`, `wal_sync_time`.
    - `pg_stat_checkpointer` (PostgreSQL 16 native) with automatic fallback to `pg_stat_bgwriter` for older versions: `num_timed`, `num_requested`, `write_time`, `sync_time`, `buffers_written`.
    - `pg_stat_database`: commits, rollbacks, buffer reads, buffer hits, deadlocks, conflicts.
    - `pg_stat_user_tables`: table-level inserts, updates, deletes, and dead tuples.
    - `pg_stat_io`: PostgreSQL 16 I/O reads, writes, and fsyncs across backends.
    - `pg_stat_activity` & `pg_locks`: active queries, lock types, modes, granted status, and wait events.
- **`PostgresPeriodicSampler`:**
  - Runs in a background thread sampling `pg_stat_activity` and `pg_locks` every $100\text{ms}$.
  - Detects transient lock serialization queues that clear before trial termination.
- **Deltas and Rate Calculations:**
  - Evaluates exact deltas and rates ($\text{MB/s}$ WAL generation, buffer hit ratio).
  - Categorizes lock state objectively: `NO_CONTENTION_OBSERVED` vs `CONFIRMED_LOCK_CONTENTION_OBSERVED`.

---

## Workstream 3 — Storage I/O Observability & Bottleneck Separation

### 3.1 Methodology Weakness Addressed
Phase 4F.2 identified that earlier analyses conflated logical WAL generation ($\approx 2.5\text{ MB/s}$) with physical disk saturation, without empirical disk queueing data.

### 3.2 Implementation Details ([`aads/benchmark/storage_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/storage_monitor.py))
- **Synchronized Snapshots:**
  - Container-level: reads `/sys/fs/cgroup/io.stat` (`rbytes`, `wbytes`, `rios`, `wios`, `dbytes`).
  - Host-level: reads `/proc/diskstats` for the underlying physical device (`read_sectors`, `write_sectors`, `io_ms`, `weighted_io_ms`).
- **Storage Metrics Delta & Throughput:**
  - Computes container read/write $\text{MB/s}$ and IOPS.
  - Computes host disk active utilization percentage:
    $$\text{utilization\_pct} = \frac{\Delta \text{host\_io\_ms}}{\text{duration\_ms}} \times 100$$
- **Bottleneck Classification Guardrails:**
  - A trial is flagged as `is_storage_bound = True` **only** if:
    1. Host disk utilization exceeds $50.0\%$, or
    2. Container write throughput exceeds $200.0\text{ MB/s}$ and sustains physical write queueing.
  - If logical WAL writes are absorbed by the Linux page cache with low host disk utilization ($<10\%$), the analyzer explicitly records `is_storage_bound = False` with `NO_STORAGE_BOTTLENECK_DETECTED`.

---

## Workstream 4 — Fine-Grained CFS Instrumentation & Correlation

### 4.1 Methodology Weakness Addressed
Phase 4F.1's 500ms sampling could not resolve 100ms CFS quota boundaries. Furthermore, dividing aggregate `throttled_usec` across clients was identified by Phase 4F.2 as methodologically invalid.

### 4.2 Implementation Details ([`aads/benchmark/resource_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/resource_monitor.py), [`aads/benchmark/cfs_correlation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/cfs_correlation.py))
- **Fine-Grained Sampling ($10\text{–}20\text{ms}$):**
  - Optimized `ContainerResourceMonitor` sampling loop: downsamples slow `/proc/stat` and `/proc/meminfo` reads to $100\text{ms}$ while continuously reading `/sys/fs/cgroup/cpu.stat` at $10\text{–}20\text{ms}$.
- **`CFSCorrelationAnalyzer` Microsecond Clustering:**
  - Microsecond-level timestamp analysis of `pgbench -l` transaction records.
  - Detects multi-client synchronization: clusters latency spikes ($\ge 10\text{ms}$) completing within $1.5\text{ms}$ of each other (the signature of simultaneous release from a CFS quota freeze).
  - Computes the median inter-cluster interval and verifies alignment against the $100\text{ms}$ CFS period ($\pm 5\text{ms}$).
- **Four-Tier Epistemological Association Taxonomy:**
  1. `NO_DETECTABLE_ASSOCIATION`: Spikes do not align with 100ms periods or cgroup throttling.
  2. `TEMPORAL_ASSOCIATION`: Spikes coincide with periods of cgroup throttling without strict 100ms periodicity or multi-client clustering.
  3. `STRONG_TEMPORAL_ASSOCIATION`: Observed spikes exhibit $\ge 90\%$ alignment to 100ms intervals and $\ge 80\%$ multi-client synchronization.
  4. `CONTROLLED_CAUSAL_EVIDENCE`: Strong temporal association corroborated by controlled variable manipulation (e.g. CPU quota doubling).
- **Prohibition of Fallacious Metrics:** Explicit guards ensure aggregate `throttled_usec` is never divided by client count.

---

## Workstream 5 — Evidence Classification Taxonomy & Epistemological Guardrails

### 5.1 Epistemological Framework ([`aads/core/evidence_classification.py`](file:///home/vicky/v_drive/Codes/AADS/aads/core/evidence_classification.py))
The `PerformanceFinding` model introduces strict runtime validation:
- **`OBSERVED`**: Direct sensor readings. Must be purely descriptive; causal words ("caused by", "due to") raise validation errors.
- **`DERIVED`**: Deterministic calculations from observed values (e.g., $\text{TPS} = \text{tx\_count} / \text{duration}$).
- **`CORRELATED`**: Temporal or statistical alignment without causal demonstration.
- **`HYPOTHESIS`**: Domain theories explaining uninstrumented phenomena (e.g., row lock contention before `pg_locks` was collected).
- **`VALIDATED`**: Causal claims confirmed by controlled variable manipulation. Requires $\ge 2$ independent supporting experiments (treatment vs control); single-trial validation raises an error.

### 5.2 Scientific Guardrails
- **Lock Contention Claims:** Asserting lock contention as causal without instrumented `pg_locks` or `pg_stat_activity` wait metrics raises `ValidationError`.
- **Storage Bottleneck Claims:** Asserting disk bottlenecks without host diskstats or cgroup `io.stat` metrics raises `ValidationError`.

### 5.3 Corrected Historical Findings Catalog
Historical findings from Phase 4F.1 were re-indexed under the standardized taxonomy:

| Finding ID | Title | Corrected Classification | Justification & Provenance |
| :--- | :--- | :--- | :--- |
| `FINDING_4F_01` | 100ms Tail Latency Periodicity | **`OBSERVED`** | Directly measured in `pgbench -l` logs (>99.7% spikes align to 100.0ms). |
| `FINDING_4F_02` | CFS Quota Causal Driver of Tail Latency | **`VALIDATED`** | Confirmed via controlled CPU quota doubling (1.0 vs 2.0 vCPU). |
| `FINDING_4F_03` | TPC-B Throughput Inversion ($c \ge 8$) | **`OBSERVED`** | Direct measurement (TPS drops from 1,361 to 1,213; p95 rises from 5.5ms to 44.1ms). |
| `FINDING_4F_04` | Branch/Teller Row Lock Serialization | **`HYPOTHESIS`** | Plausible explanation, but `pg_locks` was uninstrumented in Phase 4F.1. |
| `FINDING_4F_05` | Simultaneous 3.15s Stall in TPC-B $c=4$ Rep 1 | **`OBSERVED`** | Directly observed across 4 client threads; root cause classified as UNVERIFIED. |
| `FINDING_4F_06` | Single-Client Write Synchronous WAL Limit | **`HYPOTHESIS`** | Plausible domain deduction, but fsync duration was unmeasured in Phase 4F.1. |

---

## Workstream 6 — Validation, Tests & Verification Results

### 6.1 Test Suite Structure ([`tests/test_phase_4f3_isolation_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f3_isolation_instrumentation.py))
A comprehensive 23-test suite was implemented to validate all components offline:
- **Baseline Verification (4 tests):** Clean baseline passes; dirty history (>0 rows) fails; corrupted accounts fail; state snapshot diff computes exact row/byte deltas.
- **Container Lifecycle (2 tests):** Initialization failure triggers immediate cleanup; dirty baseline failure triggers immediate cleanup.
- **PostgreSQL Observability (4 tests):** Correct parsing of PG 16 views; fallback handling; exact deltas and rate calculations; lock contention classification.
- **Storage Observability (4 tests):** Cgroup `io.stat` parsing; diskstats parsing; logical WAL writes with low utilization classified as non-storage-bound; high utilization ($\ge 50\%$) classified as storage-bound.
- **CFS Correlation (4 tests):** Transaction log parsing; `NO_DETECTABLE_ASSOCIATION` on zero spikes; `STRONG_TEMPORAL_ASSOCIATION` on clustered 100ms spikes; `CONTROLLED_CAUSAL_EVIDENCE` requiring controlled confirmation.
- **Evidence Guardrails (4 tests):** All 5 levels supported; rejection of uninstrumented lock claims; rejection of uninstrumented disk claims; rejection of causal language in `OBSERVED`.
- **Findings Catalog (1 test):** Verification that all corrected historical findings are present.
- **Runner Integration (1 test):** Full `DockerBenchmarkRunner` isolated workflow with mocks verifying artifact persistence.

### 6.2 Test Results
- **Phase 4F.3 Test Suite:** 23/23 tests passed in 0.07 seconds.
- **Repository-Wide Test Suite:** 214/214 tests passed in 18.86 seconds with **zero regressions**.

---

## Artifact Inventory & Provenance

When running in isolated mode (`per_trial_isolation=True`), the runner generates the following artifact suite for every individual replication:

| Artifact Path Pattern | Source & Instrumentation |
| :--- | :--- |
| `database_state_baseline_{trial_prefix}.json` | Pre-trial database row counts, relation sizes, and PG configurations |
| `database_state_post_{trial_prefix}.json` | Post-trial database row counts and relation sizes |
| `database_state_diff_{trial_prefix}.json` | Net row growth, table bloat, and database byte deltas |
| `postgres_snapshot_pre_{trial_prefix}.json` | Pre-trial `pg_stat_wal`, `pg_stat_checkpointer`, `pg_stat_io`, etc. |
| `postgres_snapshot_post_{trial_prefix}.json` | Post-trial `pg_stat_wal`, `pg_stat_checkpointer`, `pg_stat_io`, etc. |
| `postgres_metrics_delta_{trial_prefix}.json` | WAL bytes, checkpoint sync times, and buffer hit rates |
| `postgres_lock_samples_{trial_prefix}.json` | Background 100ms samples of ungranted locks and active wait events |
| `storage_snapshot_pre_{trial_prefix}.json` | Pre-trial cgroup v2 `io.stat` and host `/proc/diskstats` |
| `storage_snapshot_post_{trial_prefix}.json` | Post-trial cgroup v2 `io.stat` and host `/proc/diskstats` |
| `storage_metrics_delta_{trial_prefix}.json` | Net read/write $\text{MB/s}$, IOPS, and bottleneck classification |
| `monitoring_samples_{trial_prefix}.json` | High-frequency (10–20ms) cgroup CPU and memory telemetry |
| `monitoring_summary_{trial_prefix}.json` | Mean/peak CPU, memory, and aggregate throttling metrics |
| `correlation_analysis_{trial_prefix}.json` | Offline microsecond CFS clustering and association taxonomy |
| `pglog_{trial_prefix}.log` | Raw client-level transaction log output (`pgbench -l`) |
| `pgbench_{trial_prefix}.stdout` / `.stderr` | pgbench runtime standard output and diagnostic logs |

---

## Readiness Assessment & Next Steps

1. **Readiness for Empirical Benchmark Scaling:**
   - The experimental methodology is now fully hardened against trial-to-trial contamination, unobserved engine locks, and unsupported causal inferences.
   - The platform is structurally prepared to execute $\text{SF}=20$ and $\text{SF}=100$ benchmarks with complete scientific rigor.
2. **Current Status:**
   - All engineering and offline validation requirements for Phase 4F.3 are complete.
   - Per safety guidelines, no live multi-trial benchmark campaign has been initiated.
3. **Operator Review:**
   - Awaiting operator review and formal authorization before launching subsequent empirical benchmark campaigns.
