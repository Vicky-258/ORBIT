"""
End-to-End Integration Tests.
Validates the complete workflow from workload specification to explainable recommendation.
"""
from fastapi.testclient import TestClient
from aads.api.app import app
from aads.core.schemas import WorkloadSpec, FeasibilityStatus
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.registry.component_registry import ComponentRegistry
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.modeling.model_trainer import ModelTrainer
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender


def test_end_to_end_python_workflow(tmp_path):
    # 1. User submits workload specification
    workload = WorkloadSpec(
        request_rate_rps=400.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=45.0,
        min_throughput_rps=350.0,
        max_monthly_budget_usd=250.0,
        cache_assumed_hit_rate=0.85,
    )
    assert len(workload.provenance_map) > 0

    # 2. Generator produces candidate architectures
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates(include_async=True, include_unsupported=True)
    assert len(candidates) == 4

    # 3. Model registry checks compatibility & discovers missing model
    db_path = tmp_path / "e2e_registry.db"
    registry = ComponentRegistry(db_path=db_path)
    registry.seed_baseline_data(force=True)

    status_pg, model_pg, _ = registry.check_compatibility("postgres_db", "postgres:16-alpine", workload)
    assert status_pg == "VALIDATED"

    status_mg, model_mg, _ = registry.check_compatibility("mongodb_cluster", "mongodb:7.0-cluster", workload)
    assert status_mg == "MISSING"

    # 4. Agent runs controlled benchmark to calibrate missing model across sufficient concurrency
    runner = SyntheticBenchmarkRunner(seed=999)
    benchmark_trials = runner.run_benchmark_matrix(
        component_name="mongodb_cluster",
        version="mongodb:7.0-cluster",
        concurrency_levels=[1, 4, 8, 16, 24, 32],
        replications=3,
    )
    assert len(benchmark_trials) == 6

    # 5. Fit & validate model on held-out observations
    mg_model, metrics = ModelTrainer.train_and_validate(
        component_name="mongodb_cluster",
        version="mongodb:7.0-cluster",
        experiments=benchmark_trials,
    )
    assert mg_model.is_validated is True
    registry.register_model(mg_model)

    # Re-check compatibility: now validated!
    status_mg_after, model_mg_after, _ = registry.check_compatibility("mongodb_cluster", "mongodb:7.0-cluster", workload)
    assert status_mg_after == "VALIDATED"

    # 6. Discrete-Event SimPy simulation
    sim_engine = SimPyEngine(registry=registry)
    simulatable_candidates = [c for c in candidates if c.id != "arch_mongo_unregistered"]
    sim_results = [
        sim_engine.simulate_architecture(c, workload, duration_seconds=4.0, random_seed=42)
        for c in simulatable_candidates
    ]
    assert len(sim_results) == 3

    # 7. Evaluate and Recommend
    recommendation = ArchitectureRecommender.evaluate_and_recommend(workload, sim_results)
    assert recommendation.selected_architecture_id in ("arch_a_simple", "arch_b_cached", "arch_c_async")
    assert recommendation.status == FeasibilityStatus.FEASIBLE
    assert len(recommendation.rationale) >= 2
    assert len(recommendation.assumptions_cited) >= 3
    assert recommendation.recommended_next_experiment is not None


def test_end_to_end_fastapi_workflow():
    client = TestClient(app)

    payload = {
        "workload": {
            "app_type": "social_media_feed",
            "request_rate_rps": 400.0,
            "peak_load_factor": 2.0,
            "read_ratio": 0.90,
            "write_ratio": 0.10,
            "p95_latency_target_ms": 50.0,
            "min_throughput_rps": 350.0,
            "max_monthly_budget_usd": 250.0,
            "cache_assumed_hit_rate": 0.85,
            "hard_constraints": ["p95_latency", "min_throughput", "max_budget"],
            "soft_preferences": {"cost": 0.35, "latency": 0.45, "simplicity": 0.20}
        },
        "include_async": True,
        "include_unsupported": False,
        "simulation_duration_seconds": 3.0,
        "auto_benchmark_missing": True,
        "force_synthetic": True
    }

    res = client.post("/api/workflow/run", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "candidates" in data
    assert "simulation_results" in data
    assert "recommendation" in data
    rec = data["recommendation"]
    assert rec["selected_architecture_id"] is not None
    assert rec["executive_summary"] != ""
    assert len(rec["evaluations"]) >= 2
