# AADS Phase 4F.3.2 — Corrective Engineering Patch Report

**Status:** Completed & Offline Verified  
**Branch:** `feat/phase-4f32-corrective-patches`  
**Baseline Commits:** Phase 4F.3 (`86bb5f1`), Phase 4F.3.1 Engineering Audit (`1cd998d`)  
**Date:** November 2026  
**Auditor / Engineer:** Antigravity Autonomous Agent  
**Machine-Readable Summary:** [`artifacts/audits/phase_4f32_corrective_summary.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/audits/phase_4f32_corrective_summary.json)

---

## 1. Executive Summary

Phase 4F.3.2 resolves all seven methodological, instrumentation, and causal inference defects identified during the Phase 4F.3.1 final engineering review. All patches have been implemented and validated entirely offline under strict safety constraints:

- **Zero Live Docker Containers Executed:** All container operations were simulated or verified through deterministic mock harnesses.
- **Zero Model Promotions or Calibrations:** The active model registry (`data/registry.db`) remains completely untouched (24 models, 235 experiments).
- **Zero Synthetic Substitutions:** No synthetic data was generated to mask instrumentation gaps.
- **Comprehensive Offline Verification:** 26/26 isolation tests in [`tests/test_phase_4f3_isolation_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f3_isolation_instrumentation.py) and 217/217 repository tests passed with zero failures and zero regressions.

The implementation is now robust, scientifically disciplined, and ready for an operator-authorized controlled live pilot.

---

## 2. Detailed Breakdown of Corrective Patches

### FIX 01 — Storage Cgroup Directory Binding
- **Defect Identified in Audit:** In `DockerBenchmarkRunner._benchmark_postgres_isolated`, `StorageMonitor.take_snapshot()` was called without passing `cg_dir`, leaving `cgroup_io_stat` permanently empty (`{}`) in live runs while silently failing to flag the metric as unavailable.
- **Implementation:**
  - In [`aads/benchmark/docker_runner.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/docker_runner.py), `ContainerResourceMonitor` is instantiated immediately after container readiness to resolve the exact cgroup directory: `cg_dir = monitor.resolve_cgroup_dir()`.
  - Passed `cg_dir=cg_dir` explicitly to both `pre_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)` and `post_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)`.
  - In [`aads/benchmark/storage_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/storage_monitor.py), updated `take_snapshot()` so that if `cg_dir is None` or inaccessible, `"cgroup_io_stat"` is explicitly appended to `unavailable_metrics`. Empty metrics are never silently interpreted as zero I/O.
- **Regression Tests:** `test_storage_cgroup_dir_binding_and_unavailable_status` proves cgroup `io.stat` data reaches the analysis layer when available and produces explicit unavailable status when missing.

---

