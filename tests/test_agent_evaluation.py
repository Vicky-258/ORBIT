"""
AADS Phase 4C Automated Test Suite: Agentic Evaluation & Decision Quality.
Validates comparative strategies (A, B, C), constraint correctness, recommendation
quality metrics, investigation usefulness, stability, scoring normalization,
provenance preservation, and offline reproducibility.
"""
import pytest
import numpy as np
from pathlib import Path
from pydantic import ValidationError

from orbit.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    FeasibilityStatus,
    ArchitectureGraph,
)
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.registry.component_registry import ComponentRegistry
from orbit.evaluation.recommender import ArchitectureRecommender
from orbit.evaluation.tradeoff_analyzer import TradeoffAnalyzer
from orbit.evaluation.feasibility_filter import FeasibilityFilter
from orbit.evaluation.scenarios import (
    EvaluationScenario,
    ScenarioClass,
    DatasetSplit,
    ExpectedReferenceOutcome,
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
    get_scenarios,
)
from orbit.evaluation.strategies import (
    run_strategy_a_fixed_pipeline,
    run_strategy_b_deterministic_adaptive,
    run_strategy_c_llm_adaptive,
    StrategyExecutionResult,
)
from orbit.evaluation.metrics import (
    compute_metrics,
    DecisionQualityMetrics,
)
from orbit.evaluation.runner import run_evaluation_suite
from orbit.simulation.metrics_collector import SimulationMetricsCollector, RequestTrace


def make_dummy_sim_result(
    arch_id: str,
    arch_name: str,
    p95: float,
    cost: float,
    throughput: float = 500.0,
    uncertainty: tuple = (0.0, 0.0),
) -> SimulationResult:
    return SimulationResult(
        architecture_id=arch_id,
        architecture_name=arch_name,
        throughput_achieved_rps=throughput,
        p50_latency_ms=round(p95 * 0.5, 2),
        p90_latency_ms=round(p95 * 0.8, 2),
        p95_latency_ms=p95,
        p99_latency_ms=round(p95 * 1.2, 2),
        max_latency_ms=round(p95 * 1.5, 2),
        error_rate_pct=0.0,
        total_requests=1000,
        completed_requests=1000,
        error_count=0,
        avg_queue_length=1.0,
        max_queue_length=5,
        component_utilizations={"db": 0.5},
        bottleneck_component="db",
        estimated_monthly_cost_usd=cost,
        simulation_duration_seconds=5.0,
        random_seed=42,
        latency_uncertainty_p95_ms=uncertainty,
    )


# ---------------------------------------------------------------------------
# Test 1: All three strategies run against the same frozen scenario
# ---------------------------------------------------------------------------
def test_all_three_strategies_run_on_same_scenario():
    scenario = DEV_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_a = run_strategy_a_fixed_pipeline(scenario, registry=reg)
    res_b = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
    res_c = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")

    assert res_a.strategy_name == "strategy_a_fixed"
    assert res_b.strategy_name == "strategy_b_deterministic"
    assert res_c.strategy_name == "strategy_c_llm"

    assert res_a.scenario_id == scenario.scenario_id
    assert res_b.scenario_id == scenario.scenario_id
    assert res_c.scenario_id == scenario.scenario_id

    # All three must share identical initial candidate simulation results
    assert res_a.selected_architecture_id == res_b.selected_architecture_id == res_c.selected_architecture_id
    assert res_a.status == res_b.status == res_c.status


# ---------------------------------------------------------------------------
# Test 2: Candidate ordering does not change deterministic evaluation results
# ---------------------------------------------------------------------------
def test_candidate_order_invariance():
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
        cache_assumed_hit_rate=0.85,
        soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
    )
    sim1 = make_dummy_sim_result("arch_a_simple", "Architecture A", p95=20.0, cost=133.0, uncertainty=(18.5, 21.5))
    sim2 = make_dummy_sim_result("arch_b_cached", "Architecture B", p95=7.3, cost=176.0, uncertainty=(6.8, 7.8))
    sim3 = make_dummy_sim_result("arch_c_async", "Architecture C", p95=3.3, cost=216.0, uncertainty=(3.1, 3.5))

    rec_normal = ArchitectureRecommender.evaluate_and_recommend(workload, [sim1, sim2, sim3])
    rec_reversed = ArchitectureRecommender.evaluate_and_recommend(workload, [sim3, sim2, sim1])
    rec_permuted = ArchitectureRecommender.evaluate_and_recommend(workload, [sim2, sim1, sim3])

    assert rec_normal.selected_architecture_id == rec_reversed.selected_architecture_id == rec_permuted.selected_architecture_id
    assert [e.architecture_id for e in rec_normal.evaluations] == [e.architecture_id for e in rec_reversed.evaluations]


