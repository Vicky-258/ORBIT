"""
Unit and Integration Tests for LangChain & LangGraph Agent Integration (Phase 3B).
Validates requirements extraction, ambiguous clarification routing, tool boundaries,
provenance preservation, fallback execution, and recommendation consistency.
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from orbit.agent.provider import LLMProviderManager, ExecutionMode
from orbit.agent.architecture_agent import ArchitectureAgent, WorkloadExtractionResult
from orbit.agent.orchestrator import ORBITOrchestrator
from orbit.agent.tools import (
    validate_workload,
    generate_architecture_candidates,
    check_component_models,
    run_benchmark,
    fit_and_validate_model,
    simulate_architecture,
    evaluate_candidates,
)
from orbit.core.schemas import WorkloadSpec, ArchitectureGraph, FeasibilityStatus
from orbit.registry.component_registry import ComponentRegistry
from orbit.evaluation.recommender import ArchitectureRecommender
from orbit.api.app import app


def test_fallback_mode_without_credentials(monkeypatch):
    """Test 10: Ensures provider cleanly defaults to labeled fallback when credentials are absent."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("AADS_AGENT_MODE", "auto")
    
    mgr = LLMProviderManager()
    assert mgr.get_execution_mode() == ExecutionMode.FALLBACK
    assert mgr.is_llm_available() is False
    assert mgr.get_chat_model() is None
    
    summary = mgr.get_status_summary()
    assert summary["is_fallback"] is True
    assert summary["execution_mode"] == "FALLBACK"


def test_valid_natural_language_request_fallback(monkeypatch):
    """Test 1: Valid natural language request extracted deterministically in fallback mode."""
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    orch = ORBITOrchestrator()
    prompt = "I need a social feed architecture for 500 RPS with peak 1000 RPS, 90% reads / 10% writes, p95 under 50ms, and budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0, random_seed=42)

    assert state["workflow_status"] == "RECOMMENDED"
    assert state["execution_mode"] == "FALLBACK"
    assert len(state["clarification_questions"]) == 0

    workload = state["workload_spec"]
    assert workload is not None
    assert workload.request_rate_rps == 500.0
    assert workload.peak_load_factor == 2.0
    assert workload.read_ratio == 0.90
    assert workload.write_ratio == 0.10
    assert workload.p95_latency_target_ms == 50.0
    assert workload.max_monthly_budget_usd == 250.0

    assert len(state["candidate_architectures"]) == 3
    assert len(state["simulation_results"]) == 3
    assert state["recommendation"] is not None
    assert state["recommendation"].selected_architecture_id in ("arch_a_simple", "arch_b_cached", "arch_c_async")


def test_missing_or_ambiguous_requirements():
    """Test 2: Sparse/ambiguous requirements trigger clarification questions rather than false recommendations."""
    orch = ORBITOrchestrator()
    vague_prompt = "Build me a backend system for my application"
    state = orch.run(vague_prompt)

    assert state["workflow_status"] == "NEEDS_CLARIFICATION"
    assert len(state["clarification_questions"]) >= 2
    assert state["workload_spec"] is None
    assert state["recommendation"] is None


def test_invalid_workload_specification():
    """Test 3: Schema validation tool catches invalid workload constraints."""
    # Invalid read/write ratio sum
    bad_data = {
        "request_rate_rps": 500.0,
        "read_ratio": 0.80,
        "write_ratio": 0.50,  # Sum = 1.30 != 1.0
    }
    res = validate_workload.invoke({"workload_data": bad_data})
    assert res["valid"] is False
    assert len(res["errors"]) > 0


def test_valid_and_invalid_architecture_candidates():
    """Test 4: Candidate generation and topology validation."""
    gen_res = generate_architecture_candidates.invoke({"include_async": True, "include_unsupported": False})
    assert gen_res["is_valid"] is True
    assert len(gen_res["candidates"]) == 3

    # Test invalid DAG topology
    bad_arch_data = {
        "id": "arch_broken",
        "name": "Broken Architecture",
        "description": "Missing database component",
        "components": {
            "api": {
                "name": "api",
                "component_type": "api",
                "version": "1.0",
                "cpu_cores": 1.0,
                "memory_mb": 512,
                "concurrency_limit": 10,
                "monthly_cost_usd": 20.0,
            }
        },
        "connections": [],
        "read_path": ["api"],
        "write_path": ["api"],
        "queue_present": False,
        "required_models": [],
        "total_monthly_cost_usd": 20.0,
    }
    from orbit.generator.candidate_generator import ArchitectureGenerator
    gen = ArchitectureGenerator()
    with pytest.raises(ValueError, match="missing Database"):
        gen.validate_graph(ArchitectureGraph.model_validate(bad_arch_data))


def test_missing_component_models_routing(tmp_path):
    """Test 5: Explicit routing and authorization check for missing registry models."""
    db_file = tmp_path / "test_reg.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)
    with reg._get_connection() as conn:
        conn.cursor().execute("DELETE FROM models WHERE component_name = 'mongodb_cluster'")
        conn.commit()

    orch = ORBITOrchestrator(registry=reg)
    prompt = "Feed system handling 500 RPS with 90% reads, p95 under 50ms, budget $250/mo"

    # 1. Without permission: must report UNRESOLVED
    state_unres = orch.run(prompt, include_unsupported=True, auto_benchmark_missing=False)
    assert state_unres["workflow_status"] == "UNRESOLVED"
    assert "mongodb_cluster:mongodb:7.0-cluster" in state_unres["missing_models"]

    # 2. With permission: runs benchmark, fits model, and proceeds to recommendation
    state_bench = orch.run(prompt, include_unsupported=True, auto_benchmark_missing=True, simulation_duration_seconds=2.0)
    assert state_bench["workflow_status"] == "RECOMMENDED"
    assert len(state_bench["simulation_results"]) == 4