### FIX 02 — PostgreSQL Timing Instrumentation
- **Defect Identified in Audit:** PostgreSQL 16 defaults `track_io_timing` and `track_wal_io_timing` to `off`. Without enabling these flags, all `pg_stat_io` durations and `pg_stat_wal` write/sync times reported `0.0`, risking false conclusions about storage performance.
- **Implementation:**
  - Added `-c track_io_timing=on` and `-c track_wal_io_timing=on` to container startup in both `TrialIsolationManager.initialize_fresh_container` and `DockerBenchmarkRunner._benchmark_postgres`.
  - In [`aads/benchmark/postgres_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/postgres_instrumentation.py), added `SHOW`/`current_setting` query to `PostgresMetricsCollector.take_snapshot` to capture effective runtime settings.
  - If timing flags are disabled, `PostgresMetricsCollector` explicitly flags `track_io_timing_disabled` / `track_wal_io_timing_disabled` in `unavailable_metrics` and marks `timing_instrumentation_active=False` in `PostgresMetricsDelta`, emitting `None` instead of misleading `0.0` milliseconds.
- **Regression Tests:** `test_postgres_snapshot_parsing_and_timing_verification` and `test_postgres_snapshot_flags_disabled_timing`.

---

### FIX 03 — Stronger Deterministic Database Fingerprints
- **Defect Identified in Audit:** `TrialIsolationManager.verify_baseline_state()` only verified table row counts (`count(*)`). It could not detect corrupted balances, offsetting data modifications, or schema alterations where row count was preserved.
- **Implementation:**
  - Extended [`aads/benchmark/trial_isolation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/trial_isolation.py) with exact baseline invariants:
    - Accounts: `accounts_count == 100_000 * SF`, `min_aid == 1`, `max_aid == 100_000 * SF`, `min_abalance == 0`, `max_abalance == 0`, `sum_abalance == 0`.
    - Branches: `branches_count == SF`, `min_bid == 1`, `max_bid == SF`, `min_bbalance == 0`, `max_bbalance == 0`, `sum_bbalance == 0`.
    - Tellers: `tellers_count == 10 * SF`, `min_tid == 1`, `max_tid == 10 * SF`, `min_tbalance == 0`, `max_tbalance == 0`, `sum_tbalance == 0`.
    - History: `history_count == 0` (strictly empty).
  - Deterministic Content Fingerprint: Implemented `compute_content_fingerprint()` generating an SHA256 digest (`aads_composite_aggregate_sha256_v1`) over exact structural invariants and database-side row hash aggregates (`accounts_hash`, `branches_hash`, `tellers_hash`).
  - Diagnostic Metadata: Classified `pg_stat_user_tables.n_dead_tup` as approximate diagnostic metadata. Recorded it in snapshot telemetry without requiring `n_dead_tup == 0` as a brittle baseline invariant.
- **Regression Tests:** `test_deterministic_fingerprint_detects_offsetting_balance_changes` proves that offsetting balance modifications (+100 and -100 preserving sum=0 and row count) are rejected. `test_dead_tuples_recorded_as_diagnostic_without_failing_baseline` proves approximate dead tuples do not cause false validation rejections.

---

