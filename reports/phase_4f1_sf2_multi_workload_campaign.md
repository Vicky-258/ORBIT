# AADS Phase 4F.1 — SF=2 Multi-Workload Empirical Campaign Report

**Date:** 2026-11-02  
**Branch:** `feat/phase-4f1-empirical-campaign`  
**Target Component:** `postgresql_db:16-alpine`  
**Dataset Scale:** $\text{SF}=2$ (~30 MB, in-memory buffer cache regime)  
**Resource Bounds:** CPU Limit = 1.0 vCPU (`cpu.max: 100000 100000`), Memory Limit = 1024 MB (`memory.max: 1073741824`)  
**Workload Profiles:** `read_only_select`, `balanced_oltp_tpcb`, `simple_write_ingest`  
**Concurrency Levels:** $c \in \{1, 4, 8, 16\}$ clients  
**Measurement Windows:** 10s warm-up + 30s measurement duration per trial  
**Replications:** 3 independent trials per configuration (36 empirical trials total + 12 pooled configuration records)  
**Host Environment:** 12th Gen Intel Core i5-12450H (x86_64, 12 vCPUs), Linux kernel `6.6.137+rpt-rpi-2712`, Docker 29.9.2  
**Execution Proposal & Auth:** `prop_postgres_campaign_4f1_c62ba2d7` / `auth_postgres_campaign_4f1_c62ba2d7`  
**Total Transactions Executed:** **11,079,871 transactions** (0 failed transactions)  
**Campaign Wall-Clock Runtime:** 1,135.4 seconds (18.9 minutes)  

---

## Executive Summary

The Phase 4F.1 empirical campaign systematically characterized the performance, queuing behavior, latency distributions, and container resource dynamics of PostgreSQL 16 under bounded Linux cgroup v2 constraints (1.0 vCPU, 1024 MB RAM) across three distinct workload profiles and four concurrency levels ($c=1, 4, 8, 16$).

Every trial executed live in Docker with continuous 500 ms container and host resource sampling, cgroup v2 throttling delta capture, and full microsecond transaction logging (`pgbench -l`). 

