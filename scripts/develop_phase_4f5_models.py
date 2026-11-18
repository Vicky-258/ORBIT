#!/usr/bin/env python3
"""
Phase 4F.5 — Empirical PostgreSQL Performance Model Development & Evaluation Runner.

Loads reconciled empirical evidence from Phase 4F.4.6, trains candidate models for
both read-only and balanced OLTP workloads, conducts Leave-One-Replication-Out (LORO)
cross-validation, and serializes candidate models into artifacts/phase_4f5/candidates/.
Strict offline execution: no benchmarks, no registry mutations.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orbit.models.empirical_postgres import (
    EmpiricalLinearRegressionModel,
    EmpiricalLookupModel,
    EmpiricalMechanisticModel,
    EmpiricalPiecewiseModel,
    ReconciledEvidenceLoader,
    ReplicationAwareEvaluator,
    WorkloadProfile,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase_4f5_developer")


def main() -> int:
    parser = argparse.ArgumentParser(description="Develop and evaluate Phase 4F.5 empirical PostgreSQL models.")
    parser.add_argument(
        "--evidence-dir",
        default="artifacts/phase_4f46/reconciliation",
        help="Path to Phase 4F.4.6 reconciled evidence directory",
    )
    parser.add_argument(
        "--candidates-dir",
        default="artifacts/phase_4f5/candidates",
        help="Path to candidate models output directory",
    )
    args = parser.parse_args()

    evidence_path = Path(args.evidence_dir)
    candidates_path = Path(args.candidates_dir)
    candidates_path.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing ReconciledEvidenceLoader from %s...", evidence_path)
    loader = ReconciledEvidenceLoader(evidence_path)

    # 1. Verify provenance
    valid, provenance = loader.verify_provenance()
    logger.info("Evidence provenance valid: %s (Execution ID: %s, Manifest SHA256: %s...)",
                valid, provenance.get("execution_id"), str(provenance.get("manifest_sha256"))[:16])
    if not valid:
        logger.error("Evidence provenance check failed! Aborting model development.")
        return 1

    # 2. Load observations
    observations = loader.load_trial_observations()
    logger.info("Loaded %d trial observations across all conditions.", len(observations))

    # 3. Setup evaluator
    evaluator = ReplicationAwareEvaluator(observations)

    model_families = [
        ("lookup", EmpiricalLookupModel),
        ("linear", EmpiricalLinearRegressionModel),
        ("piecewise", EmpiricalPiecewiseModel),
        ("mechanistic", EmpiricalMechanisticModel),
    ]

    target_metrics = [
        "throughput_tps",
        "latency_mean_ms",
        "p50_ms",
        "p95_ms",
        "p99_ms",
        "cpu_utilization_pct",
    ]

    evaluation_report: Dict[str, Any] = {
        "execution_id": provenance.get("execution_id"),
        "manifest_sha256": provenance.get("manifest_sha256"),
        "total_observations": len(observations),
        "evaluation_strategy": "Leave-One-Replication-Out (LORO) Cross-Validation",
        "evaluation_type": "REPLICATION_HOLDOUT",
        "scope_limitations": [
            "Evaluates repeatability across independent replications at observed configurations only.",
            "Does NOT evaluate configuration holdout (unseen CPU quotas), workload holdout, or environment holdout.",
            "Lookup, Linear, and Piecewise models produce mathematically indistinguishable predictions at observed support points (1.0 and 2.0 vCPU).",
        ],
        "workloads": {},
    }

    # 4. Train and evaluate for each workload
    for wl in [WorkloadProfile.READ_ONLY_SELECT, WorkloadProfile.BALANCED_OLTP_TPCB]:
        wl_str = wl.value
        logger.info("Processing workload: %s...", wl_str)
        evaluation_report["workloads"][wl_str] = {}

        wl_obs = loader.get_workload_observations(wl)

        for name_key, model_cls in model_families:
            model_id = f"pg16_candidate_{name_key}_{wl_str}"
            logger.info("  Training and evaluating candidate: %s...", model_id)

            # Fit candidate on full workload observations
            full_model = model_cls(
                model_id=model_id,
                workload_profile=wl,
                provenance=provenance,
            )
            full_model.fit(wl_obs)

            # Save full candidate model
            model_file = candidates_path / f"{model_id}.json"
            full_model.save_json(model_file)
            logger.info("  Saved serialized candidate to %s", model_file)

            # Evaluate candidate on all target metrics
            family_eval: Dict[str, Any] = {
                "model_id": model_id,
                "model_family": model_cls.__name__,
                "serialized_path": str(model_file),
                "metrics": {},
            }

            for metric in target_metrics:
                metric_eval = evaluator.evaluate_model_family(model_cls, wl, target_metric=metric)
                family_eval["metrics"][metric] = {
                    "overall_metrics": metric_eval["overall_metrics"],
                    "per_condition_errors": metric_eval["per_condition_errors"],
                    "ground_truth_replication_cv_pct": metric_eval["ground_truth_replication_cv_pct"],
                }

            evaluation_report["workloads"][wl_str][name_key] = family_eval

    # 5. Save evaluation comparison summary
    comparison_file = candidates_path / "model_comparison_results.json"
    with open(comparison_file, "w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)
    logger.info("Saved model comparison results to %s", comparison_file)

    print("\n" + "=" * 80)
    print("PHASE 4F.5 CANDIDATE MODEL EVALUATION SUMMARY")
    print("=" * 80)
    for wl_str, models_data in evaluation_report["workloads"].items():
        print(f"\nWorkload: {wl_str.upper()}")
        print(f"{'Candidate Model':32} | {'Throughput RMSE':15} | {'Throughput MAPE':15} | {'Latency Mean RMSE':18}")
        print("-" * 88)
        for name_key, m_data in models_data.items():
            tps_met = m_data["metrics"]["throughput_tps"]["overall_metrics"]
            lat_met = m_data["metrics"]["latency_mean_ms"]["overall_metrics"]
            tps_rmse = f"{tps_met['rmse']:.2f} TPS"
            tps_mape = f"{tps_met['mape_pct']:.2f}%" if tps_met['mape_pct'] is not None else "N/A"
            lat_rmse = f"{lat_met['rmse']:.4f} ms"
            print(f"{m_data['model_id']:32} | {tps_rmse:15} | {tps_mape:15} | {lat_rmse:18}")

    print("\n" + "=" * 80)
    print("Candidate models created and saved to artifacts/phase_4f5/candidates/.")
    print("Active model registry data/registry.db remains UNTOUCHED.")
    print("=" * 80 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
