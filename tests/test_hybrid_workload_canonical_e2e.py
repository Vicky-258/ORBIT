"""
End-to-End Canonical Integration Tests for ORBIT Hybrid Workload Intelligence
(Phase: Hybrid Workload Intelligence & Architecture Composition).

Validates the complete 5 canonical application scenarios:
1. Hotel Discovery & Booking Platform
2. AI Video Education Platform
3. Drone Delivery Fleet Tracking
4. Financial Payment & Ledger System
5. Real-Time Multiplayer Gaming
"""
import pytest
from orbit.agent.workload_intelligence import WorkloadIntelligencePipeline, ApplicationWorkloadAnalysis
from orbit.composer.topology_composer import TopologyComposer
from orbit.sdk.architecture_validator import ArchitectureValidator, ValidationVerdict
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine
from orbit.agent.composition_explainer import CompositionExplainer
from orbit.catalog.archetypes import ArchetypeID


# =============================================================================
# 1. Hotel Discovery & Booking Platform
# =============================================================================

def test_canonical_e2e_hotel_discovery():
    """E2E: Hotel discovery, ratings comparison, reviews, and bookings."""
    prompt = "Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings."

    pipeline = WorkloadIntelligencePipeline()
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    # Step 1: Workload Intelligence Pipeline
    analysis = pipeline.analyze(prompt, test_mode=True)
    assert "hotel" in analysis.domain.domain_identity
    assert len(analysis.profiles) >= 2
    archetypes = {p.archetype_id for p in analysis.profiles}
    assert ArchetypeID.READ_HEAVY_INTERACTIVE in archetypes
    assert ArchetypeID.TRANSACTIONAL_OLTP in archetypes

    # Step 2: Dynamic Architecture Composition
    topology = composer.compose(analysis.profiles, domain=analysis.domain)
    comp_ids = {c.id for c in topology.components}
    assert "api_gw" in comp_ids
    assert "redis_cache" in comp_ids
    assert "postgres_db" in comp_ids

    # Step 3: Strict Architecture Validation
    val_result = validator.validate(topology)
    assert val_result.is_simulatable is True
    assert val_result.verdict in (ValidationVerdict.VALID, ValidationVerdict.WARNING)

    # Step 4: SimPy Multi-Workload Simulation
    sim_result = engine.simulate_multi_workload(topology, analysis.profiles, duration_seconds=3.0)
    assert sim_result.completed_requests > 0
    assert len(sim_result.workload_metrics) >= 2

    # Step 5: Architectural Explanation & Synthesis
    explanation = explainer.explain(analysis.domain, analysis.profiles, topology, sim_result)
    assert len(explanation.workload_mappings) >= 2
    assert "redis_cache" in explanation.primitive_selection_reasons
    assert "# ORBIT Architecture Decision Report" in explanation.markdown_report


# =============================================================================
# 2. AI Video Generation Education Platform
# =============================================================================

def test_canonical_e2e_ai_video_education():
    """E2E: Course browsing, heavy AI video generation, and student ingestion."""
    prompt = "Create an AI-powered education platform where students browse courses, trigger asynchronous AI video generation for lessons, and stream learning progress telemetry."

    pipeline = WorkloadIntelligencePipeline()
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    analysis = pipeline.analyze(prompt, test_mode=True)
    archetypes = {p.archetype_id for p in analysis.profiles}
    assert ArchetypeID.DECOUPLED_ASYNC_COMPUTE in archetypes

    topology = composer.compose(analysis.profiles, domain=analysis.domain)
    comp_ids = {c.id for c in topology.components}
    assert "task_queue" in comp_ids
    assert "background_worker" in comp_ids
    assert "object_storage" in comp_ids

    val_result = validator.validate(topology)
    assert val_result.is_simulatable is True

    sim_result = engine.simulate_multi_workload(topology, analysis.profiles, duration_seconds=3.0)
    assert sim_result.completed_requests > 0
    assert len(sim_result.workload_metrics) >= 2

    explanation = explainer.explain(analysis.domain, analysis.profiles, topology, sim_result)
    assert "task_queue" in explanation.primitive_selection_reasons
    assert "background_worker" in explanation.primitive_selection_reasons


