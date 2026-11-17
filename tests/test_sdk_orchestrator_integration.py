"""
End-to-End Integration Tests for Phase 5.3 Simulation SDK & Orchestrator.
Validates the photo sharing 200K DAU user journey:
- Turn 0: Ambiguity ranking and threshold-based clarification (asking ranked questions, no silent assumptions).
- Turn 1: Clarified execution with SDK workspace initialization, discrete-event SimPy simulation, and comparative recommendation.
- Direct SDK REST endpoints (/api/sdk/capabilities, /api/sdk/workspaces/{id}).
"""
import pytest
from fastapi.testclient import TestClient

from aads.agent.orchestrator import AADSOrchestrator
from aads.sdk.tools import get_simulation_sdk
from aads.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_photo_sharing_turn_0_clarification_prompt():
    """
    Test Turn 0: Non-technical user gives natural language requirements with 200K DAU.
    Since latency SLA and budget ceiling are unspecified (ambiguity >= 0.50),
    the system must NOT silently invent them; it must ask 2 ranked clarification questions.
    """
    orch = AADSOrchestrator()
    prompt = (
        "I want a backend for a photo sharing app that targets around 200K active daily users, "
        "where people share photos with a wide range of followers with features to like comment share those images, "
        "people also have option to have feed and follow each other"
    )

    state = orch.run(prompt, clarification_turn=0)

    assert state["workflow_status"] == "NEEDS_CLARIFICATION"
    assert state["workload_spec"] is None
    assert len(state["clarification_questions"]) == 2
    # Verify ranked questions address the highest-weight missing dimensions: Latency (0.30) & Budget (0.20)
    assert any("latency" in q.lower() or "sla" in q.lower() for q in state["clarification_questions"])
    assert any("budget" in q.lower() or "usd" in q.lower() for q in state["clarification_questions"])


def test_photo_sharing_turn_1_clarified_execution():
    """
    Test Turn 1: Clarified follow-up turn where user confirms or proceeds with inferred parameters.
    Ensures:
    1. Bounded dialogue prevents infinite clarification loops (clarification_turn=1 proceeds).
    2. DAU is cleanly converted to ~58 avg RPS (~174 peak RPS).
    3. Access pattern is inferred as 90% Reads / 10% Writes.
    4. An isolated SDK Workspace is created and tracked.
    5. SDK experiments are populated and discrete-event simulations run.
    6. Recommendation is produced with empirical evidence.
    """
    orch = AADSOrchestrator()
    prompt = (
        "I want a backend for a photo sharing app that targets around 200K active daily users, "
        "where people share photos with a wide range of followers with features to like comment share those images, "
        "people also have option to have feed and follow each other"
    )

    state = orch.run(
        prompt,
        clarification_turn=1,
        simulation_duration_seconds=2.0,
        random_seed=42,
    )

    assert state["workflow_status"] == "RECOMMENDED"
    assert state["workload_spec"] is not None

    workload = state["workload_spec"]
    assert workload.request_rate_rps == 57.9
    assert workload.peak_load_factor == 3.0
    assert workload.read_ratio == 0.90
    assert workload.write_ratio == 0.10

    # User facts vs Agent assumptions separation
    user_facts = [p.value for p in workload.provenance_map.values() if p.provenance.value == "user_fact"]
    assert any("200K active daily users" in str(v) or "57.9" in str(v) for v in user_facts)
    assert len(state["assumptions"]) > 0

    # SDK Workspace and Experiments verification
    assert state.get("sdk_workspace_id") is not None
    sdk_exp_ids = state.get("sdk_experiments", [])
    assert len(sdk_exp_ids) >= 3

    # Simulation results & recommendation
    assert len(state["simulation_results"]) >= 3
    assert state["recommendation"] is not None
    assert state["recommendation"].selected_architecture_id in ("arch_a_simple", "arch_b_cached", "arch_c_async")

    # SDK comparison in provenance
    assert "sdk_comparison" in state["provenance"]
    sdk_comp = state["provenance"]["sdk_comparison"]
    assert "dimensions" in sdk_comp
    assert "pareto_optimal_experiment_ids" in sdk_comp
    assert "compared_experiment_ids" in sdk_comp


def test_sdk_rest_api_endpoints(client):
    """
    Validates direct REST endpoints for capability discovery and workspace inspection.
    """
    # 1. Capability Discovery
    cap_resp = client.get("/api/sdk/capabilities")
    assert cap_resp.status_code == 200
    caps = cap_resp.json()
    assert "supported_categories" in caps
    assert "components" in caps
    assert any(m["model_name"] == "postgres_db" for m in caps["components"])

    # 2. Demo Run with Turn 0 -> NEEDS_CLARIFICATION
    demo_turn_0 = client.post("/api/demo/run", json={
        "prompt": "I want a photo sharing app for 200K active daily users",
        "clarification_turn": 0,
    })
    assert demo_turn_0.status_code == 200
    resp_0 = demo_turn_0.json()
    assert resp_0["recommendation"]["is_conclusive"] is False
    assert len(resp_0["request_summary"]["clarification_questions"]) >= 1

    # 3. Demo Run with Turn 1 -> Conclusive Blueprint
    demo_turn_1 = client.post("/api/demo/run", json={
        "prompt": "I want a photo sharing app for 200K active daily users",
        "clarification_turn": 1,
        "simulation_duration_seconds": 2.0,
    })
    assert demo_turn_1.status_code == 200
    resp_1 = demo_turn_1.json()
    assert resp_1["recommendation"]["is_conclusive"] is True
    assert resp_1["recommendation"]["selected_architecture_id"] is not None
    assert len(resp_1["architecture_comparison"]) >= 3