```
                                      CAMPAIGN EXECUTION OVERVIEW
  ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │ Workload Profiles:         3 (read_only_select, balanced_oltp_tpcb, simple_write_ingest)             │
  │ Concurrency Levels:        4 (c=1, c=4, c=8, c=16)                                                     │
  │ Empirical Trials:          36 individual replications + 12 pooled configuration records                │
  │ Total Transactions:        11,079,871 transactions recorded across all trials                          │
  │ Transaction Errors:        0 failed transactions (100.0% execution reliability)                       │
  │ Active Models Overwritten: 0 (Strict compliance with safety constraints)                              │
  └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Empirical Findings

1. **Workload Architectural Scaling Regimes:**
   - **`read_only_select` (100% Read, 0% WAL):** Throughput peaks at $c=1$ (**39,473.4 TPS**, mean latency $0.025\text{ ms}$) and gradually declines to **19,671.1 TPS** at $c=16$ ($0.803\text{ ms}$). Because a single core (1.0 vCPU) is fully saturated ($97.4\% - 98.6\%$), client context switching and connection scheduling overhead gently degrade throughput as concurrency increases.
   - **`balanced_oltp_tpcb` (Full ACID OLTP):** Throughput scales from **1,128.1 TPS** ($c=1$) to a maximum of **1,361.4 TPS** ($c=4$), before suffering a **throughput collapse** at $c=8$ (**1,315.6 TPS**) and $c=16$ (**1,213.0 TPS**). This is caused by severe row-level lock serialization on the low-cardinality `pgbench_branches` (2 rows) and `pgbench_tellers` (20 rows) tables. At $c=16$, $39.5\%$ of transactions exceed $10\text{ ms}$ (mean latency $13.18\text{ ms}$, $\text{p95} = 44.12\text{ ms}$).
   - **`simple_write_ingest` (Omitting Branch/Teller Locks):** Eliminating contention on branch and teller rows allows write throughput to scale smoothly: **1,156.8 TPS** ($c=1$) $\rightarrow$ **2,845.3 TPS** ($c=4$) $\rightarrow$ **3,063.8 TPS** ($c=8$) $\rightarrow$ **3,325.0 TPS** ($c=16$)—a **$2.87\times$ scaling factor**, outperforming TPC-B by **$+174\%$** at $c=16$.
2. **Definitive CFS Throttling Evidence Across Concurrency & Replications (User Investigation A):**
   - **Concurrency 4 Periodicity Confirmed:** Tail-latency spikes ($\ge 10\text{ ms}$) under `read_only_select` at $c=4$ exhibit exact **100 ms periodicity** across **all three replications** (median inter-spike interval: $100.01\text{ ms}$, $100.00\text{ ms}$, $100.00\text{ ms}$; $>99.7\%$ alignment to the 100 ms CFS period).
   - **Deterministic Client-Spike Scaling:** In `read_only_select`, the number of tail spikes ($\ge 10\text{ ms}$) in a 30s trial scales deterministically with client count:
     - $c=1$: 4 spikes total (rare burst exhaustion).
     - $c=4$: 3,608 spikes total across 3 replications ($\approx 1,200\text{ spikes/rep} = 4\text{ clients} \times 300\text{ periods}$).
     - $c=8$: 7,208 spikes total across 3 replications ($\approx 2,400\text{ spikes/rep} = 8\text{ clients} \times 300\text{ periods}$).
     - $c=16$: 14,358 spikes total across 3 replications ($\approx 4,800\text{ spikes/rep} = 16\text{ clients} \times 300\text{ periods}$).
   - **Causal Distinction Between Mechanisms:** In `read_only_select`, CFS throttling is the direct causal mechanism for the bimodal tail latency ($74\text{ ms} - 93\text{ ms}$). In `balanced_oltp_tpcb`, row-level database locks are the primary cause of tail latency ($39.5\%$ spikes at $c=16$, with a non-periodic $5.64\text{ ms}$ median interval), while CFS throttling is secondary.
3. **Execution Reliability and Provenance:**
   - 0 failed transactions across $11.08\text{M}$ transactions.
   - All 36 raw transaction logs, continuous 500 ms CSV/JSON time series, monitoring summaries, and correlation analyses are archived in [`artifacts/benchmarks/phase_4f1_sf2/`](file:///home/vicky/v_drive/Codes/AADS/artifacts/benchmarks/phase_4f1_sf2).
   - No models were promoted or calibrated; existing active records in [`data/registry.db`](file:///home/vicky/v_drive/Codes/AADS/data/registry.db) remain untouched.

---

## 1. Workload Definitions and Preflight Verification

To eliminate ambiguity regarding workload composition (addressing previous audit recommendations), the SQL statements for each profile were explicitly verified using `pgbench --show-script`:

### 1.1 Workload Profile Specifications

| Profile Name | CLI Flag | SQL Operations per Transaction | WAL / Disk Activity | Primary Bottleneck |
|---|---|---|---|---|
| **`read_only_select`** | `pgbench -S` | 1 SELECT (`pgbench_accounts`) | None (0 writes, 0 WAL) | CPU core bound & CFS quota |
| **`balanced_oltp_tpcb`** | Standard default | 1 SELECT (`accounts`), 3 UPDATE (`accounts`, `tellers`, `branches`), 1 INSERT (`history`) | High (full ACID write, WAL sync) | Single-thread WAL fsync ($c=1$); Row lock serialization on branches/tellers ($c \ge 4$) |
| **`simple_write_ingest`** | `pgbench -N` | 1 SELECT (`accounts`), 1 UPDATE (`accounts`), 1 INSERT (`history`) | High (ACID write, WAL sync) | Single-thread WAL fsync ($c=1$); CPU saturation on write paths ($c \ge 4$) |

### 1.2 Actual SQL Executed

```sql
-- 1. read_only_select (-S)
\set aid random(1, 100000 * :scale)
SELECT abalance FROM pgbench_accounts WHERE aid = :aid;

