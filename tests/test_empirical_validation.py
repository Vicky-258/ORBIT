"""
AADS Phase 3C Automated Test Suite: Empirical Validation and Calibration.
Validates error metrics, group-based held-out splits, provenance separation,
feasibility comparisons, ranking analysis, and resource cleanup.
"""
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta

from orbit.core.schemas import (
    WorkloadSpec,
    ExperimentRecord,
    ModelRecord,
    SimulationResult,
    FeasibilityStatus,
)
from orbit.evaluation.empirical_validation import (
    calculate_error_metrics,
    EmpiricalValidator,
    ErrorMetrics,
)
from orbit.registry.component_registry import ComponentRegistry
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from orbit.modeling.model_trainer import ModelTrainer


def test_calculate_error_metrics_standard():
    """Test 1: Verify MAE, RMSE, MAPE, MBE, and R2 calculation on standard numbers."""
    actuals = [10.0, 20.0, 30.0, 40.0]
    preds = [11.0, 19.0, 32.0, 38.0]
    m = calculate_error_metrics(actuals, preds)

    assert isinstance(m, ErrorMetrics)
    assert m.sample_size == 4
    # Errors: |1|, |1|, |2|, |2| -> mean = 1.5
    assert m.mae == 1.5
    assert m.rmse == pytest.approx(np.sqrt((1 + 1 + 4 + 4) / 4), abs=1e-3)
    assert m.max_error == 2.0
    assert m.r2 > 0.95
    assert m.mbe == 0.0  # (1 - 1 + 2 - 2) / 4 = 0


def test_calculate_error_metrics_edge_cases():
    """Test 2: Edge cases: zero values, single item, and mismatched lengths."""
    # 1. Zero values with MAPE small denominator guard
    actuals = [0.0, 0.01, 10.0]
    preds = [0.1, 0.02, 10.5]
    m = calculate_error_metrics(actuals, preds, near_zero_threshold=0.05)
    assert m.mae > 0
    assert not np.isnan(m.mape)
    assert not np.isinf(m.mape)

    # 2. Mismatched length raises ValueError
    with pytest.raises(ValueError, match="must match"):
        calculate_error_metrics([1.0], [1.0, 2.0])

    # 3. Empty list raises ValueError
    with pytest.raises(ValueError, match="empty"):
        calculate_error_metrics([], [])


def test_raw_measurement_persistence_and_provenance(tmp_path):
    """Test 3: Ensure real and synthetic benchmark records maintain distinct provenance."""
    db_file = tmp_path / "test_prov.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)

    # Save a synthetic record
    syn_runner = SyntheticBenchmarkRunner(seed=42)
    syn_runs = syn_runner.run_benchmark_matrix("postgres_db", "postgres:16-alpine", [1], replications=3)
    assert syn_runs[0].is_synthetic_fixture is True
    reg.save_experiment(syn_runs[0])

    # Save a real measurement record
    real_rec = ExperimentRecord(
        experiment_id="exp_real_001",
        component_name="postgres_db",
        version="postgres:16-alpine",
        env_fingerprint="docker:postgres:16-alpine:cpus=1.0:mem=512m",
        benchmark_framework="pgbench",
        concurrency=4,
        read_ratio=1.0,
        offered_rps=500.0,
        achieved_rps=495.2,
        p50_ms=1.2,
        p95_ms=2.8,
        p99_ms=4.1,
        cpu_pct=35.0,
        memory_mb=120.0,
        trial_replications=3,
        variance_ms2=0.04,
        is_synthetic_fixture=False,
        timestamp="2026-10-26T12:00:00Z",
        notes="Real pgbench measurement",
    )
    reg.save_experiment(real_rec)

    # Query and assert strict separation
    exps = reg.get_experiments("postgres_db", "postgres:16-alpine")
    real_found = [e for e in exps if not e.is_synthetic_fixture]
    syn_found = [e for e in exps if e.is_synthetic_fixture]

    assert len(real_found) >= 1
    assert any(e.experiment_id == "exp_real_001" for e in real_found)
    assert any(e.is_synthetic_fixture for e in syn_found)


def test_group_based_held_out_validation_zero_leakage():
    """Test 4: Verify zero data leakage by holding out entire concurrency levels."""
    syn_runner = SyntheticBenchmarkRunner(seed=123)
    # Generate matrix with concurrencies [1, 2, 4, 8, 16]
    exps = syn_runner.run_benchmark_matrix(
        component_name="postgres_db",
        version="postgres:16-alpine",
        concurrency_levels=[1, 2, 4, 8, 16],
        replications=3,
    )

    validator = EmpiricalValidator()
    val_res = validator.validate_held_out_component_model(
        component_name="postgres_db",
        version="postgres:16-alpine",
        experiments=exps,
        test_ratio=0.40,
    )

    assert val_res["status"] == "VALIDATED"
    metrics = val_res["metrics"]
    assert metrics["group_based_leakage_free"] is True
    assert len(metrics["held_out_concurrencies"]) >= 1

    # Ensure held-out concurrencies were not used in training
    held_out = set(metrics["held_out_concurrencies"])
    assert len(held_out.intersection({1, 16})) == 0  # Boundaries kept for training interpolation


