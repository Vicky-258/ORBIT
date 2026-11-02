# AADS Phase 4F.3.1 — Final Offline Engineering Review

**Document ID:** `PHASE-4F.3.1-FINAL-OFFLINE-ENGINEERING-REVIEW`  
**Review Date:** November 2, 2026  
**Git Branch:** `feat/phase-4f31-final-review`  
**Baseline Commit:** `86bb5f1` (Reviewed Phase 4F.3 implementation)  
**Review Type:** Deep Offline Code & Methodology Audit (Strictly Non-Destructive)  
**Machine-Readable Summary:** [`artifacts/audits/phase_4f31_engineering_review_summary.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/audits/phase_4f31_engineering_review_summary.json)

---

## Executive Summary & Review Scope

Following the implementation of experimental isolation, engine observability, storage monitoring, fine-grained CFS correlation, and evidence guardrails in Phase 4F.3, this engineering review conducts a comprehensive, line-by-line audit of the codebase prior to authorizing any live benchmark executions.

In strict adherence to the Phase 4F.3.1 directive:
- **No live Docker containers or PostgreSQL databases were started.**
- **No registry models were modified, calibrated, or promoted.**
- **No implementation code was silently modified in-place.**
- All findings, discovered defects, risks, and proposed fixes are documented objectively for operator review.

### Key Audit Findings Overview
1. **Database Baseline Fingerprints:** Baseline verification currently checks only table row counts (`count(*)`), not actual data contents, balance checksums, table bloat, sequence values, or configuration conformance. Two databases with identical row counts but dirty balances or modified schemas would pass verification.
2. **Storage Classification:** Device utilization is computed from host disk busy ticks (`io_ms`), ignoring queue depth and service latency (`weighted_io_ms`, `await`). A hardcoded 50% threshold is inadequate across modern NVMe multi-queue devices. Crucially, `StorageMonitor.take_snapshot()` in `docker_runner.py` is invoked without passing `cg_dir`, causing cgroup v2 `io.stat` container metrics to remain empty during live runs.
3. **CFS Correlation:** The correlation analyzer detects temporal periodicity from transaction logs, but does not align transactions with the kernel's CFS period phase. Furthermore, `CONTROLLED_CAUSAL_EVIDENCE` can currently be assigned if the caller passes a boolean flag `has_controlled_experiment_confirmation=True` without automated verification of a paired control/treatment experiment.
4. **Evidence Classification:** `PerformanceFinding` requires $\ge 2$ experiment IDs for `VALIDATED`, but does not verify whether those experiment IDs are actual treatment/control variations or merely duplicate replications of the same configuration.
5. **PostgreSQL Permissions & Engine Settings:** PG 16 views require `track_io_timing = on` and `track_wal_io_timing = on` (both default to `off` in vanilla PostgreSQL) to record non-zero I/O and WAL sync times.
6. **Monitoring Overhead Contention:** The 100ms `PostgresPeriodicSampler` spawns a new `docker exec` and `psql` backend connection 10 times per second, risking significant process-forking and connection overhead inside a 1.0 vCPU container.

---

## Review 1: Database Baseline Fingerprints

**Inspected Module:** [`aads/benchmark/trial_isolation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/trial_isolation.py)

### 1.1 Scope of Current Verification
In `TrialIsolationManager.verify_baseline_state()`, lines 136–180:
```python
# 1. Scale factor consistency
if snapshot.scale_factor != expected_sf:
    violations.append(...)

# 2. Strict initial row counts
if snapshot.accounts_count != 100_000 * expected_sf:
    violations.append(...)
if snapshot.branches_count != expected_sf:
    violations.append(...)
if snapshot.tellers_count != 10 * expected_sf:
    violations.append(...)

# 3. Isolation Precondition: History table MUST be empty
if snapshot.history_count != 0:
    violations.append(...)
```

### 1.2 Identified Content Gaps
The current implementation verifies **cardinality only**. It does not inspect table contents or engine state:
1. **Table-Content Values:** Standard `pgbench` initialization populates:
   - `pgbench_accounts`: `aid` from 1 to $100,000 \times \text{SF}$, with initial `abalance = 0`.
   - `pgbench_branches`: `bid` from 1 to $\text{SF}$, with initial `bbalance = 0`.
   - `pgbench_tellers`: `tid` from 1 to $10 \times \text{SF}$, with initial `tbalance = 0`.
   - `pgbench_history`: 0 rows.
   If a prior write workload modified account or branch balances, or if rows were deleted and re-inserted with modified data, `count(*)` remains unchanged, and `verify_baseline_state()` passes.
