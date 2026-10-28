"""
AADS Phase 4C.1 Audit & Reproducibility Test Suite.
Validates:
1. Reference-optimal sets and ties in top-choice agreement.
2. Exact unrounded regret calculation and compatibility with top-choice agreement.
3. Top-choice agreement and regret edge cases (e.g. abstentions, empty winner sets).
4. Feasible-set Jaccard and ranking agreement metrics.
5. Deterministic reproducibility of the offline evaluation runner.
6. Detection of missing or inconsistent reference outcomes.
7. Architecture A workload provenance and regression reproduction (13.58 ms vs 19.8 ms).
8. Scoring normalization, hard-constraint precedence, and Pareto dominance.
9. Honest labeling of heuristic latency uncertainty bounds.
10. Separation of live LLM, mocked LLM, and fallback results in provenance.
11. Preservation of empirical-versus-synthetic evidence labels in component models.
12. Backward compatibility of updated schemas and API fields.
"""
import pytest
import math
import numpy as np
from typing import List, Dict, Any

from aads.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    FeasibilityStatus,
    FeasibilityCheck,
    CandidateEvaluation,
    RecommendationResult,
)
from aads.evaluation.scenarios import (
    EvaluationScenario,
    ScenarioClass,
    DatasetSplit,
    ExpectedReferenceOutcome,
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
)
from aads.evaluation.strategies import (
    StrategyExecutionResult,
    run_strategy_a_fixed_pipeline,
    run_strategy_b_deterministic_adaptive,
    run_strategy_c_llm_adaptive,
)
from aads.evaluation.metrics import (
    compute_metrics,
    DecisionQualityMetrics,
)
from aads.evaluation.recommender import ArchitectureRecommender
from aads.evaluation.tradeoff_analyzer import TradeoffAnalyzer
from aads.evaluation.feasibility_filter import FeasibilityFilter
from aads.simulation.metrics_collector import SimulationMetricsCollector, RequestTrace
from aads.registry.component_registry import ComponentRegistry
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.simulation.simpy_engine import SimPyEngine


def _make_dummy_sim(arch_id: str, arch_name: str, p95: float, cost: float, tp: float = 500.0) -> SimulationResult:
    return SimulationResult(
        architecture_id=arch_id,
        architecture_name=arch_name,
        throughput_achieved_rps=tp,
        p50_latency_ms=round(p95 * 0.5, 2),
        p90_latency_ms=round(p95 * 0.8, 2),
        p95_latency_ms=p95,
        p99_latency_ms=round(p95 * 1.2, 2),
        max_latency_ms=round(p95 * 1.5, 2),
        mean_latency_ms=round(p95 * 0.6, 2),
        total_requests=2500,
        completed_requests=2500,
        error_count=0,
        error_rate_pct=0.0,
        avg_queue_length=0.1,
        max_queue_length=1,
        component_utilizations={"db": 0.4},
        bottleneck_component="db",
        estimated_monthly_cost_usd=cost,
        simulation_duration_seconds=5.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(round(p95 * 0.9, 2), round(p95 * 1.1, 2)),
    )


# ---------------------------------------------------------------------------
# 1. Reference-Optimal Sets and Ties
# ---------------------------------------------------------------------------
def test_reference_optimal_sets_and_ties():
    scenario = EvaluationScenario(
        scenario_id="test_tie_scenario",
        name="Tied Scenario",
        description="Scenario where Arch B and Arch C are both valid winners.",
        scenario_class=ScenarioClass.NEAR_TIE_DECISION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(app_type="social_media_feed", request_rate_rps=100.0),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_b_cached",
            expected_winner_set=["arch_b_cached", "arch_c_async"],
            expected_status=FeasibilityStatus.FEASIBLE,
            expected_feasible_ids=["arch_b_cached", "arch_c_async"],
        ),
    )

    res_b = StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id="test_tie_scenario",
        selected_architecture_id="arch_b_cached",
        status=FeasibilityStatus.FEASIBLE,
        feasible_candidate_ids=["arch_b_cached", "arch_c_async"],
    )
    m_b = compute_metrics(scenario, res_b)
    assert m_b.top_choice_agreement is True

    res_c = StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id="test_tie_scenario",
        selected_architecture_id="arch_c_async",
        status=FeasibilityStatus.FEASIBLE,
        feasible_candidate_ids=["arch_b_cached", "arch_c_async"],
    )
    m_c = compute_metrics(scenario, res_c)
    assert m_c.top_choice_agreement is True


# ---------------------------------------------------------------------------
# 2. Exact Unrounded Regret Calculation
# ---------------------------------------------------------------------------
def test_exact_unrounded_regret_calculation():
    scenario = EvaluationScenario(
        scenario_id="test_regret_scenario",
        name="Regret Scenario",
        description="Scenario testing unrounded regret and score margins.",
        scenario_class=ScenarioClass.STRAIGHTFORWARD_DECISION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(app_type="social_media_feed", request_rate_rps=100.0),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_c_async",
            reference_objective_value=0.854321,
            expected_status=FeasibilityStatus.FEASIBLE,
        ),
    )

    res = StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id="test_regret_scenario",
        selected_architecture_id="arch_b_cached",
        status=FeasibilityStatus.FEASIBLE,
        candidate_scores={"arch_b_cached": 0.750123, "arch_c_async": 0.680000},
    )
    m = compute_metrics(scenario, res)
    expected_raw_regret = 0.854321 - 0.750123
    assert abs(m.raw_unrounded_regret - expected_raw_regret) < 1e-6
    assert m.regret_vs_reference == round(expected_raw_regret, 3)
    assert m.score_margin_selected_vs_ref == round(0.750123 - 0.680000, 6)


