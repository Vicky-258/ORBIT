"""
Phase 4F.1 — Controlled CPU-Quota Experiment Execution Script.
Compares PostgreSQL 16 under 1.0 vCPU vs 2.0 vCPU quotas (SF=2, read_only_select, c=8, 3 reps each).
Verifies process cgroup placement and captures continuous monitoring, throttling, and transaction logs.
"""
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from orbit.agent.schemas import (
    AuthorizationLevel,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
)
from orbit.benchmark.docker_runner import DockerBenchmarkRunner, PgbenchOutputParser
from orbit.benchmark.workload_profiles import resolve_workload_profile
from orbit.core.schemas import ExperimentRecord
from orbit.registry.component_registry import ComponentRegistry


def verify_cgroup_placement(container_name: str, art_dir: Path) -> Dict[str, Any]:
    """
    Verifies the Linux cgroup v2 placement of PostgreSQL processes and pgbench execution.
    Checks whether postmaster, workers, and exec processes share the container's cgroup slice.
    """
    verification: Dict[str, Any] = {
        "container_name": container_name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cgroup_version": "v2",
        "processes": [],
        "cgroup_path_host": None,
        "cpu_max": None,
        "memory_max": None,
        "placement_verified": False,
        "shared_cgroup": False,
    }

    try:
        # Get 64-char container ID
        id_res = subprocess.run(
            ["docker", "inspect", "--format", "{{.Id}}", container_name],
            capture_output=True, text=True, timeout=5,
        )
        cont_id = id_res.stdout.strip() if id_res.returncode == 0 else ""
        verification["container_id"] = cont_id

        # Determine host cgroup directory
        cgroup_scope = f"/sys/fs/cgroup/system.slice/docker-{cont_id}.scope"
        cgroup_direct = f"/sys/fs/cgroup/docker/{cont_id}"
        cgroup_dir = None
        if os.path.exists(cgroup_scope):
            cgroup_dir = cgroup_scope
        elif os.path.exists(cgroup_direct):
            cgroup_dir = cgroup_direct

        verification["cgroup_path_host"] = cgroup_dir
        if cgroup_dir:
            cpu_max_file = os.path.join(cgroup_dir, "cpu.max")
            mem_max_file = os.path.join(cgroup_dir, "memory.max")
            if os.path.exists(cpu_max_file):
                with open(cpu_max_file, "r") as f:
                    verification["cpu_max"] = f.read().strip()
            if os.path.exists(mem_max_file):
                with open(mem_max_file, "r") as f:
                    verification["memory_max"] = f.read().strip()

        # Check processes running inside container via docker top
        top_res = subprocess.run(
            ["docker", "top", container_name, "-eo", "pid,comm,args"],
            capture_output=True, text=True, timeout=5,
        )
        host_pids = []
        if top_res.returncode == 0 and top_res.stdout:
            lines = top_res.stdout.strip().splitlines()
            if len(lines) > 1:
                for line in lines[1:]:
                    parts = line.split(maxsplit=2)
                    if parts:
                        try:
                            hpid = int(parts[0])
                            comm = parts[1] if len(parts) > 1 else ""
                            args = parts[2] if len(parts) > 2 else ""
                            host_pids.append((hpid, comm, args))
                        except ValueError:
                            pass

        # For each host PID, inspect /proc/<pid>/cgroup
        all_cgroups = set()
        for hpid, comm, args in host_pids:
            cgroup_file = f"/proc/{hpid}/cgroup"
            cgroup_line = ""
            if os.path.exists(cgroup_file):
                try:
                    with open(cgroup_file, "r") as f:
                        cgroup_line = f.read().strip()
                        all_cgroups.add(cgroup_line)
                except Exception:
                    pass
            verification["processes"].append({
                "host_pid": hpid,
                "comm": comm,
                "args": args,
                "cgroup": cgroup_line,
            })

        # Check cgroup placement of docker exec process
        exec_cgroup_res = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", "cat /proc/$$/cgroup"],
            capture_output=True, text=True, timeout=5,
        )
        exec_cgroup = exec_cgroup_res.stdout.strip() if exec_cgroup_res.returncode == 0 else ""
        verification["docker_exec_cgroup"] = exec_cgroup
        if exec_cgroup:
            all_cgroups.add(exec_cgroup)

        # Inside container PID 1 cgroup
        init_cgroup_res = subprocess.run(
            ["docker", "exec", container_name, "sh", "-c", "cat /proc/1/cgroup"],
            capture_output=True, text=True, timeout=5,
        )
        init_cgroup = init_cgroup_res.stdout.strip() if init_cgroup_res.returncode == 0 else ""
        verification["container_init_cgroup"] = init_cgroup

        # Placement verification logic:
        # If all processes belong to the same scope/cgroup slice, they share CPU quota
        verification["shared_cgroup"] = (len(all_cgroups) == 1) or (
            all(cont_id in cg or cg == "0::/" for cg in all_cgroups if cg)
        )
        verification["placement_verified"] = (
            verification["shared_cgroup"]
            and cgroup_dir is not None
            and verification["cpu_max"] is not None
        )

    except Exception as exc:
        verification["error"] = str(exc)

    if art_dir:
        (art_dir / "cgroup_placement_verification.json").write_text(json.dumps(verification, indent=2))

    return verification


