# AADS Phase 4F.1 — Controlled CPU-Quota Experiment Report (1.0 vs 2.0 vCPU)

**Date:** 2026-11-02  
**Branch:** `feat/phase-4f1-empirical-campaign`  
**Target Component:** `postgresql_db:16-alpine`  
**Dataset Scale:** $\text{SF}=2$ (~30 MB, in-memory buffer cache regime)  
**Workload Profile:** `read_only_select` (`pgbench -S`, 100% read, 0% write, 0 WAL)  
**Concurrency Level:** $c = 8$ clients  
**Measurement Windows:** 10 seconds warm-up + 30 seconds active measurement  
**Replications:** 3 independent trials per configuration (6 empirical trials total)  
**Host Environment:** Linux (kernel `6.6.137+rpt-rpi-2712`, unified cgroup v2, systemd driver)  

---

## Executive Summary

Before launching the wider 36-trial $\text{SF}=2$ empirical campaign, a controlled experiment was executed comparing PostgreSQL 16 under two CPU quota allocations: **1.0 vCPU** (`cpu.max: 100000 100000`) and **2.0 vCPU** (`cpu.max: 200000 100000`), bounded by a 1024 MB memory limit.

### Key Empirical Findings
1. **Linear Throughput Scaling:** Doubling the CPU quota from 1.0 to 2.0 vCPU produced an almost exact $2\times$ linear increase in throughput, rising from **22,199.3 TPS** to **44,772.9 TPS** (**$+101.7\%$ throughput scaling**).
2. **Mean Latency Halving via Little's Law:** Mean latency was reduced by half, dropping from **0.3585 ms** to **0.1770 ms** ($0.494\times$). At $c=8$, empirical mean latency matches theoretical queuing delay ($W = L / \lambda = 8 / \text{TPS}$) to within $0.9\%$.
3. **Invariant Base Query Execution Time:** Unthrottled median transaction service time ($\text{p50}$) was identical across both configurations: **0.038 ms** (1.0 vCPU) vs. **0.039 ms** (2.0 vCPU), proving that single-query CPU execution efficiency is unaffected by quota scaling.
4. **CFS Throttling Saturation Dynamics:**
   - Both configurations experienced active CFS throttling in **100% of CFS periods** (**10.00 throttling events/sec**).
   - Under 2.0 vCPU, 8 concurrent pgbench workers still exhaust the $200,000\ \mu\text{s}$ quota in the first $\approx 25\text{ ms}$ of each 100 ms period ($200\text{ ms} / 8 = 25\text{ ms}$), leaving threads throttled for the remaining $\approx 75\text{ ms}$.
   - The total number of tail latency spikes ($\ge 10\text{ ms}$) remained constant at $\approx 7,200$ spikes across 3 trials ($\approx 2,400$ per replication), but because 2.0 vCPU processed twice as many total transactions ($4.03\text{M}$ vs $2.00\text{M}$), the **spike proportion halved from 0.361% to 0.179%**.