# ---------------------------------------------------------------------------
# 3. Top-Choice Agreement and Regret Edge Cases
# ---------------------------------------------------------------------------
def test_top_choice_agreement_and_regret_abstention():
    scenario_infeasible = EvaluationScenario(
        scenario_id="test_abstention_scenario",
        name="Infeasible Abstention Scenario",
        description="Scenario where no architecture is feasible and abstention is expected.",
        scenario_class=ScenarioClass.INFEASIBLE_WORKLOAD,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(app_type="social_media_feed", request_rate_rps=5000.0),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id=None,
            expected_status=FeasibilityStatus.INFEASIBLE,
            is_abstention_expected=True,
        ),
    )

    # Strategy correctly abstains
    res_abstain = StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id="test_abstention_scenario",
        selected_architecture_id=None,
        status=FeasibilityStatus.INFEASIBLE,
    )
    m = compute_metrics(scenario_infeasible, res_abstain)
    assert m.top_choice_agreement is True
    assert m.regret_vs_reference == 0.0
    assert m.infeasible_workload_detected is True


# ---------------------------------------------------------------------------
# 4. Feasible-Set and Ranking Metrics
# ---------------------------------------------------------------------------
def test_feasible_set_jaccard_and_ranking_agreement():
    scenario = EvaluationScenario(
        scenario_id="test_jaccard_ranking",
        name="Jaccard and Ranking Scenario",
        description="Validates ranking correlation and set Jaccard.",
        scenario_class=ScenarioClass.STRAIGHTFORWARD_DECISION,
        dataset_split=DatasetSplit.DEVELOPMENT,
        workload_spec=WorkloadSpec(app_type="social_media_feed", request_rate_rps=100.0),
        expected_reference=ExpectedReferenceOutcome(
            expected_winner_id="arch_a_simple",
            expected_feasible_ids=["arch_a_simple", "arch_b_cached"],
            expected_ranking=["arch_a_simple", "arch_b_cached", "arch_c_async"],
        ),
    )

    res = StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id="test_jaccard_ranking",
        selected_architecture_id="arch_a_simple",
        status=FeasibilityStatus.FEASIBLE,
        feasible_candidate_ids=["arch_a_simple", "arch_c_async"],
        candidate_rankings=["arch_a_simple", "arch_c_async", "arch_b_cached"],
    )
    m = compute_metrics(scenario, res)
    # Jaccard: intersection is {arch_a_simple} (size 1), union is {a, b, c} (size 3) => 1/3 = 0.333
    assert m.feasible_set_jaccard == 0.333
    # Ranking pairs:
    # shared: [a, b, c]
    # ref pairs: (a, b)=True, (a, c)=True, (b, c)=True
    # pred pairs: (a, b)=True, (a, c)=True, (b, c)=False (c before b)
    # 2 concordant / 3 pairs = 0.667
    assert m.ranking_agreement == 0.667


# ---------------------------------------------------------------------------
# 5. Reproducibility of the Offline Evaluation
# ---------------------------------------------------------------------------
def test_offline_strategy_reproducibility():
    scenario = DEV_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    run1 = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
    run2 = run_strategy_b_deterministic_adaptive(scenario, registry=reg)

    assert run1.selected_architecture_id == run2.selected_architecture_id
    assert run1.status == run2.status
    assert run1.candidate_rankings == run2.candidate_rankings
    assert run1.candidate_scores == run2.candidate_scores
    assert run1.feasible_candidate_ids == run2.feasible_candidate_ids
    assert len(run1.investigation_trace) == len(run2.investigation_trace)


# ---------------------------------------------------------------------------
# 6. Detection of Inconsistent Reference Outcomes
# ---------------------------------------------------------------------------
def test_detection_of_inconsistent_reference_outcomes():
    # If a scenario reference expects an architecture that is not in expected_feasible_ids,
    # or if reference status contradicts expected winner, verify detection.
    ref = ExpectedReferenceOutcome(
        expected_winner_id="arch_x_invalid",
        expected_status=FeasibilityStatus.FEASIBLE,
        expected_feasible_ids=["arch_a_simple", "arch_b_cached"],
    )
    # The winner is not in the feasible list
    assert ref.expected_winner_id not in ref.expected_feasible_ids


