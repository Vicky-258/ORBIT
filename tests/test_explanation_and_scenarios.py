"""
Unit & Integration Tests for Milestone D — Architectural Decision Explainer & Scenario Explorer
(Phase: Hybrid Workload Intelligence).
"""
import pytest
from orbit.catalog.archetypes import ArchetypeID
from orbit.catalog.workload_profile import generate_workload_profile
from orbit.agent.domain_understanding import DomainIdentity
from orbit.composer.topology_composer import TopologyComposer
from orbit.composer.scenario_explorer import ScenarioExplorer, ScenarioComparison
from orbit.agent.composition_explainer import CompositionExplainer, CompositionExplanation
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine


def test_composition_explainer():
    """Verify architectural decision explanation trace."""
    composer = TopologyComposer()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    domain = DomainIdentity(
        domain_identity="hotel_discovery_platform",
        description="Hotel discovery and bookings platform",
        primary_purpose="Browse hotels and make reservations",
        core_functionalities=["browsing", "booking"],
        domain_entities=["hotel", "user", "booking"],
        external_dependencies=["map_provider"],
    )

    w1 = generate_workload_profile("hotel_browsing", "Browsing", "Search hotels", ArchetypeID.READ_HEAVY_INTERACTIVE)
    w2 = generate_workload_profile("hotel_booking", "Booking", "Book rooms", ArchetypeID.TRANSACTIONAL_OLTP)

    topo = composer.compose([w1, w2], domain=domain)
    sim_res = engine.simulate_multi_workload(topo, [w1, w2], duration_seconds=3.0)

    explanation = explainer.explain(
        domain=domain,
        workloads=[w1, w2],
        topology=topo,
        simulation_result=sim_res,
    )

    assert isinstance(explanation, CompositionExplanation)
    assert len(explanation.workload_mappings) == 2
    assert "api_gw" in explanation.primitive_selection_reasons
    assert "redis_cache" in explanation.primitive_selection_reasons
    assert "postgres_db" in explanation.primitive_selection_reasons
    assert len(explanation.data_consistency_tradeoffs) > 0
    assert len(explanation.explicit_assumptions) > 0

    # Markdown report contains sections
    report = explanation.markdown_report
    assert "# ORBIT Architecture Decision Report" in report
    assert "## 2. Workload Classification & Archetype Mapping" in report
    assert "## 3. Infrastructure Primitive Selection" in report
    assert "## 5. Simulation & Bottleneck Analysis" in report


def test_scenario_explorer():
    """Verify parametric stress scenarios and headroom calculation."""
    composer = TopologyComposer()
    explorer = ScenarioExplorer()

    w1 = generate_workload_profile(
        workload_id="feed_browsing",
        operation_name="Feed Browsing",
        description="Read feed",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
        user_facts={"request_rate_rps": 100.0},
    )
    w2 = generate_workload_profile(
        workload_id="order_placement",
        operation_name="Order Placement",
        description="Place orders",
        archetype_id=ArchetypeID.TRANSACTIONAL_OLTP,
        user_facts={"request_rate_rps": 20.0},
    )

    topo = composer.compose([w1, w2], topology_name="Stress Test Platform")
    comparison = explorer.explore(
        topology=topo,
        workloads=[w1, w2],
        multipliers=[2.0],
        test_cache_degradation=True,
        duration_seconds=3.0,
    )

    assert isinstance(comparison, ScenarioComparison)
    assert comparison.baseline.throughput_achieved_rps > 0.0
    assert len(comparison.scenarios) >= 2

    # Find the 2x traffic spike scenario
    spike_2x = next((s for s in comparison.scenarios if "2.0x" in s.scenario_name or "2x" in s.scenario_name), None)
    assert spike_2x is not None
    assert spike_2x.throughput_achieved_rps > comparison.baseline.throughput_achieved_rps

    # Find cache degradation scenario
    cache_deg = next((s for s in comparison.scenarios if "Cache Degradation" in s.scenario_name), None)
    assert cache_deg is not None
    assert len(comparison.recommendations) > 0
