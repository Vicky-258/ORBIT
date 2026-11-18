"""
Unit and integration tests for LLM Recommendation Synthesis Node (Phase 4A Part 2 & 3).
Validates winner preservation, metric immutability, inconclusive outcome fidelity,
validation guardrails, graceful deterministic fallback, and LangGraph workflow integration.
Guarantees NO external network requests are made during testing.
"""
import pytest
from unittest.mock import MagicMock, patch

from orbit.agent.provider import LLMProviderManager, ExecutionMode
from orbit.agent.schemas import RecommendationExplanation
from orbit.agent.architecture_agent import WorkloadExtractionResult
from orbit.agent.recommendation_synthesizer import RecommendationSynthesizer
from orbit.agent.orchestrator import ORBITOrchestrator
from orbit.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    RecommendationResult,
    CandidateEvaluation,
    FeasibilityCheck,
    FeasibilityStatus,
)
from orbit.evaluation.recommender import ArchitectureRecommender


@pytest.fixture
def sample_workload():
    return WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
        cache_assumed_hit_rate=0.85,
    )


@pytest.fixture
def sample_sim_results():
    r_a = SimulationResult(
        architecture_id="arch_a_simple",
        architecture_name="Single DB (No Cache)",
        throughput_achieved_rps=480.0,
        p50_latency_ms=18.5,
        p90_latency_ms=42.0,
        p95_latency_ms=55.0,  # Fails SLA (< 50)
        p99_latency_ms=90.0,
        max_latency_ms=120.0,
        error_rate_pct=0.0,
        total_requests=2400,
        completed_requests=2400,
        error_count=0,
        avg_queue_length=3.2,
        max_queue_length=15,
        component_utilizations={"db": 85.0, "api": 30.0},
        cache_hit_rate=None,
        bottleneck_component="db",
        estimated_monthly_cost_usd=90.0,
        simulation_duration_seconds=5.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(52.0, 58.0),
    )
    r_b = SimulationResult(
        architecture_id="arch_b_cached",
        architecture_name="API + Redis Cache + PostgreSQL",
        throughput_achieved_rps=500.0,
        p50_latency_ms=4.2,
        p90_latency_ms=12.0,
        p95_latency_ms=16.8,  # Meets SLA (< 50)
        p99_latency_ms=28.0,
        max_latency_ms=45.0,
        error_rate_pct=0.0,
        total_requests=2500,
        completed_requests=2500,
        error_count=0,
        avg_queue_length=0.4,
        max_queue_length=4,
        component_utilizations={"db": 22.0, "cache": 35.0, "api": 32.0},
        cache_hit_rate=0.85,
        bottleneck_component="cache",
        estimated_monthly_cost_usd=135.0,  # Within budget (< 250)
        simulation_duration_seconds=5.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(15.2, 18.4),
    )
    return [r_a, r_b]


@pytest.fixture
def deterministic_recommendation(sample_workload, sample_sim_results):
    return ArchitectureRecommender.evaluate_and_recommend(
        workload=sample_workload,
        sim_results=sample_sim_results,
    )


# --- Unit Tests: RecommendationSynthesizer ---

def test_synthesis_fallback_when_llm_unavailable(sample_workload, sample_sim_results, deterministic_recommendation):
    """Test 1: When LLM is unavailable, synthesizer preserves deterministic rationale and labels mode."""
    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = False

    synthesizer = RecommendationSynthesizer(provider_mgr=prov_mgr)
    rec_out, mode = synthesizer.synthesize(
        workload=sample_workload,
        sim_results=sample_sim_results,
        recommendation=deterministic_recommendation,
    )

    assert mode == ExecutionMode.FALLBACK
    assert rec_out.explanation_source == "deterministic"
    assert rec_out.selected_architecture_id == deterministic_recommendation.selected_architecture_id
    assert rec_out.status == deterministic_recommendation.status
    assert rec_out.rationale == deterministic_recommendation.rationale
    assert rec_out.executive_summary == deterministic_recommendation.executive_summary
    assert rec_out.structured_explanation is not None