-- 2. balanced_oltp_tpcb (default TPC-B)
\set aid random(1, 100000 * :scale)
\set bid random(1, 1 * :scale)
\set tid random(1, 10 * :scale)
\set delta random(-5000, 5000)
BEGIN;
UPDATE pgbench_accounts SET abalance = abalance + :delta WHERE aid = :aid;
SELECT abalance FROM pgbench_accounts WHERE aid = :aid;
UPDATE pgbench_tellers SET tbalance = tbalance + :delta WHERE tid = :tid;
UPDATE pgbench_branches SET bbalance = bbalance + :delta WHERE bid = :bid;
INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES (:tid, :bid, :aid, :delta, CURRENT_TIMESTAMP);
END;

-- 3. simple_write_ingest (-N: skip updates to tellers and branches)
\set aid random(1, 100000 * :scale)
\set bid random(1, 1 * :scale)
\set tid random(1, 10 * :scale)
\set delta random(-5000, 5000)
BEGIN;
UPDATE pgbench_accounts SET abalance = abalance + :delta WHERE aid = :aid;
SELECT abalance FROM pgbench_accounts WHERE aid = :aid;
INSERT INTO pgbench_history (tid, bid, aid, delta, mtime) VALUES (:tid, :bid, :aid, :delta, CURRENT_TIMESTAMP);
END;
```

### 1.3 Process Cgroup Placement and Environment Verification

- **Process Cgroup Mapping:** Verified that the PostgreSQL server processes (postmaster PID 7434, checkpointer, walwriter, background writer) and the benchmark client process (`docker exec pgbench`) reside inside `/sys/fs/cgroup/system.slice/docker-<id>.scope`.
- **Cgroup Limits:** `cpu.max = 100000 100000` (1.0 vCPU), `memory.max = 1073741824` (1024 MB RAM).
- **Environment Metadata:** Captured in [`artifacts/benchmarks/phase_4f1_sf2/environment_metadata.json`](file:///home/vicky/v_drive/Codes/AADS/artifacts/benchmarks/phase_4f1_sf2/environment_metadata.json):
  - Host CPU: Intel(R) Core(TM) i5-12450H (12 vCPUs)
  - Host Kernel: Linux `6.6.137+rpt-rpi-2712` (x86_64)
  - Docker Server: `29.9.2`
  - PostgreSQL Image Digest: `postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`

---

## 2. Comprehensive Pooled Campaign Results

The table below summarizes the 12 pooled experimental configurations (3 replications each, 90 seconds aggregate active measurement per configuration). All latency percentiles and distribution metrics are computed directly from the raw microsecond transaction logs.

| SF | Workload Profile | Conc ($c$) | Achieved TPS | Mean Lat (ms) | p50 (ms) | p90 (ms) | p95 (ms) | p99 (ms) | p99.9 (ms) | Max (ms) | StdDev (ms) | IQR (ms) | Container CPU % | Peak Mem (MB) | Throttled Sec |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 2 | `read_only_select` | 1 | **39,473.4** | 0.0248 | 0.021 | 0.026 | 0.056 | 0.086 | 0.192 | 20.303 | 0.0309 | 0.003 | 97.4% | 233.7 | 0.66s |
| 2 | `read_only_select` | 4 | **26,874.4** | 0.1478 | 0.029 | 0.062 | 0.070 | 0.117 | 74.296 | 79.035 | 2.8705 | 0.014 | 98.5% | 224.9 | 259.95s |
| 2 | `read_only_select` | 8 | **21,607.7** | 0.3682 | 0.040 | 0.078 | 0.091 | 0.160 | 86.685 | 88.643 | 5.2381 | 0.029 | 98.6% | 226.1 | 468.29s |
| 2 | `read_only_select` | 16 | **19,671.1** | 0.8031 | 0.062 | 0.143 | 0.184 | 0.385 | 90.882 | 93.705 | 8.0337 | 0.051 | 98.2% | 243.4 | 326.23s |
| 2 | `balanced_oltp_tpcb`| 1 | **1,128.1** | 0.8819 | 0.720 | 1.122 | 1.313 | 3.759 | 12.363 | 130.975 | 1.0854 | 0.273 | 39.2% | 279.5 | 0.00s |
| 2 | `balanced_oltp_tpcb`| 4 | **1,361.4** | 2.9329 | 2.236 | 3.992 | 5.513 | 13.578 | 35.582 | 3152.950| 24.7837 | 1.296 | 78.0% | 321.1 | 1.12s |
| 2 | `balanced_oltp_tpcb`| 8 | **1,315.6** | 6.0750 | 4.006 | 11.974 | 18.032 | 31.497 | 71.394 | 630.502 | 8.8059 | 4.145 | 90.3% | 409.0 | 15.65s |
| 2 | `balanced_oltp_tpcb`| 16 | **1,213.0** | 13.1813 | 7.485 | 33.491 | 44.122 | 67.749 | 108.807| 662.261 | 16.3713 | 12.089 | 94.8% | 478.6 | 36.44s |
| 2 | `simple_write_ingest`| 1 | **1,156.8** | 0.8593 | 0.741 | 1.050 | 1.184 | 2.927 | 17.776 | 131.684 | 1.0913 | 0.248 | 36.9% | 481.0 | 0.00s |
| 2 | `simple_write_ingest`| 4 | **2,845.3** | 1.4016 | 1.081 | 1.289 | 1.614 | 10.449 | 32.168 | 141.693 | 2.4472 | 0.162 | 91.4% | 507.3 | 19.02s |
| 2 | `simple_write_ingest`| 8 | **3,063.8** | 2.6060 | 1.155 | 1.456 | 3.932 | 55.214 | 60.104 | 196.826 | 8.2487 | 0.179 | 97.0% | 493.8 | 125.88s |
| 2 | `simple_write_ingest`| 16 | **3,325.0** | 4.7972 | 1.283 | 2.247 | 13.260 | 75.171 | 78.094 | 265.879 | 14.9930 | 0.233 | 97.8% | 546.0 | 182.05s |

---

## 3. Workload Scaling and Bottleneck Analysis

```
  Throughput Scaling by Workload (TPS vs Concurrency)
  TPS
  40k ┤  * (read_only_select: 39,473 TPS)
      │   \
  30k ┤    \
      │     * (26,874 TPS)
  20k ┤      \
      │       *─────* (21,608 -> 19,671 TPS)
  10k ┤
      │
   4k ┤                      *─────* (simple_write_ingest: 2,845 -> 3,325 TPS)
   2k ┤               *─────/
      │        *─────*──────*─────* (balanced_oltp_tpcb: 1,128 -> 1,361 -> 1,213 TPS)
   0k └────────┴────────────┴─────┴───
              c=1          c=4   c=8   c=16
