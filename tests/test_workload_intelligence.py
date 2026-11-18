"""
Unit & Integration Tests for Milestone A — Workload Intelligence (Phase: Hybrid Workload Intelligence).
Tests Dynamic Domain Understanding, Workload Decomposition,
System Archetype Catalog, and Workload Profile Generation with Parameter Provenance.
"""
import pytest
from orbit.catalog.archetypes import (
    ArchetypeID,
    SystemArchetype,
    SYSTEM_ARCHETYPE_CATALOG,
    get_archetype,
    list_archetypes,
    classify_workload_text,
)
from orbit.catalog.workload_profile import (
    ParameterProvenanceSource,
    WorkloadProfile,
    generate_workload_profile,
)
from orbit.agent.domain_understanding import (
    DomainIdentity,
    DomainUnderstandingAgent,
    DomainOfflineError,
)
from orbit.agent.workload_decomposer import (
    DecomposedWorkload,
    WorkloadDecomposer,
    WorkloadDecompositionResult,
    WorkloadDecompositionOfflineError,
)
from orbit.agent.workload_intelligence import (
    WorkloadIntelligencePipeline,
    ApplicationWorkloadAnalysis,
)
from orbit.agent.provider import LLMProviderManager


# =============================================================================
# 1. System Archetype Catalog Tests
# =============================================================================

def test_archetype_catalog_completeness():
    """Verify all 6 canonical universal system archetypes exist in catalog."""
    archetypes = list_archetypes()
    assert len(archetypes) == 6
    ids = {a.id for a in archetypes}
    expected_ids = {
        ArchetypeID.READ_HEAVY_INTERACTIVE,
        ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
        ArchetypeID.TRANSACTIONAL_OLTP,
        ArchetypeID.WRITE_HEAVY_INGESTION,
        ArchetypeID.REALTIME_STREAM_TRACKING,
        ArchetypeID.GENERAL_WEB_SERVICE,
    }
    assert ids == expected_ids


def test_archetype_retrieval():
    """Verify retrieval by string or Enum ID."""
    arch = get_archetype("READ_HEAVY_INTERACTIVE")
    assert arch is not None
    assert arch.id == ArchetypeID.READ_HEAVY_INTERACTIVE
    assert arch.baseline_assumptions.default_read_ratio == 0.85
    assert arch.baseline_assumptions.default_p95_sla_ms == 50.0

    arch_async = get_archetype(ArchetypeID.DECOUPLED_ASYNC_COMPUTE)
    assert arch_async is not None
    assert "background_worker" in arch_async.candidate_primitives

    # Unknown ID returns None
    assert get_archetype("NON_EXISTENT_ARCHETYPE") is None


def test_classify_workload_text():
    """Verify word-boundary heuristic text classification into archetypes."""
    # Read-heavy
    aid, conf, indicators = classify_workload_text("Browse hotel listings, view ratings, and search amenities")
    assert aid == ArchetypeID.READ_HEAVY_INTERACTIVE
    assert conf >= 0.65
    assert "browse" in indicators or "ratings" in indicators or "search" in indicators

    # Async compute
    aid, conf, indicators = classify_workload_text("Generate AI educational video and transcode media in background")
    assert aid == ArchetypeID.DECOUPLED_ASYNC_COMPUTE
    assert conf >= 0.70
    assert "video" in indicators or "ai" in indicators

    # Transactional OLTP
    aid, conf, indicators = classify_workload_text("Process hotel room booking reservation and handle payments")
    assert aid == ArchetypeID.TRANSACTIONAL_OLTP
    assert "booking" in indicators or "payments" in indicators

    # Telemetry ingestion
    aid, conf, indicators = classify_workload_text("Continuous sensor telemetry and event stream logging")
    assert aid == ArchetypeID.WRITE_HEAVY_INGESTION
    assert "telemetry" in indicators or "sensor" in indicators

    # Real-time tracking
    aid, conf, indicators = classify_workload_text("Live GPS coordinates tracking and websocket push notifications")
    assert aid == ArchetypeID.REALTIME_STREAM_TRACKING
    assert "gps" in indicators or "websocket" in indicators


# =============================================================================
# 2. Dynamic Domain Understanding Tests
# =============================================================================

def test_domain_understanding_offline_protection():
    """In live mode (test_mode=False), offline LLM must raise DomainOfflineError rather than fabricating."""
    # Force fallback / offline provider
    agent = DomainUnderstandingAgent()
    if agent.provider_mgr.get_execution_mode().value == "fallback":
        with pytest.raises(DomainOfflineError) as exc_info:
            agent.analyze_domain("Build a hotel discovery app", test_mode=False)
        assert "ORBIT Domain Intelligence requires an active LLM provider" in str(exc_info.value)