def test_synthesis_preserves_winner_and_metrics_with_llm(sample_workload, sample_sim_results, deterministic_recommendation):
    """Test 2: LLM explanation enriches text but strictly preserves winner, status, and metrics."""
    mock_explanation = RecommendationExplanation(
        summary="Architecture B (Redis + PostgreSQL) is definitively recommended as the only option satisfying the 50ms p95 SLA.",
        why_this_option=[
            "Achieves 16.8ms p95 latency well within the 50ms constraint, whereas Architecture A exceeds it at 55.0ms.",
            "Monthly cost of $135.00 easily complies with the $250.00 infrastructure budget limit.",
            "85% cache hit rate shields the relational database from saturation under 500 RPS load.",
        ],
        trade_offs=[
            "Introduces cache invalidation complexity and Redis operational overhead.",
            "Cost is $45/mo higher than un-cached Architecture A.",
        ],
        constraint_status="All hard constraints satisfied: p95 latency 16.8ms <= 50.0ms; budget $135.00 <= $250.00.",
        uncertainties=["95% confidence interval for p95 latency spans [15.2, 18.4] ms."],
        evidence_limitations=["Simulations based on SimPy queueing model; production network latency not modeled."],
    )

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = mock_explanation

    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = True
    prov_mgr.get_chat_model.return_value = mock_model

    synthesizer = RecommendationSynthesizer(provider_mgr=prov_mgr)
    rec_out, mode = synthesizer.synthesize(
        workload=sample_workload,
        sim_results=sample_sim_results,
        recommendation=deterministic_recommendation,
    )

    assert mode == ExecutionMode.LLM
    assert rec_out.explanation_source == "llm"
    # Authoritative immutable fields MUST match deterministic evaluator
    assert rec_out.selected_architecture_id == deterministic_recommendation.selected_architecture_id
    assert rec_out.selected_architecture_name == deterministic_recommendation.selected_architecture_name
    assert rec_out.status == deterministic_recommendation.status
    assert rec_out.predicted_metrics == deterministic_recommendation.predicted_metrics

    # Enriched fields reflect LLM synthesis
    assert rec_out.executive_summary == mock_explanation.summary
    assert rec_out.rationale == mock_explanation.why_this_option
    assert rec_out.trade_offs_and_risks == mock_explanation.trade_offs
    assert rec_out.structured_explanation == mock_explanation.model_dump()


def test_malformed_llm_output_triggers_deterministic_fallback(sample_workload, sample_sim_results, deterministic_recommendation):
    """Test 3: Malformed LLM output (e.g. empty summary or empty rationale) falls back gracefully."""
    bad_explanation = RecommendationExplanation(
        summary="Too short",  # validation requires >= 15 chars
        why_this_option=[],   # empty rationale
        trade_offs=[],
    )

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = bad_explanation

    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = True
    prov_mgr.get_chat_model.return_value = mock_model

    synthesizer = RecommendationSynthesizer(provider_mgr=prov_mgr)
    rec_out, mode = synthesizer.synthesize(
        workload=sample_workload,
        sim_results=sample_sim_results,
        recommendation=deterministic_recommendation,
    )

    assert mode == ExecutionMode.FALLBACK
    assert rec_out.explanation_source == "deterministic_fallback"
    assert rec_out.selected_architecture_id == deterministic_recommendation.selected_architecture_id
    assert rec_out.rationale == deterministic_recommendation.rationale
    assert rec_out.executive_summary == deterministic_recommendation.executive_summary