2. **Table and Index Bloat:** `capture_database_state()` records `pg_total_relation_size()`, but `verify_baseline_state()` does not assert any size envelope or dead tuple check. A vacuumed table with significant page fragmentation and bloated indexes will pass.
3. **Sequences:** `pgbench_history` does not have a primary key sequence by default in standard pgbench, but custom workloads or table modifications could alter sequence generators.
4. **PostgreSQL Configuration Settings:** `capture_database_state()` queries `shared_buffers`, `work_mem`, `max_connections`, `checkpoint_timeout`, `synchronous_commit`, and `autovacuum`. However, `verify_baseline_state()` **never validates these settings against an expected baseline configuration**.

### 1.3 Scenario: Identical Counts, Contaminated Database
Consider a benchmark run where a trial previously completed 10,000 TPC-B transactions, dirtying balances across thousands of accounts. If the database is "reset" by executing `TRUNCATE pgbench_history;` without recreating the container:
- `accounts_count = 200,000` (Matches expected $100,000 \times 2$)
- `branches_count = 2` (Matches expected 2)
- `tellers_count = 20` (Matches expected 20)
- `history_count = 0` (Matches expected 0)
- **Result:** `verify_baseline_state()` returns `is_valid = True`, despite the fact that `abalance` and `bbalance` values are dirty and index structures are fragmented.

### 1.4 Recommended Fingerprinting Architecture
To achieve deterministic content verification without the latency of computing cryptographic hashes (e.g. `md5(string_agg(...))`) across millions of account rows, we recommend a lightweight aggregate fingerprint:
```sql
SELECT 
  count(*) as n_acc,
  sum(abalance) as sum_abalance,
  min(abalance) as min_abalance,
  max(abalance) as max_abalance,
  min(aid) as min_aid,
  max(aid) as max_aid,
  (SELECT sum(bbalance) FROM pgbench_branches) as sum_bbalance,
  (SELECT sum(tbalance) FROM pgbench_tellers) as sum_tbalance
FROM pgbench_accounts;
```
**Verification Invariant:**
- $\text{sum}(abalance) == 0, \quad \min(abalance) == 0, \quad \max(abalance) == 0$
- $\min(aid) == 1, \quad \max(aid) == 100,000 \times \text{SF}$
- $\text{sum}(bbalance) == 0, \quad \text{sum}(tbalance) == 0$
- Dead tuples check: `SELECT sum(n_dead_tup) FROM pg_stat_user_tables == 0`
- Overhead: Runs in $\approx 15\text{ms}$ at $\text{SF}=2$ and $\approx 150\text{ms}$ at $\text{SF}=20$ (single sequential table scan).

---

## Review 2: Storage Classification

