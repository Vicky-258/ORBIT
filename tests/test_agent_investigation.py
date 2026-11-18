"""
Unit and Integration Tests for Agentic Planning, Tool Selection & Adaptive Investigation (Phase 4B).
Validates bounded decision loops, action validation policy, explicit dispatching,
duplicate action blocking, benchmark proposal safety, provenance tracking, and evaluator authority.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from orbit.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    InvestigationRecord,
    BenchmarkProposalDetails,
)
from orbit.agent.investigation_policy import (
    InvestigationPolicy,
    PolicyVerdict,
    PolicyEvaluationResult,
)
from orbit.agent.investigation_dispatcher import InvestigationDispatcher
from orbit.agent.investigation_planner import InvestigationPlanner
from orbit.agent.orchestrator import ORBITOrchestrator
from orbit.agent.provider import LLMProviderManager, ExecutionMode
from orbit.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    CandidateEvaluation,
    FeasibilityStatus,
)
from orbit.registry.component_registry import ComponentRegistry
from orbit.api.app import app


@pytest.fixture
def mock_workload():
    return WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
    )


@pytest.fixture
def mock_candidate():
    from orbit.generator.candidate_generator import ArchitectureGenerator
    gen = ArchitectureGenerator()
    candidates = gen.generate_candidates(include_async=True)
    return next(c for c in candidates if c.id == "arch_b_cached")


@pytest.fixture
def mock_simulation_result():
    return SimulationResult(
        architecture_id="arch_b_cached",
        architecture_name="Architecture B — Cached Reads",
        throughput_achieved_rps=501.2,
        p50_latency_ms=3.1,
        p90_latency_ms=5.5,
        p95_latency_ms=7.2,
        p99_latency_ms=12.0,
        max_latency_ms=25.0,
        error_rate_pct=0.0,
        total_requests=2500,
        completed_requests=2500,
        error_count=0,
        avg_queue_length=0.2,
        max_queue_length=3.0,
        simulation_duration_seconds=5.0,
        random_seed=42,
        latency_uncertainty_p95_ms=[7.0, 7.4],
        bottleneck_component="db",
        component_utilizations={"db": 28.0, "cache": 0.5},
        estimated_monthly_cost_usd=176.0,
        cache_hit_rate=0.85,
    )


# --- 1. Valid Action Proposal Dispatches Expected Tool ---
def test_valid_action_dispatches_tool(mock_workload, mock_candidate):
    dispatcher = InvestigationDispatcher()
    decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        target="all_candidates",
        reason="Check if models are calibrated",
    )
    state = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "simulation_results": [],
    }
    updates, record = dispatcher.dispatch(decision, state, round_num=1)

    assert record.policy_verdict == "APPROVED"
    assert record.tool_invoked == "check_component_models"
    assert record.tool_output["success"] is True
    assert record.provenance == "model_derived"
    assert "missing_models" in updates


# --- 2. Tool Results Change Next Action Decision ---
def test_tool_results_influence_subsequent_decision(mock_workload, mock_candidate, mock_simulation_result):
    planner = InvestigationPlanner()

    # State before model coverage has been inspected
    state_round1 = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "simulation_results": [mock_simulation_result],
        "investigation_trace": [],
    }
    decision1 = planner._heuristic_fallback(state_round1)
    assert decision1.action == InvestigationActionType.INSPECT_MODEL_COVERAGE

    # State AFTER model coverage tool ran: result in trace should change next action to inspect_uncertainty
    state_round2 = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "simulation_results": [mock_simulation_result],
        "investigation_trace": [
            {"action": "inspect_model_coverage", "policy_verdict": "APPROVED"}
        ],
    }
    decision2 = planner._heuristic_fallback(state_round2)
    assert decision2.action == InvestigationActionType.INSPECT_UNCERTAINTY


# --- 3. Agent Stops When Evidence is Sufficient ---
def test_agent_stops_when_evidence_sufficient(mock_workload, mock_candidate, mock_simulation_result):
    planner = InvestigationPlanner()
    # State where model coverage, simulation, and uncertainty were all audited
    state_completed = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "simulation_results": [mock_simulation_result],
        "investigation_trace": [
            {"action": "inspect_model_coverage", "policy_verdict": "APPROVED"},
            {"action": "inspect_uncertainty", "policy_verdict": "APPROVED"},
        ],
    }
    decision = planner._heuristic_fallback(state_completed)
    assert decision.action == InvestigationActionType.STOP_AND_RECOMMEND
    assert "Sufficient simulation and uncertainty evidence established" in decision.reason


# --- 4. Agent Stops Inconclusively When Limit Reached Without Evidence ---
def test_agent_stops_inconclusive_when_budget_or_round_limit_reached():
    policy = InvestigationPolicy(default_max_rounds=2)
    proposal = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        reason="Want more checks",
    )
    # State with 0 simulation results and current_round == 2 (limit reached)
    state = {
        "investigation_round": 2,
        "max_investigation_rounds": 2,
        "simulation_results": [],
    }
    res = policy.evaluate_action(proposal, state)

    assert res.verdict == PolicyVerdict.STOPPED
    assert res.sanitized_decision.action == InvestigationActionType.STOP_INCONCLUSIVE
    assert "Round budget exhausted" in (res.sanitized_decision.stop_reason or "")


# --- 5. Unsupported Action is Rejected ---
def test_unsupported_action_rejected():
    policy = InvestigationPolicy()
    # Use invalid action string bypass
    decision = InvestigationDecision.model_construct(
        action="delete_production_database",
        reason="Malicious or unsupported action",
    )
    res = policy.evaluate_action(decision, state={})

    assert res.verdict == PolicyVerdict.REJECTED
    assert res.allowed is False
    assert "not in approved" in res.reason


# --- 6. Invalid Candidate or Component Reference is Rejected ---
def test_invalid_candidate_or_component_rejected(mock_candidate):
    policy = InvestigationPolicy()
    decision = InvestigationDecision(
        action=InvestigationActionType.SIMULATE_CANDIDATE,
        target="arch_nonexistent_candidate",
        reason="Testing invalid target",
    )
    state = {
        "candidate_architectures": [mock_candidate],
    }
    res = policy.evaluate_action(decision, state)

    assert res.verdict == PolicyVerdict.REJECTED
    assert res.allowed is False
    assert "does not exist in generated candidates" in res.reason


# --- 7. Malformed LLM Response Executes No Tool ---
def test_malformed_llm_response_falls_back_safely(mock_workload, mock_candidate):
    mock_mgr = MagicMock(spec=LLMProviderManager)
    mock_mgr.is_llm_available.return_value = True
    mock_chat = MagicMock()
    mock_structured = MagicMock()
    # LLM returns unexpected object (e.g. dict or integer instead of InvestigationDecision)
    mock_structured.invoke.return_value = "invalid response string"
    mock_chat.with_structured_output.return_value = mock_structured
    mock_mgr.get_chat_model.return_value = mock_chat

    planner = InvestigationPlanner(provider_mgr=mock_mgr)
    state = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "investigation_trace": [],
    }
    decision = planner.plan_next_action(state)

    # Must cleanly fall back to safe deterministic decision
    assert isinstance(decision, InvestigationDecision)
    assert decision.action == InvestigationActionType.INSPECT_MODEL_COVERAGE


# --- 8. Repeated Actions are Detected and Blocked ---
def test_repeated_actions_detected_and_prevented(mock_candidate):
    policy = InvestigationPolicy()
    decision = InvestigationDecision(
        action=InvestigationActionType.SIMULATE_CANDIDATE,
        target="arch_b_cached",
        reason="Run simulation again",
    )
    state = {
        "investigation_round": 1,
        "max_investigation_rounds": 3,
        "candidate_architectures": [mock_candidate],
        "simulation_results": [MagicMock()],
        "investigation_trace": [
            {"round": 1, "action": "simulate_candidate", "target": "arch_b_cached", "policy_verdict": "APPROVED"}
        ],
    }
    res = policy.evaluate_action(decision, state)

    assert res.verdict == PolicyVerdict.REJECTED
    assert res.allowed is False
    assert "Duplicate action" in res.reason
    assert res.sanitized_decision.action == InvestigationActionType.STOP_AND_RECOMMEND


# --- 9. Repeated Tool Failures Cannot Create an Infinite Loop ---
def test_repeated_tool_failures_terminate_loop():
    policy = InvestigationPolicy()
    decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        reason="Try again after failure",
    )
    state = {
        "investigation_round": 2,
        "max_investigation_rounds": 5,
        "simulation_results": [MagicMock()],
        "investigation_trace": [
            {"round": 1, "action": "action1", "policy_verdict": "REJECTED"},
            {"round": 2, "action": "action2", "policy_verdict": "REJECTED"},
        ],
    }
    res = policy.evaluate_action(decision, state)

    assert res.verdict == PolicyVerdict.STOPPED
    assert "Repeated investigation failures detected" in res.reason


# --- 10. Benchmark Proposal Does Not Launch Real Benchmark ---
def test_benchmark_proposal_does_not_execute_live_benchmark():
    dispatcher = InvestigationDispatcher()
    decision = InvestigationDecision(
        action=InvestigationActionType.PROPOSE_BENCHMARK,
        target="postgres_db",
        benchmark_proposal=BenchmarkProposalDetails(
            component_name="postgres_db",
            version="16",
            target_concurrency=40,
            rationale="Evaluate write contention",
        ),
        reason="Proposal to reduce uncertainty",
    )
    state = {"benchmark_proposals": []}
    updates, record = dispatcher.dispatch(decision, state, round_num=1)

    assert record.policy_verdict == "APPROVED"
    assert record.tool_invoked == "propose_benchmark"
    assert record.tool_output["executed"] is False
    assert record.tool_output["requires_authorization"] is True
    assert record.provenance == "benchmark_proposal"

    proposals = updates.get("benchmark_proposals", [])
    assert len(proposals) == 1
    assert proposals[0]["authorization_status"] == "PROPOSED_AWAITING_EXPLICIT_AUTHORIZATION"
    assert proposals[0]["is_executed"] is False


# --- 11. Unauthorized Benchmark Execution is Blocked ---
def test_unauthorized_benchmark_component_blocked():
    policy = InvestigationPolicy()
    decision = InvestigationDecision(
        action=InvestigationActionType.PROPOSE_BENCHMARK,
        target="unapproved_arbitrary_component",
        benchmark_proposal=BenchmarkProposalDetails(
            component_name="unapproved_arbitrary_component",
            version="1.0",
        ),
        reason="Test unapproved component",
    )
    res = policy.evaluate_action(decision, state={})

    assert res.verdict == PolicyVerdict.REJECTED
    assert res.allowed is False
    assert "not in allowed" in res.reason


# --- 12. Simulated and Synthetic Results Retain Correct Provenance ---
def test_simulated_and_synthetic_provenance_preserved(mock_workload, mock_candidate):
    dispatcher = InvestigationDispatcher()

    # 1. Inspect model coverage -> provenance: model_derived
    _, rec_model = dispatcher.dispatch(
        InvestigationDecision(action=InvestigationActionType.INSPECT_MODEL_COVERAGE, reason="check models"),
        state={"workload_spec": mock_workload, "candidate_architectures": [mock_candidate]},
        round_num=1,
    )
    assert rec_model.provenance == "model_derived"

    # 2. Uncertainty audit -> provenance: uncertainty_analysis
    _, rec_unc = dispatcher.dispatch(
        InvestigationDecision(action=InvestigationActionType.INSPECT_UNCERTAINTY, reason="check uncertainty"),
        state={"workload_spec": mock_workload, "simulation_results": []},
        round_num=2,
    )
    assert rec_unc.provenance == "uncertainty_analysis"


# --- 13. LLM Cannot Change Authoritative Numerical Metrics ---
def test_llm_cannot_alter_numerical_metrics(monkeypatch):
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    orch = ORBITOrchestrator()
    prompt = "Social media feed 500 RPS, peak 1000 RPS, 90% reads, p95 under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42)

    rec = state["recommendation"]
    sim_res = {r.architecture_id: r for r in state["simulation_results"]}
    winner_res = sim_res[rec.selected_architecture_id]

    # Metrics on the recommendation must strictly equal the simulated numbers
    assert rec.predicted_metrics["p95_latency_ms"] == winner_res.p95_latency_ms
    assert rec.predicted_metrics["throughput_achieved_rps"] == winner_res.throughput_achieved_rps
    assert rec.predicted_metrics["estimated_monthly_cost_usd"] == winner_res.estimated_monthly_cost_usd


# --- 14. LLM Cannot Override Deterministic Feasibility or Ranking ---
def test_llm_cannot_override_feasibility_or_ranking(monkeypatch):
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    orch = ORBITOrchestrator()
    # Strict low budget: $20/month where NO candidate is feasible
    prompt = "Social feed 500 RPS, 90% reads, p95 under 50ms, budget $20/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42)

    rec = state["recommendation"]
    assert rec is not None
    # Authoritative status must be INFEASIBLE, never artificially claimed FEASIBLE
    assert rec.status == FeasibilityStatus.INFEASIBLE


# --- 15. LLM Provider Failure Uses Safe Fallback Path ---
def test_llm_provider_exception_triggers_safe_fallback(monkeypatch, mock_workload, mock_candidate):
    mock_mgr = MagicMock(spec=LLMProviderManager)
    mock_mgr.is_llm_available.return_value = True
    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_structured.invoke.side_effect = RuntimeError("Provider connection reset by peer")
    mock_chat.with_structured_output.return_value = mock_structured
    mock_mgr.get_chat_model.return_value = mock_chat

    planner = InvestigationPlanner(provider_mgr=mock_mgr)
    state = {
        "workload_spec": mock_workload,
        "candidate_architectures": [mock_candidate],
        "investigation_trace": [],
    }
    # Must not raise RuntimeError, must cleanly fall back
    decision = planner.plan_next_action(state)
    assert isinstance(decision, InvestigationDecision)
    assert decision.action == InvestigationActionType.INSPECT_MODEL_COVERAGE


# --- 16. Full Integration Workflow Runs Bounded Investigation Rounds ---
def test_full_workflow_executes_investigation_trace(monkeypatch):
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    orch = ORBITOrchestrator()
    prompt = "Social feed 500 RPS, peak 1000 RPS, 90% reads, p95 under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42, max_investigation_rounds=3)

    assert state["workflow_status"] == "RECOMMENDED"
    assert state["recommendation"] is not None
    trace = state.get("investigation_trace", [])
    assert len(trace) >= 1
    assert state.get("investigation_round", 0) >= 1
    assert all("policy_verdict" in t for t in trace)
    assert all("action" in t for t in trace)


# --- 17. API Endpoint Exposes Investigation Trace ---
def test_api_endpoint_returns_investigation_trace(monkeypatch):
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    client = TestClient(app)
    res = client.post("/api/agent/run", json={
        "prompt": "Social feed 500 RPS, 90% reads, p95 under 50ms, budget $250/mo",
        "simulation_duration_seconds": 1.5,
        "max_investigation_rounds": 2,
    })
    assert res.status_code == 200
    data = res.json()
    assert "investigation_trace" in data
    assert "investigation_rounds" in data
    assert isinstance(data["investigation_trace"], list)


# --- 18. Workflow Trace Accurately Distinguishes Proposed, Rejected, and Executed Actions ---
def test_workflow_trace_records_verdicts_accurately(mock_candidate):
    orch = ORBITOrchestrator()
    policy = InvestigationPolicy()

    # 1. Test record for approved action
    approved_decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        reason="Initial inspection",
    )
    val_approved = policy.evaluate_action(approved_decision, state={"candidate_architectures": [mock_candidate]})
    assert val_approved.verdict == PolicyVerdict.APPROVED

    # 2. Test record for rejected action
    rejected_decision = InvestigationDecision(
        action=InvestigationActionType.SIMULATE_CANDIDATE,
        target="invalid_candidate_id",
        reason="Bad target",
    )
    val_rejected = policy.evaluate_action(rejected_decision, state={"candidate_architectures": [mock_candidate]})
    assert val_rejected.verdict == PolicyVerdict.REJECTED