### FIX 04 — PostgreSQL Sampler Overhead & Persistent Session
- **Defect Identified in Audit:** The 100ms lock/wait sampler invoked `docker exec psql` 10 times per second, spawning 300 processes per 30-second trial and creating significant fork jitter and backend connection churn in a CPU-limited 1.0 vCPU container.
- **Implementation:**
  - In [`aads/benchmark/postgres_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/postgres_instrumentation.py), refactored `PostgresPeriodicSampler` to establish a single persistent interactive `psql` coprocess session via `subprocess.Popen(..., stdin=PIPE, stdout=PIPE, bufsize=1)`.
  - Queries are streamed over the stdin pipe and delimited by `\echo __END_SAMPLE__` over the stdout pipe, eliminating per-sample process spawning and connection establishment.
  - Implemented automatic fallback to discrete queries at 500ms if the coprocess fails to launch or terminates unexpectedly.
  - Added comprehensive telemetry metadata in `get_telemetry()`: `sampler_mode`, `sampling_interval_sec`, `successful_samples`, `missed_samples`, `mean_query_duration_ms`, `total_query_duration_ms`, and `monitoring_connection_count`.
  - Guaranteed clean coprocess termination with `\q` command and process join.
- **Regression Tests:** `test_postgres_periodic_sampler_telemetry_and_cleanup`.

---

### FIX 05 — Strict VALIDATED Evidence Requirements
- **Defect Identified in Audit:** `PerformanceFinding` allowed any assertion with two experiment IDs to claim `VALIDATED` status. Duplicate replications (`_r0` vs `_r1`) or identical configurations could falsely qualify as causal validations.
- **Implementation:**
  - Upgraded [`aads/core/evidence_classification.py`](file:///home/vicky/v_drive/Codes/AADS/aads/core/evidence_classification.py) `PerformanceFinding` schema with mandatory controlled intervention fields:
    - `control_experiment_id: str`
    - `treatment_experiment_id: str`
    - `manipulated_variable: str`
    - `expected_intervention: str`
    - `observed_intervention: str`
    - `comparable_baseline_confirmed: bool = True`
    - `outcome_metrics: List[str]`
  - Added strict Pydantic model validation:
    - Rejects identical control and treatment IDs.
    - Rejects duplicate replications matching `_(?:r|rep)\d+` patterns.
    - Rejects missing manipulated variables or expected/observed interventions.
    - Rejects unconfirmed baseline starting conditions.
    - Requires non-empty outcome metrics.
  - Updated `HistoricalSF2FindingsCatalog.get_corrected_findings()` with complete structured validation metadata for `FINDING_4F_02`.
- **Regression Tests:** `test_guardrail_rejects_duplicate_replications_as_intervention` and `test_guardrail_rejects_unconfirmed_baseline_for_validated`.

---

### FIX 06 — Conservative Storage Classification
- **Defect Identified in Audit:** The storage analyzer used a hardcoded rule that classified any trial with $>50\%$ host disk busy time as "storage-bound", ignoring that modern multi-queue NVMe SSDs routinely operate at high device busy percentages without queuing or saturation.
- **Implementation:**
  - Replaced arbitrary thresholds in [`aads/benchmark/storage_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/storage_monitor.py) with `StoragePressureClassification` enum:
    - `INSUFFICIENT_STORAGE_EVIDENCE`: Missing host diskstats or cgroup metrics.
    - `NO_STORAGE_PRESSURE_OBSERVED`: Host busy time $<50\%$, average queue depth $<1.0$, request latency $<10\text{ms}$.
    - `STORAGE_PRESSURE_SUSPECTED`: Elevated busy time or queue depth $\ge 1.0$, but lacking concurrent saturation criteria.
    - `STORAGE_PRESSURE_SUPPORTED`: High host busy time $\ge 70\%$ **AND** average queue depth $\ge 2.0$ **AND** average request latency $\ge 10\text{ms}$, OR sustained container write saturation $>200\text{ MB/s}$ with queue depth $\ge 2.0$.
  - Derived multi-queue NVMe metrics from `/proc/diskstats`:
    - $\Delta \text{weighted\_io\_ms} \implies \text{avg\_queue\_depth} = \Delta \text{weighted\_io\_ms} / (\text{duration} \times 1000)$.
    - $\Delta \text{io\_time\_ms} / \Delta \text{ops} \implies \text{avg\_await\_ms}$.
- **Regression Tests:** `test_conservative_storage_classification_rules` covering all four classification states.

---