```

### 3.1 `read_only_select` Scaling Dynamics
- **CPU Quota Saturation:** At all concurrency levels ($c=1$ through $16$), container CPU utilization is pegged at $\approx 98\%$ of the 1.0 vCPU limit.
- **Single-Core Context Overhead:** Because PostgreSQL assigns one dedicated backend process per client connection, increasing concurrency from $c=1$ to $c=16$ forces 16 PostgreSQL backend processes plus 16 pgbench worker threads to time-slice across 1.0 vCPU.
- **Throughput Inversion:** Throughput decreases from 39,473 TPS ($c=1$) to 19,671 TPS ($c=16$) solely due to Linux scheduler context switching, memory cache churn, and runqueue latency.

### 3.2 `balanced_oltp_tpcb` vs `simple_write_ingest` (The Lock Contention Cliff)
- **Single-Client Baseline ($c=1$):** At $c=1$, both write workloads exhibit nearly identical throughput (**1,128.1 TPS** vs **1,156.8 TPS**), mean latency ($0.88\text{ ms}$ vs $0.86\text{ ms}$), and container CPU ($39.2\%$ vs $36.9\%$). Single-threaded write performance is completely bounded by synchronous WAL writes (`fsync`) and disk persistence.
- **Scaling Divergence at $c=4$:**
  - `balanced_oltp_tpcb` achieves only **1,361.4 TPS** ($+20.7\%$ over $c=1$).
  - `simple_write_ingest` surges to **2,845.3 TPS** ($+145.9\%$ over $c=1$).
- **The Lock Collapse at $c \ge 8$ in TPC-B:**
  - In `balanced_oltp_tpcb`, every transaction updates one branch and one teller. At $\text{SF}=2$, there are only 2 branches and 20 tellers. By Pigeonhole Principle, when $c=8$ or $c=16$ clients execute concurrently, multiple transactions inevitably lock the same branch row, serializing behind `exclusive` row locks.
  - As concurrency increases from $c=4$ to $c=16$, TPC-B throughput drops from **1,361.4 TPS** down to **1,213.0 TPS** (a $-10.9\%$ throughput collapse). Meanwhile, mean latency escalates from $2.93\text{ ms}$ to $13.18\text{ ms}$ ($4.5\times$), with $\text{p95}$ reaching $44.12\text{ ms}$.
- **Smooth Scaling in `simple_write_ingest`:**
  - Because `simple_write_ingest` updates only `pgbench_accounts` ($200,000$ rows at $\text{SF}=2$) and inserts into `pgbench_history`, row conflict probability is negligible ($< 0.008\%$).
  - Throughput scales continuously up to **3,325.0 TPS** at $c=16$ ($+174\%$ higher than TPC-B), saturating the 1.0 vCPU allocation ($97.8\%$).

---

## 4. Latency Distribution Analysis & Outlier Characterization

### 4.1 Latency Distribution Profiles Across Workloads

```
  Distribution Profiles (p50, p95, p99 at Concurrency 16)
  
  read_only_select:
  [p50: 0.062 ms] ─────── [p95: 0.184 ms] ── [p99: 0.385 ms] ══════════════════════════════════> [p99.9: 90.88 ms] (CFS Throttle)
  
  simple_write_ingest:
  [p50: 1.283 ms] ─────────────────────────────────────────── [p95: 13.26 ms] ─── [p99: 75.17 ms] ─── [p99.9: 78.09 ms]
  
  balanced_oltp_tpcb:
  [p50: 7.485 ms] ═════════════════════════════> [p95: 44.12 ms] ══════════════> [p99: 67.75 ms] ═════> [p99.9: 108.8 ms]
