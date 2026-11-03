# Phase 4F.4.1 — Execution Engine Safety & Evidence Hardening Report

**Status:** Hardened & Offline Verified — Awaiting Operator Authorization  
**Branch:** `feat/phase-4f41-hardening`  
**Baseline Branch:** `feat/phase-4f4-execution`  
**Manifest:** [`artifacts/manifests/phase_4f4_execution_manifest.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/manifests/phase_4f4_execution_manifest.json)  
**Manifest SHA256:** `69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6`  
**Execution Engine:** [`aads/benchmark/phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py)  
**Test Suite:** [`tests/test_phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f4_runner.py)  
**Machine-Readable Summary:** [`artifacts/audits/phase_4f41_hardening_summary.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/audits/phase_4f41_hardening_summary.json)  
**Execution State:** NOT STARTED  
**Authorization State:** NOT AUTHORIZED  
**Model Promotion State:** DISABLED  
**Registry Mutation State:** DISABLED  

---

## 1. Executive Summary

Phase 4F.4.1 resolves all execution-path safety, client isolation, metric provenance, lifecycle cleanup, and evidence persistence vulnerabilities identified during the final engineering review of Phase 4F.4.

The frozen 12-trial empirical campaign manifest, workload configurations, CPU limits (1.0 vs 2.0 vCPU), memory limit (1024 MB), client concurrency (8 clients, 2 threads), and randomized execution schedule (seed 4104) remain strictly preserved.

All verification was conducted completely offline using unit tests, mocks, and controlled fixtures. **No live Docker benchmark containers were launched, no databases were initialized, and no models were calibrated or promoted in `data/registry.db`.**

All 238 repository unit and integration tests pass cleanly, including 21 dedicated tests in [`tests/test_phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f4_runner.py) covering all 17 specified failure and edge-case scenarios.

---

## 2. Corrective Engineering Implementation

### FIX 01 — Strong Authorization Binding

**Defect Addressed:** Previous implementation used a simple boolean parameter (`authorized=True`) in `execute_campaign()`, which could be invoked without cryptographically verifiable binding to the manifest, proposal, operator, or execution scope.

**Implementation Details:**
- Defined [`CampaignAuthorizationRecord`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L90-L150) enforcing:
  - `phase == "4F.4"`
  - `execution_scope == "PHASE_4F4_12_TRIAL_EMPIRICAL_CAMPAIGN"`
  - `manifest_sha256 == "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"`
  - Valid `proposal_id`, `authorization_id`, `operator_identity`, and `authorized_at_utc`
  - Expiration check against current UTC time
  - Revocation check (`revoked == False`)
  - Single-use lifecycle tracking (`consumed == False`)
- Removed `authorized: bool` argument entirely from [`Phase4F4Runner.execute_campaign()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L860-L920). Boolean inputs (`True` or `False`) are rejected fail-closed with `RuntimeError`.
- Atomic consumption: When executed, the authorization is atomically marked `consumed=True` with `consumed_at_utc` and `consumed_by_execution_id`, and persisted to `consumed_authorization.json`.

**Verification:**
- `test_01_missing_authorization_rejection`: Rejects `None` and boolean bypass.
- `test_02_wrong_manifest_hash_rejection`: Rejects mismatched manifest hash.
- `test_03_wrong_proposal_id_rejection`: Rejects mismatched proposal ID.
- `test_04_reused_authorization_rejection`: Rejects already consumed authorization record.

---

### FIX 02 — Actual Benchmark Client Isolation

**Defect Addressed:** Relying on the host-side presence of `/usr/bin/pgbench` did not prove that the benchmark process was actually executing outside the PostgreSQL container's cgroup slice at runtime.

