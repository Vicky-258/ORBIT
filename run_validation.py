"""
AADS Empirical Validation Campaign Runner (Phase 3C).
Executes reproducible Docker benchmarks for PostgreSQL & Redis microbenchmarks,
runs multi-tier end-to-end calibration for Architecture A & B, performs group-based
held-out model validation, and compares simulated vs measured feasibility and ranking.

Usage:
    .venv/bin/python run_validation.py [--mode docker|synthetic] [--duration 2.5] [--report-out path]
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.e2e_calibration import RealDeploymentCalibrationHarness
from aads.core.schemas import WorkloadSpec, ExperimentRecord
from aads.evaluation.empirical_validation import EmpiricalValidator, calculate_error_metrics
from aads.registry.component_registry import ComponentRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aads.validation")


def run_campaign(
    mode: str = "docker",
    duration: float = 2.5,
    output_report_path: Optional[str] = None,
) -> Dict[str, Any]:
    registry = ComponentRegistry()
    registry.seed_baseline_data()
    validator = EmpiricalValidator(registry=registry)

    use_docker = (mode == "docker")
    logger.info(f"Starting Phase 3C Empirical Validation Campaign (Mode: {mode.upper()})")

    # 1. Preflight Infrastructure Check
    if use_docker:
        docker_runner = DockerBenchmarkRunner()
        health = docker_runner.health_check()
        if not health["docker_available"]:
            logger.error(f"Docker is unavailable: {health.get('docker_version')}")
            return {"status": "BLOCKED", "reason": "Docker daemon unavailable"}
        logger.info(f"Docker verified: {health.get('docker_version')} on {health.get('host_os')}")
    else:
        logger.info("Operating in synthetic baseline validation mode.")

    # 2. Microbenchmark Matrix Collection (PostgreSQL and Redis)
    concurrencies = [1, 2, 4, 8, 16]
    microbenchmark_results = {}

    if use_docker:
        logger.info("Executing real PostgreSQL 16 pgbench matrix (concurrencies=[1, 2, 4, 8, 16], replications=3)...")
        pg_experiments = docker_runner.run_benchmark_matrix(
            component_name="postgres_db",
            version="postgres:16-alpine",
            concurrency_levels=concurrencies,
            replications=3,
        )
        logger.info("Executing real Redis 7 redis-benchmark matrix (concurrencies=[1, 2, 4, 8, 16], replications=3)...")
        rd_experiments = docker_runner.run_benchmark_matrix(
            component_name="redis_cache",
            version="redis:7-alpine",
            concurrency_levels=concurrencies,
            replications=3,
        )
    else:
        syn_runner = SyntheticBenchmarkRunner(seed=42)
        pg_experiments = syn_runner.run_benchmark_matrix("postgres_db", "postgres:16-alpine", concurrencies, replications=3)
        rd_experiments = syn_runner.run_benchmark_matrix("redis_cache", "redis:7-alpine", concurrencies, replications=3)

    # Persist experiments to registry
    for exp in pg_experiments + rd_experiments:
        registry.save_experiment(exp)

    logger.info(f"Saved {len(pg_experiments)} PostgreSQL trials and {len(rd_experiments)} Redis trials to registry.")

    # 3. Held-Out Component Model Validation (Zero Data Leakage)
    logger.info("Performing group-based held-out validation on PostgreSQL performance model...")
    pg_val = validator.validate_held_out_component_model(
        component_name="postgres_db",
        version="postgres:16-alpine",
        experiments=pg_experiments,
        test_ratio=0.40,
    )

    logger.info("Performing group-based held-out validation on Redis performance model...")
    rd_val = validator.validate_held_out_component_model(
        component_name="redis_cache",
        version="redis:7-alpine",
        experiments=rd_experiments,
        test_ratio=0.40,
    )

    # 4. Multi-Tier End-to-End Calibration (Architecture A and Architecture B)
    load_levels = [40.0, 80.0, 120.0, 160.0]
    calibration_runs = []

    if use_docker:
        harness = RealDeploymentCalibrationHarness()
        for rps in load_levels:
            logger.info(f"Running End-to-End Calibration for Architecture A at {rps} RPS...")
            res_a = harness.run_calibration_experiment(
                duration_seconds=duration,
                target_rps=rps,
                architecture="arch_a",
            )
            calibration_runs.append(res_a)

            logger.info(f"Running End-to-End Calibration for Architecture B at {rps} RPS...")
            res_b = harness.run_calibration_experiment(
                duration_seconds=duration,
                target_rps=rps,
                architecture="arch_b",
            )
            calibration_runs.append(res_b)
    else:
        # Synthetic calibration placeholder for offline CI
        for rps in load_levels:
            calibration_runs.append({
                "status": "VERIFIED",
                "architecture_id": "arch_a_simple",
                "architecture_name": "Architecture A — Simple",
                "real_measurements": {"throughput_rps": rps * 0.98, "p50_latency_ms": 1.2, "p95_latency_ms": 3.8, "p99_latency_ms": 5.0, "total_requests": int(rps * duration), "duration_seconds": duration},
                "simpy_predictions": {"throughput_rps": rps * 0.95, "p50_latency_ms": 2.5, "p95_latency_ms": 6.8, "p99_latency_ms": 7.4, "bottleneck": "db", "estimated_cost_usd": 133.0},
                "discrepancies": {"throughput_error_pct": 3.1, "p50_latency_error_pct": 108.0, "p95_latency_error_pct": 78.9, "latency_mae_ms": 3.0},
            })
            calibration_runs.append({
                "status": "VERIFIED",
                "architecture_id": "arch_b_cached",
                "architecture_name": "Architecture B — Cached Reads",
                "real_measurements": {"throughput_rps": rps * 0.99, "p50_latency_ms": 0.6, "p95_latency_ms": 3.2, "p99_latency_ms": 4.5, "cache_hit_rate": 0.85, "total_requests": int(rps * duration), "duration_seconds": duration},
                "simpy_predictions": {"throughput_rps": rps * 0.97, "p50_latency_ms": 0.9, "p95_latency_ms": 6.5, "p99_latency_ms": 7.2, "cache_hit_rate": 0.85, "bottleneck": "db", "estimated_cost_usd": 176.0},
                "discrepancies": {"throughput_error_pct": 2.0, "p50_latency_error_pct": 50.0, "p95_latency_error_pct": 103.1, "latency_mae_ms": 3.3},
            })

    # 5. Prediction vs Measurement Error Analysis
    e2e_comparison = validator.compare_real_vs_simulated_e2e(calibration_runs)

    # 6. Architecture Feasibility & Ranking Comparisons
    # Low Load Workload (40 RPS)
    low_workload = WorkloadSpec(
        request_rate_rps=40.0,
        min_throughput_rps=35.0,
        p95_latency_target_ms=50.0,
        max_monthly_budget_usd=250.0,
        soft_preferences={"cost": 0.50, "latency": 0.30, "simplicity": 0.20},
    )
    # High Load Workload (160 RPS)
    high_workload = WorkloadSpec(
        request_rate_rps=160.0,
        min_throughput_rps=135.0,
        p95_latency_target_ms=20.0,
        max_monthly_budget_usd=250.0,
        soft_preferences={"cost": 0.20, "latency": 0.60, "simplicity": 0.20},
    )

    low_runs = [r for r in calibration_runs if abs(r["real_measurements"]["throughput_rps"] - 40.0) < 15.0][:2]
    high_runs = [r for r in calibration_runs if abs(r["real_measurements"]["throughput_rps"] - 160.0) < 25.0][:2]

    low_comparison = validator.compare_feasibility_and_ranking(low_workload, low_runs if len(low_runs) == 2 else calibration_runs[:2])
    high_comparison = validator.compare_feasibility_and_ranking(high_workload, high_runs if len(high_runs) == 2 else calibration_runs[-2:])

    campaign_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "is_real_docker": use_docker,
        "docker_environment": health if use_docker else "Synthetic Fixture Mock",
        "microbenchmarks": {
            "postgres_trials": len(pg_experiments),
            "redis_trials": len(rd_experiments),
            "postgres_held_out_validation": {
                "status": pg_val["status"],
                "model_type": pg_val.get("model_type"),
                "metrics": pg_val.get("metrics"),
            },
            "redis_held_out_validation": {
                "status": rd_val["status"],
                "model_type": rd_val.get("model_type"),
                "metrics": rd_val.get("metrics"),
            },
        },
        "end_to_end_calibration": e2e_comparison,
        "feasibility_and_ranking": {
            "low_load": low_comparison,
            "high_load": high_comparison,
        },
    }

    if output_report_path:
        with open(output_report_path, "w") as f:
            json.dump(campaign_summary, f, indent=2, default=str)
        logger.info(f"Campaign results saved to {output_report_path}")

    return campaign_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AADS Phase 3C Empirical Validation Campaign")
    parser.add_argument("--mode", choices=["docker", "synthetic"], default="docker", help="Execution mode")
    parser.add_argument("--duration", type=float, default=2.5, help="Measurement duration per calibration point")
    parser.add_argument("--report-out", type=str, default="validation_results.json", help="Path to save output JSON")
    args = parser.parse_args()

    results = run_campaign(mode=args.mode, duration=args.duration, output_report_path=args.report_out)
    print("\n=======================================================")
    print("  PHASE 3C EMPIRICAL VALIDATION CAMPAIGN SUMMARY")
    print("=======================================================")
    print(f"  • Execution Mode   : {results.get('mode', '').upper()}")
    print(f"  • Microbenchmarks  : Postgres ({results['microbenchmarks']['postgres_trials']} trials), Redis ({results['microbenchmarks']['redis_trials']} trials)")
    print(f"  • Model Validation : Postgres [{results['microbenchmarks']['postgres_held_out_validation']['status']}], Redis [{results['microbenchmarks']['redis_held_out_validation']['status']}]")
    if "overall_throughput_metrics" in results.get("end_to_end_calibration", {}):
        e2e = results["end_to_end_calibration"]
        print(f"  • E2E TPS Error    : MAE={e2e['overall_throughput_metrics']['mae']} RPS, MAPE={e2e['overall_throughput_metrics']['mape']}%")
        print(f"  • E2E p95 Latency  : MAE={e2e['overall_p95_latency_metrics']['mae']} ms, MAPE={e2e['overall_p95_latency_metrics']['mape']}%")
    print("=======================================================\n")