**Inspected Module:** [`aads/benchmark/storage_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/storage_monitor.py)

### 2.1 Formula and Classification Mechanism
In `StorageMonitor.compute_deltas()`, lines 261–273:
```python
io_util_pct = (host_io_ms / (dur * 1000.0)) * 100.0 if dur > 0 else 0.0
is_bound = False
reason = "NO_STORAGE_BOTTLENECK_DETECTED"

if io_util_pct >= 50.0:
    is_bound = True
    reason = f"High host disk utilization ({io_util_pct:.1f}% >= 50.0%) during measurement window."
elif tot_wbytes > 0 and (tot_wbytes / (1024.0 * 1024.0 * dur)) > 200.0:
    is_bound = True
    reason = f"Saturated container write throughput ({tot_wbytes / (1024.0 * 1024.0 * dur):.1f} MB/s)."
else:
    reason = f"Host I/O utilization is low ({io_util_pct:.1f}%)..."
```

### 2.2 Methodological Evaluation
1. **Device Busy Time vs. Parallel Queueing:**
   - Field 12 of `/proc/diskstats` (`io_ms`) measures the duration during which at least one I/O request was in-flight (device active ticks).
   - On legacy rotational hard drives (HDDs), `io_ms` close to 100% correlates with head saturation.
   - On modern NVMe SSDs operating with 32 to 64 parallel submission queues, a device can be "active" ($100\%$ busy) while serving only a single queue depth with minimal latency ($\approx 50\mu\text{s}$). 
   - Conversely, high queueing latency can occur even with moderate utilization if large `fsync` barriers stall writes.
   - **Flaw:** Treating $50\%$ `io_ms` utilization as a universal indicator of a storage bottleneck is technically invalid on modern storage devices.
2. **Ignored Queueing and Latency Telemetry:**
   - `StorageMonitor` reads `read_ms`, `write_ms`, and `weighted_io_ms` from `/proc/diskstats` (lines 166, 170, 171), but **never uses them in `compute_deltas()`**.
   - Average request queue depth is given by:
     $$\text{Queue Depth} = \frac{\Delta \text{weighted\_io\_ms}}{\text{duration\_ms}}$$
   - Average I/O service latency (`await`) is given by:
     $$\text{Avg Latency (ms)} = \frac{\Delta \text{read\_ms} + \Delta \text{write\_ms}}{\Delta \text{reads\_completed} + \Delta \text{writes\_completed}}$$
   - True storage-bound behavior requires measuring both high utilization **and** elevated queue depth or latency.
3. **Primary Device Detection Heuristic:**
   - Lines 162–175: The device discovery matches `nvme`, `sd`, `vd` and selects the first one matching `"0n1"`, `"sda"`, or `"vda"`.
   - If the Docker storage root (`/var/lib/docker`) resides on a secondary volume (e.g. `/dev/nvme1n1`, an LVM volume, or a partition mount), `primary_dev` can latch onto the wrong physical disk.
4. **Critical Bug in Docker Runner Integration:**
   - In `aads/benchmark/docker_runner.py`:
     - Line 815: `pre_storage = StorageMonitor.take_snapshot()`
     - Line 874: `post_storage = StorageMonitor.take_snapshot()`
   - Notice that `cg_dir` is **omitted**.
   - In `StorageMonitor.take_snapshot(cls, cg_dir=None)`:
     `cgroup_io = cls._read_cgroup_io_stat(cg_dir) if cg_dir else {}`
   - **Impact:** During live runs, `cgroup_io_stat` is **always empty (`{}`)**, meaning container-level read/write byte counters (`tot_wbytes`, `tot_rbytes`) are permanently zero! Consequently, the container write saturation check (`tot_wbytes / ... > 200.0 MB/s`) is dead code.

---

## Review 3: CFS Correlation

**Inspected Modules:** [`aads/benchmark/cfs_correlation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/cfs_correlation.py), [`aads/benchmark/resource_monitor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/resource_monitor.py)

### 3.1 Monotonic vs. Wall-Clock Timestamps
- `pgbench -l` emits UNIX epoch timestamps (`sec` + `usec / 1e6`) obtained via `gettimeofday()`.
- `ContainerResourceMonitor` samples cgroup metrics using Python's `time.monotonic()`.
- In `CFSCorrelationAnalyzer.analyze()`:
  - Cluster intervals and spike clustering are calculated **purely from `pgbench` transaction timestamps**:
    `inter_cluster_intervals_ms = [(cluster_times[i] - cluster_times[i-1]) * 1000.0]`
  - The analyzer does not convert monotonic cgroup sample times to epoch time using a synchronized anchor.
  - While relative inter-spike intervals ($100\text{ms}$) are mathematically independent of absolute clock offsets, cross-referencing a specific latency spike with a specific cgroup throttling sample is currently unanchored.

### 3.2 Periodicity vs. Absolute Phase Alignment
- The analyzer tests whether intervals between multi-client stall clusters are integer multiples of $100\text{ms}$ ($\pm 5\text{ms}$).
- This confirms **temporal periodicity**, but cannot determine the kernel's CFS epoch phase (the Linux kernel does not export the wall-clock time of CFS period resets).
- Thus, the analysis establishes that transactions stall with a $100\text{ms}$ recurrence, not that they align to a known external clock.

### 3.3 Epistemological Guard on `CONTROLLED_CAUSAL_EVIDENCE`
- In `cfs_correlation.py`, line 189:
  ```python
  if period_alignment_pct >= 90.0 and sync_cluster_pct >= 80.0:
      if has_controlled_experiment_confirmation:
          association_level = CFSAssociationLevel.CONTROLLED_CAUSAL_EVIDENCE
  ```
- **Vulnerability:** `has_controlled_experiment_confirmation` is an unverified boolean argument passed by the caller. If a user or automated pipeline passes `has_controlled_experiment_confirmation=True` on a single-trial run, the analyzer emits `CONTROLLED_CAUSAL_EVIDENCE`.
- **Requirement:** A single experiment can **never** be classified as `CONTROLLED_CAUSAL_EVIDENCE`. Causal classification requires an explicit comparative structure referencing both treatment and control datasets.

---

## Review 4: Evidence Classification & Epistemological Boundaries

**Inspected Module:** [`aads/core/evidence_classification.py`](file:///home/vicky/v_drive/Codes/AADS/aads/core/evidence_classification.py)

### 4.1 Requirement Definitions
- **`OBSERVED`:** Directly captured by instrumented hardware, OS, or engine counters.
  - *Guardrail:* Validated to ensure no causal words (`caused by`, `due to`, `because of`) exist in the claim.
- **`DERIVED`:** Deterministically computed from observed quantities (e.g. $\text{TPS} = \text{transactions} / \text{duration}$).
- **`CORRELATED`:** Multiple metrics show statistical or temporal association without isolated experimental proof.
- **`HYPOTHESIS`:** Domain-knowledge explanations lacking supporting telemetry.
- **`VALIDATED`:** Causal mechanism demonstrated through controlled variable manipulation.

### 4.2 Independence Flaw in `VALIDATED` Rule
- Current Rule 1 in `PerformanceFinding` (lines 54–60):
  ```python
  if self.classification == EvidenceClassification.VALIDATED:
      if len(self.supporting_experiment_ids) < 2:
          raise ValueError(...)
  ```
- **Defect:** The rule merely checks `len(supporting_experiment_ids) >= 2`.
- Two replications of the exact same configuration (e.g. `exp_sf2_c8_rep0` and `exp_sf2_c8_rep1`) pass this check! Replications do not constitute a controlled experiment.
- Furthermore, two experiments could differ across multiple confounding variables (e.g. Concurrency=16 on 1 vCPU vs Concurrency=4 on 2 vCPU), confounding the causal attribution.
- **Proposed Requirement for `VALIDATED`:**
  A finding claiming `VALIDATED` must explicitly specify:
  1. `control_experiment_id`: Reference to baseline condition.
  2. `treatment_experiment_id`: Reference to manipulated condition.
  3. `manipulated_variable`: The single independent variable varied (e.g. `cpu_quota`, `shared_buffers`).
  4. Identical baseline state across both experiments (same dataset scale, workload, and hardware limits).

---

## Review 5: PostgreSQL Permissions & Engine Views

**Inspected Module:** [`aads/benchmark/postgres_instrumentation.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/postgres_instrumentation.py)

