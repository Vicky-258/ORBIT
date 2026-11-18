"""
Standardized System Archetype Catalog for ORBIT (Phase: Hybrid Workload Intelligence).
Defines universal distributed-system workload archetypes with engineering-grounded
indicators, baseline priors, candidate infrastructure primitives, and operational boundaries.

Archetypes are workload classifications, NOT complete application categories.
An application typically decomposes into multiple workloads across these archetypes.
"""
from enum import Enum
import re
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field


class ArchetypeID(str, Enum):
    """The six universal distributed-system workload archetypes."""
    READ_HEAVY_INTERACTIVE = "READ_HEAVY_INTERACTIVE"
    DECOUPLED_ASYNC_COMPUTE = "DECOUPLED_ASYNC_COMPUTE"
    TRANSACTIONAL_OLTP = "TRANSACTIONAL_OLTP"
    WRITE_HEAVY_INGESTION = "WRITE_HEAVY_INGESTION"
    REALTIME_STREAM_TRACKING = "REALTIME_STREAM_TRACKING"
    GENERAL_WEB_SERVICE = "GENERAL_WEB_SERVICE"


class BaselineWorkloadAssumptions(BaseModel):
    """Default engineering priors for simulation when values are not explicitly stated."""
    default_read_ratio: float = Field(ge=0.0, le=1.0)
    default_write_ratio: float = Field(ge=0.0, le=1.0)
    default_arrival_distribution: str = "poisson"
    default_burst_multiplier: float = 2.0
    default_cacheability: float = Field(default=0.0, ge=0.0, le=1.0)
    default_compute_intensity: str = "medium"  # "low", "medium", "high"
    default_p95_sla_ms: float = Field(gt=0.0)
    latency_sensitivity: str = "normal_interactive"  # "critical_low_latency", "normal_interactive", "asynchronous_delayed"
    default_consistency: str = "eventual"  # "strict_acid", "eventual", "read_your_writes"


class ParameterRanges(BaseModel):
    """Calibrated operational ranges."""
    min_rps: float = 1.0
    max_rps: float = 20000.0
    min_p95_ms: float = 1.0
    max_p95_ms: float = 5000.0
    typical_cache_hit_rate_range: Tuple[float, float] = (0.70, 0.95)


class SystemArchetype(BaseModel):
    """Machine-readable archetype definition."""
    id: ArchetypeID
    name: str
    description: str
    typical_applications: List[str]
    classification_indicators: List[str] = Field(description="Keywords and signals used for heuristic and LLM classification")
    baseline_assumptions: BaselineWorkloadAssumptions
    expected_behavior: str
    candidate_primitives: List[str] = Field(description="IDs of candidate infrastructure primitives")
    common_bottlenecks: List[str]
    parameter_ranges: ParameterRanges = Field(default_factory=ParameterRanges)


# =============================================================================
# THE 6 STANDARDIZED SYSTEM ARCHETYPES
# =============================================================================

ARCHETYPE_READ_HEAVY_INTERACTIVE = SystemArchetype(
    id=ArchetypeID.READ_HEAVY_INTERACTIVE,
    name="Read-Heavy Interactive",
    description="Read-dominated browsing, retrieval, and search operations involving frequently accessed or cacheable data.",
    typical_applications=[
        "Product catalogs",
        "Hotel and restaurant discovery",
        "Search interfaces",
        "Social media feeds",
        "Content portals",
    ],
    classification_indicators=[
        "browse", "browsing", "search", "searching", "lookup", "view", "viewing",
        "read", "reads", "catalog", "feed", "feeds", "display", "fetch", "query",
        "retrieve", "retrieval", "explore", "filter", "ratings", "reviews"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.85,
        default_write_ratio=0.15,
        default_arrival_distribution="poisson",
        default_burst_multiplier=2.0,
        default_cacheability=0.80,
        default_compute_intensity="low",
        default_p95_sla_ms=50.0,
        latency_sensitivity="critical_low_latency",
        default_consistency="eventual",
    ),
    expected_behavior="High cache hit rates shield the primary database from read spikes; sub-millisecond cache lookups provide rapid interactive responses.",
    candidate_primitives=[
        "api_gateway",
        "distributed_cache",
        "app_service",
        "relational_database",
        "search_index",
    ],
    common_bottlenecks=[
        "Database CPU saturation on cache miss storms",
        "Cache stampedes on expired keys",
        "Cache invalidation latency under occasional mutations",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=10.0,
        max_rps=10000.0,
        min_p95_ms=2.0,
        max_p95_ms=100.0,
        typical_cache_hit_rate_range=(0.75, 0.95),
    ),
)