**Implementation Details:**
- Implemented [`Phase4F4Runner.verify_benchmark_process_isolation()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L225-L290).
- When launching the measured benchmark, the process is initiated via `subprocess.Popen`.
- Before benchmark execution proceeds:
  1. Reads `/proc/<client_pid>/cgroup` directly from the OS.
  2. Resolves client unified cgroup path against the container cgroup directory (`cg_dir`).
  3. Verifies client cgroup path is not identical to or a descendant of `cg_dir`.
  4. Inspects container `cgroup.procs` to ensure `client_pid` is not placed inside container cgroup.
  5. If any isolation check fails, `proc.kill()` is immediately executed and `RuntimeError` is raised.
  6. On success, persists full isolation metadata to `trial_art_dir / "client_isolation.json"`.

**Verification:**
- `test_05_client_cgroup_isolation_failure`: Rejects clients within identical cgroups and clients listed in container `cgroup.procs`.

---

### FIX 03 — Strict Metric Provenance & Transaction Reconciliation

**Defect Addressed:** Fallback formulas (`p90 = p95 * 0.95`, `p99.9 = p99`, `max = p99`, `std = 0`, `failed_transactions = 0`) fabricated metric values when pgbench summaries or log parsers lacked explicit measurements.

**Implementation Details:**
- Updated [`PgbenchOutputParser.parse_summary()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/docker_runner.py#L73-L90):
  - Missing `number of failed transactions:` sets `failed_transactions: None` with `failed_transactions_status: "UNAVAILABLE"` and explicit reason.
- Updated [`Phase4F4Runner.execute_single_trial()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L740-L800):
  - Completely removed all fallback multiplier formulas.
  - Generates comprehensive `metric_provenance` dictionary documenting source (`raw_transaction_logs` vs `pgbench_summary_stdout`), formula/method (`linear` quantiles, `numpy.max`, `numpy.std`), and availability status.
  - If any required metric (`tps`, `total_transactions`, `failed_transactions`, `latency_avg_ms`, `p50_ms`, `p90_ms`, `p95_ms`, `p99_ms`, `p999_ms`, `max_ms`, `std_ms`) is `None`, the trial is marked `FAILED` with an explicit missing metric error.
  - Added transaction count reconciliation: validates that raw transaction log sample count (`sample_count`) equals benchmark reported total transactions (`total_transactions`). Any unaccounted mismatch fails the trial.

**Verification:**
- `test_09_missing_percentiles_metrics_handling`: Verifies missing percentiles fail trial validation without fallback substitution.
- `test_10_missing_failed_transaction_count_handling`: Verifies missing failed transaction line sets `UNAVAILABLE`.
- `test_11_incomplete_transaction_logs_reconciliation_failure`: Verifies raw log count mismatch (e.g., 1500 vs 2000) fails trial validation.

---

### FIX 04 — Effective Resource and Image Verification

**Defect Addressed:** Container limits declared at launch (`--cpus`, `-m`) could differ from effective cgroup v2 limits due to Docker daemon configuration or platform constraints.

**Implementation Details:**
- Implemented [`Phase4F4Runner.verify_container_effective_resources()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L295-L385).
- Before warm-up, queries the running container via `docker inspect` and cgroup v2 filesystem:
  1. **Image Digest:** Verifies `RepoDigests` contains `self.pinned_digest` (`sha256:cf78e766...`).
  2. **Effective CPU Quota:** Reads `cg_dir / "cpu.max"`, verifies quota equals `expected_cpu_limit * period` (100,000 usec for 1.0 vCPU; 200,000 usec for 2.0 vCPU).
  3. **Effective Memory Limit:** Reads `cg_dir / "memory.max"`, verifies bytes equal expected (1,073,741,824 bytes for 1024m).
  4. **Cgroup Path:** Confirms directory exists and is accessible.
  5. **Process Placement:** Reads `cg_dir / "cgroup.procs"`, verifies PostgreSQL main PID is present.
- Any mismatch raises `RuntimeError` before warm-up begins, triggering cleanup and aborting the trial.

**Verification:**
- `test_06_cpu_quota_mismatch_abort`: Rejects mismatched `cpu.max` before warm-up.
- `test_07_memory_limit_mismatch_abort`: Rejects mismatched `memory.max` before warm-up.
- `test_08_image_digest_mismatch_abort`: Rejects mismatched image digest before warm-up.

---

### FIX 05 — Complete Lifecycle Cleanup

**Defect Addressed:** Exceptions during intermediate stages (warm-up, benchmark timeout, log parsing) could leave background monitor threads, psql coprocess sessions, or Docker containers orphaned.

**Implementation Details:**
- Structured [`Phase4F4Runner.execute_single_trial()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L520-L860) with comprehensive `try ... except ... finally` blocks.
- Tracks `container_started`, `monitor_started`, `sampler_started`, and `current_stage`.
- The `finally` block executes independent cleanup steps:
  1. Stops `PostgresPeriodicSampler` if active. Errors are captured in `cleanup_errors`.
  2. Stops `ContainerResourceMonitor` if active. Errors are captured in `cleanup_errors`.
  3. Executes `TrialIsolationManager.cleanup_container()` via `docker rm -f`. Errors are captured in `cleanup_errors`.
- Preserves the primary exception (`trial_exc`) so failures are never masked by secondary cleanup issues.

**Verification:**
- `test_12_warmup_failure_lifecycle_cleanup`: Verifies warm-up error cleans up monitors, samplers, and container.
- `test_13_benchmark_timeout_lifecycle_cleanup`: Verifies benchmark timeout kills client and cleans up all components.
- `test_14_sampler_failure_lifecycle_cleanup`: Verifies sampler failure does not prevent container cleanup.
- `test_15_monitor_shutdown_failure_lifecycle_cleanup`: Verifies monitor shutdown error does not block container cleanup.
- `test_16_container_cleanup_failure_handling`: Verifies container cleanup failure is recorded in `cleanup_errors` without masking the primary exception.

---

### FIX 06 — Durable Failure Evidence

**Defect Addressed:** Previous implementation did not preserve intermediate diagnostic artifacts or execution progress when a trial failed midway through execution.

**Implementation Details:**
- Assigned explicit terminal statuses to every trial: `SUCCESS`, `FAILED`, `ABORTED`, or `INCOMPLETE`.
  - Aborted before measurement (e.g. resource or isolation failure) -> `ABORTED`.
  - Failed during benchmark or parsing -> `FAILED`.
  - Failed during initialization -> `INCOMPLETE`.
- On failure, writes `trial_failure.json` and `trial_summary.json` containing:
  - Sequence, trial ID, execution ID, workload profile, CPU quota, replication
  - Terminal status and failure stage
  - Exception class and message
  - Returncode, stdout, and stderr
  - Available raw transaction logs
  - Cleanup results and error log
  - Artifact directory path and timestamp
- Implemented [`Phase4F4Runner._persist_campaign_state()`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py#L390-L420): writes `campaign_state_partial.json` after every single trial, maintaining clear counts for completed, failed, aborted, incomplete, and never-started trials.

**Verification:**
- `test_17_failure_artifact_persistence`: Verifies `trial_failure.json` and partial state persistence.

---

### FIX 07 — Strict Campaign Completion Validation

**Defect Addressed:** Generating summary comparisons or reporting success on partial or failed runs could introduce flawed evidence into downstream modeling.

**Implementation Details:**
- Implemented strict completion gates in `execute_campaign()`:
  1. Exactly 12 scheduled trials executed.
  2. Exactly 12 trials have terminal status `SUCCESS`.
  3. Exactly 3 successful replications exist for each of the 4 conditions: `ro_1cpu`, `ro_2cpu`, `tpcb_1cpu`, `tpcb_2cpu`.
  4. All required raw transaction logs and metrics are present and valid.
  5. All trials report `cleanup_result["success"] == True`.
- If any condition is violated:
  - Manifest status is marked `FAILED` (or `INCOMPLETE`).
  - Condition summaries and comparison deltas are set to `None` (preventing misleading partial comparisons).
  - Persists partial `campaign_summary.json` with `completion_issues` listed.
  - Raises `RuntimeError` fail-closed.

**Verification:**
- `test_mock_campaign_execution`: Verifies successful campaign completion only when all 12 trials pass with complete provenance.

---

## 3. Comprehensive Test Results

The test suite was executed offline against the complete codebase:

```bash
.venv/bin/pytest tests/test_phase_4f4_runner.py
============================== 21 passed in 0.14s ==============================

.venv/bin/pytest tests/
============================= 238 passed in 18.11s =============================
```

### Regression Test Matrix (FIX 08)

| Test Identifier | Fix Addressed | Scenario Tested | Result |
| :--- | :--- | :--- | :---: |
| `test_01_missing_authorization_rejection` | FIX 01 | Missing or boolean-only authorization | **PASS** |
| `test_02_wrong_manifest_hash_rejection` | FIX 01 | Hash mismatch against frozen manifest | **PASS** |
| `test_03_wrong_proposal_id_rejection` | FIX 01 | Proposal ID binding mismatch | **PASS** |
| `test_04_reused_authorization_rejection` | FIX 01 | Replay attack on consumed authorization | **PASS** |
| `test_05_client_cgroup_isolation_failure` | FIX 02 | Client PID placed inside container cgroup | **PASS** |
| `test_06_cpu_quota_mismatch_abort` | FIX 04 | Cgroup v2 `cpu.max` mismatch before warm-up | **PASS** |
| `test_07_memory_limit_mismatch_abort` | FIX 04 | Cgroup v2 `memory.max` mismatch before warm-up | **PASS** |
| `test_08_image_digest_mismatch_abort` | FIX 04 | Container image digest mismatch before warm-up | **PASS** |
| `test_09_missing_percentiles_metrics_handling` | FIX 03 | Missing tail latency percentiles without fallback | **PASS** |
| `test_10_missing_failed_transaction_count_handling` | FIX 03 | Missing failed transaction reporting | **PASS** |
| `test_11_incomplete_transaction_logs_reconciliation_failure` | FIX 03 | Raw log samples vs reported tx count mismatch | **PASS** |
| `test_12_warmup_failure_lifecycle_cleanup` | FIX 05 | Teardown on warm-up process failure | **PASS** |
| `test_13_benchmark_timeout_lifecycle_cleanup` | FIX 05 | Process kill & teardown on benchmark timeout | **PASS** |
| `test_14_sampler_failure_lifecycle_cleanup` | FIX 05 | Container teardown despite sampler error | **PASS** |
| `test_15_monitor_shutdown_failure_lifecycle_cleanup` | FIX 05 | Container teardown despite monitor error | **PASS** |
| `test_16_container_cleanup_failure_handling` | FIX 05 | Cleanup error logging without masking trial error | **PASS** |
| `test_17_failure_artifact_persistence` | FIX 06 | Diagnostic `trial_failure.json` persistence | **PASS** |

---

## 4. State Invariants & Execution Posture

All safety invariants remain fully preserved:

1. **Manifest Preserved:** [`artifacts/manifests/phase_4f4_execution_manifest.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/manifests/phase_4f4_execution_manifest.json) remains byte-identical with SHA256 `69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6`.
2. **Authorization State:** `NOT_AUTHORIZED`.
3. **Execution State:** `NOT_STARTED`.
4. **Model Promotion State:** `DISABLED`.
5. **Registry Mutation State:** `DISABLED`. All 24 models in `data/registry.db` are unmodified.
6. **No Live Execution:** No Docker containers have been launched or databases initialized during this hardening phase.

---

## 5. Conclusion & Operator Authorization Gate

The execution engine is fully hardened, strictly typed, fail-closed, and verified across all lifecycle failure modes.

The system is now completely prepared for live execution when the operator provides an authorized `CampaignAuthorizationRecord`. Execution cannot proceed until that record is submitted.
