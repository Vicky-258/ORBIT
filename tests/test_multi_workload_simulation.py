"""
Unit & Integration Tests for Milestone C — SimPy Multi-Workload Discrete-Event Simulation
(Phase: Hybrid Workload Intelligence).
"""
import pytest
from orbit.catalog.archetypes import ArchetypeID
from orbit.catalog.workload_profile import generate_workload_profile
from orbit.composer.topology_composer import TopologyComposer
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine
from orbit.core.schemas import SimulationResult


def test_multi_workload_simulation_hotel_platform():
    """Verify simultaneous execution of browsing and booking workloads."""
    composer = TopologyComposer()
    engine = DynamicSimPyEngine()

    w_browsing = generate_workload_profile(
        workload_id="hotel_browsing",
        operation_name="Hotel Browsing",
        description="Search and view hotels",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
        user_facts={"request_rate_rps": 150.0},
    )
    w_booking = generate_workload_profile(
        workload_id="hotel_booking",
        operation_name="Hotel Booking",
        description="Transactional booking and payment",
        archetype_id=ArchetypeID.TRANSACTIONAL_OLTP,
        user_facts={"request_rate_rps": 20.0},
    )

    topo = composer.compose([w_browsing, w_booking], topology_name="Hotel Multi-Workload Sim")
    result = engine.simulate_multi_workload(
        topology=topo,
        workloads=[w_browsing, w_booking],
        duration_seconds=5.0,
        random_seed=42,
    )

    assert isinstance(result, SimulationResult)
    assert result.completed_requests > 500
    assert result.throughput_achieved_rps > 100.0

    # Verify per-workload metrics
    metrics = result.workload_metrics
    assert "hotel_browsing" in metrics
    assert "hotel_booking" in metrics

    browsing_stats = metrics["hotel_browsing"]
    booking_stats = metrics["hotel_booking"]

    assert browsing_stats["completed_requests"] > 0
    assert booking_stats["completed_requests"] > 0
    assert browsing_stats["p95_latency_ms"] > 0.0
    assert booking_stats["p95_latency_ms"] > 0.0
    assert "sla_compliant" in browsing_stats
    assert "sla_compliant" in booking_stats


def test_multi_workload_simulation_async_decoupling():
    """
    Verify decoupled asynchronous compute returns fast client response
    while queue buffers the workload.
    """
    composer = TopologyComposer()
    engine = DynamicSimPyEngine()

    w_interactive = generate_workload_profile(
        workload_id="catalog_read",
        operation_name="Catalog Read",
        description="Fast reading",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
        user_facts={"request_rate_rps": 100.0},
    )
    w_async = generate_workload_profile(
        workload_id="video_render",
        operation_name="Video Render Job",
        description="Heavy video rendering job",
        archetype_id=ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
        user_facts={"request_rate_rps": 15.0},
    )

    topo = composer.compose([w_interactive, w_async], topology_name="Async Video Sim")
    result = engine.simulate_multi_workload(
        topology=topo,
        workloads=[w_interactive, w_async],
        duration_seconds=5.0,
        random_seed=123,
    )

    assert result.completed_requests > 300
    metrics = result.workload_metrics
    assert "video_render" in metrics
    # Enqueue latency for decoupled task should be fast (< 20ms client perceived acknowledgment)
    assert metrics["video_render"]["p50_latency_ms"] < 25.0