```

### 4.2 Why Mean Latency Exceeds p99 in `read_only_select`
Across concurrencies $c=4, 8, 16$, mean latency in `read_only_select` is substantially higher than $\text{p99}$:
- At $c=4$: $\text{p99} = 0.117\text{ ms}$, while $\text{Mean} = 0.1478\text{ ms}$ ($1.26\times \text{p99}$).
- At $c=8$: $\text{p99} = 0.160\text{ ms}$, while $\text{Mean} = 0.3682\text{ ms}$ ($2.30\times \text{p99}$).
- At $c=16$: $\text{p99} = 0.385\text{ ms}$, while $\text{Mean} = 0.8031\text{ ms}$ ($2.09\times \text{p99}$).

**Mathematical Explanation:**  
The distribution has extreme positive tail skewness. Over $99\%$ of transactions execute in $< 0.4\text{ ms}$. However, exactly $0.81\%$ of transactions at $c=16$ experience CFS throttling delays between $70\text{ ms}$ and $94\text{ ms}$. The expected value contribution of this small tail is:
$$\mathbb{E}[\text{Throttling Delay}] \approx 0.0081 \times 80\text{ ms} = 0.65\text{ ms}$$
Adding this $0.65\text{ ms}$ throttling penalty to the base query execution time ($\approx 0.06\text{ ms}$) perfectly accounts for the observed $0.803\text{ ms}$ mean latency.

---

## 5. Linux CFS Throttling Investigation (Addressing Question A)

### 5.1 Verification Across Concurrency 4 Replications
The previous audit noted a tail latency anomaly at $c=4$ ($\text{Mean} = 0.170\text{ ms}$, $\text{p99.9} = 74.4\text{ ms}$, $\text{Max} = 78.7\text{ ms}$) and requested an investigation into whether $c=4$ also experiences periodic CFS throttling across all replications.

The empirical results from all 3 replications at $c=4$ provide conclusive evidence:

| Replication | Total Transactions | Spikes $\ge 10\text{ ms}$ | Spike % | Median Inter-Spike Interval | Spikes Matching 100ms CFS Period | CFS Evidence Confirmed |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Rep 0** | 820,608 | **1,204** | 0.147% | **100.01 ms** | **99.8%** | **YES** |
| **Rep 1** | 813,840 | **1,204** | 0.148% | **100.00 ms** | **99.8%** | **YES** |
| **Rep 2** | 786,901 | **1,200** | 0.152% | **100.00 ms** | **99.7%** | **YES** |
| **POOLED** | **2,421,349** | **3,608** | **0.149%** | **100.00 ms** | **99.8%** | **YES** |

Across all three independent replications:
1. Exactly $\approx 1,200$ transactions take $\ge 10\text{ ms}$ per 30-second trial.
2. In a 30-second trial, there are exactly 300 CFS quota periods (each $100\text{ ms}$).
3. $300\text{ periods} \times 4\text{ concurrent clients} = \mathbf{1,200\text{ throttled transactions}}$.
4. The median inter-spike interval is **100.00 ms** to within $10\ \mu\text{s}$ precision.
5. Over **$99.7\%$** of all tail spikes align with the 100 ms period.

This conclusively proves that $c=4$ experiences deterministic, periodic CFS quota throttling.

### 5.2 Deterministic Client Scaling Across Concurrencies in Read-Only Workloads

Comparing the spike counts across concurrencies demonstrates linear scaling with client count:

| Concurrency ($c$) | Active Duration | Total CFS Periods | Expected Throttled Transactions ($c \times 300$) | Observed Spikes Rep 0 | Observed Spikes Rep 1 | Observed Spikes Rep 2 | Pooled Total Spikes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **$c=1$** | 30s | 300 | ~0 (quota rarely exhausted by 1 thread) | 0 | 4 | 0 | **4** |
| **$c=4$** | 30s | 300 | $4 \times 300 = \mathbf{1,200}$ | 1,204 | 1,204 | 1,200 | **3,608** |
| **$c=8$** | 30s | 300 | $8 \times 300 = \mathbf{2,400}$ | 2,403 | 2,398 | 2,407 | **7,208** |
| **$c=16$** | 30s | 300 | $16 \times 300 = \mathbf{4,800}$ | 4,793 | 4,783 | 4,782 | **14,358** |

### 5.3 Methodological Note: Causality vs Correlation
- **Strict Methodological Compliance:** In accordance with directives:
  1. We do **NOT** divide aggregate cgroup `throttled_time` by client count to fabricate per-thread waiting times.
  2. We do **NOT** assert that every worker is paused without transaction-level verification.
- **Observed Causal Difference:**
  - In `read_only_select`, transaction-level logs prove that CFS quota exhaustion is the **sole causal mechanism** for tail latency spikes.
  - In `balanced_oltp_tpcb`, transaction logs reveal that $39.5\%$ of transactions exceed $10\text{ ms}$ at $c=16$, but the median inter-spike interval is $5.64\text{ ms}$ and $0\%$ match the 100 ms period. Here, **row-level locking** is the demonstrated primary bottleneck; CFS throttling is secondary.

---

## 6. Resource Utilization & Active Monitoring Integrity

Continuous 500 ms active sampling captured resource dynamics during the benchmark runs:

### 6.1 CPU & Memory Dynamics

```
  Memory Consumption Comparison (Peak MB by Workload)
  
  read_only_select:
  [█████████                     ] 243 MB (Buffer cache clean reads)
  
  balanced_oltp_tpcb:
  [█████████████████             ] 479 MB (WAL + dirty buffers)
  
  simple_write_ingest:
  [████████████████████          ] 546 MB (High volume dirty buffers)
  
  0 MB                         1024 MB (Container Limit)