### FIX 07 — CFS Causal Classification Guardrail
- **Defect Identified in Audit:** Single-trial analysis in `CFSCorrelationAnalyzer` allowed promotion to `CONTROLLED_CAUSAL_EVIDENCE` solely based on caller-supplied boolean `has_controlled_experiment_confirmation=True`.
- **Implementation:**
  - Removed the boolean bypass in [`aads/benchmark/cfs_correlation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/cfs_correlation.py).
  - Introduced `verify_controlled_intervention()` function requiring structured intervention data:
    - Distinct control and treatment experiment IDs.
    - Disallow duplicate replications.
    - Verified quota core manipulation (`treatment_quota_cores > control_quota_cores`).
    - Verified comparable baseline starting conditions.
    - Measured outcome response (`treatment_tps > control_tps`).
  - Without this verified intervention evidence, high temporal alignment ($>90\%$ 100ms periodicity and synchronized client stalls) strictly remains `STRONG_TEMPORAL_ASSOCIATION`.
- **Regression Tests:** `test_cfs_correlation_analyzer_strong_temporal_association` and `test_cfs_causal_classification_guardrail_with_intervention`.

---

## 3. Test & Verification Results

### Test Execution Summary
- **Targeted Isolation & Instrumentation Suite:**
  ```bash
  .venv/bin/pytest tests/test_phase_4f3_isolation_instrumentation.py
  # Result: 26 passed in 0.18s
  ```
- **Full Repository Test Suite:**
  ```bash
  .venv/bin/pytest tests/
  # Result: 217 passed in 18.04s
  ```
- **Regression Delta:** 0 failures, 0 errors, 0 regressions across all 217 tests.

### Safety & Integrity Audit
| Verification Item | Required State | Observed State | Compliance |
| :--- | :--- | :--- | :--- |
| **Live Docker Execution** | 0 live containers executed | 0 live containers executed | **COMPLIANT** |
| **Active Models Altered** | 0 models promoted / changed | 24 models intact in registry | **COMPLIANT** |
| **Experiments Altered** | 0 historical records modified | 235 experiments intact in registry | **COMPLIANT** |
| **Synthetic Substitutions** | 0 synthetic records used | 0 synthetic records used | **COMPLIANT** |
| **Host System Modifications** | None | None | **COMPLIANT** |

---

## 4. Changed-File Inventory

The following files have been modified or created on branch `feat/phase-4f32-corrective-patches`:

| File | Type | Description |
| :--- | :--- | :--- |
| [`aads/benchmark/storage_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/storage_monitor.py) | Modified | Cgroup dir binding, unavailable metrics handling, multi-queue metrics, conservative classification |
| [`aads/benchmark/trial_isolation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/trial_isolation.py) | Modified | Timing flags in container startup, 37-field query, exact balance invariants, SHA256 content fingerprinting |
| [`aads/benchmark/postgres_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/postgres_instrumentation.py) | Modified | Timing flag verification and reporting, persistent coprocess psql sampler, sampler telemetry |
| [`aads/benchmark/docker_runner.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/docker_runner.py) | Modified | Bound resolved cgroup dir to storage snapshots, timing flags, recorded sampler telemetry artifacts |
| [`aads/core/evidence_classification.py`](file:///home/vicky/v_drive/Codes/AADS/aads/core/evidence_classification.py) | Modified | Strict VALIDATED schema validation, anti-replication guards, updated historical catalog |
| [`aads/benchmark/cfs_correlation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/cfs_correlation.py) | Modified | Controlled intervention verification guardrail for causal claims, correlation-only default |
| [`tests/test_phase_4f3_isolation_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f3_isolation_instrumentation.py) | Modified | 26 offline regression tests covering all 7 fixes |
| [`artifacts/audits/phase_4f32_corrective_summary.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/audits/phase_4f32_corrective_summary.json) | Created | Machine-readable audit summary |
| [`reports/phase_4f32_corrective_patches.md`](file:///home/vicky/v_drive/Codes/AADS/reports/phase_4f32_corrective_patches.md) | Created | Comprehensive engineering patch report |

---

## 5. Pilot Readiness Assessment

Following the resolution of all seven engineering defects:
1. **Trial-to-trial database isolation** is guaranteed by per-trial fresh containers, deterministic SHA256 content fingerprints, exact bounds, and diagnostic dead tuple logging.
2. **PostgreSQL engine and storage observability** captures valid I/O and WAL timing metrics without process fork contention via a persistent psql coprocess.
3. **Storage bottleneck classification** uses multi-queue saturation criteria rather than a fragile 50% busy threshold.
4. **CFS causal claims** are guarded against single-trial over-claiming and require verifiable paired intervention evidence.

**Readiness Verdict:** `READY_FOR_CONTROLLED_PILOT_AUTHORIZATION`

### Next Step Recommendation
Execute a controlled **6-trial live verification pilot**:
- Workload: `read_only_select` and `balanced_oltp_tpcb`
- Scale Factor: SF=2
- Concurrency: $c=8$
- CPU Quotas: 1.0 vCPU vs 2.0 vCPU
- Replications: 3 per configuration (total 6 trials)
- Verify that live cgroup `io.stat` data, timing flags, content fingerprints, and coprocess sampler operate smoothly in the live Docker environment.

*Per safety guidelines, live execution is held pending operator review and explicit authorization.*