ARCHETYPE_DECOUPLED_ASYNC_COMPUTE = SystemArchetype(
    id=ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
    name="Decoupled Asynchronous Compute",
    description="Long-running, computationally heavy, or batch operations separated from synchronous request handling via message queues and worker pools.",
    typical_applications=[
        "AI model inference / generation",
        "Video transcoding and rendering",
        "Batch data exports and report generation",
        "Document processing and OCR",
    ],
    classification_indicators=[
        "video", "videos", "render", "rendering", "generate", "generation",
        "ai", "batch", "transcode", "transcoding", "encode", "encoding",
        "export", "exporting", "worker", "workers", "queue", "async",
        "asynchronous", "background", "pipeline", "job", "jobs", "heavy compute"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.20,
        default_write_ratio=0.80,
        default_arrival_distribution="poisson",
        default_burst_multiplier=3.0,
        default_cacheability=0.10,
        default_compute_intensity="high",
        default_p95_sla_ms=50.0,  # SLA for HTTP 202 submission ACK
        latency_sensitivity="asynchronous_delayed",
        default_consistency="eventual",
    ),
    expected_behavior="API gateway immediately acknowledges job submission (HTTP 202 Accepted) within low latency; heavy processing is buffered in queues and drained by decoupled workers.",
    candidate_primitives=[
        "api_gateway",
        "message_queue",
        "background_worker",
        "object_storage",
        "relational_database",
    ],
    common_bottlenecks=[
        "Queue backlog growth when task arrival exceeds worker drain capacity",
        "Worker pool resource starvation (CPU/Memory/GPU)",
        "Database connection exhaustion when workers report task progress",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=1.0,
        max_rps=2000.0,
        min_p95_ms=10.0,
        max_p95_ms=200.0,
        typical_cache_hit_rate_range=(0.0, 0.30),
    ),
)

ARCHETYPE_TRANSACTIONAL_OLTP = SystemArchetype(
    id=ArchetypeID.TRANSACTIONAL_OLTP,
    name="Transactional OLTP",
    description="Operations involving strict ACID transactional data modifications, concurrent record updates, and strong consistency requirements.",
    typical_applications=[
        "Payment processing",
        "Hotel, flight, and seat bookings",
        "Inventory and checkout reservations",
        "Financial ledgers and order books",
    ],
    classification_indicators=[
        "booking", "bookings", "reserve", "reservation", "reservations",
        "payment", "payments", "pay", "bank", "banking", "financial",
        "finance", "transaction", "transactions", "transactional", "checkout",
        "order", "orders", "ledger", "balance", "wallet", "transfer", "oltp", "acid"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.50,
        default_write_ratio=0.50,
        default_arrival_distribution="poisson",
        default_burst_multiplier=1.8,
        default_cacheability=0.0,  # Transactional data is typically not cached directly
        default_compute_intensity="medium",
        default_p95_sla_ms=150.0,
        latency_sensitivity="normal_interactive",
        default_consistency="strict_acid",
    ),
    expected_behavior="Requests directly modify authoritative database records within atomic transactions; strict locking ensures consistency at the cost of concurrency constraints.",
    candidate_primitives=[
        "api_gateway",
        "app_service",
        "relational_database",
    ],
    common_bottlenecks=[
        "Row-level and table-level lock contention",
        "Database connection pool exhaustion under concurrent transactions",
        "Transaction commit latency due to WAL write fsync overhead",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=5.0,
        max_rps=3000.0,
        min_p95_ms=15.0,
        max_p95_ms=250.0,
        typical_cache_hit_rate_range=(0.0, 0.20),
    ),
)

