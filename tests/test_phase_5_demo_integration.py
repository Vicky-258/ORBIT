"""
Phase 5.0 End-to-End Demo Integration & Reliability Tests.
Validates the complete integrated user journey from natural-language input
to structured architectural recommendation across all 3 scenarios,
enforcing policy guardrails, evidence integrity, and response standardization.
"""
import pytest
from fastapi.testclient import TestClient

from aads.api.app import app
from aads.agent.orchestrator import AADSOrchestrator
from aads.agent.architecture_agent import ArchitectureAgent
from aads.agent.schemas import InvestigationActionType, InvestigationDecision
from aads.agent.investigation_policy import InvestigationPolicy, PolicyVerdict
from aads.core.schemas import (
    WorkloadSpec,
    FeasibilityStatus,
    DemoWorkflowResponse,
)
from aads.core.demo_response_builder import build_demo_workflow_response
from aads.registry.component_registry import ComponentRegistry
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.feasibility_filter import FeasibilityFilter
from aads.evaluation.recommender import ArchitectureRecommender


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


@pytest.fixture(scope="module")
def orchestrator():
    reg = ComponentRegistry()
    reg.seed_baseline_data()
    return AADSOrchestrator(registry=reg)


# =============================================================================
# 1. Natural Language Workload Extraction & Normalization
# =============================================================================

def test_natural_language_workload_extraction_scenario_1():
    prompt = (
        "Design a backend for an e-commerce API expecting approximately 500 requests per second. "
        "The p95 latency must remain below 100 ms, the monthly infrastructure budget is $250, "
        "and the system should support read-heavy traffic with occasional writes."
    )
    result = ArchitectureAgent.fallback_parse(prompt)
    assert result.app_type == "ecommerce"
    assert result.request_rate_rps == 500.0
    assert result.p95_latency_target_ms == 100.0
    assert result.max_monthly_budget_usd == 250.0
    assert result.read_ratio == 0.90
    assert result.write_ratio == 0.10
    assert "ecommerce" in result.user_facts.values() or result.user_facts.get("app_type") == "ecommerce"


def test_natural_language_workload_extraction_scenario_2():
    prompt = "Write-heavy transactional workload with 150 RPS, 40% reads and 60% writes, p95 latency under 150 ms, monthly budget $300"
    result = ArchitectureAgent.fallback_parse(prompt)
    assert result.app_type == "transactional"
    assert result.request_rate_rps == 150.0
    assert result.read_ratio == 0.40
    assert result.write_ratio == 0.60
    assert result.p95_latency_target_ms == 150.0
    assert result.max_monthly_budget_usd == 300.0


def test_natural_language_workload_extraction_scenario_3():
    prompt = "Background processing workload: 300 RPS incoming, background tasks can be processed asynchronously, p95 API response target 100 ms, budget $350/month"
    result = ArchitectureAgent.fallback_parse(prompt)
    assert result.app_type == "background_processing"
    assert result.request_rate_rps == 300.0
    assert result.p95_latency_target_ms == 100.0
    assert result.max_monthly_budget_usd == 350.0


def test_vague_prompt_triggers_clarification():
    vague_prompt = "Build a fast website"
    result = ArchitectureAgent.fallback_parse(vague_prompt)
    assert len(result.clarification_questions) >= 2
    assert len(result.ambiguities) >= 1


# =============================================================================
# 2. Candidate Generation & Model Coverage Inspection
# =============================================================================

def test_candidate_generation_and_coverage(orchestrator):
    candidates = orchestrator.agent.generator.generate_candidates(include_async=True, include_unsupported=True)
    assert len(candidates) >= 3
    candidate_ids = [c.id for c in candidates]
    assert "arch_a_simple" in candidate_ids
    assert "arch_b_cached" in candidate_ids
    assert "arch_c_async" in candidate_ids

    # Check model coverage
    workload = WorkloadSpec(request_rate_rps=500.0, p95_latency_target_ms=100.0)
    for c in candidates:
        if c.id != "arch_mongo_unregistered":
            for req in c.required_models:
                comp, ver = req.split(":", 1) if ":" in req else (req, "latest")
                status, model, _ = orchestrator.registry.check_compatibility(comp, ver, workload)
                assert status in ("COMPATIBLE", "AVAILABLE", "VALIDATED", "INTERPOLATED", "OBSERVED")
                assert model is not None


# =============================================================================
# 3. Discrete-Event SimPy Simulation Execution
# =============================================================================