### 5.1 Query Audit & Required Engine Settings

| View / Function | Monitored Columns | PG 16 Compatibility | Required Role / Settings | Defect / Risk |
| :--- | :--- | :--- | :--- | :--- |
| `pg_stat_wal` | `wal_records, wal_fpi, wal_bytes, wal_write, wal_sync, wal_write_time, wal_sync_time` | Compatible (PG 14+) | Superuser or `pg_read_all_stats`. **Requires `track_wal_io_timing = on`** | In vanilla PG 16, `track_wal_io_timing` is **off** by default. `wal_write_time` and `wal_sync_time` will silently return `0.0`. |
| `pg_stat_checkpointer` | `num_timed, num_requested, write_time, sync_time, buffers_written` | Native in PG 16 | Superuser or `pg_read_all_stats`. | Cleanly separated from bgwriter. Fallback for older PG is implemented. |
| `pg_stat_bgwriter` | `buffers_clean, maxwritten_clean, buffers_alloc` | Compatible | Superuser or `pg_read_all_stats`. | Standard view across all versions. |
| `pg_stat_database` | `xact_commit, xact_rollback, blks_read, blks_hit, tup_*, conflicts, deadlocks` | Compatible | Superuser or `pg_read_all_stats`. | Fully compatible. |
| `pg_stat_user_tables` | `relname, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup, ...` | Compatible | Superuser or `pg_read_all_stats`. | Fully compatible. |
| `pg_stat_io` | `sum(reads), sum(writes), sum(fsyncs)` | Native in PG 16 | Superuser or `pg_read_all_stats`. **Requires `track_io_timing = on`** | If `track_io_timing` is off, counts are available but I/O service times are unpopulated. |
| `pg_stat_activity` | `pid, state, wait_event_type, wait_event` | Compatible | Superuser or `pg_read_all_stats`. | Non-superusers cannot see other sessions' query text. (Our runner uses `postgres`). |
| `pg_locks` | `locktype, mode, granted, count(*)` | Compatible | Superuser or `pg_read_all_stats`. | Fully compatible. |