def test_domain_understanding_test_mode():
    """In test_mode=True, deterministic linguistic extractor parses domain and entities."""
    agent = DomainUnderstandingAgent()
    prompt = "Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings."
    domain = agent.analyze_domain(prompt, test_mode=True)

    assert isinstance(domain, DomainIdentity)
    assert "hotel" in domain.domain_identity
    assert "map_provider" in domain.external_dependencies
    assert any("brows" in f for f in domain.core_functionalities)
    assert any("book" in f for f in domain.core_functionalities)
    assert "hotel" in domain.domain_entities
    assert "review" in domain.domain_entities


def test_domain_understanding_arbitrary_domains():
    """Verify free-form domain extraction for diverse applications."""
    agent = DomainUnderstandingAgent()

    # Drone delivery
    d1 = agent.analyze_domain("Design a drone delivery tracking system for live GPS positions and telemetry ingestion", test_mode=True)
    assert "drone" in d1.domain_identity or "delivery" in d1.domain_identity
    assert "map_provider" in d1.external_dependencies

    # Multiplayer game
    d2 = agent.analyze_domain("Create a multiplayer gaming platform with live matches and chat sessions", test_mode=True)
    assert "game" in d2.domain_identity or "gaming" in d2.domain_identity or "multiplayer" in d2.domain_identity


# =============================================================================
# 3. Workload Decomposition Tests
# =============================================================================

def test_workload_decomposition_offline_protection():
    """In live mode (test_mode=False), offline LLM must raise WorkloadDecompositionOfflineError."""
    decomposer = WorkloadDecomposer()
    domain = DomainIdentity(
        domain_identity="test_app",
        description="test",
        primary_purpose="test",
    )
    if decomposer.provider_mgr.get_execution_mode().value == "fallback":
        with pytest.raises(WorkloadDecompositionOfflineError) as exc_info:
            decomposer.decompose(domain, "Test prompt", test_mode=False)
        assert "ORBIT Workload Decomposition requires an active LLM provider" in str(exc_info.value)


def test_workload_decomposition_hotel_platform():
    """Verify hotel platform is decomposed into browsing, bookings, reviews, etc."""
    domain_agent = DomainUnderstandingAgent()
    decomposer = WorkloadDecomposer()

    prompt = "Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings."
    domain = domain_agent.analyze_domain(prompt, test_mode=True)
    result = decomposer.decompose(domain, prompt, test_mode=True)

    assert isinstance(result, WorkloadDecompositionResult)
    assert len(result.workloads) >= 2

    archetypes_found = {w.classified_archetype_id for w in result.workloads}
    # Hotel platform must decompose to at least READ_HEAVY_INTERACTIVE and TRANSACTIONAL_OLTP
    assert ArchetypeID.READ_HEAVY_INTERACTIVE in archetypes_found
    assert ArchetypeID.TRANSACTIONAL_OLTP in archetypes_found


def test_workload_decomposition_ai_education_platform():
    """Verify AI education platform decomposes into browsing, video generation, payments."""
    domain_agent = DomainUnderstandingAgent()
    decomposer = WorkloadDecomposer()

    prompt = "AI-powered education platform: students browse courses, generate personalized AI educational videos, and pay for subscriptions."
    domain = domain_agent.analyze_domain(prompt, test_mode=True)
    result = decomposer.decompose(domain, prompt, test_mode=True)

    archetypes_found = {w.classified_archetype_id for w in result.workloads}
    assert ArchetypeID.READ_HEAVY_INTERACTIVE in archetypes_found
    assert ArchetypeID.DECOUPLED_ASYNC_COMPUTE in archetypes_found
    assert ArchetypeID.TRANSACTIONAL_OLTP in archetypes_found


# =============================================================================
# 4. Workload Profile Generation Tests
# =============================================================================