def test_discrete_event_simulation_executes(orchestrator):
    workload = WorkloadSpec(request_rate_rps=400.0, p95_latency_target_ms=80.0, max_monthly_budget_usd=250.0)
    candidates = orchestrator.agent.generator.generate_candidates(include_async=True, include_unsupported=False)
    engine = SimPyEngine(orchestrator.registry)

    for cand in candidates:
        sim_res = engine.simulate_architecture(cand, workload, duration_seconds=3.0, random_seed=42)
        assert sim_res.throughput_achieved_rps > 0.0
        assert sim_res.p50_latency_ms > 0.0
        assert sim_res.p95_latency_ms >= sim_res.p50_latency_ms
        assert sim_res.p99_latency_ms >= sim_res.p95_latency_ms
        assert sim_res.estimated_monthly_cost_usd > 0.0
        assert sim_res.bottleneck_component != ""
        assert isinstance(sim_res.latency_uncertainty_p95_ms, tuple)
        assert len(sim_res.latency_uncertainty_p95_ms) == 2


# =============================================================================
# 4. Policy Gatekeeper & Bounded Investigation Enforcement
# =============================================================================

def test_policy_gatekeeper_enforces_round_limit():
    policy = InvestigationPolicy(default_max_rounds=3, hard_max_rounds=5)
    state = {
        "investigation_round": 3,
        "max_investigation_rounds": 3,
        "investigation_budget_spent": 5.0,
        "investigation_budget_seconds": 60.0,
        "investigation_trace": [],
        "candidate_architectures": [],
        "simulation_results": [
            type("SimResult", (), {"architecture_id": "arch_a", "p95_latency_ms": 10.0})()
        ],
    }
    decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        target="all_candidates",
        reason="Continue audit",
    )
    result = policy.evaluate_action(decision, state)
    assert result.verdict == PolicyVerdict.STOPPED
    assert result.sanitized_decision.action == InvestigationActionType.STOP_AND_RECOMMEND


def test_policy_gatekeeper_prohibits_duplicate_actions():
    policy = InvestigationPolicy()
    state = {
        "investigation_round": 1,
        "max_investigation_rounds": 3,
        "investigation_budget_spent": 1.0,
        "investigation_budget_seconds": 60.0,
        "candidate_architectures": [],
        "simulation_results": [],
        "investigation_trace": [
            {"action": "inspect_model_coverage", "target": "all_candidates", "policy_verdict": "APPROVED"}
        ],
    }
    decision = InvestigationDecision(
        action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
        target="all_candidates",
        reason="Repeat audit",
    )
    result = policy.evaluate_action(decision, state)
    assert result.verdict in (PolicyVerdict.REJECTED, PolicyVerdict.STOPPED)


def test_policy_gatekeeper_blocks_unauthorized_docker_execution():
    policy = InvestigationPolicy()
    state = {
        "investigation_round": 1,
        "max_investigation_rounds": 3,
        "investigation_budget_spent": 1.0,
        "investigation_budget_seconds": 60.0,
        "candidate_architectures": [],
        "simulation_results": [],
        "investigation_trace": [],
        "experiment_authorization": None,  # No authorization granted
    }
    decision = InvestigationDecision(
        action=InvestigationActionType.EXECUTE_EXPERIMENT,
        target="postgres_db",
        reason="Run live benchmark trial",
    )
    result = policy.evaluate_action(decision, state)
    # Must reject unauthorized benchmark execution
    assert result.verdict == PolicyVerdict.REJECTED
    assert "authorization" in result.reason.lower() or not result.allowed


# =============================================================================
# 5. Deterministic Feasibility Filtering & Honest Evidence Contracts
# =============================================================================

def test_feasibility_filter_hard_sla_and_evidence():
    workload = WorkloadSpec(
        request_rate_rps=500.0,
        p95_latency_target_ms=50.0,
        max_monthly_budget_usd=200.0,
    )
    sim = SimPyEngine(ComponentRegistry()).simulate_architecture(
        ArchitectureAgent().generator.generate_candidates()[0],
        workload,
        duration_seconds=2.0,
    )

    # Infeasible latency case
    sim_infeasible = sim.model_copy(update={"p95_latency_ms": 75.0})
    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_infeasible)
    assert status == FeasibilityStatus.INFEASIBLE

    # Infeasible cost case
    sim_cost_exceeded = sim.model_copy(update={"estimated_monthly_cost_usd": 350.0})
    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_cost_exceeded)
    assert status == FeasibilityStatus.INFEASIBLE

    # Insufficient evidence case
    sim_insufficient = sim.model_copy(update={"warnings": ["INSUFFICIENT_EVIDENCE: MongoDB model uncalibrated"]})
    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_insufficient)
    assert status == FeasibilityStatus.UNCERTAIN


# =============================================================================
# 6. Canonical Scenario Executions & Defensible Recommendations
# =============================================================================

def test_scenario_1_caching_architecture_wins(orchestrator):
    prompt = (
        "Design a backend for an e-commerce API expecting approximately 500 requests per second. "
        "The p95 latency must remain below 100 ms, the monthly infrastructure budget is $250, "
        "and the system should support read-heavy traffic with occasional writes."
    )
    state = orchestrator.run(prompt, simulation_duration_seconds=5.0)
    resp = build_demo_workflow_response(state)

    assert resp.workflow_status == "RECOMMENDED"
    assert resp.recommendation.winner_architecture_id == "arch_b_cached"
    assert resp.recommendation.is_conclusive is True
    assert len(resp.architecture_comparison) >= 3
    assert len(resp.recommendation.rejected_alternatives) >= 2


