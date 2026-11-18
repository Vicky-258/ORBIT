"""
Universal Infrastructure Primitive Catalog for ORBIT (Phase: Hybrid Workload Intelligence).
Defines standard, mathematically verifiable infrastructure building blocks available
for topology composition and simulation modeling.

Design Principle:
Infrastructure primitives represent real, executable system components.
ORBIT prevents LLMs from hallucinating nonexistent or unsupported infrastructure components.
"""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PrimitiveCategory(str, Enum):
    """Universal classification of infrastructure primitives."""
    TRAFFIC_MANAGEMENT = "traffic_management"
    COMPUTE = "compute"
    CACHING = "caching"
    STORAGE = "storage"
    MESSAGING = "messaging"
    COMMUNICATION = "communication"


class InfrastructurePrimitive(BaseModel):
    """Specification of a validated infrastructure component primitive."""
    primitive_id: str = Field(description="Unique snake_case identifier e.g. 'api_gateway', 'relational_database'")
    name: str = Field(description="Standardized name")
    category: PrimitiveCategory = Field(description="Infrastructure category")
    description: str = Field(description="Operational function of this primitive")
    supported_protocols: List[str] = Field(description="Network protocols supported e.g. ['http', 'grpc']")
    default_service_time_ms: float = Field(description="Baseline processing service time in milliseconds")
    capacity_limit_units: int = Field(description="Standard concurrency or connection limit per instance")
    compatible_inbound_primitives: List[str] = Field(description="Primitive IDs allowed to connect into this component")
    compatible_outbound_primitives: List[str] = Field(description="Primitive IDs this component is allowed to connect to")
    simulation_model: str = Field(description="SimPy queueing model type: 'multi_server_queue', 'cache_node', 'storage_node', 'buffer_queue'")
    scaling_model: str = Field(default="horizontal", description="Scaling behavior: 'horizontal', 'vertical', 'partitioned'")
    typical_bottlenecks: List[str] = Field(default_factory=list, description="Common failure or saturation modes")


# =============================================================================
# Canonical Infrastructure Primitive Catalog
# =============================================================================

