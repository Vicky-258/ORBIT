"""
Phase 4F.0 — Resource Monitoring Verification Script.
Executes an authorized, bounded PostgreSQL benchmark (concurrency 8, 2 replications)
with continuous active resource monitoring (CPU %, memory MB, and cgroup v2 throttling).
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from aads.agent.schemas import (
    AuthorizationLevel,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
)
from aads.benchmark.bounded_executor import BoundedBenchmarkExecutor
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.registry.component_registry import ComponentRegistry


def main():
    print("=" * 80)
    print("AADS Phase 4F.0 — Resource Monitoring Verification Pilot")
    print("=" * 80)

    artifacts_path = BASE_DIR / "artifacts" / "benchmarks" / "phase_4f0_monitoring"
    artifacts_path.mkdir(parents=True, exist_ok=True)
    print(f"Artifact directory: {artifacts_path}")

    # 1. Proposal definition
    proposal_id = "prop_postgres_monitoring_4f0_001"
    proposal = ExperimentProposal(
        proposal_id=proposal_id,
        target_component="postgresql_db",
        version="16-alpine",
        hypothesis=(
            "Continuous active sampling during pgbench execution accurately captures container CPU utilization "
            "and Linux cgroup v2 CFS throttling counters (nr_throttled, throttled_usec), resolving the idle "
            "sampling defect from Phase 4E.1 and correlating throttling bursts with transaction tail latency."
        ),
        unknown_being_investigated=(
            "Active CPU utilization and CFS throttling dynamics during pgbench execution at concurrency 8 "
            "under 1.0 vCPU and 1024 MB RAM envelope."
        ),
        concurrency_levels=[8],
        read_ratio=1.0,
        replications=2,
        duration_seconds=30,
        warmup_seconds=10,
        scale_factor=2,
        artifacts_dir=str(artifacts_path),
        benchmark_framework="pgbench:16-select-only",
        timeout_seconds=300,
        expected_runtime_seconds=120.0,
        authorization_level=AuthorizationLevel.OPERATOR_APPROVAL_REQUIRED,
        reasoning="Phase 4F.0 Resource Monitoring Verification Pilot approved by operator.",
    )

    # 2. Authorization record
    auth_id = "auth_postgres_monitoring_4f0_001"
    auth = AuthorizationRecord(
        authorization_id=auth_id,
        proposal_id=proposal_id,
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="docker",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=300.0,
        token="auth_token_phase_4f0_monitoring_approved",
    )

    # 3. Component registry initialization and authorization persistence
    registry = ComponentRegistry()
    registry.save_authorization(auth)
    print(f"Authorization '{auth_id}' persisted in component registry (status: {auth.status.value}).")

    # 4. Instantiate BoundedBenchmarkExecutor with DockerBenchmarkRunner
    docker_runner = DockerBenchmarkRunner(
        cpu_limit="1.0",
        memory_limit="1024m",
        timeout_seconds=300,
    )

    executor = BoundedBenchmarkExecutor(
        registry=registry,
        docker_runner=docker_runner,
    )

    # 5. Execute benchmark experiment
    print(f"\n[EXECUTION START] Launching authorized PostgreSQL resource monitoring pilot...")
    print(f"  Proposal ID: {proposal.proposal_id}")
    print(f"  Authorization ID: {auth.authorization_id}")
    print(f"  Component: {proposal.target_component}:{proposal.version}")
    print(f"  Resource Envelope: 1.0 vCPU, 1024 MB RAM")
    print(f"  Dataset: pgbench scale factor 2 (~200,000 rows)")
    print(f"  Concurrency levels: {proposal.concurrency_levels}")
    print(f"  Replications: {proposal.replications}")
    print(f"  Warm-up: {proposal.warmup_seconds}s | Measurement: {proposal.duration_seconds}s per trial")
    print(f"  Artifacts directory: {artifacts_path}")

    start_wall = time.perf_counter()
    result = executor.execute_experiment(proposal, auth)
    duration_wall = round(time.perf_counter() - start_wall, 2)

    print(f"\n[EXECUTION FINISHED] Wall-clock time: {duration_wall}s")
    print(f"  Execution ID: {result.execution_id}")
    print(f"  Status: {result.status}")
    print(f"  Raw records count: {result.raw_records_count}")
    print(f"  Saved experiment IDs: {len(result.experiment_ids)}")

    if result.status != "SUCCESS":
        print(f"\n[ERROR] Benchmark execution failed: {result.error_message}")
        sys.exit(1)

    # 6. Retrieve and display collected empirical records
    print("\n" + "=" * 80)
    print("EMPIRICAL BENCHMARK & MONITORING MEASUREMENTS (Phase 4F.0)")
    print("=" * 80)

    header = f"{'Conc':<6} {'Rep':<8} {'TPS':<10} {'Avg Lat (ms)':<14} {'p50 (ms)':<10} {'p95 (ms)':<10} {'p99 (ms)':<10} {'Active CPU %':<14} {'Mem (MB)':<10}"
    print(header)
    print("-" * len(header))

    all_exps = registry.get_experiments(proposal.target_component, proposal.version)
    pilot_exps = [e for e in all_exps if e.experiment_id in result.experiment_ids]

    indiv_trials = [e for e in pilot_exps if e.trial_replications == 1]
    pooled_trials = [e for e in pilot_exps if e.trial_replications > 1]

    for e in sorted(indiv_trials, key=lambda x: (x.concurrency, x.experiment_id)):
        rep_label = "Rep 1"
        if "Replication 2" in (e.notes or ""):
            rep_label = "Rep 2"

        row = (
            f"{e.concurrency:<6} "
            f"{rep_label:<8} "
            f"{e.achieved_rps:<10.1f} "
            f"{round(e.concurrency / e.achieved_rps * 1000, 3):<14.3f} "
            f"{e.p50_ms:<10.3f} "
            f"{e.p95_ms:<10.3f} "
            f"{e.p99_ms:<10.3f} "
            f"{e.cpu_pct:<14.1f} "
            f"{e.memory_mb:<10.1f}"
        )
        print(row)

    print("-" * len(header))
    for e in sorted(pooled_trials, key=lambda x: x.concurrency):
        row = (
            f"{e.concurrency:<6} "
            f"{'POOLED':<8} "
            f"{e.achieved_rps:<10.1f} "
            f"{round(e.concurrency / e.achieved_rps * 1000, 3):<14.3f} "
            f"{e.p50_ms:<10.3f} "
            f"{e.p95_ms:<10.3f} "
            f"{e.p99_ms:<10.3f} "
            f"{e.cpu_pct:<14.1f} "
            f"{e.memory_mb:<10.1f}"
        )
        print(row)

    # 7. List and summarize generated artifacts
    saved_artifacts = sorted([p.name for p in artifacts_path.iterdir() if p.is_file()])
    print("\n" + "=" * 80)
    print("SAVED EXPERIMENTAL ARTIFACTS:")
    print("=" * 80)
    for art in saved_artifacts:
        size_bytes = (artifacts_path / art).stat().st_size
        print(f"  - {art} ({size_bytes:,} bytes)")

    # 8. Display monitoring summary contents
    for rep in range(proposal.replications):
        summary_p = artifacts_path / f"monitoring_summary_c8_r{rep}.json"
        if summary_p.exists():
            print(f"\n--- Resource Monitoring Summary (Replication {rep+1}) ---")
            with open(summary_p, "r") as f:
                mon_data = json.load(f)
            for k, v in mon_data.items():
                print(f"  {k}: {v}")

        corr_p = artifacts_path / f"correlation_analysis_c8_r{rep}.json"
        if corr_p.exists():
            print(f"\n--- Latency Spike vs Throttling Correlation (Replication {rep+1}) ---")
            with open(corr_p, "r") as f:
                corr_data = json.load(f)
            for k, v in corr_data.items():
                print(f"  {k}: {v}")

    # 9. Write execution summary artifact
    summary_file = artifacts_path / "execution_summary.json"
    summary_data = {
        "proposal_id": proposal_id,
        "authorization_id": auth_id,
        "execution_id": result.execution_id,
        "status": result.status,
        "target_component": proposal.target_component,
        "version": proposal.version,
        "concurrency_levels": proposal.concurrency_levels,
        "replications": proposal.replications,
        "scale_factor": proposal.scale_factor,
        "duration_seconds": proposal.duration_seconds,
        "warmup_seconds": proposal.warmup_seconds,
        "wall_clock_duration_seconds": duration_wall,
        "individual_experiments_count": len(indiv_trials),
        "pooled_experiments_count": len(pooled_trials),
        "experiment_ids": result.experiment_ids,
        "artifacts_directory": str(artifacts_path),
        "saved_artifacts": saved_artifacts,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nExecution summary artifact saved to: {summary_file}")
    print("\nPhase 4F.0 resource monitoring verification completed successfully.")


if __name__ == "__main__":
    main()
