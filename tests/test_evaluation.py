"""
Unit tests for Architecture Evaluation and Recommender.
"""
from aads.core.schemas import WorkloadSpec, FeasibilityStatus
from aads.evaluation.recommender import ArchitectureRecommender


def test_feasibility_filtering(sim_engine, generator, default_workload):
    candidates = generator.generate_candidates(include_async=True)
    sim_results = [sim_engine.simulate_architecture(c, default_workload, duration_seconds=3.0) for c in candidates]
    rec = ArchitectureRecommender.evaluate_and_recommend(default_workload, sim_results)

    assert rec.status in (FeasibilityStatus.FEASIBLE, FeasibilityStatus.UNCERTAIN)
    assert len(rec.evaluations) == 3
    assert len(rec.rationale) >= 2
    assert len(rec.assumptions_cited) >= 3


def test_infeasible_budget_filtering(sim_engine, generator):
    # Very tight budget ($140/mo): Arch B ($176) and Arch C ($216) must be INFEASIBLE, Arch A ($133) FEASIBLE
    tight_budget_workload = WorkloadSpec(
        request_rate_rps=400.0,
        max_monthly_budget_usd=140.0,
        p95_latency_target_ms=50.0,
    )
    candidates = generator.generate_candidates(include_async=True)
    sim_results = [sim_engine.simulate_architecture(c, tight_budget_workload, duration_seconds=3.0) for c in candidates]
    rec = ArchitectureRecommender.evaluate_and_recommend(tight_budget_workload, sim_results)

    assert rec.selected_architecture_id == "arch_a_simple"
    b_eval = next(e for e in rec.evaluations if e.architecture_id == "arch_b_cached")
    assert b_eval.feasibility_status == FeasibilityStatus.INFEASIBLE


def test_performance_preference_selection(sim_engine, generator):
    # Performance-first preference: latency weight = 0.90, cost = 0.05
    perf_workload = WorkloadSpec(
        request_rate_rps=400.0,
        max_monthly_budget_usd=300.0,
        p95_latency_target_ms=50.0,
        soft_preferences={"cost": 0.05, "latency": 0.90, "simplicity": 0.05},
    )
    candidates = generator.generate_candidates(include_async=True)
    sim_results = [sim_engine.simulate_architecture(c, perf_workload, duration_seconds=3.0) for c in candidates]
    rec = ArchitectureRecommender.evaluate_and_recommend(perf_workload, sim_results)

    # Architecture C with async decoupling has the lowest p95 latency
    assert rec.selected_architecture_id in ("arch_c_async", "arch_b_cached")
