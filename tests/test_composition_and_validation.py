"""
Unit & Integration Tests for Milestone B — Dynamic Architecture Composition & Topology Validation
(Phase: Hybrid Workload Intelligence).
"""
import pytest
from orbit.catalog.archetypes import ArchetypeID
from orbit.catalog.primitives import (
    PrimitiveCategory,
    InfrastructurePrimitive,
    INFRASTRUCTURE_PRIMITIVE_CATALOG,
    get_primitive,
    list_primitives,
    validate_primitive_connection,
)
from orbit.catalog.workload_profile import generate_workload_profile
from orbit.composer.topology_composer import TopologyComposer
from orbit.sdk.architecture_validator import (
    ArchitectureValidator,
    ArchitectureValidationResult,
    ValidationVerdict,
    ValidationIssueSeverity,
)
from orbit.sdk.models import (
    TopologyGraph,
    ComponentNode,
    ComponentCategory,
    ConnectionEdge,
)


# =============================================================================
# 1. Infrastructure Primitive Catalog Tests
# =============================================================================

def test_infrastructure_primitive_catalog():
    """Verify all required primitives exist and have valid specifications."""
    primitives = list_primitives()
    assert len(primitives) >= 10
    ids = {p.primitive_id for p in primitives}
    required = {
        "api_gateway",
        "load_balancer",
        "websocket_gateway",
        "app_service",
        "background_worker",
        "distributed_cache",
        "relational_database",
        "nosql_database",
        "object_storage",
        "message_queue",
        "event_stream",
    }
    assert required.issubset(ids)

    api_gw = get_primitive("api_gateway")
    assert api_gw is not None
    assert api_gw.category == PrimitiveCategory.TRAFFIC_MANAGEMENT
    assert "app_service" in api_gw.compatible_outbound_primitives

    # Test interface connection validation
    assert validate_primitive_connection("api_gateway", "app_service") is True
    assert validate_primitive_connection("app_service", "message_queue") is True
    assert validate_primitive_connection("message_queue", "background_worker") is True
    # Incompatible connection (e.g. database cannot directly call API gateway)
    assert validate_primitive_connection("relational_database", "api_gateway") is False


# =============================================================================
# 2. Topology Composer Tests
# =============================================================================

def test_topology_composer_hotel_platform():
    """Verify composition of multi-workload hotel platform (browsing + bookings)."""
    composer = TopologyComposer()

    w_browsing = generate_workload_profile(
        workload_id="hotel_browsing",
        operation_name="Hotel Browsing",
        description="Search and view hotels",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
    )
    w_booking = generate_workload_profile(
        workload_id="hotel_booking",
        operation_name="Hotel Booking",
        description="Transactional booking and payment",
        archetype_id=ArchetypeID.TRANSACTIONAL_OLTP,
    )

    topo = composer.compose(
        workloads=[w_browsing, w_booking],
        topology_name="Hotel Discovery Platform Architecture",
    )

    assert isinstance(topo, TopologyGraph)
    comp_ids = {c.id for c in topo.components}
    assert "api_gw" in comp_ids
    assert "app_server" in comp_ids
    assert "redis_cache" in comp_ids
    assert "postgres_db" in comp_ids

    # Check routes
    assert "hotel_browsing" in topo.workload_routes
    assert "hotel_booking" in topo.workload_routes
    assert topo.workload_routes["hotel_browsing"] == ["api_gw", "app_server", "redis_cache", "postgres_db"]
    assert topo.workload_routes["hotel_booking"] == ["api_gw", "app_server", "postgres_db"]


def test_topology_composer_ai_video_platform():
    """Verify composition of AI video platform with asynchronous queue & background worker."""
    composer = TopologyComposer()

    w_browsing = generate_workload_profile(
        workload_id="course_browsing",
        operation_name="Course Browsing",
        description="Browse courses",
        archetype_id=ArchetypeID.READ_HEAVY_INTERACTIVE,
    )
    w_video_gen = generate_workload_profile(
        workload_id="ai_video_gen",
        operation_name="AI Video Generation",
        description="Heavy GPU/CPU video synthesis",
        archetype_id=ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
    )

    topo = composer.compose(
        workloads=[w_browsing, w_video_gen],
        topology_name="AI Video Education Architecture",
    )

    comp_ids = {c.id for c in topo.components}
    assert "task_queue" in comp_ids
    assert "background_worker" in comp_ids
    assert "object_storage" in comp_ids
    assert topo.workload_routes["ai_video_gen"] == [
        "api_gw", "app_server", "task_queue", "background_worker", "object_storage"
    ]


def test_topology_composer_realtime_tracking():
    """Verify composition for realtime streaming and write-heavy telemetry."""
    composer = TopologyComposer()

    w_tracking = generate_workload_profile(
        workload_id="live_tracking",
        operation_name="Live GPS Tracking",
        description="Continuous bidirectional WebSocket tracking",
        archetype_id=ArchetypeID.REALTIME_STREAM_TRACKING,
    )
    w_telemetry = generate_workload_profile(
        workload_id="telemetry_ingest",
        operation_name="Sensor Telemetry Ingestion",
        description="High throughput sensor ingestion",
        archetype_id=ArchetypeID.WRITE_HEAVY_INGESTION,
    )

    topo = composer.compose(
        workloads=[w_tracking, w_telemetry],
        topology_name="Drone Telemetry Architecture",
    )

    comp_ids = {c.id for c in topo.components}
    assert "ws_gw" in comp_ids
    assert "state_cache" in comp_ids
    assert "ingest_stream" in comp_ids
    assert "timeseries_db" in comp_ids