### 5.2 Missing Metrics Representation
- `PostgresMetricsCollector` gracefully marks unavailable views in `unavailable_metrics`.
- However, if `track_wal_io_timing` is off, `wal_sync_time` returns `0.0` from PostgreSQL, which `PostgresMetricsCollector` records as valid `0.0` instead of detecting that the timing subsystem was disabled.

---

## Review 6: Monitoring Overhead Analysis

### 6.1 Quantitative Overhead Estimates

| Instrumentation Component | Mechanism | Frequency | CPU Overhead | Memory / I/O Overhead | Risk / Contention Severity |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CFS Resource Monitor** | Reads `/sys/fs/cgroup/cpu.stat` from host kernfs | 10–20 ms ($50\text{–}100\text{ Hz}$) | $< 0.3\%$ of 1 host core | Negligible ($< 10\text{ KB}$ buffer, zero disk I/O) | **LOW:** Runs entirely outside container namespace in kernel memory. |
| **Storage Monitor** | Reads cgroup `io.stat` & host `/proc/diskstats` | 2 snapshots per trial (boundary only) | $0.0\%$ during benchmark | Negligible | **ZERO:** Does not run during active measurement. |
| **Database Fingerprinting** | `SELECT count(*)` on accounts, branches, tellers | 2 queries per trial (boundary only) | $0.0\%$ during benchmark | Negligible | **ZERO:** Does not run during active measurement. |
| **Postgres Periodic Sampler** | `docker exec psql` executing lock/activity query | 100 ms ($10\text{ Hz}$) | **$3\%\text{–}8\%$ of container vCPU** | Spawns 10 OS processes/sec; 10 backend connections/sec | **HIGH:** Can induce CPU jitter and lock contention on 1.0 vCPU container. |

### 6.2 The `PostgresPeriodicSampler` Contention Risk
`PostgresPeriodicSampler` uses `_execute_sql(container, query)`, which executes:
```bash
docker exec <container> psql -U postgres -d aadsbench -t -A -F "|" -c "<query>"
```
At $100\text{ms}$ interval:
1. Spawns 10 `docker exec` processes per second on the host.
2. Spawns 10 `psql` client processes per second inside the container.
3. Establishes and tears down 10 PostgreSQL backend connections per second.
4. On a single-vCPU container (`--cpus=1.0`), this constant process creation competes with `pgbench` client worker threads for CPU time and kernel process scheduler slices.

### 6.3 Pilot Protocol to Measure Monitoring Overhead
Before running production campaigns, execute a **2x2 Factorial Overhead Pilot**:
- **Workload:** `read_only_select` and `balanced_oltp_tpcb` at Concurrency = 8, SF = 2, 30 seconds.
- **Conditions:**
  1. **Condition 0 (Uninstrumented Baseline):** Pure `pgbench`, zero background monitors.
  2. **Condition 1 (CFS Monitor Only):** 10ms `ContainerResourceMonitor` active.
  3. **Condition 2 (Postgres Sampler Only):** 100ms `PostgresPeriodicSampler` active.
  4. **Condition 3 (Full Instrumentation):** Both CFS monitor and Postgres sampler active.
- **Evaluation Metric:** Measure throughput degradation ($\Delta \text{TPS}$) and latency inflation ($\Delta \text{p95}$). If Condition 3 degrades throughput by $>2.0\%$, the Postgres sampler interval should be backed off to $500\text{ms}$ or refactored into a persistent backend query session.

---

## Confirmed Defects, Risks, and Recommendations Table

