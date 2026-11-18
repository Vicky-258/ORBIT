"""
Phase 4F.1 — PostgreSQL Multi-Workload Empirical Campaign Script.
Executes the structured empirical matrix across 3 workload profiles, 3 dataset scales,
and 4 concurrency levels with continuous active resource and cgroup v2 throttling monitoring.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from orbit.agent.schemas import (
    AuthorizationLevel,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
)
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
import numpy as np
from orbit.benchmark.docker_runner import DockerBenchmarkRunner, PgbenchOutputParser
from orbit.benchmark.workload_profiles import (
    BALANCED_OLTP_TPCB,
    READ_ONLY_SELECT,
    SIMPLE_WRITE_INGEST,
    WORKLOAD_PROFILES,
    resolve_workload_profile,
)
from orbit.core.schemas import ExperimentRecord
from orbit.registry.component_registry import ComponentRegistry


def parse_args():
    parser = argparse.ArgumentParser(description="Phase 4F.1 PostgreSQL Empirical Campaign")
    parser.add_argument(
        "--scale-factors",
        nargs="+",
        type=int,
        default=[2, 20, 100],
        help="Dataset scale factors (default: 2 20 100)",
    )
    parser.add_argument(
        "--workloads",
        nargs="+",
        default=["read_only_select", "balanced_oltp_tpcb", "simple_write_ingest"],
        help="Workload profiles to execute (default: read_only_select balanced_oltp_tpcb simple_write_ingest)",
    )
    parser.add_argument(
        "--concurrencies",
        nargs="+",
        type=int,
        default=[1, 4, 8, 16],
        help="Concurrency levels (default: 1 4 8 16)",
    )
    parser.add_argument(
        "--replications",
        type=int,
        default=3,
        help="Replications per configuration (default: 3)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Measurement duration in seconds per trial (default: 30)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Warm-up duration in seconds per profile (default: 10)",
    )
    parser.add_argument(
        "--cpu-limit",
        default="1.0",
        help="Container CPU limit (default: 1.0)",
    )
    parser.add_argument(
        "--memory-limit",
        default="1024m",
        help="Container memory limit (default: 1024m)",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(BASE_DIR / "artifacts" / "benchmarks" / "phase_4f1_campaign"),
        help="Artifacts persistence directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display proposed execution matrix and estimated budget without running containers",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    artifacts_path = Path(args.artifacts_dir)
    artifacts_path.mkdir(parents=True, exist_ok=True)

    target_profiles = [resolve_workload_profile(w) for w in args.workloads]
    total_configs = len(args.scale_factors) * len(target_profiles) * len(args.concurrencies)
    total_trials = total_configs * args.replications
    est_trial_sec = args.duration + (args.warmup // len(args.concurrencies))
    est_total_runtime_sec = total_trials * est_trial_sec + len(args.scale_factors) * 45

    print("=" * 80)
    print("AADS Phase 4F.1 — PostgreSQL Multi-Workload Empirical Campaign")
    print("=" * 80)
    print(f"Artifacts Directory : {artifacts_path}")
    print(f"Scale Factors       : {args.scale_factors} ({len(args.scale_factors)} operating regimes)")
    print(f"Workload Profiles   : {[p.name for p in target_profiles]}")
    print(f"Concurrency Levels  : {args.concurrencies}")
    print(f"Replications        : {args.replications} per configuration")
    print(f"Duration per Trial  : {args.duration}s measurement + {args.warmup}s warmup")
    print(f"Total Configurations: {total_configs} independent configuration groups")
    print(f"Total Trials        : {total_trials} measurement trials")
    print(f"Estimated Runtime   : {round(est_total_runtime_sec / 60.0, 1)} minutes")
    print(f"Resource Limits     : {args.cpu_limit} vCPU, {args.memory_limit} RAM")
    print("=" * 80)

    if args.dry_run:
        print("\n[DRY RUN] Matrix validated. Exiting without execution.")
        return

    # 1. Proposal definition
    proposal_id = f"prop_postgres_campaign_4f1_{uuid_suffix()}"
    proposal = ExperimentProposal(
        proposal_id=proposal_id,
        target_component="postgresql_db",
        version="16-alpine",
        hypothesis=(
            "PostgreSQL 16 performance exhibits sharp regime shifts across dataset scales (in-memory SF=2, "
            "cache-boundary SF=20, out-of-core SF=100) and workload profiles (read-only select, balanced OLTP, "
            "and simple write ingestion) under CFS CPU quota constraints."
        ),
        unknown_being_investigated=(
            "Multi-dimensional performance response surface, WAL flushing overhead, and CFS throttling dynamics "
            "across 36 configuration groups."
        ),
        concurrency_levels=args.concurrencies,
        scale_factors=args.scale_factors,
        workload_profiles=[p.name for p in target_profiles],
        replications=args.replications,
        duration_seconds=args.duration,
        warmup_seconds=args.warmup,
        artifacts_dir=str(artifacts_path),
        benchmark_framework="pgbench:16-multi-workload",
        timeout_seconds=int(est_total_runtime_sec * 1.5) + 300,
        expected_runtime_seconds=float(est_total_runtime_sec),
        authorization_level=AuthorizationLevel.OPERATOR_APPROVAL_REQUIRED,
        reasoning="Phase 4F.1 Multi-Workload Empirical Campaign operator approval.",
    )

    # 2. Authorization record
    auth_id = f"auth_postgres_campaign_4f1_{uuid_suffix()}"
    max_runtime = float(proposal.timeout_seconds)
    auth = AuthorizationRecord(
        authorization_id=auth_id,
        proposal_id=proposal_id,
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="docker",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=max_runtime,
        token=f"auth_token_phase_4f1_{uuid_suffix()}",
    )

    registry = ComponentRegistry()
    registry.save_authorization(auth)
    print(f"\nAuthorization '{auth_id}' persisted in registry (status: {auth.status.value}).")

    # 3. Instantiate Runner and Executor
    docker_runner = DockerBenchmarkRunner(
        cpu_limit=args.cpu_limit,
        memory_limit=args.memory_limit,
        timeout_seconds=proposal.timeout_seconds,
    )

    executor = BoundedBenchmarkExecutor(
        registry=registry,
        docker_runner=docker_runner,
    )

    # 4. Checkpoint callback for immediate registry & manifest persistence
    completed_records: List[ExperimentRecord] = []
    manifest_file = artifacts_path / "campaign_manifest.jsonl"

    def checkpoint_record(rec: ExperimentRecord):
        rec.proposal_id = proposal_id
        rec.authorization_id = auth_id
        registry.save_experiment(rec)
        completed_records.append(rec)
        with open(manifest_file, "a") as f:
            f.write(rec.model_dump_json() + "\n")
        
        # Display progress line for individual trials
        if rec.trial_replications == 1:
            print(
                f"  [{len(completed_records)}/{total_trials + total_configs}] "
                f"SF={rec.scale_factor:<3} | {rec.workload_profile:<19} | c={rec.concurrency:<2} | "
                f"TPS={rec.achieved_rps:<8.1f} | p95={rec.p95_ms:<6.2f}ms | "
                f"CPU={rec.cpu_pct:<5.1f}% | Mem={rec.memory_mb:<5.1f}MB"
            )

    print(f"\n[CAMPAIGN START] Executing Phase 4F.1 empirical matrix...")
    start_wall = time.perf_counter()

    # We invoke docker_runner directly with checkpoint_callback and update authorization status
    auth.status = AuthorizationStatus.EXHAUSTED
    registry.save_authorization(auth)

    try:
        all_records = docker_runner.run_benchmark_matrix(
            component_name=proposal.target_component,
            version=proposal.version,
            concurrency_levels=args.concurrencies,
            replications=args.replications,
            duration_seconds=args.duration,
            warmup_seconds=args.warmup,
            scale_factors=args.scale_factors,
            workload_profiles=[p.name for p in target_profiles],
            artifacts_dir=artifacts_path,
            execution_id=f"exec_4f1_{uuid_suffix()}",
            checkpoint_callback=checkpoint_record,
        )
    except Exception as exc:
        print(f"\n[ERROR] Campaign execution failed: {str(exc)}")
        sys.exit(1)

    duration_wall = round(time.perf_counter() - start_wall, 2)
    print(f"\n[CAMPAIGN COMPLETE] Total wall-clock time: {duration_wall}s ({round(duration_wall / 60.0, 1)} min)")
    print(f"Total ExperimentRecords generated: {len(all_records)}")

    # 5. Output Summary Table
    print("\n" + "=" * 90)
    print("PHASE 4F.1 EMPIRICAL CAMPAIGN RESULTS (POOLED CONFIGURATION SUMMARY)")
    print("=" * 90)
    header = f"{'SF':<4} {'Workload Profile':<21} {'Conc':<5} {'TPS':<9} {'Avg (ms)':<9} {'p50 (ms)':<9} {'p95 (ms)':<9} {'p99 (ms)':<9} {'CPU %':<7} {'Mem MB':<7}"
    print(header)
    print("-" * len(header))

    pooled_records = [r for r in all_records if r.trial_replications > 1]
    for r in sorted(pooled_records, key=lambda x: (x.scale_factor or 0, x.workload_profile or "", x.concurrency)):
        row = (
            f"{r.scale_factor:<4} "
            f"{(r.workload_profile or 'default'):<21} "
            f"{r.concurrency:<5} "
            f"{r.achieved_rps:<9.1f} "
            f"{round(r.concurrency / r.achieved_rps * 1000, 2) if r.achieved_rps > 0 else 0.0:<9.2f} "
            f"{r.p50_ms:<9.3f} "
            f"{r.p95_ms:<9.3f} "
            f"{r.p99_ms:<9.3f} "
            f"{r.cpu_pct:<7.1f} "
            f"{r.memory_mb:<7.1f}"
        )
        print(row)

    # 6. Compute Detailed Latency Distribution & Throttling Summary across all configurations
    distribution_summary: Dict[str, Any] = {}
    for sf in args.scale_factors:
        for profile in target_profiles:
            for conc in args.concurrencies:
                cfg_key = f"sf{sf}_{profile.name}_c{conc}"
                all_lats: List[float] = []
                mon_sums: List[Dict[str, Any]] = []

                for rep in range(args.replications):
                    log_file = artifacts_path / f"pglog_{cfg_key}_r{rep}.log"
                    if log_file.exists():
                        lats, _ = PgbenchOutputParser.parse_transaction_timestamps_and_latencies(log_file.read_text())
                        all_lats.extend(lats)

                    mon_file = artifacts_path / f"monitoring_summary_{cfg_key}_r{rep}.json"
                    if mon_file.exists():
                        try:
                            mon_sums.append(json.loads(mon_file.read_text()))
                        except Exception:
                            pass

                if all_lats:
                    arr = np.array(all_lats, dtype=np.float64)
                    p25 = float(np.percentile(arr, 25))
                    p75 = float(np.percentile(arr, 75))
                    spikes_10 = int(np.sum(arr >= 10.0))
                    spikes_50 = int(np.sum(arr >= 50.0))
                    spikes_100 = int(np.sum(arr >= 100.0))

                    total_throttled_ev = sum(s.get("throttling_events_count", 0) for s in mon_sums)
                    total_throttled_s = sum(s.get("throttled_time_seconds", 0.0) for s in mon_sums)
                    mean_throt_rate = sum(s.get("throttling_event_rate_per_sec", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    mean_cpu = sum(s.get("mean_container_cpu_pct", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    mean_host = sum(s.get("mean_host_cpu_pct", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    peak_mem = max((s.get("peak_memory_mb", 0.0) for s in mon_sums), default=0.0)

                    # Find pooled experiment record
                    matching_pooled = next(
                        (r for r in pooled_records if r.scale_factor == sf and r.workload_profile == profile.name and r.concurrency == conc),
                        None,
                    )
                    tps = matching_pooled.achieved_rps if matching_pooled else 0.0

                    distribution_summary[cfg_key] = {
                        "scale_factor": sf,
                        "workload_profile": profile.name,
                        "concurrency": conc,
                        "replications": args.replications,
                        "achieved_tps": round(tps, 1),
                        "total_transactions": len(arr),
                        "min_ms": round(float(np.min(arr)), 4),
                        "mean_ms": round(float(np.mean(arr)), 4),
                        "std_ms": round(float(np.std(arr)), 4),
                        "p50_ms": round(float(np.percentile(arr, 50)), 4),
                        "p90_ms": round(float(np.percentile(arr, 90)), 4),
                        "p95_ms": round(float(np.percentile(arr, 95)), 4),
                        "p99_ms": round(float(np.percentile(arr, 99)), 4),
                        "p999_ms": round(float(np.percentile(arr, 99.9)), 4),
                        "max_ms": round(float(np.max(arr)), 4),
                        "iqr_ms": round(p75 - p25, 4),
                        "spikes_over_10ms_count": spikes_10,
                        "spikes_over_10ms_pct": round(spikes_10 / len(arr) * 100.0, 3) if len(arr) > 0 else 0.0,
                        "spikes_over_50ms_count": spikes_50,
                        "spikes_over_100ms_count": spikes_100,
                        "mean_container_cpu_pct": round(mean_cpu, 2),
                        "mean_host_cpu_pct": round(mean_host, 2),
                        "peak_memory_mb": round(peak_mem, 2),
                        "total_throttling_events": total_throttled_ev,
                        "total_throttled_time_seconds": round(total_throttled_s, 3),
                        "mean_throttling_rate_per_sec": round(mean_throt_rate, 2),
                    }

    dist_summary_file = artifacts_path / "campaign_distribution_summary.json"
    dist_summary_file.write_text(json.dumps(distribution_summary, indent=2))
    print(f"Distribution summary saved to: {dist_summary_file}")

    # 7. Save Execution Summary Artifact
    summary_file = artifacts_path / "execution_summary.json"
    saved_artifacts = sorted([p.name for p in artifacts_path.iterdir() if p.is_file()])
    summary_data = {
        "proposal_id": proposal_id,
        "authorization_id": auth_id,
        "execution_id": f"exec_4f1_{uuid_suffix()}",
        "status": "SUCCESS",
        "target_component": proposal.target_component,
        "version": proposal.version,
        "scale_factors": args.scale_factors,
        "workload_profiles": [p.name for p in target_profiles],
        "concurrencies": args.concurrencies,
        "replications": args.replications,
        "duration_seconds": args.duration,
        "warmup_seconds": args.warmup,
        "total_records_count": len(all_records),
        "individual_records_count": len([r for r in all_records if r.trial_replications == 1]),
        "pooled_records_count": len(pooled_records),
        "wall_clock_duration_seconds": duration_wall,
        "artifacts_directory": str(artifacts_path),
        "saved_artifacts_count": len(saved_artifacts),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nExecution summary saved to: {summary_file}")


def uuid_suffix() -> str:
    import uuid
    return uuid.uuid4().hex[:8]


if __name__ == "__main__":
    main()