def test_scenario_2_transactional_direct_db_wins(orchestrator):
    prompt = "Write-heavy transactional workload with 150 RPS, 40% reads and 60% writes, p95 latency under 150 ms, monthly budget $300"
    state = orchestrator.run(prompt, simulation_duration_seconds=5.0)
    resp = build_demo_workflow_response(state)

    assert resp.workflow_status == "RECOMMENDED"
    assert resp.recommendation.winner_architecture_id == "arch_a_simple"
    assert resp.recommendation.is_conclusive is True


def test_scenario_3_background_worker_wins(orchestrator):
    prompt = "Background processing workload: 300 RPS incoming, background tasks can be processed asynchronously, p95 API response target 100 ms, budget $350/month"
    state = orchestrator.run(prompt, simulation_duration_seconds=5.0)
    resp = build_demo_workflow_response(state)

    assert resp.workflow_status == "RECOMMENDED"
    assert resp.recommendation.winner_architecture_id == "arch_c_async"
    assert resp.recommendation.is_conclusive is True


# =============================================================================
# 7. Standardized Demo Response Schema (Sections A - E)
# =============================================================================

def test_demo_response_schema_completeness(orchestrator):
    prompt = "Design a backend for an e-commerce API expecting approximately 500 requests per second. p95 under 100ms, budget $250"
    state = orchestrator.run(prompt, simulation_duration_seconds=2.0)
    resp = build_demo_workflow_response(state)

    # Section A
    assert isinstance(resp.request_summary.request_rate_rps, float)
    assert resp.request_summary.p95_latency_target_ms > 0
    assert resp.request_summary.max_monthly_budget_usd > 0
    assert isinstance(resp.request_summary.user_facts, dict)
    assert isinstance(resp.request_summary.agent_assumptions, list)

    # Section B
    assert resp.investigation_summary.investigation_rounds >= 1
    assert len(resp.investigation_summary.actions) >= 1
    assert resp.investigation_summary.why_agent_stopped != ""

    # Section C
    assert len(resp.architecture_comparison) >= 3
    for comp in resp.architecture_comparison:
        assert comp.architecture_id != ""
        assert comp.topology != ""
        assert comp.throughput_achieved_rps > 0
        assert comp.p95_latency_ms > 0
        assert comp.estimated_monthly_cost_usd > 0
        assert comp.evidence_status in ("OBSERVED", "INTERPOLATED", "OUT_OF_RANGE", "INSUFFICIENT_EVIDENCE")
        assert comp.sla_result in ("SATISFIED", "BORDERLINE", "VIOLATED")

    # Section D
    assert resp.recommendation.winner_architecture_id is not None
    assert resp.recommendation.executive_summary != ""
    assert len(resp.recommendation.decision_rationale) >= 1
    assert len(resp.recommendation.rejected_alternatives) >= 1
    assert len(resp.recommendation.conditions_for_change) >= 1

    # Section E
    assert len(resp.evidence_disclosure.empirical_calibrated_components) >= 1
    assert len(resp.evidence_disclosure.simulation_derived_metrics) >= 1
    assert len(resp.evidence_disclosure.disclosures) >= 1
    assert "EMPIRICAL" in resp.evidence_disclosure.overall_evidence_integrity


# =============================================================================
# 8. FastAPI Endpoints Integration
# =============================================================================

def test_api_endpoints_integration(api_client):
    # Test Root
    res_root = api_client.get("/")
    assert res_root.status_code == 200
    assert "/api/demo/run" in res_root.json()["endpoints"]

    # Test /api/agent/run
    res_agent = api_client.post("/api/agent/run", json={
        "prompt": "Social feed 500 RPS, 90% reads, p95 under 50ms, budget $250/mo",
        "simulation_duration_seconds": 1.5,
    })
    assert res_agent.status_code == 200
    agent_data = res_agent.json()
    assert agent_data["workflow_status"] == "RECOMMENDED"
    assert "request_summary" in agent_data
    assert "investigation_summary" in agent_data
    assert "architecture_comparison" in agent_data
    assert "recommendation" in agent_data
    assert "evidence_disclosure" in agent_data
    assert "demo_response" in agent_data

    # Test /api/demo/run
    res_demo = api_client.post("/api/demo/run", json={
        "prompt": "Write-heavy transactional workload with 150 RPS, 40% reads and 60% writes, p95 latency under 150 ms, monthly budget $300",
        "simulation_duration_seconds": 1.5,
    })
    assert res_demo.status_code == 200
    demo_data = res_demo.json()
    assert demo_data["recommendation"]["winner_architecture_id"] == "arch_a_simple"
    assert demo_data["recommendation"]["is_conclusive"] is True