INFRASTRUCTURE_PRIMITIVE_CATALOG: Dict[str, InfrastructurePrimitive] = {
    "api_gateway": InfrastructurePrimitive(
        primitive_id="api_gateway",
        name="API Gateway",
        category=PrimitiveCategory.TRAFFIC_MANAGEMENT,
        description="Unified ingress layer providing routing, SSL termination, rate limiting, and auth enforcement.",
        supported_protocols=["http", "https", "grpc"],
        default_service_time_ms=1.5,
        capacity_limit_units=5000,
        compatible_inbound_primitives=["client"],
        compatible_outbound_primitives=["app_service", "distributed_cache", "message_queue", "event_stream"],
        simulation_model="multi_server_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["connection_exhaustion", "cpu_saturation", "ssl_handshake_overhead"],
    ),
    "load_balancer": InfrastructurePrimitive(
        primitive_id="load_balancer",
        name="Load Balancer",
        category=PrimitiveCategory.TRAFFIC_MANAGEMENT,
        description="L4/L7 traffic distributor balancing client requests across stateless compute instances.",
        supported_protocols=["http", "https", "tcp"],
        default_service_time_ms=0.8,
        capacity_limit_units=10000,
        compatible_inbound_primitives=["client", "api_gateway"],
        compatible_outbound_primitives=["app_service", "background_worker"],
        simulation_model="multi_server_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["connection_limits", "packet_forwarding_saturation"],
    ),
    "websocket_gateway": InfrastructurePrimitive(
        primitive_id="websocket_gateway",
        name="WebSocket Gateway",
        category=PrimitiveCategory.COMMUNICATION,
        description="Stateful duplex connection gateway managing persistent bidirectional client sessions.",
        supported_protocols=["websocket", "wss"],
        default_service_time_ms=2.0,
        capacity_limit_units=10000,
        compatible_inbound_primitives=["client"],
        compatible_outbound_primitives=["app_service", "distributed_cache", "event_stream"],
        simulation_model="multi_server_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["open_file_descriptors", "memory_per_socket", "keepalive_churn"],
    ),
    "app_service": InfrastructurePrimitive(
        primitive_id="app_service",
        name="Application Service",
        category=PrimitiveCategory.COMPUTE,
        description="Stateless application compute executing business logic, data transformation, and service orchestration.",
        supported_protocols=["http", "grpc"],
        default_service_time_ms=8.0,
        capacity_limit_units=500,
        compatible_inbound_primitives=["api_gateway", "load_balancer", "websocket_gateway"],
        compatible_outbound_primitives=[
            "distributed_cache",
            "relational_database",
            "nosql_database",
            "object_storage",
            "message_queue",
            "event_stream",
        ],
        simulation_model="multi_server_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["thread_pool_exhaustion", "cpu_bound_execution", "database_connection_pool_limits"],
    ),
    "background_worker": InfrastructurePrimitive(
        primitive_id="background_worker",
        name="Background Worker",
        category=PrimitiveCategory.COMPUTE,
        description="Asynchronous compute worker consuming queued tasks for decoupled long-running execution.",
        supported_protocols=["async_event"],
        default_service_time_ms=50.0,
        capacity_limit_units=100,
        compatible_inbound_primitives=["message_queue", "event_stream"],
        compatible_outbound_primitives=["relational_database", "nosql_database", "object_storage"],
        simulation_model="multi_server_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["worker_starvation", "high_memory_consumption", "slow_downstream_storage_writes"],
    ),
    "distributed_cache": InfrastructurePrimitive(
        primitive_id="distributed_cache",
        name="Distributed Cache",
        category=PrimitiveCategory.CACHING,
        description="In-memory key-value cache serving high-frequency reads and ephemeral session/location state.",
        supported_protocols=["redis_protocol", "memcached_protocol", "tcp"],
        default_service_time_ms=0.5,
        capacity_limit_units=20000,
        compatible_inbound_primitives=["app_service", "api_gateway", "websocket_gateway"],
        compatible_outbound_primitives=["relational_database", "nosql_database"],
        simulation_model="cache_node",
        scaling_model="horizontal",
        typical_bottlenecks=["cache_stampede", "memory_eviction_pressure", "hot_key_contention"],
    ),
    "relational_database": InfrastructurePrimitive(
        primitive_id="relational_database",
        name="Relational Database",
        category=PrimitiveCategory.STORAGE,
        description="ACID-compliant transactional database providing structured relational storage and strict consistency.",
        supported_protocols=["sql", "tcp"],
        default_service_time_ms=12.0,
        capacity_limit_units=200,
        compatible_inbound_primitives=["app_service", "background_worker", "distributed_cache"],
        compatible_outbound_primitives=[],
        simulation_model="storage_node",
        scaling_model="vertical",
        typical_bottlenecks=["lock_contention", "connection_pool_starvation", "disk_iops_saturation"],
    ),
    "nosql_database": InfrastructurePrimitive(
        primitive_id="nosql_database",
        name="NoSQL Database",
        category=PrimitiveCategory.STORAGE,
        description="Horizontally partitionable document/wide-column datastore optimized for high write throughput and scale.",
        supported_protocols=["document_protocol", "http", "grpc"],
        default_service_time_ms=5.0,
        capacity_limit_units=2000,
        compatible_inbound_primitives=["app_service", "background_worker", "distributed_cache"],
        compatible_outbound_primitives=[],
        simulation_model="storage_node",
        scaling_model="partitioned",
        typical_bottlenecks=["partition_hotspots", "eventual_consistency_replication_lag"],
    ),
    "object_storage": InfrastructurePrimitive(
        primitive_id="object_storage",
        name="Object Storage",
        category=PrimitiveCategory.STORAGE,
        description="Blob storage repository designed for immutable media files, videos, documents, and backups.",
        supported_protocols=["http_s3", "https"],
        default_service_time_ms=25.0,
        capacity_limit_units=1000,
        compatible_inbound_primitives=["app_service", "background_worker", "api_gateway"],
        compatible_outbound_primitives=[],
        simulation_model="storage_node",
        scaling_model="horizontal",
        typical_bottlenecks=["bandwidth_throttling", "multipart_upload_overhead"],
    ),
    "message_queue": InfrastructurePrimitive(
        primitive_id="message_queue",
        name="Message Queue",
        category=PrimitiveCategory.MESSAGING,
        description="Point-to-point asynchronous queue providing durable task buffering and flow control.",
        supported_protocols=["amqp", "async_event", "http"],
        default_service_time_ms=2.0,
        capacity_limit_units=10000,
        compatible_inbound_primitives=["app_service", "api_gateway"],
        compatible_outbound_primitives=["background_worker"],
        simulation_model="buffer_queue",
        scaling_model="horizontal",
        typical_bottlenecks=["queue_backlog_growth", "memory_pressure_on_unacked_messages"],
    ),
    "event_stream": InfrastructurePrimitive(
        primitive_id="event_stream",
        name="Event Stream",
        category=PrimitiveCategory.MESSAGING,
        description="Distributed partitioned append-only log for high-throughput event ingestion and real-time streaming.",
        supported_protocols=["kafka_protocol", "async_event"],
        default_service_time_ms=1.0,
        capacity_limit_units=50000,
        compatible_inbound_primitives=["app_service", "websocket_gateway", "api_gateway"],
        compatible_outbound_primitives=["background_worker", "nosql_database"],
        simulation_model="buffer_queue",
        scaling_model="partitioned",
        typical_bottlenecks=["partition_skew", "consumer_group_rebalancing_lag"],
    ),
}


def get_primitive(primitive_id: str) -> Optional[InfrastructurePrimitive]:
    """Retrieve an infrastructure primitive by ID."""
    return INFRASTRUCTURE_PRIMITIVE_CATALOG.get(primitive_id.lower().strip())


def list_primitives() -> List[InfrastructurePrimitive]:
    """Return all available infrastructure primitives."""
    return list(INFRASTRUCTURE_PRIMITIVE_CATALOG.values())


def validate_primitive_connection(source_primitive_id: str, target_primitive_id: str) -> bool:
    """
    Validates whether source_primitive can legally connect to target_primitive
    under standard distributed system interface rules.
    """
    src = get_primitive(source_primitive_id)
    tgt = get_primitive(target_primitive_id)
    if not src or not tgt:
        return False
    
    can_out = target_primitive_id in src.compatible_outbound_primitives
    can_in = source_primitive_id in tgt.compatible_inbound_primitives
    return can_out and can_in