| Area | Defect / Vulnerability | Severity | Impact | Recommended Fix |
| :--- | :--- | :--- | :--- | :--- |
| **Storage Monitor** | `take_snapshot()` in `docker_runner.py` omits `cg_dir` | **HIGH** | Container cgroup I/O counters (`wbytes`, `rbytes`) are permanently empty (`{}`) in live runs. | Pass `self.resolve_cgroup_dir()` from the resource monitor into `StorageMonitor.take_snapshot(cg_dir)`. |
| **Storage Monitor** | 50% device busy time threshold treats all disks as single-queue HDDs | **MEDIUM** | Misclassifies uncongested multi-queue NVMe SSDs as storage-bound. | Incorporate average queue depth ($\Delta \text{weighted\_io\_ms} / \Delta t$) and service latency (`await`). |
| **Postgres Sampler** | `PostgresPeriodicSampler` spawns 10 `docker exec psql` processes per second | **HIGH** | Induces process-forking jitter and connection overhead in 1.0 vCPU container. | Back off sampler interval to $500\text{ms}$, or maintain a single persistent client connection. |
| **Postgres Settings** | Vanilla PostgreSQL defaults `track_wal_io_timing` and `track_io_timing` to `off` | **MEDIUM** | WAL sync times and I/O durations report `0.0` ms despite active write workloads. | Start container with `-c track_io_timing=on -c track_wal_io_timing=on`. |
| **Trial Isolation** | `verify_baseline_state()` validates row counts only, ignoring table contents and configs | **MEDIUM** | Dirtied balances or configuration drift between trials pass baseline validation. | Implement aggregate balance and ID checksum (`sum(abalance)==0`, etc.) and config dictionary check. |
| **CFS Correlation** | `CONTROLLED_CAUSAL_EVIDENCE` is assignable on single trials via unvalidated parameter | **MEDIUM** | Risk of claiming causality without a verified control/treatment experiment pair. | Require explicit multi-experiment comparison structure before allowing causal level. |
| **Evidence Schema** | `PerformanceFinding` accepts any 2 experiment IDs for `VALIDATED` (including replications) | **HIGH** | False validation claims on un-manipulated replications. | Enforce structured `treatment_experiment_id`, `control_experiment_id`, and `manipulated_variable`. |

---

## Proposed Minimal Fixes (Pre-Pilot Hardening)

To prepare the codebase for a completely trustworthy six-trial pilot, the following minimal, targeted adjustments should be authorized:

1. **Fix `StorageMonitor` Cgroup Directory Binding:**
   In `aads/benchmark/docker_runner.py`, resolve `cg_dir = monitor.resolve_cgroup_dir()` and pass `cg_dir` to `StorageMonitor.take_snapshot(cg_dir)`.
2. **Enable PostgreSQL I/O Timing Flags:**
   In container startup commands (`docker_runner.py` and `trial_isolation.py`), add:
   `-c track_io_timing=on -c track_wal_io_timing=on`
3. **Add Aggregate Balance Checksum to Baseline Verification:**
   In `trial_isolation.py`, verify `sum(abalance) == 0`, `sum(bbalance) == 0`, `sum(tbalance) == 0`, and `n_dead_tup == 0`.
4. **Relax Periodic Postgres Sampler to 500ms or Daemonize:**
   Adjust default `pg_sample_interval` from `0.100s` to `0.500s` to eliminate process-forking overhead on 1.0 vCPU.
5. **Harden `VALIDATED` Schema:**
   Require distinct `control_experiment_id`, `treatment_experiment_id`, and `manipulated_variable` in `PerformanceFinding`.

---

## Readiness Verdict for the Six-Trial Pilot

### Verdict: **CONDITIONAL — NOT READY FOR UNATTENDED EXECUTION**

**Justification:**  
While the architectural design of Phase 4F.3 is exceptionally strong and thoroughly tested offline ($214/214$ passing tests), launching the 6-trial pilot immediately would suffer from three technical flaws:
1. Container cgroup I/O metrics would be missing due to the omitted `cg_dir` parameter.
2. WAL sync times would record zero due to unset `track_wal_io_timing`.
3. The 100ms `docker exec psql` sampler would inject unnecessary process-spawning jitter into 1.0 vCPU benchmark measurements.

**Action Plan:**
Once the operator approves the minimal set of 5 fixes described above, the codebase will be fully hardened and ready to execute the six-trial empirical pilot with complete scientific integrity.