def test_provider_exception_triggers_fallback_without_crashing(sample_workload, sample_sim_results, deterministic_recommendation):
    """Test 4: Transient LLM errors (e.g. timeout or 500) revert to deterministic explanation."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = RuntimeError("OpenAI 503 Service Unavailable")

    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = True
    prov_mgr.get_chat_model.return_value = mock_model

    synthesizer = RecommendationSynthesizer(provider_mgr=prov_mgr)
    rec_out, mode = synthesizer.synthesize(
        workload=sample_workload,
        sim_results=sample_sim_results,
        recommendation=deterministic_recommendation,
    )

    assert mode == ExecutionMode.FALLBACK
    assert rec_out.explanation_source == "deterministic_fallback"
    assert rec_out.selected_architecture_id == deterministic_recommendation.selected_architecture_id
    assert rec_out.rationale == deterministic_recommendation.rationale


def test_inconclusive_or_infeasible_status_preserved():
    """Test 5: If deterministic evaluator reports INFEASIBLE, LLM cannot claim full feasibility."""
    workload = WorkloadSpec(max_monthly_budget_usd=50.0)  # impossible budget
    infeasible_rec = RecommendationResult(
        selected_architecture_id="arch_none",
        selected_architecture_name="No Feasible Architecture Found",
        status=FeasibilityStatus.INFEASIBLE,
        executive_summary="All architectures violate the $50 budget.",
        rationale=["No architecture satisfies all hard constraints."],
        predicted_metrics={},
        evaluations=[],
        trade_offs_and_risks=["Budget cap too restrictive."],
        assumptions_cited=[],
        validation_gaps=["Requires higher budget or smaller resource allocations."],
    )

    # Hallucinating LLM claiming full feasibility
    hallucinating_explanation = RecommendationExplanation(
        summary="This architecture is fully feasible and satisfies all constraints perfectly.",
        why_this_option=["Everything is great."],
        trade_offs=["None."],
    )

    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured
    mock_structured.invoke.return_value = hallucinating_explanation

    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = True
    prov_mgr.get_chat_model.return_value = mock_model

    synthesizer = RecommendationSynthesizer(provider_mgr=prov_mgr)
    rec_out, mode = synthesizer.synthesize(
        workload=workload,
        sim_results=[],
        recommendation=infeasible_rec,
    )

    # Must be rejected by validator and fallen back to deterministic
    assert mode == ExecutionMode.FALLBACK
    assert rec_out.explanation_source == "deterministic_fallback"
    assert rec_out.status == FeasibilityStatus.INFEASIBLE
    assert "All architectures violate the $50 budget." in rec_out.executive_summary


def test_provenance_and_evidence_payload_structure(sample_workload, sample_sim_results, deterministic_recommendation):
    """Test 6: Evidence payload distinguishes synthetic fixtures from measured data."""
    prov_map = {
        "simulation": "simulated",
        "benchmark_postgres_db": "synthetic",
        "model_postgres_db": "model-predicted",
    }
    synthesizer = RecommendationSynthesizer()
    payload = synthesizer.prepare_evidence_payload(
        workload=sample_workload,
        sim_results=sample_sim_results,
        recommendation=deterministic_recommendation,
        provenance=prov_map,
        raw_prompt="Build me a 500 RPS feed system",
    )

    assert "workload_requirements" in payload
    assert "candidate_simulations" in payload
    assert "provenance" in payload
    assert payload["provenance"]["simulation"] == "simulated"
    assert "synthetic" in payload["provenance"]["component_benchmarks"]["benchmark_postgres_db"]
    assert "Not production traffic" in payload["provenance"]["environment_note"]


# --- Integration Tests: LangGraph Active Workflow with Synthesis Node ---

def test_orchestrator_integration_with_mocked_llm():
    """Test 7: Full LangGraph workflow successfully routes through synthesis node in LLM mode."""
    mock_chat = MagicMock()
    mock_extraction_structured = MagicMock()
    mock_explanation_structured = MagicMock()

    # When called for WorkloadExtractionResult vs RecommendationExplanation
    def structured_side_effect(schema_cls):
        if schema_cls.__name__ == "WorkloadExtractionResult":
            return mock_extraction_structured
        return mock_explanation_structured

    mock_chat.with_structured_output.side_effect = structured_side_effect

    mock_extraction_structured.invoke.return_value = WorkloadExtractionResult(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        max_monthly_budget_usd=250.0,
    )

    mock_explanation_structured.invoke.return_value = RecommendationExplanation(
        summary="Synthesized LLM Recommendation: Architecture B is chosen due to robust 16.8ms p95 latency under cache.",
        why_this_option=["Meets all SLAs with 85% cache hit rate."],
        trade_offs=["Requires managing Redis caching layer."],
        constraint_status="p95 latency 16.8ms <= 50ms; budget $135 <= $250.",
        uncertainties=["Simulated queue variance within 95% CI."],
        evidence_limitations=["Container isolation benchmarks."],
    )

    prov_mgr = MagicMock()
    prov_mgr.is_llm_available.return_value = True
    prov_mgr.get_chat_model.return_value = mock_chat
    prov_mgr.get_execution_mode.return_value = ExecutionMode.LLM

    orch = ORBITOrchestrator(provider_mgr=prov_mgr)
    prompt = "I need a social feed architecture for 500 RPS, 90% reads, p95 under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42)

    assert state["workflow_status"] == "RECOMMENDED"
    assert state["recommendation"] is not None
    rec = state["recommendation"]
    assert rec.explanation_source == "llm"
    assert "Synthesized LLM Recommendation" in rec.executive_summary
    assert state["provenance"]["recommendation_explanation"] == "llm_synthesized"
    assert state["structured_explanation"] is not None


def test_orchestrator_integration_in_fallback_mode(monkeypatch):
    """Test 8: Full LangGraph workflow operates seamlessly in deterministic fallback mode."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")

    orch = ORBITOrchestrator()
    prompt = "I need a social feed architecture for 500 RPS, 90% reads, p95 under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42)

    assert state["workflow_status"] == "RECOMMENDED"
    assert state["recommendation"] is not None
    rec = state["recommendation"]
    assert rec.explanation_source == "deterministic"
    assert state["provenance"]["recommendation_explanation"] == "deterministic_template"