def compute_distribution_metrics(latencies_ms: List[float]) -> Dict[str, Any]:
    """Computes comprehensive distribution statistics on raw transaction latencies."""
    if not latencies_ms:
        return {}

    arr = np.array(latencies_ms, dtype=np.float64)
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))
    iqr = p75 - p25

    return {
        "count": int(len(arr)),
        "min_ms": round(float(np.min(arr)), 4),
        "mean_ms": round(float(np.mean(arr)), 4),
        "std_ms": round(float(np.std(arr)), 4),
        "p50_ms": round(float(np.percentile(arr, 50)), 4),
        "p90_ms": round(float(np.percentile(arr, 90)), 4),
        "p95_ms": round(float(np.percentile(arr, 95)), 4),
        "p99_ms": round(float(np.percentile(arr, 99)), 4),
        "p999_ms": round(float(np.percentile(arr, 99.9)), 4),
        "max_ms": round(float(np.max(arr)), 4),
        "iqr_ms": round(iqr, 4),
        "spikes_over_10ms_count": int(np.sum(arr >= 10.0)),
        "spikes_over_10ms_pct": round(float(np.sum(arr >= 10.0)) / len(arr) * 100.0, 3),
        "spikes_over_50ms_count": int(np.sum(arr >= 50.0)),
        "spikes_over_100ms_count": int(np.sum(arr >= 100.0)),
    }