# ---------------------------------------------------------------------------
# Test 3: Hard constraint violations are detected and counted correctly
# ---------------------------------------------------------------------------
def test_hard_constraint_violations_counted_correctly():
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        p95_latency_target_ms=10.0,
        min_throughput_rps=480.0,
        max_monthly_budget_usd=150.0,
        hard_constraints=["p95_latency", "min_throughput", "max_budget"],
    )
    sim_violating_budget = make_dummy_sim_result("arch_b_cached", "Architecture B", p95=7.0, cost=176.0, uncertainty=(6.5, 7.5))
    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_violating_budget)
    assert status == FeasibilityStatus.INFEASIBLE
    budget_chk = next(c for c in checks if c.criterion == "max_budget")
    assert budget_chk.status == FeasibilityStatus.INFEASIBLE


# ---------------------------------------------------------------------------
# Test 4: Infeasible workload scenarios are handled correctly
# ---------------------------------------------------------------------------
def test_no_feasible_candidate_handled_correctly():
    scenario = next(s for s in DEV_SCENARIOS if s.scenario_class == ScenarioClass.INFEASIBLE_WORKLOAD)
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res = run_strategy_a_fixed_pipeline(scenario, registry=reg)
    metrics = compute_metrics(scenario, res)

    assert metrics.infeasible_workload_detected is True
    assert metrics.infeasible_candidate_recommended is False
    assert metrics.hard_constraints_satisfied is True
    assert res.status == FeasibilityStatus.INFEASIBLE


# ---------------------------------------------------------------------------
# Test 5: Inconclusive outcomes are not misreported as successful recommendations
# ---------------------------------------------------------------------------
def test_inconclusive_outcomes_not_misreported_as_successful():
    scenario = next(s for s in DEV_SCENARIOS if s.scenario_class == ScenarioClass.INSUFFICIENT_EVIDENCE)
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
    metrics = compute_metrics(scenario, res)

    assert metrics.inconclusive_correctly_reported is True
    assert res.status == FeasibilityStatus.INFEASIBLE


# ---------------------------------------------------------------------------
# Test 6: Synthetic fixture expectations are kept separate from empirical reference outcomes
# ---------------------------------------------------------------------------
def test_synthetic_fixtures_separated_from_empirical_references():
    for sc in DEV_SCENARIOS + HELDOUT_SCENARIOS:
        prov = sc.expected_reference.reference_provenance
        assert prov in ("synthetic_fixture", "empirical_measurement")
        assert len(prov) > 0


# ---------------------------------------------------------------------------
# Test 7: LLM planner output cannot modify simulation metrics or objective weights
# ---------------------------------------------------------------------------
def test_llm_planner_cannot_modify_simulation_metrics():
    scenario = DEV_SCENARIOS[1]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_a = run_strategy_a_fixed_pipeline(scenario, registry=reg)
    res_c = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")

    assert res_a.predicted_metrics.get("p95_latency_ms") == res_c.predicted_metrics.get("p95_latency_ms")
    assert res_a.predicted_metrics.get("estimated_monthly_cost_usd") == res_c.predicted_metrics.get("estimated_monthly_cost_usd")


# ---------------------------------------------------------------------------
# Test 8: Disallowed or invalid actions are rejected by schema or policy
# ---------------------------------------------------------------------------
def test_disallowed_actions_rejected_by_policy():
    from orbit.agent.schemas import InvestigationDecision, InvestigationActionType
    from orbit.agent.investigation_policy import InvestigationPolicy, PolicyVerdict

    # 1. Pydantic validation rejects unapproved action strings
    with pytest.raises(ValidationError):
        InvestigationDecision(
            action="execute_arbitrary_shell",
            reason="Testing security boundary",
        )

    # 2. Policy rejects unknown candidate ID
    policy = InvestigationPolicy()
    state = {"candidate_architectures": [], "simulation_results": []}
    decision = InvestigationDecision(
        action=InvestigationActionType.SIMULATE_CANDIDATE,
        target="non_existent_arch_999",
        reason="Testing invalid target",
    )
    val = policy.evaluate_action(decision, state)
    assert val.verdict == PolicyVerdict.REJECTED
    assert "does not exist in generated candidates" in val.reason


# ---------------------------------------------------------------------------
# Test 9: Repeated actions and exhausted budgets are recorded correctly
# ---------------------------------------------------------------------------
def test_repeated_actions_and_exhausted_budgets():
    from orbit.agent.schemas import InvestigationDecision, InvestigationActionType
    from orbit.agent.investigation_policy import InvestigationPolicy, PolicyVerdict

    policy = InvestigationPolicy()
    state = {
        "investigation_round": 3,
        "max_investigation_rounds": 3,
        "candidate_architectures": [],
        "simulation_results": [],
    }
    decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        reason="Trying another round",
    )
    val = policy.evaluate_action(decision, state)
    assert val.verdict == PolicyVerdict.STOPPED
    assert "round limit" in val.reason.lower()


# ---------------------------------------------------------------------------
# Test 10: Investigation usefulness calculated from evidence, not action count alone
# ---------------------------------------------------------------------------
def test_investigation_usefulness_calculation():
    scenario_obvious = next(s for s in DEV_SCENARIOS if s.scenario_class == ScenarioClass.UNNECESSARY_INVESTIGATION)
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_fixed = run_strategy_a_fixed_pipeline(scenario_obvious, registry=reg)
    res_adapt = run_strategy_b_deterministic_adaptive(scenario_obvious, registry=reg)

    m_fixed = compute_metrics(scenario_obvious, res_fixed)
    m_adapt = compute_metrics(scenario_obvious, res_adapt)

    assert m_fixed.investigation_usefulness_score >= m_adapt.investigation_usefulness_score


