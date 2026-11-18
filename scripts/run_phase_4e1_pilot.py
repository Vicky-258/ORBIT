"""
Phase 4E.1 — Execution Script for Authorized PostgreSQL Empirical Pilot.
Executes the first real Docker-backed benchmark using BoundedBenchmarkExecutor.
Requires prior explicit operator authorization.
Captures all replication measurements, transaction logs, stdout/stderr, and environment metadata.
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

from orbit.agent.schemas import (
    AuthorizationLevel,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
)
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.benchmark.docker_runner import DockerBenchmarkRunner
from orbit.modeling.calibration_pipeline import CalibrationPipeline
from orbit.modeling.model_trainer import ModelTrainer
from orbit.registry.component_registry import ComponentRegistry


def main():
    print("=" * 80)
    print("AADS Phase 4E.1 — First Authorized PostgreSQL Empirical Pilot")
    print("=" * 80)

    artifacts_path = BASE_DIR / "artifacts" / "benchmarks" / "phase_4e1_pilot"
    artifacts_path.mkdir(parents=True, exist_ok=True)
    print(f"Artifact directory: {artifacts_path}")

    # 1. Proposal definition
    proposal_id = "prop_postgres_pilot_4e1_001"
    proposal = ExperimentProposal(
        proposal_id=proposal_id,
        target_component="postgresql_db",
        version="16-alpine",
        hypothesis=(
            "PostgreSQL 16 under 1.0 vCPU and 1024MB memory exhibits sublinear throughput scaling "
            "up to concurrency 8 with sharp queuing latency increases at concurrency 16 for read-only pgbench workloads."
        ),
        unknown_being_investigated=(
            "Empirical tail latency (p95/p99) and saturation knee under read-only transactional "
            "concurrency [1, 4, 8, 16] in isolated Docker container."
        ),
        concurrency_levels=[1, 4, 8, 16],
        read_ratio=1.0,
        replications=3,
        duration_seconds=30,
        warmup_seconds=10,
        scale_factor=2,
        artifacts_dir=str(artifacts_path),
        benchmark_framework="pgbench:16-select-only",
        timeout_seconds=600,
        expected_runtime_seconds=430.0,
        authorization_level=AuthorizationLevel.OPERATOR_APPROVAL_REQUIRED,
        reasoning="Phase 4E.1 First Authorized PostgreSQL Empirical Pilot approved by operator.",
    )

    # 2. Authorization record
    auth_id = "auth_postgres_pilot_4e1_001"
    auth = AuthorizationRecord(
        authorization_id=auth_id,
        proposal_id=proposal_id,
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="docker",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=600.0,
        token="auth_token_phase_4e1_operator_approved",
    )

    # 3. Component registry initialization and authorization persistence
    registry = ComponentRegistry()
    registry.save_authorization(auth)
    print(f"Authorization '{auth_id}' persisted in component registry (status: {auth.status.value}).")

    # 4. Instantiate BoundedBenchmarkExecutor with DockerBenchmarkRunner
    docker_runner = DockerBenchmarkRunner(
        cpu_limit="1.0",
        memory_limit="1024m",
        timeout_seconds=600,
    )

    executor = BoundedBenchmarkExecutor(
        registry=registry,
        docker_runner=docker_runner,
    )

    # 5. Execute benchmark experiment
    print(f"\n[EXECUTION START] Launching authorized PostgreSQL empirical pilot...")
    print(f"  Component: {proposal.target_component}:{proposal.version}")
    print(f"  Resource Envelope: 1.0 vCPU, 1024 MB RAM")
    print(f"  Dataset: pgbench scale factor 2 (~200,000 rows)")
    print(f"  Concurrency levels: {proposal.concurrency_levels}")
    print(f"  Replications: {proposal.replications}")
    print(f"  Warm-up: {proposal.warmup_seconds}s | Measurement: {proposal.duration_seconds}s per trial")
    print(f"  Total planned trials: {len(proposal.concurrency_levels) * proposal.replications} measurement runs")

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

    # 6. Load and display collected empirical records
    print("\n" + "=" * 80)
    print("EMPIRICAL BENCHMARK MEASUREMENTS (Phase 4E.1)")
    print("=" * 80)

    header = f"{'Conc':<6} {'Rep':<8} {'TPS':<10} {'Avg Lat (ms)':<14} {'p50 (ms)':<10} {'p95 (ms)':<10} {'p99 (ms)':<10} {'Failed Tx':<10} {'CPU %':<8} {'Mem (MB)':<8}"
    print(header)
    print("-" * len(header))

    # Retrieve all saved experiments from registry
    all_exps = registry.get_experiments(proposal.target_component, proposal.version)
    # Filter to current execution
    pilot_exps = [e for e in all_exps if e.experiment_id in result.experiment_ids]

    # Sort individual trials first, then pooled
    indiv_trials = [e for e in pilot_exps if e.trial_replications == 1]
    pooled_trials = [e for e in pilot_exps if e.trial_replications > 1]

    for e in sorted(indiv_trials, key=lambda x: (x.concurrency, x.experiment_id)):
        # Extract replication index from notes
        rep_label = "Rep 1"
        if "Replication 2" in (e.notes or ""):
            rep_label = "Rep 2"
        elif "Replication 3" in (e.notes or ""):
            rep_label = "Rep 3"

        row = (
            f"{e.concurrency:<6} "
            f"{rep_label:<8} "
            f"{e.achieved_rps:<10.1f} "
            f"{round(e.concurrency / e.achieved_rps * 1000, 3):<14.3f} "
            f"{e.p50_ms:<10.3f} "
            f"{e.p95_ms:<10.3f} "
            f"{e.p99_ms:<10.3f} "
            f"{e.error_count:<10} "
            f"{e.cpu_pct:<8.1f} "
            f"{e.memory_mb:<8.1f}"
        )
        print(row)

    print("-" * len(header))
    print("POOLED CONFIGURATION PERCENTILES (Mathematically exact pooled transaction latencies):")
    for e in sorted(pooled_trials, key=lambda x: x.concurrency):
        row = (
            f"{e.concurrency:<6} "
            f"{'POOLED':<8} "
            f"{e.achieved_rps:<10.1f} "
            f"{round(e.concurrency / e.achieved_rps * 1000, 3):<14.3f} "
            f"{e.p50_ms:<10.3f} "
            f"{e.p95_ms:<10.3f} "
            f"{e.p99_ms:<10.3f} "
            f"{e.error_count:<10} "
            f"{e.cpu_pct:<8.1f} "
            f"{e.memory_mb:<8.1f}"
        )
        print(row)

    # 7. Inspect Environment Metadata
    env_file = artifacts_path / "environment_metadata.json"
    if env_file.exists():
        print("\n" + "=" * 80)
        print("CAPTURED ENVIRONMENTAL METADATA:")
        print("=" * 80)
        with open(env_file, "r") as f:
            env_data = json.load(f)
        for k, v in env_data.items():
            if isinstance(v, list):
                print(f"  {k}:")
                for item in v:
                    print(f"    - {item}")
            else:
                print(f"  {k}: {v}")

    # 8. Calibration Inspection (Do NOT automatically promote per Section 7)
    print("\n" + "=" * 80)
    print("CALIBRATION POLICY EVALUATION (INSPECTION ONLY - NO AUTOMATIC PROMOTION)")
    print("=" * 80)

    try:
        candidate_model, eval_metrics = ModelTrainer.train_and_validate(
            component_name=proposal.target_component,
            version=proposal.version,
            experiments=indiv_trials,  # individual empirical replications
            test_ratio=0.25,
        )
        print(f"Candidate Model ID: {candidate_model.model_id}")
        print(f"Chosen Model Type: {candidate_model.model_type}")
        print(f"Held-Out Validation RMSE: {candidate_model.validation_rmse_ms} ms")
        print(f"Held-Out Validation MAPE: {candidate_model.validation_mape_pct} %")
        print(f"R2 Score: {candidate_model.r2_score}")
        print(f"Is Validated: {candidate_model.is_validated}")
        print(f"Candidate Provenance:\n  {candidate_model.provenance}")
        print(f"Candidate Limitations:\n  {candidate_model.known_limitations}")
        print("\nNOTE: In compliance with Section 7 of Phase 4E.1 instructions, this model has NOT been")
        print("automatically promoted. Promotion must be reviewed based on empirical pilot inspection.")
    except Exception as exc:
        print(f"Calibration inspection result: {str(exc)}")
        print("Active baseline model in registry is preserved intact.")

    # 9. Write execution summary artifact
    summary_file = artifacts_path / "execution_summary.json"
    summary_data = {
        "proposal_id": proposal_id,
        "authorization_id": auth_id,
        "execution_id": result.execution_id,
        "status": result.status,
        "wall_clock_duration_seconds": duration_wall,
        "individual_experiments_count": len(indiv_trials),
        "pooled_experiments_count": len(pooled_trials),
        "experiment_ids": result.experiment_ids,
        "artifacts_directory": str(artifacts_path),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nExecution summary artifact saved to: {summary_file}")
    print("\nPhase 4E.1 empirical pilot execution completed successfully.")


if __name__ == "__main__":
    main()