def test_workload_profile_provenance_tracking():
    """Verify parameter provenance distinguishes USER_PROVIDED from ARCHETYPE_DEFAULT."""
    user_facts = {
        "arrival_rate_rps": 750.0,
        "read_ratio": 0.90,
        "write_ratio": 0.10,
        "p95_latency_target_ms": 40.0,
    }

    profile = generate_workload_profile(
        workload_id="catalog_browsing",
        operation_name="Catalog Browsing",
        description="User browsing items",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
        user_facts=user_facts,
    )

    assert isinstance(profile, WorkloadProfile)
    assert profile.traffic.arrival_rate_rps == 750.0
    assert profile.operations.read_ratio == 0.90
    assert profile.performance.p95_latency_target_ms == 40.0

    # Stated parameters are USER_PROVIDED
    assert profile.provenance_map["arrival_rate_rps"].source == ParameterProvenanceSource.USER_PROVIDED
    assert profile.provenance_map["arrival_rate_rps"].is_assumed is False
    assert profile.provenance_map["read_ratio"].source == ParameterProvenanceSource.USER_PROVIDED
    assert profile.provenance_map["p95_latency_target_ms"].source == ParameterProvenanceSource.USER_PROVIDED

    # Unstated parameters fall back to ARCHETYPE_DEFAULT with is_assumed=True
    assert profile.provenance_map["cacheability"].source == ParameterProvenanceSource.ARCHETYPE_DEFAULT
    assert profile.provenance_map["cacheability"].is_assumed is True
    assert profile.provenance_map["burst_multiplier"].is_assumed is True


def test_workload_profile_async_computation_intensity():
    """Verify decoupled async workloads receive appropriate task duration and intensity."""
    profile = generate_workload_profile(
        workload_id="video_gen",
        operation_name="Video Generation",
        description="Rendering video tasks",
        archetype_id=ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
        user_facts={"task_duration_ms": 5000.0},
    )

    assert profile.computation.compute_intensity == "high"
    assert profile.computation.task_duration_ms == 5000.0
    assert profile.operations.read_ratio == 0.20
    assert profile.operations.write_ratio == 0.80


# =============================================================================
# 5. End-to-End Workload Intelligence Pipeline Tests
# =============================================================================

def test_pipeline_hotel_platform():
    """Full pipeline execution on Hotel Discovery Platform."""
    pipeline = WorkloadIntelligencePipeline()
    prompt = "Build a hotel discovery platform where users can browse hotels, compare ratings, view locations on maps, upload reviews, and make bookings."
    analysis = pipeline.analyze(prompt, test_mode=True)

    assert isinstance(analysis, ApplicationWorkloadAnalysis)
    assert len(analysis.profiles) >= 2
    assert analysis.total_estimated_rps > 0.0
    assert analysis.assumptions_count > 0

    # Check profiles
    profile_archetypes = {p.archetype_id for p in analysis.profiles}
    assert ArchetypeID.READ_HEAVY_INTERACTIVE in profile_archetypes
    assert ArchetypeID.TRANSACTIONAL_OLTP in profile_archetypes


def test_pipeline_five_canonical_scenarios():
    """Execute pipeline against all 5 canonical requirement scenarios."""
    pipeline = WorkloadIntelligencePipeline()

    scenarios = [
        # 1. Hotel Discovery Platform
        ("Hotel platform: browse hotels, compare ratings, view maps, upload reviews, and book rooms.", [ArchetypeID.READ_HEAVY_INTERACTIVE, ArchetypeID.TRANSACTIONAL_OLTP]),
        # 2. AI Video Education Platform
        ("AI education platform: browse courses, generate personalized AI educational videos, pay for access.", [ArchetypeID.READ_HEAVY_INTERACTIVE, ArchetypeID.DECOUPLED_ASYNC_COMPUTE, ArchetypeID.TRANSACTIONAL_OLTP]),
        # 3. Drone Delivery Tracking Platform
        ("Drone delivery platform: continuous GPS telemetry ingestion and live tracking on map.", [ArchetypeID.WRITE_HEAVY_INGESTION, ArchetypeID.REALTIME_STREAM_TRACKING]),
        # 4. Financial Transaction Platform
        ("Financial platform supporting account balances, transfers, and transaction ledger history.", [ArchetypeID.TRANSACTIONAL_OLTP]),
        # 5. Multiplayer Gaming Platform
        ("Multiplayer game with live player positions, chat sessions, and match history.", [ArchetypeID.REALTIME_STREAM_TRACKING]),
    ]

    for prompt, expected_archetypes in scenarios:
        analysis = pipeline.analyze(prompt, test_mode=True)
        assert len(analysis.profiles) >= 1
        found_archetypes = {p.archetype_id for p in analysis.profiles}
        for exp in expected_archetypes:
            assert exp in found_archetypes, f"Scenario '{prompt[:30]}...' expected {exp}, found {found_archetypes}"
