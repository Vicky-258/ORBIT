# Phase 4F.4 — Final 12-Trial Execution Readiness Report

**Status:** Prepared & Preflight Verified — Awaiting Operator Authorization  
**Branch:** `feat/phase-4f4-execution`  
**Manifest:** [`artifacts/manifests/phase_4f4_execution_manifest.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/manifests/phase_4f4_execution_manifest.json)  
**Execution Engine:** [`aads/benchmark/phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/aads/benchmark/phase_4f4_runner.py)  
**Unit & Mock Tests:** [`tests/test_phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f4_runner.py)  
**Execution State:** NOT STARTED  
**Authorization State:** NOT AUTHORIZED  
**Model Promotion State:** DISABLED  
**Registry Mutation State:** DISABLED  

---

## 1. Executive Summary

The Phase 4F.4 execution manifest and dedicated execution engine have been prepared, hardened, and verified offline. The execution framework enforces all experimental isolation invariants, PostgreSQL timing flags, deterministic content fingerprint verification, host-side client placement, and strict fail-closed safety guardrails.

All 222 tests in the repository test suite pass cleanly, confirming zero regressions across historical audits, modeling, simulation, and benchmark infrastructure.

Per strict operating instructions, **no live benchmarks have been launched**. Execution is frozen and awaiting explicit operator authorization.

---

## 2. Preflight & Environment Verification

Preflight checks were executed to verify all required dependencies, pinned digests, and client placement requirements on the target host:

| Prerequisite | Required Specification | Verified State | Status |
| :--- | :--- | :--- | :--- |
| **Docker Daemon** | Active local Docker engine | Docker Server `29.9.2` accessible | **PASS** |
| **Pinned Image** | `postgres:16-alpine` | Digest `sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685` verified | **PASS** |
| **Client Placement** | Host-side `pgbench` outside container cgroup | `/usr/bin/pgbench` (`pgbench (PostgreSQL) 18.6`) verified on host | **PASS** |
| **Host Architecture** | x86_64 Linux | `x86_64`, Kernel `6.18.59-1-lts` | **PASS** |
| **Host CPU Model** | Documented model | `12th Gen Intel(R) Core(TM) i5-12450H` | **PASS** |
| **Port Binding** | Loopback published port (`127.0.0.1::5432`) | Ephemeral host port mapping implemented | **PASS** |
| **Timing Flags** | `track_io_timing=on`, `track_wal_io_timing=on` | Enabled in container startup & verified via `SHOW` | **PASS** |
| **Baseline Fingerprint** | `aads_composite_aggregate_sha256_v1` | Verified in baseline check | **PASS** |

---

## 3. Frozen 12-Trial Execution Matrix

Deterministic randomized schedule generated with seed `4104`:

| Seq | Trial ID | Workload Profile | CPU Limit | Memory Limit | Clients / Threads | Duration (Warm/Meas) | Rep |
|---:|:---|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | `ro_2cpu_r1` | `read_only_select` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 1 |
| 2 | `ro_1cpu_r1` | `read_only_select` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 1 |
| 3 | `tpcb_2cpu_r1` | `balanced_oltp_tpcb` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 1 |
| 4 | `ro_2cpu_r2` | `read_only_select` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 2 |
| 5 | `tpcb_2cpu_r2` | `balanced_oltp_tpcb` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 2 |
| 6 | `tpcb_1cpu_r1` | `balanced_oltp_tpcb` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 1 |
| 7 | `ro_2cpu_r3` | `read_only_select` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 3 |
| 8 | `ro_1cpu_r3` | `read_only_select` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 3 |
| 9 | `tpcb_1cpu_r3` | `balanced_oltp_tpcb` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 3 |
| 10 | `tpcb_1cpu_r2` | `balanced_oltp_tpcb` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 2 |
| 11 | `ro_1cpu_r2` | `read_only_select` | 1.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 2 |
| 12 | `tpcb_2cpu_r3` | `balanced_oltp_tpcb` | 2.0 vCPU | 1024 MB | 8 / 2 | 10s / 30s | 3 |

---

## 4. Client Isolation & Architecture

```
+-------------------------------------------------------------------------------+
| HOST OPERATING SYSTEM (Linux x86_64, unconstrained user cgroup)              |
|                                                                               |
|   +-----------------------------------------------------------------------+   |
|   | Host-Side Benchmark Client (/usr/bin/pgbench)                         |   |
|   | - 8 client connections, 2 threads (-c 8 -j 2)                         |   |
|   | - Writes raw transaction logs directly to host trial artifact dir     |   |
|   | - Target: postgresql://postgres@127.0.0.1:<host_port>/aadsbench       |   |
|   +-----------------------------------------------------------------------+   |
|                                      | TCP (127.0.0.1)                        |
|                                      v                                        |
|   +-----------------------------------------------------------------------+   |
|   | Docker Container (aads-p4f4-...)                                      |   |
|   | - Isolated Cgroup v2 (cpu.max = 100000 or 200000; memory.max = 1024M)|   |
|   | - PostgreSQL 16 (track_io_timing=on, track_wal_io_timing=on)          |   |
|   | - Newly initialized SF2 dataset (200k accounts, 0 history rows)       |   |
|   | - Persistent coprocess psql sampler (100ms lock/wait monitoring)      |   |
|   | - Guaranteed container removal on completion/failure                  |   |
|   +-----------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------+
```

---

## 5. Offline Verification Suite

The runner implementation was tested with complete mock coverage in [`tests/test_phase_4f4_runner.py`](file:///home/vicky/v_drive/Codes/AADS/tests/test_phase_4f4_runner.py):
- `test_frozen_schedule_integrity`: Validates exact 12-trial sequence and metadata.
- `test_authorization_guardrail`: Validates `execute_campaign()` raises `RuntimeError` without explicit authorization.
- `test_prerequisite_verification_with_mocks`: Validates Docker, digest, and host-side `pgbench` detection.
- `test_client_isolation_enforcement`: Validates fail-closed stop if host-side `pgbench` is missing.
- `test_mock_campaign_execution`: Validates complete mock lifecycle across all 12 trials, host command formatting, artifact persistence, and condition comparisons.

Full repository test results: **222 passed in 19.74s**.

---

## 6. Authorization Request

The Phase 4F.4 empirical campaign is fully prepared and validated offline.

To authorize execution of the 12-trial campaign, the operator must provide explicit approval.
No benchmark container will be launched without this explicit confirmation.