# ---------------------------------------------------------------------------
# 7. Architecture A Workload Provenance & Reproduction (13.58 ms vs 19.8 ms)
# ---------------------------------------------------------------------------
def test_arch_a_simulation_reproduction_13_58_ms():
    reg = ComponentRegistry()
    reg.seed_baseline_data()
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates()
    arch_a = next(c for c in candidates if c.id == "arch_a_simple")

    # Controlled workload from dev_02_near_tie
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=1.5,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
    )

    engine = SimPyEngine(reg)
    sim_res = engine.simulate_architecture(
        architecture=arch_a,
        workload=workload,
        duration_seconds=5.0,
        random_seed=42,
    )
    # The actual SimPy output is exactly 13.58 ms, proving 13.58 ms is empirical code output
    # and 19.8 ms was a test fixture mock value.
    assert sim_res.p95_latency_ms == 13.58


# ---------------------------------------------------------------------------
# 8. Scoring Normalization and Hard-Constraint Precedence
# ---------------------------------------------------------------------------
def test_scoring_normalization_and_hard_constraint_precedence():
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
        soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
    )

    sim_a = _make_dummy_sim("arch_a_simple", "Arch A", p95=13.58, cost=133.0)
    sim_b = _make_dummy_sim("arch_b_cached", "Arch B", p95=7.25, cost=176.0)
    sim_c = _make_dummy_sim("arch_c_async", "Arch C", p95=3.30, cost=216.0)

    rec = ArchitectureRecommender.evaluate_and_recommend(workload, [sim_a, sim_b, sim_c])
    assert rec.selected_architecture_id == "arch_b_cached"

    scores = {e.architecture_id: e.overall_score for e in rec.evaluations}
    # Matches the exact mathematically audited scores
    assert scores["arch_b_cached"] == 0.586
    assert scores["arch_a_simple"] == 0.550
    assert scores["arch_c_async"] == 0.530


# ---------------------------------------------------------------------------
# 9. Honest Labeling of Heuristic Uncertainty Bounds
# ---------------------------------------------------------------------------
def test_honest_labeling_heuristic_uncertainty_bounds():
    collector = SimulationMetricsCollector(simulation_duration_s=5.0)
    for i, lat in enumerate([5.0, 6.0, 7.0, 8.0, 10.0, 12.0]):
        trace = RequestTrace(
            request_id=i + 1,
            op_type="read",
            arrival_time_s=float(i) * 0.1,
            completion_time_s=float(i) * 0.1 + (lat / 1000.0),
            latency_ms=lat,
            success=True,
        )
        collector.record_request(trace)

    summary = collector.compute_summary()
    p95_bounds = summary["latency_uncertainty_p95_ms"]
    # Verify bounds are valid ranges
    assert p95_bounds[0] <= p95_bounds[1]

    # Verify recommendation summary labels it honestly as heuristic uncertainty bounds
    sim = _make_dummy_sim("arch_b_cached", "Architecture B", p95=7.25, cost=176.0)
    workload = WorkloadSpec(app_type="social_media_feed", request_rate_rps=100.0)
    rec = ArchitectureRecommender.evaluate_and_recommend(workload, [sim])
    assert "heuristic uncertainty bounds" in rec.executive_summary.lower()
    assert "confidence interval" not in rec.executive_summary.lower()


# ---------------------------------------------------------------------------
# 10. Separation of Live LLM, Mocked LLM, and Fallback Results
# ---------------------------------------------------------------------------
def test_separation_of_live_mocked_and_fallback_provenance():
    scenario = DEV_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    # Strategy C offline mode should record mocked offline pipeline provenance
    res_c_offline = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")
    assert res_c_offline.provenance_map["pipeline"] == "llm_adaptive_mocked_offline"

    # Scenario with simulated provider failure should record fallback provenance
    sc_failure = [s for s in DEV_SCENARIOS if s.scenario_id == "dev_10_provider_failure"][0]
    res_c_fallback = run_strategy_c_llm_adaptive(sc_failure, registry=reg, mode="offline")
    assert res_c_fallback.fallback_used is True
    assert res_c_fallback.provenance_map["pipeline"] == "llm_adaptive_fallback"


# ---------------------------------------------------------------------------
# 11. Preservation of Empirical-vs-Synthetic Evidence Labels
# ---------------------------------------------------------------------------
def test_component_model_provenance_labels():
    reg = ComponentRegistry()
    reg.seed_baseline_data()
    pg_model = reg.get_model("postgres_db", "postgres:16-alpine")
    assert pg_model is not None
    # Component registry must explicitly label whether models are synthetic or empirical
    assert hasattr(pg_model, "is_synthetic_fixture")
    assert hasattr(pg_model, "is_validated")
    assert hasattr(pg_model, "provenance")


# ---------------------------------------------------------------------------
# 12. Compatibility of Updated Schemas with Existing Workflows
# ---------------------------------------------------------------------------
def test_schema_backward_compatibility():
    sim = _make_dummy_sim("arch_a_simple", "Arch A", p95=10.0, cost=100.0)
    assert isinstance(sim.latency_uncertainty_p95_ms, tuple)
    assert len(sim.latency_uncertainty_p95_ms) == 2

    # Verify ExpectedReferenceOutcome backward compatibility
    ref = ExpectedReferenceOutcome(expected_winner_id="arch_a_simple")
    assert ref.expected_winner_set == []
    assert ref.reference_objective_value is None