# ---------------------------------------------------------------------------
# Test 11: LLM failure triggers documented fallback
# ---------------------------------------------------------------------------
def test_llm_failure_triggers_documented_fallback():
    scenario = next(s for s in DEV_SCENARIOS if s.scenario_class == ScenarioClass.PROVIDER_FAILURE)
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_c = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")
    assert res_c.fallback_used is True
    assert res_c.selected_architecture_id is not None
    assert res_c.status == FeasibilityStatus.FEASIBLE


# ---------------------------------------------------------------------------
# Test 12: Provenance is retained through final report
# ---------------------------------------------------------------------------
def test_provenance_retention():
    scenario = DEV_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_a = run_strategy_a_fixed_pipeline(scenario, registry=reg)
    assert "pipeline" in res_a.provenance_map
    assert res_a.provenance_map["pipeline"] == "deterministic_fixed"


# ---------------------------------------------------------------------------
# Test 13: Scoring normalization and Phase 4B B vs C ranking regression
# ---------------------------------------------------------------------------
def test_phase_4b_b_vs_c_ranking_regression():
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
        soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
    )
    sim_a = make_dummy_sim_result("arch_a_simple", "Architecture A", p95=19.8, cost=133.0)
    sim_b = make_dummy_sim_result("arch_b_cached", "Architecture B", p95=7.25, cost=176.0)
    sim_c = make_dummy_sim_result("arch_c_async", "Architecture C", p95=3.30, cost=216.0)

    rec = ArchitectureRecommender.evaluate_and_recommend(workload, [sim_a, sim_b, sim_c])
    assert rec.selected_architecture_id == "arch_b_cached"

    eval_b = next(e for e in rec.evaluations if e.architecture_id == "arch_b_cached")
    eval_c = next(e for e in rec.evaluations if e.architecture_id == "arch_c_async")
    assert eval_b.overall_score > eval_c.overall_score


# ---------------------------------------------------------------------------
# Test 14: Confidence intervals audited and labeled heuristic
# ---------------------------------------------------------------------------
def test_confidence_interval_audit_heuristics():
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
    bounds = summary.get("latency_uncertainty_p95_ms")
    assert bounds is not None
    assert bounds[0] <= bounds[1]
    p95 = summary.get("p95_latency_ms")
    assert bounds[0] <= p95 <= bounds[1]


# ---------------------------------------------------------------------------
# Test 15: Evaluation results reproducible under fixed offline inputs
# ---------------------------------------------------------------------------
def test_evaluation_reproducibility():
    scenario = DEV_SCENARIOS[1]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res1 = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
    res2 = run_strategy_b_deterministic_adaptive(scenario, registry=reg)

    assert res1.selected_architecture_id == res2.selected_architecture_id
    assert res1.candidate_rankings == res2.candidate_rankings
    assert res1.candidate_scores == res2.candidate_scores
    assert res1.investigation_rounds == res2.investigation_rounds


# ---------------------------------------------------------------------------
# Test 16: Stability under +/- 5% workload perturbation
# ---------------------------------------------------------------------------
def test_perturbation_sensitivity():
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    base_scenario = DEV_SCENARIOS[1]
    w_base = base_scenario.workload_spec

    w_plus = w_base.model_copy(update={"request_rate_rps": w_base.request_rate_rps * 1.05})
    w_minus = w_base.model_copy(update={"request_rate_rps": w_base.request_rate_rps * 0.95})

    sc_plus = base_scenario.model_copy(update={"workload_spec": w_plus})
    sc_minus = base_scenario.model_copy(update={"workload_spec": w_minus})

    res_base = run_strategy_a_fixed_pipeline(base_scenario, registry=reg)
    res_plus = run_strategy_a_fixed_pipeline(sc_plus, registry=reg)
    res_minus = run_strategy_a_fixed_pipeline(sc_minus, registry=reg)

    assert res_base.selected_architecture_id == res_plus.selected_architecture_id == res_minus.selected_architecture_id


# ---------------------------------------------------------------------------
# Test 17: Full suite runs across Development and Held-Out sets
# ---------------------------------------------------------------------------
def test_full_suite_runs_development_and_heldout():
    dev_res = run_evaluation_suite(DEV_SCENARIOS, suite_name="dev_test", mode="offline")
    heldout_res = run_evaluation_suite(HELDOUT_SCENARIOS, suite_name="heldout_test", mode="offline")

    assert dev_res.scenarios_evaluated_count == 12
    assert heldout_res.scenarios_evaluated_count == 12
    assert len(dev_res.aggregate_summaries) == 3
    assert len(heldout_res.aggregate_summaries) == 3

    for sname, agg in dev_res.aggregate_summaries.items():
        assert agg.sample_size == 12
        assert agg.mean_constraint_correctness > 0.9