def run_configuration(
    cpu_limit: str,
    proposal_id: str,
    auth_id: str,
    artifacts_base: Path,
    registry: ComponentRegistry,
) -> Dict[str, Any]:
    """Executes 3 replications for a single CPU quota configuration."""
    art_dir = artifacts_base / f"cpu_{cpu_limit}"
    art_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n" + "-" * 70)
    print(f"RUNNING CONFIGURATION: CPU Limit = {cpu_limit} vCPU (SF=2, c=8, 3 reps, 30s)")
    print("-" * 70)

    # Authorization
    auth = AuthorizationRecord(
        authorization_id=auth_id,
        proposal_id=proposal_id,
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="docker",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=300.0,
        token=f"token_{cpu_limit}_{uuid_suffix()}",
    )
    registry.save_authorization(auth)

    runner = DockerBenchmarkRunner(
        cpu_limit=cpu_limit,
        memory_limit="1024m",
        timeout_seconds=300,
    )

    placement_result: Dict[str, Any] = {}

    def on_ready_cb(container_name: str, out_dir: Path):
        nonlocal placement_result
        print(f"  [CGROUP CHECK] Container ready: {container_name}")
        placement_result = verify_cgroup_placement(container_name, out_dir)
        print(f"  [CGROUP CHECK] Scope: {placement_result.get('cgroup_path_host')}")
        print(f"  [CGROUP CHECK] cpu.max: {placement_result.get('cpu_max')}")
        print(f"  [CGROUP CHECK] Processes found: {len(placement_result.get('processes', []))}")
        print(f"  [CGROUP CHECK] Shared cgroup verified: {placement_result.get('shared_cgroup')}")

    checkpointed_records = []
    def checkpoint_cb(rec: ExperimentRecord):
        rec.proposal_id = proposal_id
        rec.authorization_id = auth_id
        registry.save_experiment(rec)
        checkpointed_records.append(rec)
        if rec.trial_replications == 1:
            print(
                f"  -> Rep completed: TPS={rec.achieved_rps:<8.1f} | "
                f"p50={rec.p50_ms:<5.3f}ms | p95={rec.p95_ms:<5.3f}ms | p99={rec.p99_ms:<5.3f}ms | "
                f"CPU={rec.cpu_pct:<5.1f}% | Mem={rec.memory_mb:<5.1f}MB"
            )

    start_t = time.perf_counter()
    records = runner.run_benchmark_matrix(
        component_name="postgresql_db",
        version="16-alpine",
        concurrency_levels=[8],
        replications=3,
        duration_seconds=30,
        warmup_seconds=10,
        scale_factor=2,
        workload_profile="read_only_select",
        artifacts_dir=art_dir,
        execution_id=f"exec_cpu{cpu_limit}_{uuid_suffix()}",
        checkpoint_callback=checkpoint_cb,
        on_container_ready=on_ready_cb,
    )
    wall_duration = round(time.perf_counter() - start_t, 2)

    auth.status = AuthorizationStatus.EXHAUSTED
    registry.save_authorization(auth)

    # Read monitoring summaries
    mon_summaries = []
    for rep in range(3):
        sum_file = art_dir / f"monitoring_summary_c8_r{rep}.json"
        if sum_file.exists():
            with open(sum_file, "r") as f:
                mon_summaries.append(json.load(f))

    # Read and parse all raw transaction logs for distribution calculation
    all_latencies_ms = []
    rep_latencies_list = []
    for rep in range(3):
        log_file = art_dir / f"pglog_c8_r{rep}.log"
        if log_file.exists():
            lats, _ = PgbenchOutputParser.parse_transaction_timestamps_and_latencies(log_file.read_text())
            all_latencies_ms.extend(lats)
            rep_latencies_list.append(lats)

    distribution_stats = compute_distribution_metrics(all_latencies_ms)

    # Throttling aggregation across replications
    total_throttled_events = sum(s.get("throttling_events_count", 0) for s in mon_summaries)
    total_throttled_sec = sum(s.get("throttled_time_seconds", 0.0) for s in mon_summaries)
    mean_throttling_rate = sum(s.get("throttling_event_rate_per_sec", 0.0) for s in mon_summaries) / max(1, len(mon_summaries))
    mean_container_cpu = sum(s.get("mean_container_cpu_pct", 0.0) for s in mon_summaries) / max(1, len(mon_summaries))
    mean_host_cpu = sum(s.get("mean_host_cpu_pct", 0.0) for s in mon_summaries) / max(1, len(mon_summaries))
    peak_memory_mb = max((s.get("peak_memory_mb", 0.0) for s in mon_summaries), default=0.0)

    # Total TPS and failed transactions
    indiv_recs = [r for r in records if r.trial_replications == 1]
    pooled_rec = next((r for r in records if r.trial_replications > 1), None)
    mean_tps = sum(r.achieved_rps for r in indiv_recs) / max(1, len(indiv_recs))
    total_failed_tx = sum(r.error_count for r in indiv_recs)

    config_result = {
        "cpu_limit": cpu_limit,
        "proposal_id": proposal_id,
        "authorization_id": auth_id,
        "wall_duration_seconds": wall_duration,
        "replications_count": len(indiv_recs),
        "mean_tps": round(mean_tps, 1),
        "pooled_tps": pooled_rec.achieved_rps if pooled_rec else round(mean_tps, 1),
        "total_transactions": len(all_latencies_ms),
        "total_failed_transactions": total_failed_tx,
        "mean_container_cpu_pct": round(mean_container_cpu, 2),
        "mean_host_cpu_pct": round(mean_host_cpu, 2),
        "peak_memory_mb": round(peak_memory_mb, 2),
        "total_throttled_events": total_throttled_events,
        "total_throttled_time_seconds": round(total_throttled_sec, 3),
        "mean_throttling_rate_per_sec": round(mean_throttling_rate, 2),
        "throttled_time_per_thread_seconds": round(total_throttled_sec / (3 * 8), 3),
        "cgroup_placement": placement_result,
        "distribution_stats": distribution_stats,
        "records": [r.model_dump() for r in records],
        "monitoring_summaries": mon_summaries,
    }

    (art_dir / "config_summary.json").write_text(json.dumps(config_result, indent=2))
    return config_result


def uuid_suffix() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


