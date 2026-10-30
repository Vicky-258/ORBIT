# AADS Phase 4E.0 — Empirical Pilot Readiness Verification Report

**Date:** 2026-10-30  
**Baseline Commit:** [`e51ac03`](file:///home/vicky/v_drive/Codes/AADS)  
**Branch:** `feat/phase-4e0-pilot-readiness`  
**Execution Context:** Strictly offline verification; no real Docker containers executed; no models promoted; persistent evidence preserved.

---

## 1. Executive Summary & Audit Scope

Phase 4E.0 independently inspected, hardened, and verified the readiness of the AADS empirical benchmarking and calibration subsystems prior to authorizing the first real Docker-backed PostgreSQL benchmark (Phase 4E.1).

Following the hardening performed in Phase 4D.2, this phase verified the complete execution path, measurement semantics, authorization persistence across restarts, failed transaction accounting, error handling, container cleanup guarantees, and calibration safety.

All verification steps were conducted offline using simulated processes, unit mocks, and test fixtures. The existing persistent registry (`data/registry.db`) remains completely untouched.

---

## 2. Inspected and Modified Files

### Files Inspected and Hardened:
- [`aads/core/schemas.py`](file:///home/vicky/v_drive/Codes/AADS/aads/core/schemas.py):
  - Extended [`ExperimentRecord`](file:///home/vicky/v_drive/Codes/AADS/aads/core/schemas.py#L125) with structured provenance fields: `proposal_id`, `authorization_id`, `execution_id`, `execution_mode`, `benchmark_command`, `duration_seconds`, `raw_artifact_path`, `status`, and `error_message`.
- [`aads/registry/component_registry.py`](file:///home/vicky/v_drive/Codes/AADS/aads/registry/component_registry.py):
  - Updated `_row_to_experiment` to parse `raw_json` payload, ensuring all extended provenance fields survive serialization and deserialization across database connections.
  - Implemented persistent authorization methods: `save_authorization`, `get_authorization`, and `list_authorizations`.
  - Added support for `Union[Path, str]` in registry initialization.
- [`aads/benchmark/docker_runner.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/docker_runner.py):
  - Updated `_benchmark_postgres` to track failed transaction counts (`total_failed_tx`) across trials and record them in `ExperimentRecord.error_count`.
  - Populated all provenance fields on produced records (`execution_mode="docker"`, `benchmark_command`, `duration_seconds`, `raw_artifact_path`).
  - Guaranteed container cleanup in `finally` blocks upon success, failure, and timeout.
- [`aads/benchmark/bounded_executor.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/bounded_executor.py):
  - Hardened single-use authorization lifecycle to check both in-memory cache and persisted registry status.
  - Stamped authorization lineage (`proposal_id`, `authorization_id`, `execution_id`, `execution_mode`) onto saved experiment records.
  - Added `"postgresql_db"` to `ALLOWED_COMPONENTS`.
- [`aads/modeling/model_trainer.py`](file:///home/vicky/v_drive/Codes/AADS/aads/modeling/model_trainer.py):
  - Updated `train_and_validate` to stamp `source_experiment_ids`, `train_experiment_ids`, and `test_experiment_ids` in evaluation metrics.
  - Updated `ModelRecord.provenance` to explicitly reference source experiment IDs and state that validation is strictly interpolative within $[c_{\min}, c_{\max}]$.
  - Updated `ModelRecord.known_limitations` to explicitly warn that extrapolation beyond verified bounds is unvalidated.
- [`aads/modeling/calibration_pipeline.py`](file:///home/vicky/v_drive/Codes/AADS/aads/modeling/calibration_pipeline.py):
  - Verified fail-closed behavior: preserves prior active models upon insufficient evidence, insufficient independent groups, or failed quality validation gates.
- [`tests/test_phase_4e0_readiness.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4e0_readiness.py):
  - Created 8 dedicated readiness verification tests covering end-to-end execution, authorization lifecycle, container cleanup, parsing edge cases, and calibration safety.

---

## 3. Test Suite Verification Results

Full offline verification was executed across the entire repository:

```
============================= test session starts ==============================
platform linux -- Python 3.12.12, pytest-9.1.1, pluggy-1.7.0
rootdir: /mnt/v_drive/Codes/AADS
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.0, langsmith-0.14.12
collected 170 items

tests/test_agent_evaluation.py .................                         [ 10%]
tests/test_agent_investigation.py ..................                     [ 20%]
tests/test_agent_workflow.py ...........                                 [ 27%]
tests/test_benchmarks.py ...                                             [ 28%]
tests/test_candidate_generator.py .....                                  [ 31%]
tests/test_empirical_validation.py ...........                           [ 38%]
tests/test_end_to_end.py ..                                              [ 39%]
tests/test_evaluation.py ...                                             [ 41%]
tests/test_live_llm_verification.py ........                             [ 45%]
tests/test_modeling.py ...                                               [ 47%]
tests/test_phase_4c1_audit.py ............                               [ 54%]
tests/test_phase_4c2_live_evaluation.py ........                         [ 59%]
tests/test_phase_4d1_audit.py ..........                                 [ 65%]
tests/test_phase_4d2_hardening.py ...................                    [ 76%]
tests/test_phase_4d_active_experimentation.py .........                  [ 81%]
tests/test_phase_4e0_readiness.py ........                               [ 86%]
tests/test_recommendation_synthesis.py ........                          [ 91%]
tests/test_registry.py ....                                              [ 93%]
tests/test_schemas.py ....                                               [ 95%]
tests/test_scientific_validation.py ....                                 [ 98%]
tests/test_simulation.py ...                                             [100%]

============================= 170 passed in 18.36s =============================
```

### Dedicated Phase 4E.0 Readiness Tests:
1. `test_authorization_persistence_across_simulated_restart`: **PASSED**
   - Validates that consuming an authorization persists `AuthorizationStatus.EXHAUSTED` to SQLite.
   - Re-instantiating `BoundedBenchmarkExecutor` with a cold in-memory cache against the database correctly detects the exhausted state and rejects replay attempts with `AUTHORIZATION_EXHAUSTED`.
2. `test_atomic_authorization_consumption_single_use`: **PASSED**
   - Validates that an authorization can only be executed once within the same process session.
3. `test_docker_readiness_failure_triggers_cleanup`: **PASSED**
   - Simulates container startup where `pg_isready` times out or fails; verifies that the runner fails closed with `RuntimeError` and immediately executes `docker rm -f <container_name>`, preventing leaked containers.
4. `test_docker_benchmark_timeout_and_container_cleanup`: **PASSED**
   - Simulates execution timeout during `pgbench` measurement; verifies that container removal is performed in the `finally` block and `BoundedBenchmarkExecutor` records `status="TIMED_OUT"` with 0 records.
5. `test_pgbench_output_parser_transaction_log_validation`: **PASSED**
   - Validates that empty logs or logs with $<10$ samples raise descriptive `ValueError`s; validates that valid logs correctly compute empirical p50, p95, and p99 percentiles in milliseconds.
6. `test_experiment_record_failed_transaction_accounting`: **PASSED**
   - Validates that failed transactions parsed from `pgbench` summary are recorded into `ExperimentRecord.error_count`.
7. `test_model_provenance_and_extrapolation_warnings`: **PASSED**
   - Validates that trained models record all source experiment IDs and clearly document their interpolation-only validity envelope.
8. `test_calibration_failure_preserves_active_model`: **PASSED**
   - Validates that on insufficient observations ($<3$), insufficient independent groups ($<3$), or validation quality gate failures, the pre-existing active model in the registry remains untouched.

---

## 4. Verified Behaviors

### 4.1. PostgreSQL Benchmark Lifecycle
The full benchmark sequence in [`DockerBenchmarkRunner._benchmark_postgres`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/docker_runner.py#L251) was inspected:
1. **Container Creation:** Starts an isolated container with explicit resource limits (`--cpus <cpu_limit> --memory <mem_limit>`) using `postgres:16-alpine`.
2. **Readiness Check:** Polls `pg_isready -U postgres` up to 20 times (with 0.5s intervals) and fails closed if readiness is not achieved within the window.
3. **Dataset Initialization:** Executes `pgbench -i -s 2 -U postgres aadsbench` (approx. 200,000 rows, ~30 MB).
4. **Warm-up Execution:** Runs a separate, unlogged warm-up run (`pgbench -T 2 -c 2 -U postgres aadsbench`). Warm-up transactions do not pollute the measurement log.
5. **Measurement Trials:** Executes `pgbench -c <conc> -j <threads> -T 3 -S -l --log-prefix=/tmp/pglog_<conc>_<rep>` for each concurrency level and replication.
6. **Log Retrieval & Parsing:** Extracts transaction logs inside the container via `cat /tmp/pglog_<conc>_<rep>.*`, computes empirical percentiles (p50, p95, p99), and extracts summary TPS and failed transaction counts.
7. **Container Cleanup:** Enforces `docker rm -f <container_name>` in a `finally` block guaranteed to execute upon success, exception, or timeout.

### 4.2. Measurement Semantics & Log Format
- **Raw Log Structure:** Each line contains `client_id transaction_no time_in_us file_no [epoch_sec epoch_usec [schedule_lag]]`.
- **Latency Field:** Field index 2 (`time_in_us`) represents transaction latency in microseconds.
- **Unit Conversion:** Explicitly converted to milliseconds via `time_us / 1000.0`.
- **Quantile Computation:** Tail latencies (p50, p95, p99) are computed via numpy linear quantile interpolation (`np.percentile(latencies_ms, [50, 95, 99], method="linear")`) directly from raw transaction records.
- **Sample Count Validation:** Rejects logs with fewer than 10 valid transaction samples.
- **Failed Transaction Accounting:** Parsed from `number of failed transactions: <N>` and mapped to `ExperimentRecord.error_count`.

### 4.3. Authorization Lifecycle
- Authorizations are tied to a specific proposal ID (`authorization.proposal_id == proposal.proposal_id`).
- When consumed, the status transitions to `EXHAUSTED` and is persisted to SQLite via `ComponentRegistry.save_authorization()`.
- On cold executor restarts, any replay attempt queries the persistent SQLite database, finds `status == EXHAUSTED`, and aborts execution with `AUTHORIZATION_EXHAUSTED`.

### 4.4. Model Calibration & Safety Envelope
- **Group-Based Split:** Splits data by independent configuration `(concurrency, round(read_ratio, 2))` rather than individual replications.
- **Boundary-Point Policy:** Retains boundary configurations ($c_{\min}$ and $c_{\max}$) in the training set and evaluates held-out predictions strictly on intermediate configurations ($c \in (c_{\min}, c_{\max})$) to test true interpolation.
- **Extrapolation Policy:** Models are stamped with `min_supported_concurrency`, `max_supported_concurrency`, `min_supported_rps`, and `max_supported_rps`. Requests outside this envelope are rejected with `OUT_OF_RANGE`.
- **Fail-Closed Promotion:** If calibration fails quality gates (RMSE, MAE, R2, MAPE) or encounters insufficient groups, the prior active model in the registry is preserved without modification.

---

## 5. Unverified Behaviors (Host & Real Environment Dependencies)

Because Phase 4E.0 was strictly restricted to offline verification, the following host-level behaviors remain unverified until the authorized Phase 4E.1 pilot run:

1. **Host Docker Daemon Socket Access:** Whether the host user has read/write permissions for `/var/run/docker.sock` without requiring `sudo` (i.e. user in `docker` group).
2. **Local Image Availability:** Whether `postgres:16-alpine` is pre-pulled or must be pulled on demand over the network.
3. **Host Storage & I/O Contention:** Boundedness of transaction log file generation when running longer trials ($T \ge 10\text{s}$) under high concurrency.
4. **Host CPU Allocation:** Real hardware variance and hypervisor throttling when enforcing `--cpus 1.0` or `--cpus 2.0` on the actual host machine.

---

## 6. Remaining Blockers for Empirical Benchmark Execution

Before launching Phase 4E.1 (the live Docker benchmark pilot), the following external operational conditions must be met:
1. **Host Docker Verification:** Confirm `docker info` succeeds on the host outside the sandbox.
2. **Pre-pulled Image:** Ensure `postgres:16-alpine` is pulled (`docker pull postgres:16-alpine`) to avoid benchmark timeout during image download.
3. **Human Evaluator Authorization:** Generate an explicit, signed `AuthorizationRecord` with:
   - Target component: `postgresql_db` (or `postgres_db`)
   - Target version: `16-alpine`
   - Allowed execution mode: `docker`
   - Maximum runtime budget: 180 seconds.

---

## 7. Exact Docker and Benchmark Prerequisites

- **Host OS:** Linux (x86_64 or aarch64) with Linux kernel $\ge 5.4$.
- **Docker Engine:** Docker 20.10+ / 24.0+ with active daemon.
- **User Permissions:** Current user must be a member of the `docker` group.
- **Image:** `postgres:16-alpine` (official library image).
- **Disk Space:** At least 2.0 GB free in `/tmp` and Docker storage.
- **RAM:** At least 2.0 GB available unreserved system memory.

---

## 8. Recommended PostgreSQL Pilot Benchmark Configuration

For the initial Phase 4E.1 empirical pilot, the following controlled matrix is recommended:

| Parameter | Recommended Pilot Value | Rationale |
| :--- | :--- | :--- |
| **Component Name** | `postgresql_db` | Primary relational store component |
| **Version** | `16-alpine` | Official lightweight PostgreSQL 16 image |
| **CPU Limit** | `1.0` (1 vCPU core) | Prevents host core starvation; establishes clear baseline |
| **Memory Limit** | `1024m` (1 GB) | Ample headroom for scale factor 2 buffer pool |
| **Dataset Scale Factor** | `2` (~200,000 rows) | Quick initialization (~2-3s) while fitting memory |
| **Concurrency Levels** | `[1, 4, 8, 16]` | Spans low, medium, and saturation regimes |
| **Read Ratio** | `1.0` (select-only) | Matches standard query profile without table bloat |
| **Warm-up Duration** | `2s` (`-c 2`) | Warms shared buffers; excluded from logs |
| **Trial Duration** | `5s` per concurrency level | Sufficient sample count ($>500$ tx) with low overhead |
| **Replications** | `3` per concurrency level | Enables empirical sample variance calculation |
| **Total Test Duration** | $\approx 60\text{s}$ | Well within the 180s bounded timeout envelope |

---

## 9. Explicit Confirmation

1. **NO real Docker benchmarks were executed during this phase.**
2. **NO real Docker containers were launched or created.**
3. **NO model was promoted in `data/registry.db`.**
4. **NO existing empirical evidence or registry tables were modified.**
5. **The system is confirmed READY for the Phase 4E.1 empirical pilot.**