ARCHETYPE_WRITE_HEAVY_INGESTION = SystemArchetype(
    id=ArchetypeID.WRITE_HEAVY_INGESTION,
    name="Write-Heavy Ingestion",
    description="Continuous, high-volume ingestion of incoming telemetry, sensor streams, clickstream events, or system logs.",
    typical_applications=[
        "IoT and drone sensor telemetry",
        "User activity and clickstream tracking",
        "Application and infrastructure log ingestion",
        "Time-series metric collection",
    ],
    classification_indicators=[
        "telemetry", "sensor", "sensors", "analytics", "tracking", "log",
        "logs", "logging", "metric", "metrics", "ingest", "ingestion",
        "events", "event collection", "audit trail", "clickstream", "timeseries"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.10,
        default_write_ratio=0.90,
        default_arrival_distribution="poisson",
        default_burst_multiplier=2.5,
        default_cacheability=0.05,
        default_compute_intensity="low",
        default_p95_sla_ms=100.0,
        latency_sensitivity="normal_interactive",
        default_consistency="eventual",
    ),
    expected_behavior="Incoming write events are buffered into high-throughput streaming brokers or append-only queues, and batched to persistent analytical storage.",
    candidate_primitives=[
        "api_gateway",
        "event_stream",
        "message_queue",
        "background_worker",
        "nosql_database",
        "relational_database",
    ],
    common_bottlenecks=[
        "Disk I/O and write bandwidth saturation",
        "Consumer lag accumulating on streaming partitions",
        "Index maintenance degradation on continuous insert workloads",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=50.0,
        max_rps=20000.0,
        min_p95_ms=5.0,
        max_p95_ms=150.0,
        typical_cache_hit_rate_range=(0.0, 0.10),
    ),
)

ARCHETYPE_REALTIME_STREAM_TRACKING = SystemArchetype(
    id=ArchetypeID.REALTIME_STREAM_TRACKING,
    name="Real-Time Stream Tracking",
    description="Persistent bidirectional connections, live coordinate updates, and low-latency state synchronization across concurrent clients.",
    typical_applications=[
        "Live vehicle / drone GPS tracking",
        "Real-time multiplayer gaming sessions",
        "Chat and collaborative whiteboard applications",
        "Live financial dashboard tickers",
    ],
    classification_indicators=[
        "gps", "live location", "live tracking", "realtime", "real-time",
        "websocket", "stream", "streaming", "chat", "multiplayer", "presence",
        "live updates", "coordinates", "pubsub", "push notifications"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.50,
        default_write_ratio=0.50,
        default_arrival_distribution="poisson",
        default_burst_multiplier=2.0,
        default_cacheability=0.20,
        default_compute_intensity="low",
        default_p95_sla_ms=30.0,
        latency_sensitivity="critical_low_latency",
        default_consistency="eventual",
    ),
    expected_behavior="Clients maintain persistent WebSocket or gRPC connections; state changes are fanned out via in-memory pub/sub brokers with minimal serialization latency.",
    candidate_primitives=[
        "websocket_gateway",
        "pubsub_broker",
        "in_memory_store",
        "app_service",
    ],
    common_bottlenecks=[
        "Socket file descriptor exhaustion under high concurrent connection counts",
        "Pub/Sub message fanout CPU overhead",
        "Network serialization and deserialization delays",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=20.0,
        max_rps=15000.0,
        min_p95_ms=1.0,
        max_p95_ms=50.0,
        typical_cache_hit_rate_range=(0.10, 0.40),
    ),
)