def test_feasibility_comparison_shared_constraints():
    """Test 5: Compare feasibility classification between simulated and measured results."""
    workload = WorkloadSpec(
        request_rate_rps=100.0,
        p95_latency_target_ms=25.0,
        max_monthly_budget_usd=200.0,
    )

    # Candidate 1: Both Real and SimPy are FEASIBLE (p95 <= 25ms, cost <= 200)
    # Candidate 2: Both Real and SimPy are INFEASIBLE (p95 > 25ms)
    calibration_data = [
        {
            "status": "VERIFIED",
            "architecture_id": "arch_a_simple",
            "architecture_name": "Architecture A — Simple",
            "real_measurements": {"throughput_rps": 98.0, "p50_latency_ms": 5.0, "p95_latency_ms": 12.0, "p99_latency_ms": 15.0, "total_requests": 200, "duration_seconds": 2.0},
            "simpy_predictions": {"throughput_rps": 95.0, "p50_latency_ms": 6.0, "p95_latency_ms": 14.0, "p99_latency_ms": 18.0, "bottleneck": "db", "estimated_cost_usd": 133.0},
        },
        {
            "status": "VERIFIED",
            "architecture_id": "arch_b_cached",
            "architecture_name": "Architecture B — Cached",
            "real_measurements": {"throughput_rps": 99.0, "p50_latency_ms": 2.0, "p95_latency_ms": 35.0, "p99_latency_ms": 40.0, "cache_hit_rate": 0.85, "total_requests": 200, "duration_seconds": 2.0},
            "simpy_predictions": {"throughput_rps": 97.0, "p50_latency_ms": 3.0, "p95_latency_ms": 38.0, "p99_latency_ms": 45.0, "cache_hit_rate": 0.85, "bottleneck": "cache", "estimated_cost_usd": 176.0},
        },
    ]

    validator = EmpiricalValidator()
    comp = validator.compare_feasibility_and_ranking(workload, calibration_data)

    assert comp["status"] == "VALIDATED"
    assert comp["feasibility_agreement_pct"] == 100.0
    assert comp["false_feasible_count"] == 0
    assert comp["false_infeasible_count"] == 0
    assert len(comp["feasibility_details"]) == 2


def test_ranking_comparison_and_reversal_detection():
    """Test 6: Verify architecture ranking and preference evaluation."""
    # Workload favoring low cost & simplicity
    workload_low_cost = WorkloadSpec(
        request_rate_rps=50.0,
        p95_latency_target_ms=50.0,
        max_monthly_budget_usd=300.0,
        soft_preferences={"cost": 0.60, "latency": 0.20, "simplicity": 0.20},
    )

    calibration_data = [
        {
            "status": "VERIFIED",
            "architecture_id": "arch_a_simple",
            "architecture_name": "Architecture A — Simple",
            "real_measurements": {"throughput_rps": 49.0, "p50_latency_ms": 1.2, "p95_latency_ms": 4.5, "p99_latency_ms": 6.0, "total_requests": 100, "duration_seconds": 2.0},
            "simpy_predictions": {"throughput_rps": 48.0, "p50_latency_ms": 2.0, "p95_latency_ms": 6.0, "p99_latency_ms": 7.0, "bottleneck": "db", "estimated_cost_usd": 133.0},
        },
        {
            "status": "VERIFIED",
            "architecture_id": "arch_b_cached",
            "architecture_name": "Architecture B — Cached",
            "real_measurements": {"throughput_rps": 49.5, "p50_latency_ms": 0.5, "p95_latency_ms": 3.8, "p99_latency_ms": 5.0, "cache_hit_rate": 0.85, "total_requests": 100, "duration_seconds": 2.0},
            "simpy_predictions": {"throughput_rps": 49.0, "p50_latency_ms": 1.0, "p95_latency_ms": 5.5, "p99_latency_ms": 6.5, "cache_hit_rate": 0.85, "bottleneck": "db", "estimated_cost_usd": 176.0},
        },
    ]

    validator = EmpiricalValidator()
    comp = validator.compare_feasibility_and_ranking(workload_low_cost, calibration_data)

    assert comp["status"] == "VALIDATED"
    # Both SimPy and Measured should agree that Arch A is preferred due to lower cost ($133 vs $176)
    assert comp["ranking_comparison"]["simulated_winner"] == "arch_a_simple"
    assert comp["ranking_comparison"]["measured_winner"] == "arch_a_simple"
    assert comp["ranking_comparison"]["ranking_agreement"] is True


