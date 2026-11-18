"""
Live End-to-End LLM Integration Verification Suite (Opt-in live network test).
Executes actual live calls to the configured LLM provider (Groq / OpenAI)
to verify that live models produce schema-compliant outputs that successfully
feed into the Architecture Composition, Validation, and SimPy simulation engine.

Run with:
    pytest tests/test_live_hybrid_pipeline.py -m live -s
"""
import pytest
import os
from orbit.agent.provider import LLMProviderManager, ExecutionMode
from orbit.agent.domain_understanding import DomainUnderstandingAgent
from orbit.agent.workload_decomposer import WorkloadDecomposer
from orbit.catalog.workload_profile import generate_workload_profile
from orbit.composer.topology_composer import TopologyComposer
from orbit.sdk.architecture_validator import ArchitectureValidator, ValidationVerdict
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine
from orbit.agent.composition_explainer import CompositionExplainer


@pytest.mark.live
def test_live_groq_llm_hotel_discovery_pipeline():
    """Live test: Groq LLM -> Domain -> Decomposer -> Composer -> Validator -> SimPy."""
    mgr = LLMProviderManager()
    if not mgr.is_llm_available():
        pytest.skip("Live LLM credentials not available or network offline.")

    domain_agent = DomainUnderstandingAgent(provider_mgr=mgr)
    decomposer = WorkloadDecomposer(provider_mgr=mgr)
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    prompt = "Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings."

    # 1. Live LLM Domain Understanding
    domain = domain_agent.analyze_domain(prompt, test_mode=False)
    assert domain.domain_identity == "hotel_discovery_platform"
    assert len(domain.core_functionalities) >= 3
    assert len(domain.domain_entities) >= 3

    # 2. Live LLM Workload Decomposition
    decomp = decomposer.decompose(domain, prompt, test_mode=False)
    assert len(decomp.workloads) >= 2
    for w in decomp.workloads:
        assert w.workload_id
        assert w.classified_archetype_id in [
            "READ_HEAVY_INTERACTIVE",
            "TRANSACTIONAL_OLTP",
            "WRITE_HEAVY_INGESTION",
            "GENERAL_WEB_SERVICE",
            "DECOUPLED_ASYNC_COMPUTE",
            "REALTIME_STREAM_TRACKING",
        ]

    # 3. Dynamic Architecture Composition from Live LLM Outputs
    profiles = [
        generate_workload_profile(
            workload_id=w.workload_id,
            operation_name=w.operation_name,
            description=w.description,
            archetype_id=w.classified_archetype_id,
        )
        for w in decomp.workloads
    ]
    topology = composer.compose(profiles, domain=domain)
    assert len(topology.components) >= 3
    assert len(topology.connections) >= 2

    # 4. Strict Deterministic Architecture Validation
    val_res = validator.validate(topology)
    assert val_res.is_simulatable is True
    assert val_res.verdict in (ValidationVerdict.VALID, ValidationVerdict.WARNING)

    # 5. SimPy Multi-Workload Simulation
    sim_res = engine.simulate_multi_workload(topology, profiles, duration_seconds=2.0)
    assert sim_res.completed_requests > 0
    assert len(sim_res.workload_metrics) == len(profiles)

    # 6. Explainer
    explanation = explainer.explain(domain, profiles, topology, sim_res)
    assert len(explanation.workload_mappings) == len(profiles)
    assert len(explanation.markdown_report) > 300