5. **Verified Process Cgroup Placement:** Host inspection confirmed that all PostgreSQL server processes (postmaster, checkpointer, background writer, walwriter, autovacuum launcher, logical replication launcher) and the `docker exec` pgbench client processes reside in the **exact same cgroup v2 slice** (`/system.slice/docker-<id>.scope`) and share the container's CPU quota.
6. **Zero Failures & Zero Model Overwrites:** Across all **6,034,780 transactions executed**, **0 failed transactions** occurred. No active models were promoted or modified in [`data/registry.db`](file:///home/vicky/v_drive/Codes/AADS/data/registry.db).

---

## 1. Process Cgroup Placement Verification

Process placement was verified using host `/proc/<pid>/cgroup` traversal, `docker top`, and container introspection before benchmark execution.

### 1.1 Placement Evidence (Host & Container)
- **Cgroup Hierarchy:** Unified cgroup v2 (`/sys/fs/cgroup/system.slice/`)
- **Container Cgroup Slices:**
  - 1.0 vCPU: `/sys/fs/cgroup/system.slice/docker-31f797f4a6c491e0e98ccb6b32cf1d7c48a6dcf6f8463ce16cdbba0bc9cf4308.scope`
  - 2.0 vCPU: `/sys/fs/cgroup/system.slice/docker-a0859cdc2f59c76b1e2f50cd313a74c45058a6c529e5ecec86ecdf1daa5f0dd1.scope`
- **Quota Bounds in `cpu.max`:**
  - 1.0 vCPU: `100000 100000` (quota: $100,000\ \mu\text{s}$, period: $100,000\ \mu\text{s} = 1.0\text{ core}$)
  - 2.0 vCPU: `200000 100000` (quota: $200,000\ \mu\text{s}$, period: $100,000\ \mu\text{s} = 2.0\text{ cores}$)
- **Memory Bound in `memory.max`:** `1073741824` ($1024\text{ MB}$) for both configurations.

### 1.2 Process Inventory & Shared Quota Confirmation
All container processes were confirmed to reside within the container's designated cgroup slice:

| Process | Host Command | Host Cgroup v2 Scope | Shared Quota |
|---|---|---|---|
| **Postmaster** | `postgres` (PID 7434 / 8774) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **Checkpointer** | `postgres: checkpointer` (PID 7650 / 8785) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **Background Writer** | `postgres: background writer` (PID 7651 / 8786) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **WAL Writer** | `postgres: walwriter` (PID 7653 / 8788) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **Autovacuum Launcher** | `postgres: autovacuum launcher` (PID 7654 / 8789) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **Logical Rep Launcher** | `postgres: logical replication launcher` (PID 7655 / 8790) | `0::/system.slice/docker-<id>.scope` | **YES** |
| **Benchmark Client** | `docker exec ... pgbench` | `0::/system.slice/docker-<id>.scope` | **YES** |

> [!NOTE]
> **Process Co-location Implication:**  
> Because both the `pgbench` client process and the PostgreSQL backend worker processes run inside the same cgroup scope, both client socket serialization and server query execution consume CPU cycles from the same 1.0 or 2.0 vCPU CFS quota. This mirrors realistic collocated application architectures.

---

## 2. Head-to-Head Comparative Metrics

The table below contrasts aggregate empirical measurements across all 6 trials (3 replications $\times$ 30s each):

| Metric | 1.0 vCPU | 2.0 vCPU | Absolute Delta ($\Delta$) | Relative Change |
|---|---|---|---|---|
| **Pooled Throughput (TPS)** | **22,199.3** | **44,772.9** | $+22,573.6\text{ TPS}$ | **$+101.7\%$** ($2.017\times$) |
| **Mean Latency (ms)** | **0.3585** | **0.1770** | $-0.1815\text{ ms}$ | **$-50.6\%$** ($0.494\times$) |
| **Median Latency p50 (ms)** | **0.0380** | **0.0390** | $+0.0010\text{ ms}$ | $+2.6\%$ (invariant) |
| **Tail Latency p90 (ms)** | **0.0760** | **0.0710** | $-0.0050\text{ ms}$ | $-6.6\%$ |
| **Tail Latency p95 (ms)** | **0.0890** | **0.0810** | $-0.0080\text{ ms}$ | $-9.0\%$ |
| **Tail Latency p99 (ms)** | **0.1850** | **0.1350** | $-0.0500\text{ ms}$ | **$-27.0\%$** |
| **Tail Latency p99.9 (ms)** | **86.7590** | **72.8550** | $-13.9040\text{ ms}$ | **$-16.0\%$** |
| **Maximum Latency (ms)** | **89.3310** | **78.5460** | $-10.7850\text{ ms}$ | $-12.1\%$ |
| **Latency Std Dev ($\sigma$)** | **5.1577 ms** | **3.0701 ms** | $-2.0876\text{ ms}$ | **$-40.5\%$** |
| **Interquartile Range IQR (ms)**| **0.0280** | **0.0270** | $-0.0010\text{ ms}$ | $-3.6\%$ |
| **Spikes $\ge 10\text{ ms}$ (Count)** | **7,218** | **7,203** | $-15$ | $-0.2\%$ |
| **Spikes $\ge 10\text{ ms}$ (%)** | **0.361%** | **0.179%** | $-0.182\text{ percentage pts}$ | **$-50.4\%$** |
| **Active Container CPU %** | **98.5%** | **197.2%** | $+98.7\%$ | Saturated (1.0 vs 2.0 core) |
| **Active Host CPU %** | **11.5%** | **21.5%** | $+10.0\%$ | Headroom available |
| **Peak Container Memory (MB)** | **182.7 MB** | **202.3 MB** | $+19.6\text{ MB}$ | Well below 1024 MB limit |
| **Total Throttling Events** | **904** | **903** | $-1$ | Identical event count |
| **Throttling Rate (/sec)** | **10.00 /s** | **10.00 /s** | $0.00$ | 100% of periods throttled |
| **Throttled Wait / Thread** | **18.559 s** | **18.169 s** | $-0.390\text{ s}$ | $-2.1\%$ |
| **Failed Transactions** | **0** | **0** | $0$ | 100% reliability |
| **Total Transactions Executed**| **2,001,364** | **4,033,416** | $+2,032,052$ | **$+101.5\%$** ($2.015\times$) |

---

## 3. Replication Breakdown

### 3.1 1.0 vCPU Replications (`cpu.max: 100000 100000`)

| Rep | Transactions | TPS | Avg Lat (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Active CPU % | Mem (MB) | Throttled Sec |
|---|---|---|---|---|---|---|---|---|---|
| **Rep 1** | 674,727 | 22,442.0 | 0.356 | 0.038 | 0.087 | 0.181 | 98.2% | 180.3 | 152.97s |
| **Rep 2** | 657,186 | 21,861.8 | 0.365 | 0.039 | 0.094 | 0.204 | 98.6% | 182.1 | 142.28s |
| **Rep 3** | 669,451 | 22,294.1 | 0.358 | 0.038 | 0.088 | 0.171 | 98.6% | 182.7 | 150.17s |
| **POOLED** | **2,001,364** | **22,199.3** | **0.3585** | **0.038** | **0.089** | **0.185** | **98.5%** | **182.7** | **445.41s** |

### 3.2 2.0 vCPU Replications (`cpu.max: 200000 100000`)

| Rep | Transactions | TPS | Avg Lat (ms) | p50 (ms) | p95 (ms) | p99 (ms) | Active CPU % | Mem (MB) | Throttled Sec |
|---|---|---|---|---|---|---|---|---|---|
| **Rep 1** | 1,359,356 | 45,271.2 | 0.176 | 0.039 | 0.080 | 0.141 | 197.2% | 201.7 | 147.36s |
| **Rep 2** | 1,335,744 | 44,484.8 | 0.179 | 0.040 | 0.083 | 0.142 | 197.2% | 202.3 | 142.34s |
| **Rep 3** | 1,338,316 | 44,562.8 | 0.179 | 0.040 | 0.080 | 0.123 | 197.2% | 202.2 | 146.36s |
| **POOLED** | **4,033,416** | **44,772.9** | **0.1770** | **0.039** | **0.081** | **0.135** | **197.2%** | **202.3** | **436.06s** |

---

## 4. Latency Distribution Analysis & Outlier Characterization

### 4.1 Bimodal Latency Distribution
Both configurations exhibit a distinctly bimodal latency distribution caused by Linux CFS quota scheduling:

```
Fast In-Memory Path (~99.6% of queries)          CFS Throttled Path (~0.2% - 0.4% of queries)
[0.02 ms - 0.15 ms]                             [70.0 ms - 89.3 ms]
        |                                                |
        v                                                v
Active execution in CPU core                    Worker thread paused awaiting 100ms quota reset
p50 = 0.038 ms / p95 = 0.089 ms (1.0 vCPU)      p99.9 = 86.76 ms (1.0 vCPU)
p50 = 0.039 ms / p95 = 0.081 ms (2.0 vCPU)      p99.9 = 72.86 ms (2.0 vCPU)
```

### 4.2 Why Mean Latency is Higher than p99
In both configurations:
- Under 1.0 vCPU: $\text{p99} = 0.185\text{ ms}$, while $\text{Mean} = 0.3585\text{ ms}$ ($1.94\times \text{p99}$).
- Under 2.0 vCPU: $\text{p99} = 0.135\text{ ms}$, while $\text{Mean} = 0.1770\text{ ms}$ ($1.31\times \text{p99}$).

**Mathematical Explanation:**  
The distribution has extreme positive skewness ($\sigma = 5.16\text{ ms}$ in 1.0 vCPU; $\sigma = 3.07\text{ ms}$ in 2.0 vCPU). While 99% of transactions complete in $< 0.185\text{ ms}$, the top 0.36% of transactions experience descheduling delays between $70\text{ ms}$ and $89\text{ ms}$.
$$\text{Expected Value Contribution} \approx 0.0036 \times 75\text{ ms} = 0.27\text{ ms}$$
This $0.27\text{ ms}$ throttling contribution accounts for the gap between the $\approx 0.04\text{ ms}$ unthrottled execution latency and the observed $0.36\text{ ms}$ mean latency.

### 4.3 Why Spike Count is Identical but Spike Percentage Halves
Across the 3 replications (90 seconds total active runtime):
- 1.0 vCPU: exactly **7,218 spikes** $\ge 10\text{ ms}$.
- 2.0 vCPU: exactly **7,203 spikes** $\ge 10\text{ ms}$.

Because pgbench ran with $c=8$ concurrent client connections, whenever a quota period boundary is reached and the container is throttled, all 8 worker threads pause. When the 100 ms period renews, the 8 threads resume and complete their paused transactions simultaneously.
- 90 seconds active execution contains 900 CFS periods (100 ms each).
- $900\text{ periods} \times 8\text{ clients} = 7,200\text{ throttled transactions}$.
This matches the observed spike counts (**7,218** and **7,203**) with $> 99.8\%$ accuracy.

Because 2.0 vCPU processed **$4,033,416$ transactions** compared to **$2,001,364$ transactions** under 1.0 vCPU, the spike percentage was halved:
$$\text{Spike Rate (1.0 vCPU)} = \frac{7,218}{2,001,364} = \mathbf{0.361\%}$$
$$\text{Spike Rate (2.0 vCPU)} = \frac{7,203}{4,033,416} = \mathbf{0.179\%}$$

---

## 5. Artifact Inventory & Execution Provenance

All raw logs, monitoring samples, and summaries were saved to [`artifacts/benchmarks/phase_4f1_cpu_quota/`](file:///home/vicky/v_drive/Codes/AADS/artifacts/benchmarks/phase_4f1_cpu_quota):

```
artifacts/benchmarks/phase_4f1_cpu_quota/
├── comparison_summary.json                      [Comparative JSON artifact across both configs]
├── cpu_1.0/
│   ├── cgroup_placement_verification.json       [Process PID cgroup mapping and cpu.max=100000]
│   ├── config_summary.json                      [Aggregated 1.0 vCPU empirical statistics]
│   ├── environment_metadata.json                [Kernel, Docker digest, PG build]
│   ├── monitoring_samples_c8_r{0,1,2}.csv       [Continuous 500ms time series samples (CSV)]
│   ├── monitoring_samples_c8_r{0,1,2}.json      [Continuous 500ms time series samples (JSON)]
│   ├── monitoring_summary_c8_r{0,1,2}.json      [Trial CPU, memory, and throttling deltas]
│   ├── correlation_analysis_c8_r{0,1,2}.json    [Spike vs throttling alignment analysis]
│   ├── pgbench_c8_r{0,1,2}.stdout               [Standard pgbench summary reports]
│   ├── pgbench_c8_r{0,1,2}.stderr               [Standard vacuum logs]
│   └── pglog_c8_r{0,1,2}.log                    [2,001,364 raw microsecond transaction logs]
└── cpu_2.0/
    ├── cgroup_placement_verification.json       [Process PID cgroup mapping and cpu.max=200000]
    ├── config_summary.json                      [Aggregated 2.0 vCPU empirical statistics]
    ├── environment_metadata.json                [Kernel, Docker digest, PG build]
    ├── monitoring_samples_c8_r{0,1,2}.csv       [Continuous 500ms time series samples (CSV)]
    ├── monitoring_samples_c8_r{0,1,2}.json      [Continuous 500ms time series samples (JSON)]
    ├── monitoring_summary_c8_r{0,1,2}.json      [Trial CPU, memory, and throttling deltas]
    ├── correlation_analysis_c8_r{0,1,2}.json    [Spike vs throttling alignment analysis]
    ├── pgbench_c8_r{0,1,2}.stdout               [Standard pgbench summary reports]
    ├── pgbench_c8_r{0,1,2}.stderr               [Standard vacuum logs]
    └── pglog_c8_r{0,1,2}.log                    [4,033,416 raw microsecond transaction logs]
```

---

## 6. Model Safety Confirmation

In compliance with instructions:
- **NO models were promoted** to active status.
- **NO synthetic fixtures** were substituted for any empirical trial.
- Active baseline records in [`data/registry.db`](file:///home/vicky/v_drive/Codes/AADS/data/registry.db) remain untouched.
- Clean container cleanup was verified post-execution (0 orphaned containers).

---

## 7. Readiness for the 36-Trial SF=2 Campaign

The controlled CPU quota experiment proves that:
1. Docker container resource monitoring and cgroup v2 throttling capture operate with high reliability across varying CPU quotas.
2. The benchmark harness accurately reflects Little's Law scaling and distinguishes unthrottled query execution latency ($0.038\text{ ms}$) from periodic CFS throttling pauses.
3. The system is structurally verified and ready to proceed to the 36-trial $\text{SF}=2$ multi-workload empirical campaign upon operator review and authorization.