def main():
    print("=" * 80)
    print("AADS Phase 4F.1 — Controlled CPU-Quota Experiment (1.0 vs 2.0 vCPU)")
    print("=" * 80)

    artifacts_base = BASE_DIR / "artifacts" / "benchmarks" / "phase_4f1_cpu_quota"
    artifacts_base.mkdir(parents=True, exist_ok=True)
    registry = ComponentRegistry()

    # 1. Run 1.0 vCPU configuration
    res_1cpu = run_configuration(
        cpu_limit="1.0",
        proposal_id="prop_postgres_cpu1.0_4f1_001",
        auth_id="auth_postgres_cpu1.0_4f1_001",
        artifacts_base=artifacts_base,
        registry=registry,
    )

    # 2. Run 2.0 vCPU configuration
    res_2cpu = run_configuration(
        cpu_limit="2.0",
        proposal_id="prop_postgres_cpu2.0_4f1_001",
        auth_id="auth_postgres_cpu2.0_4f1_001",
        artifacts_base=artifacts_base,
        registry=registry,
    )

    # 3. Save comparative summary
    comparison = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "workload": "read_only_select",
        "scale_factor": 2,
        "concurrency": 8,
        "replications": 3,
        "duration_seconds": 30,
        "cpu_1.0": res_1cpu,
        "cpu_2.0": res_2cpu,
    }
    comp_file = artifacts_base / "comparison_summary.json"
    comp_file.write_text(json.dumps(comparison, indent=2))
    print(f"\nComparative summary saved to: {comp_file}")

    # 4. Display terminal comparison table
    print("\n" + "=" * 90)
    print("CONTROLLED EXPERIMENT SUMMARY: 1.0 vCPU vs 2.0 vCPU")
    print("=" * 90)
    print(f"{'Metric':<35} {'1.0 vCPU':<25} {'2.0 vCPU':<25}")
    print("-" * 90)
    print(f"{'Throughput (Pooled TPS)':<35} {res_1cpu['pooled_tps']:<25.1f} {res_2cpu['pooled_tps']:<25.1f}")
    print(f"{'Mean Transaction Latency (ms)':<35} {res_1cpu['distribution_stats']['mean_ms']:<25.4f} {res_2cpu['distribution_stats']['mean_ms']:<25.4f}")
    print(f"{'Median Latency p50 (ms)':<35} {res_1cpu['distribution_stats']['p50_ms']:<25.4f} {res_2cpu['distribution_stats']['p50_ms']:<25.4f}")
    print(f"{'Tail Latency p95 (ms)':<35} {res_1cpu['distribution_stats']['p95_ms']:<25.4f} {res_2cpu['distribution_stats']['p95_ms']:<25.4f}")
    print(f"{'Tail Latency p99 (ms)':<35} {res_1cpu['distribution_stats']['p99_ms']:<25.4f} {res_2cpu['distribution_stats']['p99_ms']:<25.4f}")
    print(f"{'Tail Latency p99.9 (ms)':<35} {res_1cpu['distribution_stats']['p999_ms']:<25.4f} {res_2cpu['distribution_stats']['p999_ms']:<25.4f}")
    print(f"{'Maximum Latency (ms)':<35} {res_1cpu['distribution_stats']['max_ms']:<25.4f} {res_2cpu['distribution_stats']['max_ms']:<25.4f}")
    print(f"{'Standard Deviation (ms)':<35} {res_1cpu['distribution_stats']['std_ms']:<25.4f} {res_2cpu['distribution_stats']['std_ms']:<25.4f}")
    print(f"{'Interquartile Range IQR (ms)':<35} {res_1cpu['distribution_stats']['iqr_ms']:<25.4f} {res_2cpu['distribution_stats']['iqr_ms']:<25.4f}")
    s1_cnt = res_1cpu["distribution_stats"]["spikes_over_10ms_count"]
    s1_pct = res_1cpu["distribution_stats"]["spikes_over_10ms_pct"]
    s2_cnt = res_2cpu["distribution_stats"]["spikes_over_10ms_count"]
    s2_pct = res_2cpu["distribution_stats"]["spikes_over_10ms_pct"]
    s1_str = f"{s1_cnt} ({s1_pct}%)"
    s2_str = f"{s2_cnt} ({s2_pct}%)"
    print(f"{'Spikes >= 10ms (count / %)':<35} {s1_str:<25} {s2_str:<25}")
    print(f"{'Active Container CPU %':<35} {res_1cpu['mean_container_cpu_pct']:<25.1f} {res_2cpu['mean_container_cpu_pct']:<25.1f}")
    print(f"{'Active Host CPU %':<35} {res_1cpu['mean_host_cpu_pct']:<25.1f} {res_2cpu['mean_host_cpu_pct']:<25.1f}")
    print(f"{'Peak Memory Usage (MB)':<35} {res_1cpu['peak_memory_mb']:<25.1f} {res_2cpu['peak_memory_mb']:<25.1f}")
    print(f"{'Total Throttling Events':<35} {res_1cpu['total_throttled_events']:<25} {res_2cpu['total_throttled_events']:<25}")
    print(f"{'Throttling Rate (events/sec)':<35} {res_1cpu['mean_throttling_rate_per_sec']:<25.2f} {res_2cpu['mean_throttling_rate_per_sec']:<25.2f}")
    print(f"{'Throttled Wait / Thread (sec)':<35} {res_1cpu['throttled_time_per_thread_seconds']:<25.3f} {res_2cpu['throttled_time_per_thread_seconds']:<25.3f}")
    print(f"{'Failed Transactions':<35} {res_1cpu['total_failed_transactions']:<25} {res_2cpu['total_failed_transactions']:<25}")
    print("=" * 90)


if __name__ == "__main__":
    main()