# =============================================================================
# 3. Architecture Validator Tests
# =============================================================================

def test_architecture_validator_composed_topologies():
    """Validate that dynamically composed topologies pass strict validation."""
    composer = TopologyComposer()
    validator = ArchitectureValidator()

    w1 = generate_workload_profile("browse", "Browse", "Desc", ArchetypeID.READ_HEAVY_INTERACTIVE)
    w2 = generate_workload_profile("order", "Order", "Desc", ArchetypeID.TRANSACTIONAL_OLTP)
    w3 = generate_workload_profile("async_job", "Job", "Desc", ArchetypeID.DECOUPLED_ASYNC_COMPUTE)

    topo = composer.compose([w1, w2, w3])
    result = validator.validate(topo)

    assert isinstance(result, ArchitectureValidationResult)
    assert result.verdict in (ValidationVerdict.VALID, ValidationVerdict.WARNING)
    assert result.is_simulatable is True
    assert not any(i.severity == ValidationIssueSeverity.ERROR for i in result.issues)


def test_architecture_validator_missing_ingress():
    """Validator catches missing ingress node."""
    validator = ArchitectureValidator()
    bad_topo = TopologyGraph.model_construct(
        topology_id="bad_1",
        name="Bad Ingress",
        ingress_node_id="nonexistent_ingress",
        components=[
            ComponentNode(
                id="server",
                category=ComponentCategory.COMPUTE,
                model_name="app_service",
            )
        ],
        connections=[],
        read_path=["server"],
        write_path=["server"],
        workload_routes={},
    )
    res = validator.validate(bad_topo)
    assert res.verdict == ValidationVerdict.INVALID
    assert res.is_simulatable is False
    assert any(i.code == "ERR_INGRESS_MISSING" for i in res.issues)


def test_architecture_validator_self_loop():
    """Validator catches self loops."""
    validator = ArchitectureValidator()
    topo = TopologyGraph(
        topology_id="bad_2",
        name="Self Loop",
        ingress_node_id="gw",
        components=[
            ComponentNode(id="gw", category=ComponentCategory.INGRESS, model_name="api_gateway"),
            ComponentNode(id="app", category=ComponentCategory.COMPUTE, model_name="app_service"),
        ],
        connections=[
            ConnectionEdge(source_id="gw", target_id="app"),
            ConnectionEdge(source_id="app", target_id="app"),  # Self loop!
        ],
        read_path=["gw", "app"],
        write_path=["gw", "app"],
    )
    res = validator.validate(topo)
    assert res.verdict == ValidationVerdict.INVALID
    assert any(i.code == "ERR_SELF_LOOP" for i in res.issues)


def test_architecture_validator_disconnected_route_hop():
    """Validator catches a workload route containing disconnected hops."""
    validator = ArchitectureValidator()
    topo = TopologyGraph(
        topology_id="bad_3",
        name="Disconnected Route",
        ingress_node_id="gw",
        components=[
            ComponentNode(id="gw", category=ComponentCategory.INGRESS, model_name="api_gateway"),
            ComponentNode(id="app", category=ComponentCategory.COMPUTE, model_name="app_service"),
            ComponentNode(id="db", category=ComponentCategory.DATABASE, model_name="postgres_db"),
        ],
        connections=[
            ConnectionEdge(source_id="gw", target_id="app"),
            # Missing connection from app -> db!
        ],
        read_path=["gw", "app"],
        write_path=["gw", "app"],
        workload_routes={
            "broken_route": ["gw", "app", "db"]  # app -> db is disconnected!
        },
    )
    res = validator.validate(topo)
    assert res.verdict == ValidationVerdict.INVALID
    assert any(i.code == "ERR_DISCONNECTED_ROUTE_HOP" for i in res.issues)


def test_architecture_validator_synchronous_cycle():
    """Validator detects cyclic deadlocks in synchronous request paths."""
    validator = ArchitectureValidator()
    topo = TopologyGraph(
        topology_id="bad_4",
        name="Cyclic Graph",
        ingress_node_id="gw",
        components=[
            ComponentNode(id="gw", category=ComponentCategory.INGRESS, model_name="api_gateway"),
            ComponentNode(id="srv_a", category=ComponentCategory.COMPUTE, model_name="app_service"),
            ComponentNode(id="srv_b", category=ComponentCategory.COMPUTE, model_name="app_service"),
        ],
        connections=[
            ConnectionEdge(source_id="gw", target_id="srv_a", protocol="http"),
            ConnectionEdge(source_id="srv_a", target_id="srv_b", protocol="http"),
            ConnectionEdge(source_id="srv_b", target_id="srv_a", protocol="http"),  # Synchronous cycle!
        ],
        read_path=["gw", "srv_a", "srv_b"],
        write_path=["gw", "srv_a", "srv_b"],
    )
    res = validator.validate(topo)
    assert res.verdict == ValidationVerdict.INVALID
    assert any(i.code == "ERR_SYNCHRONOUS_CYCLE" for i in res.issues)