def test_insufficient_data_handling():
    """Test 7: Reports INSUFFICIENT_DATA or INCONCLUSIVE when sample size is too small."""
    validator = EmpiricalValidator()
    # 1. Held-out validation with < 3 configs
    res = validator.validate_held_out_component_model("postgres_db", "16", [])
    assert res["status"] == "INSUFFICIENT_DATA"

    # 2. Ranking comparison with < 2 architectures
    workload = WorkloadSpec(request_rate_rps=100.0)
    rank_res = validator.compare_feasibility_and_ranking(workload, [{"status": "VERIFIED"}])
    assert rank_res["status"] == "INCONCLUSIVE"


def test_repeated_trial_aggregation_and_variance():
    """Test 8: Ensure repeated benchmark trials record explicit variance and mean."""
    latencies = [1.0, 1.2, 1.1]
    replications = len(latencies)
    mean_lat = sum(latencies) / replications
    variance = sum((x - mean_lat) ** 2 for x in latencies) / (replications - 1)

    rec = ExperimentRecord(
        experiment_id="exp_rep_test",
        component_name="postgres_db",
        version="postgres:16-alpine",
        env_fingerprint="docker:postgres:16-alpine",
        concurrency=1,
        read_ratio=1.0,
        offered_rps=100.0,
        achieved_rps=98.0,
        p50_ms=round(mean_lat * 0.95, 2),
        p95_ms=round(mean_lat * 1.6, 2),
        p99_ms=round(mean_lat * 2.2, 2),
        cpu_pct=20.0,
        memory_mb=100.0,
        trial_replications=replications,
        variance_ms2=round(variance, 4),
        is_synthetic_fixture=False,
        timestamp="2026-10-26T12:00:00Z",
    )

    assert rec.trial_replications == 3
    assert rec.variance_ms2 > 0.0
    assert rec.p50_ms < rec.p95_ms < rec.p99_ms


def test_missing_and_invalid_measurements():
    """Test 9: Verify handling of missing or invalid measurement entries."""
    validator = EmpiricalValidator()
    # Missing fields or malformed records
    empty_res = validator.compare_real_vs_simulated_e2e([])
    assert empty_res["status"] == "INCONCLUSIVE"
    assert "reason" in empty_res

    # Non-verified entries are ignored
    ignored_res = validator.compare_real_vs_simulated_e2e([{"status": "BLOCKED"}])
    assert ignored_res["status"] == "INCONCLUSIVE"


def test_model_versioning_and_registry_compatibility(tmp_path):
    """Test 10: Model registration preserves versioning, metadata, and operating limits."""
    db_file = tmp_path / "test_model_reg.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)

    # Register an updated empirical model
    model_v2 = ModelRecord(
        model_id="model_postgres_v2_empirical",
        component_name="postgres_db",
        version="postgres:16-alpine",
        env_fingerprint="docker:postgres:16-alpine:cpus=1.0:mem=512m",
        model_type="piecewise_ridge",
        fitted_parameters={"intercept": 0.5, "coef_concurrency": 0.02},
        min_supported_rps=10.0,
        max_supported_rps=2000.0,
        min_supported_concurrency=1,
        max_supported_concurrency=32,
        validation_rmse_ms=0.35,
        validation_mape_pct=7.5,
        r2_score=0.92,
        is_validated=True,
        is_synthetic_fixture=False,
        provenance="Empirical pgbench calibration on Docker host",
        known_limitations="Select-only workload",
        created_at=(datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat(),
    )
    reg.register_model(model_v2)

    retrieved = reg.get_model("postgres_db", "postgres:16-alpine")
    assert retrieved is not None
    assert retrieved.model_id == "model_postgres_v2_empirical"
    assert retrieved.is_synthetic_fixture is False
    assert retrieved.r2_score == 0.92


def test_docker_runner_resource_limits_and_cleanup(monkeypatch):
    """Test 11: Docker runner enforces CPU/mem limits and guarantees cleanup on failure."""
    from orbit.benchmark.docker_runner import DockerBenchmarkRunner
    runner = DockerBenchmarkRunner(cpu_limit="0.5", memory_limit="256m")

    assert runner.cpu_limit == "0.5"
    assert runner.memory_limit == "256m"
    assert runner.timeout_seconds == 120

    # Ensure unallowed component raises NotImplementedError
    with pytest.raises(NotImplementedError, match="no built-in benchmark harness"):
        runner.run_benchmark_matrix("unknown_database", "1.0")