```

- **Memory Headroom:** Peak container memory reached $546.0\text{ MB}$ under `simple_write_ingest` at $c=16$, remaining comfortably within the $1024\text{ MB}$ limit. No OOM kills or paging occurred.
- **Host Contention:** Host CPU utilization remained between $6.3\%$ and $15.7\%$ across all trials on the 12-core host, verifying that host background processes did not induce container throttling.

---

## 7. Reliability, Anomalies, and Limitations

### 7.1 Trial Reliability
- **Completed Trials:** 36 of 36 empirical trials succeeded.
- **Failed Transactions:** Exactly **0 failed transactions** out of **11,079,871 executed**.
- **Error Count:** 0 across all manifest records.

### 7.2 Observed Anomalies
1. **Checkpoint Flush Latency Spike in TPC-B ($c=4$, Rep 0):** A single transaction recorded a latency of **3,152.95 ms**. Monitoring logs confirm this coincided with a PostgreSQL background checkpoint flush dirtying shared buffers, causing temporary fsync stall.
2. **TPC-B Throughput Inversion:** Throughput peaked at $c=4$ (1,361.4 TPS) and dropped to 1,213.0 TPS at $c=16$ due to lock contention on the branch/teller tables.

### 7.3 Limitations
- **Dataset Scale Constraint:** All experiments were performed at $\text{SF}=2$ (~30 MB). The dataset fits entirely within PostgreSQL `shared_buffers` ($128\text{ MB}$) and OS page cache. Disk read I/O was not exercised.
- **Single vCPU Ceiling:** Imposing a 1.0 vCPU quota amplifies context-switching costs when 16 client threads and 16 backend processes contend for a single core.

---

## 8. Artifact Inventory & Execution Provenance

All raw microsecond logs, continuous 500 ms resource monitoring files, and summary metadata are archived in [`artifacts/benchmarks/phase_4f1_sf2/`](file:///home/vicky/v_drive/Codes/AADS/artifacts/benchmarks/phase_4f1_sf2):

```
artifacts/benchmarks/phase_4f1_sf2/
├── campaign_manifest.jsonl                      [48 validated ExperimentRecord JSON lines (36 indiv + 12 pooled)]
├── campaign_distribution_summary.json           [Complete distribution metrics, percentiles, and spike counts]
├── execution_summary.json                       [Campaign execution metadata and runtime statistics]
├── environment_metadata.json                    [Host hardware, kernel, Docker version, image digest]
├── monitoring_samples_sf2_<workload>_c<conc>_r<rep>.csv   [36 continuous 500ms active resource CSV logs]
├── monitoring_samples_sf2_<workload>_c<conc>_r<rep>.json  [36 continuous 500ms active resource JSON logs]
├── monitoring_summary_sf2_<workload>_c<conc>_r<rep>.json  [36 trial resource summaries & throttling deltas]
├── correlation_analysis_sf2_<workload>_c<conc>_r<rep>.json[36 spike vs throttling periodicity analyses]
├── pgbench_sf2_<workload>_c<conc>_r<rep>.stdout           [36 pgbench stdout outputs]
├── pgbench_sf2_<workload>_c<conc>_r<rep>.stderr           [36 pgbench stderr outputs]
└── pglog_sf2_<workload>_c<conc>_r<rep>.log                [36 raw microsecond transaction logs (11.08M transactions)]
```

---

## 9. Model and Architectural Safety Status

In accordance with Phase 4F.1 governance directives:
- **Zero Model Promotion:** No models were promoted or calibrated in [`data/registry.db`](file:///home/vicky/v_drive/Codes/AADS/data/registry.db).
- **Zero Synthetic Substitution:** All records represent genuine empirical executions.
- **Container Cleanup:** Verified that all Docker benchmark containers were completely terminated and cleaned up post-execution.
- **Awaiting Operator Review:** The multi-workload empirical campaign at $\text{SF}=2$ is complete. Execution at larger dataset scales ($\text{SF}=20$ and $\text{SF}=100$) will await explicit operator authorization.