ARCHETYPE_GENERAL_WEB_SERVICE = SystemArchetype(
    id=ArchetypeID.GENERAL_WEB_SERVICE,
    name="General Web Service",
    description="Standard request-response application workloads with balanced CRUD operations and no dominant specialized bottleneck.",
    typical_applications=[
        "Internal administration portals",
        "User profile and account settings management",
        "Basic CRUD applications",
        "Low-volume microservices",
    ],
    classification_indicators=[
        "crud", "profile", "account", "settings", "admin", "dashboard",
        "management", "general", "standard", "web service", "api", "forms"
    ],
    baseline_assumptions=BaselineWorkloadAssumptions(
        default_read_ratio=0.60,
        default_write_ratio=0.40,
        default_arrival_distribution="poisson",
        default_burst_multiplier=1.5,
        default_cacheability=0.30,
        default_compute_intensity="medium",
        default_p95_sla_ms=100.0,
        latency_sensitivity="normal_interactive",
        default_consistency="eventual",
    ),
    expected_behavior="Balanced request-response cycles handled by application servers backed directly by relational databases.",
    candidate_primitives=[
        "api_gateway",
        "app_service",
        "relational_database",
    ],
    common_bottlenecks=[
        "Application server thread pool saturation",
        "Database connection pool limitations",
    ],
    parameter_ranges=ParameterRanges(
        min_rps=5.0,
        max_rps=5000.0,
        min_p95_ms=10.0,
        max_p95_ms=150.0,
        typical_cache_hit_rate_range=(0.20, 0.50),
    ),
)

# Central registry of all 6 canonical archetypes
SYSTEM_ARCHETYPE_CATALOG: Dict[ArchetypeID, SystemArchetype] = {
    ArchetypeID.READ_HEAVY_INTERACTIVE: ARCHETYPE_READ_HEAVY_INTERACTIVE,
    ArchetypeID.DECOUPLED_ASYNC_COMPUTE: ARCHETYPE_DECOUPLED_ASYNC_COMPUTE,
    ArchetypeID.TRANSACTIONAL_OLTP: ARCHETYPE_TRANSACTIONAL_OLTP,
    ArchetypeID.WRITE_HEAVY_INGESTION: ARCHETYPE_WRITE_HEAVY_INGESTION,
    ArchetypeID.REALTIME_STREAM_TRACKING: ARCHETYPE_REALTIME_STREAM_TRACKING,
    ArchetypeID.GENERAL_WEB_SERVICE: ARCHETYPE_GENERAL_WEB_SERVICE,
}


def get_archetype(archetype_id: str) -> Optional[SystemArchetype]:
    """Retrieves an archetype definition by string or enum ID."""
    try:
        aid = ArchetypeID(archetype_id)
        return SYSTEM_ARCHETYPE_CATALOG.get(aid)
    except (ValueError, KeyError):
        return None


def list_archetypes() -> List[SystemArchetype]:
    """Returns all 6 archetypes in canonical order."""
    return list(SYSTEM_ARCHETYPE_CATALOG.values())


def classify_workload_text(text: str) -> Tuple[ArchetypeID, float, List[str]]:
    """
    Classifies an operation or workload description into one of the 6 archetypes.
    Uses word-boundary matching over canonical indicators to prevent substring collisions.
    Returns: (archetype_id, confidence, matched_indicators)
    """
    text_lower = text.lower()
    scores: Dict[ArchetypeID, List[str]] = {aid: [] for aid in ArchetypeID}

    # Weight indicators based on specificity
    for aid, archetype in SYSTEM_ARCHETYPE_CATALOG.items():
        for indicator in archetype.classification_indicators:
            pattern = r"\b" + re.escape(indicator) + r"\b"
            if re.search(pattern, text_lower):
                scores[aid].append(indicator)

    # Specificity preference ordering when counts tie
    specificity_order = [
        ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
        ArchetypeID.REALTIME_STREAM_TRACKING,
        ArchetypeID.TRANSACTIONAL_OLTP,
        ArchetypeID.WRITE_HEAVY_INGESTION,
        ArchetypeID.READ_HEAVY_INTERACTIVE,
        ArchetypeID.GENERAL_WEB_SERVICE,
    ]

    best_aid = ArchetypeID.GENERAL_WEB_SERVICE
    max_matches = 0
    matched_indicators: List[str] = []

    for aid in specificity_order:
        matches = scores[aid]
        if len(matches) > max_matches:
            max_matches = len(matches)
            best_aid = aid
            matched_indicators = matches

    # Confidence calculation based on match strength
    if max_matches == 0:
        confidence = 0.40  # Default fallback confidence
    else:
        confidence = min(0.95, round(0.50 + (max_matches * 0.15), 2))

    return best_aid, confidence, matched_indicators