def test_tool_layer_safety_and_boundaries(tmp_path):
    """Test 6 & 8: Tools reject unallowed components and enforce bounds."""
    db_file = tmp_path / "test_tools.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)

    workload = WorkloadSpec(request_rate_rps=100.0)

    # Attempting to benchmark an untrusted/unallowed component
    bad_bench = run_benchmark.invoke({
        "component_name": "malicious_binary; cat /etc/passwd",
        "version": "1.0",
        "workload_data": workload.model_dump(),
        "registry": reg,
    })
    assert bad_bench["success"] is False
    assert "not in allowed benchmark catalog" in bad_bench["error"]
    assert bad_bench["provenance"] == "unknown"


def test_mocked_llm_structured_output_and_malformed_handling():
    """Test 9 & 13: Mocked LLM structured response and recovery from transient failure."""
    mock_model = MagicMock()
    mock_structured = MagicMock()
    mock_model.with_structured_output.return_value = mock_structured

    # Simulated LLM structured extraction output
    mock_structured.invoke.return_value = WorkloadExtractionResult(
        app_type="social_media_feed",
        request_rate_rps=600.0,
        peak_load_factor=2.5,
        read_ratio=0.85,
        write_ratio=0.15,
        p95_latency_target_ms=35.0,
        max_monthly_budget_usd=300.0,
        user_facts={"request_rate_rps": 600.0, "p95_latency_target_ms": 35.0},
    )

    prov_mgr = MagicMock()
    prov_mgr.get_chat_model.return_value = mock_model
    prov_mgr.is_llm_available.return_value = True

    agent = ArchitectureAgent(provider_mgr=prov_mgr)
    spec, q, a, mode = agent.parse_request("Mock prompt")
    assert mode == ExecutionMode.LLM
    assert spec is not None
    assert spec.request_rate_rps == 600.0
    assert spec.peak_load_factor == 2.5
    assert spec.p95_latency_target_ms == 35.0

    # Test error recovery: if LLM raises exception (rate limit or timeout), gracefully reverts to fallback
    mock_structured.invoke.side_effect = RuntimeError("OpenAI rate limit exceeded (429)")
    spec_fallback, q_f, a_f, mode_f = agent.parse_request("500 RPS feed with p95 50ms and budget $250")
    assert mode_f == ExecutionMode.FALLBACK
    assert spec_fallback is not None
    assert spec_fallback.request_rate_rps == 500.0


def test_provenance_preservation_and_evidence_labeling():
    """Test 11: Traceability of all evidence types (user_fact, agent_assumption, synthetic, simulated)."""
    orch = ORBITOrchestrator()
    prompt = "Social media feed handling 500 RPS with 90% reads, p95 latency under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=2.0)

    provenance = state["provenance"]
    assert "request_parsing" in provenance
    assert "simulation" in provenance
    assert provenance["simulation"] == "simulated"
    assert "recommendation" in provenance
    assert provenance["recommendation"] == "model-predicted"

    # Workload specification provenance items
    w_prov = state["workload_spec"].provenance_map
    assert w_prov["request_rate_rps"].provenance.value == "user_fact"
    assert w_prov["cache_assumed_hit_rate"].provenance.value == "agent_assumption"


def test_recommendation_consistency_with_deterministic_eval(monkeypatch):
    """Test 12: Orchestrator recommendation strictly mirrors underlying deterministic evaluator."""
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    orch = ORBITOrchestrator()
    prompt = "Social media feed handling 500 RPS with 90% reads, p95 latency under 50ms, budget $250/mo"
    state = orch.run(prompt, simulation_duration_seconds=3.0, random_seed=42)

    orch_rec = state["recommendation"]
    assert orch_rec is not None

    # Directly evaluate the exact same simulation results through ArchitectureRecommender
    direct_rec = ArchitectureRecommender.evaluate_and_recommend(
        workload=state["workload_spec"],
        sim_results=state["simulation_results"],
    )

    assert orch_rec.selected_architecture_id == direct_rec.selected_architecture_id
    assert orch_rec.status == direct_rec.status
    assert orch_rec.predicted_metrics["p95_latency_ms"] == direct_rec.predicted_metrics["p95_latency_ms"]
    assert orch_rec.rationale == direct_rec.rationale


def test_fastapi_agent_endpoint():
    """Test API integration for natural-language agent endpoint."""
    client = TestClient(app)

    # 1. Valid request
    res = client.post("/api/agent/run", json={
        "prompt": "Social feed 500 RPS, peak 1000 RPS, 90% reads, p95 under 50ms, budget $250/mo",
        "simulation_duration_seconds": 2.0,
        "force_synthetic": True,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["workflow_status"] == "RECOMMENDED"
    assert data["execution_mode"] in ("LLM", "FALLBACK")
    assert data["workload_spec"] is not None
    assert len(data["candidates"]) >= 2
    assert len(data["simulation_results"]) >= 2
    assert data["recommendation"] is not None

    # 2. Ambiguous request triggers clarification
    res_vague = client.post("/api/agent/run", json={
        "prompt": "A scalable system",
    })
    assert res_vague.status_code == 200
    data_vague = res_vague.json()
    assert data_vague["workflow_status"] == "NEEDS_CLARIFICATION"
    assert len(data_vague["clarification_questions"]) >= 2
    assert data_vague["recommendation"] is None
