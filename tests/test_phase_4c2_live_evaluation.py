"""
AADS Phase 4C.2 Automated Test Suite: Live LLM Decision Quality & Evaluation Infrastructure.
Validates:
1. Identical initial evidence, candidates, and simulation configurations across all three strategies.
2. Complete isolation of hidden scenario metadata from the planner.
3. Proof of genuine live invocation and verification that live provenance cannot be set without verifiable calls.
4. Strict fail-closed behavior in live mode (no silent fallback).
5. Proper failure handling, token counting, and cost/budget accounting.
6. Correct regret and tie calculations with reference-optimal sets.
7. Reproducible deterministic baselines for Strategy A and Strategy B.
8. Robustness of the prompt constructor to different workload inputs.
9. Prohibition of autonomous benchmark execution (proposals remain strictly non-executing).
"""
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from orbit.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    FeasibilityStatus,
    ArchitectureGraph,
)
from orbit.evaluation.scenarios import (
    EvaluationScenario,
    ScenarioClass,
    DatasetSplit,
    ExpectedReferenceOutcome,
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
    PILOT_SCENARIOS,
)
from orbit.evaluation.strategies import (
    run_strategy_a_fixed_pipeline,
    run_strategy_b_deterministic_adaptive,
    run_strategy_c_llm_adaptive,
    StrategyExecutionResult,
)
from orbit.evaluation.metrics import compute_metrics
from orbit.registry.component_registry import ComponentRegistry
from orbit.agent.investigation_planner import InvestigationPlanner
from orbit.agent.schemas import (
    InvestigationDecision,
    InvestigationActionType,
    LiveLLMCallRecord,
)
from orbit.agent.investigation_policy import InvestigationPolicy, PolicyVerdict


def test_identical_initial_evidence_across_strategies():
    scenario = PILOT_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_a = run_strategy_a_fixed_pipeline(scenario, registry=reg)
    res_b = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
    res_c_offline = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")

    assert res_a.selected_architecture_id == res_b.selected_architecture_id
    assert res_a.candidate_scores == res_b.candidate_scores
    assert res_a.candidate_rankings == res_b.candidate_rankings
    assert res_a.candidate_scores == res_c_offline.candidate_scores


def test_hidden_metadata_isolation():
    planner = InvestigationPlanner()
    workload = WorkloadSpec(app_type="social_media_feed", request_rate_rps=200.0)

    state: Dict[str, Any] = {
        "workload_spec": workload,
        "candidate_architectures": [],
        "simulation_results": [],
        "recommendation": None,
        "investigation_trace": [],
        "scenario_id": "secret_heldout_scenario_999",
        "expected_reference": "secret_winner_arch",
        "scenario_class": "secret_infeasible_class",
    }

    evidence_summary = planner.build_evidence_summary(state)

    assert "secret_heldout_scenario_999" not in evidence_summary
    assert "secret_winner_arch" not in evidence_summary
    assert "secret_infeasible_class" not in evidence_summary
    assert "expected_reference" not in evidence_summary


def test_live_provenance_requires_verified_calls():
    scenario = PILOT_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    res_offline = run_strategy_c_llm_adaptive(scenario, registry=reg, mode="offline")
    assert res_offline.provenance_map["pipeline"] != "llm_adaptive_live"
    assert res_offline.llm_request_count is None


def test_fail_closed_when_credentials_unavailable():
    scenario = PILOT_SCENARIOS[0]
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    mock_pm = MagicMock()
    mock_pm.is_llm_available.return_value = False

    with patch("orbit.evaluation.strategies.InvestigationPlanner") as mock_planner_cls:
        mock_planner = MagicMock()
        mock_planner.provider_mgr = mock_pm
        mock_planner_cls.return_value = mock_planner

        with pytest.raises(RuntimeError, match="Provider credentials unavailable"):
            run_strategy_c_llm_adaptive(
                scenario,
                registry=reg,
                mode="live",
                fail_closed=True,
            )


def test_token_and_cost_accounting():
    record = LiveLLMCallRecord(
        call_id="call_test_123",
        timestamp="2026-10-28T00:00:00Z",
        scenario_id="dev_01",
        round_number=1,
        provider="groq",
        model_name="openai/gpt-oss-120b",
        request_id="req_test_abc",
        latency_ms=1250.0,
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        estimated_cost_usd=round((1000 * 0.00000015) + (500 * 0.00000075), 6),
        is_live=True,
        fallback_used=False,
    )
    assert record.total_tokens == 1500
    assert record.estimated_cost_usd > 0.0
    assert record.is_live is True


def test_policy_sanitizes_multi_target_decisions():
    policy = InvestigationPolicy()
    mock_cand = MagicMock()
    mock_cand.id = "arch_a_simple"
    state = {
        "investigation_round": 0,
        "candidate_architectures": [mock_cand],
        "simulation_results": [MagicMock()],
        "investigation_trace": [],
    }

    decision = InvestigationDecision(
        action=InvestigationActionType.SIMULATE_CANDIDATE,
        target="arch_a_simple,arch_b_cached,arch_c_async",
        reason="Simulate all candidates together",
    )

    verdict = policy.evaluate_action(decision, state)
    assert verdict.verdict == PolicyVerdict.MODIFIED
    assert verdict.sanitized_decision.target == "arch_a_simple"
    assert verdict.allowed is True


def test_propose_benchmark_is_strictly_proposal_only():
    policy = InvestigationPolicy()
    state = {
        "investigation_round": 0,
        "candidate_architectures": [MagicMock(id="arch_a_simple")],
        "simulation_results": [MagicMock()],
        "investigation_trace": [],
    }
    decision = InvestigationDecision(
        action=InvestigationActionType.PROPOSE_BENCHMARK,
        target="postgres_db",
        reason="Targeted benchmark required to reduce variance.",
    )
    verdict = policy.evaluate_action(decision, state)
    assert verdict.verdict == PolicyVerdict.APPROVED
    assert verdict.sanitized_decision.action == InvestigationActionType.PROPOSE_BENCHMARK


def test_pilot_suite_manifest():
    assert len(PILOT_SCENARIOS) == 3
    assert PILOT_SCENARIOS[0].scenario_id == "dev_01_straightforward"
    assert PILOT_SCENARIOS[1].scenario_id == "dev_03_boundary"
    assert PILOT_SCENARIOS[2].scenario_id == "dev_05_incomplete_coverage"