# =============================================================================
# 3. Drone Delivery Fleet Tracking System
# =============================================================================

def test_canonical_e2e_drone_delivery_tracking():
    """E2E: Live bidirectional GPS location tracking and sensor telemetry ingestion."""
    prompt = "Design a drone delivery tracking system for live GPS positions, high-volume sensor telemetry ingestion, and package delivery bookings."

    pipeline = WorkloadIntelligencePipeline()
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    analysis = pipeline.analyze(prompt, test_mode=True)
    archetypes = {p.archetype_id for p in analysis.profiles}
    assert ArchetypeID.REALTIME_STREAM_TRACKING in archetypes or ArchetypeID.WRITE_HEAVY_INGESTION in archetypes

    topology = composer.compose(analysis.profiles, domain=analysis.domain)
    comp_ids = {c.id for c in topology.components}
    assert "ws_gw" in comp_ids or "api_gw" in comp_ids

    val_result = validator.validate(topology)
    assert val_result.is_simulatable is True

    sim_result = engine.simulate_multi_workload(topology, analysis.profiles, duration_seconds=3.0)
    assert sim_result.completed_requests > 0
    assert len(sim_result.workload_metrics) >= 2

    explanation = explainer.explain(analysis.domain, analysis.profiles, topology, sim_result)
    assert len(explanation.workload_mappings) >= 2


# =============================================================================
# 4. Financial Payment & Ledger System
# =============================================================================

def test_canonical_e2e_financial_payment_ledger():
    """E2E: Strict ACID transactions, fund transfers, balance lookups."""
    prompt = "Architect a financial payment gateway and ledger system where users make atomic fund transfers, check balances, and view transaction history."

    pipeline = WorkloadIntelligencePipeline()
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    analysis = pipeline.analyze(prompt, test_mode=True)
    archetypes = {p.archetype_id for p in analysis.profiles}
    assert ArchetypeID.TRANSACTIONAL_OLTP in archetypes

    topology = composer.compose(analysis.profiles, domain=analysis.domain)
    comp_ids = {c.id for c in topology.components}
    assert "postgres_db" in comp_ids

    val_result = validator.validate(topology)
    assert val_result.is_simulatable is True

    sim_result = engine.simulate_multi_workload(topology, analysis.profiles, duration_seconds=3.0)
    assert sim_result.completed_requests > 0

    explanation = explainer.explain(analysis.domain, analysis.profiles, topology, sim_result)
    assert "postgres_db" in explanation.primitive_selection_reasons
    assert any("ACID" in t for t in explanation.data_consistency_tradeoffs)


# =============================================================================
# 5. Real-Time Multiplayer Gaming Matchmaking
# =============================================================================

def test_canonical_e2e_multiplayer_gaming():
    """E2E: Player matchmaking, low-latency state synchronization, leaderboard telemetry."""
    prompt = "Create a multiplayer gaming backend with live player matchmaking, real-time gameplay state synchronization, and high throughput leaderboard telemetry ingestion."

    pipeline = WorkloadIntelligencePipeline()
    composer = TopologyComposer()
    validator = ArchitectureValidator()
    engine = DynamicSimPyEngine()
    explainer = CompositionExplainer()

    analysis = pipeline.analyze(prompt, test_mode=True)
    topology = composer.compose(analysis.profiles, domain=analysis.domain)

    val_result = validator.validate(topology)
    assert val_result.is_simulatable is True

    sim_result = engine.simulate_multi_workload(topology, analysis.profiles, duration_seconds=3.0)
    assert sim_result.completed_requests > 0

    explanation = explainer.explain(analysis.domain, analysis.profiles, topology, sim_result)
    assert len(explanation.workload_mappings) >= 2
    assert len(explanation.markdown_report) > 200
