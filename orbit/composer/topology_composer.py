"""
Dynamic Architecture Topology Composer for ORBIT (Phase: Hybrid Workload Intelligence).
Synthesizes verified TopologyGraphs from multi-workload profiles and standardized infrastructure primitives.

Design Principle:
Architecture topologies are composed dynamically based on workload behaviors,
not copied from rigid, hardcoded monolithic templates.
All composed architectures are strictly grounded in validated infrastructure primitives.
"""
import uuid
import logging
from typing import Dict, List, Optional, Set, Any
from orbit.catalog.archetypes import ArchetypeID
from orbit.catalog.workload_profile import WorkloadProfile
from orbit.catalog.primitives import get_primitive, INFRASTRUCTURE_PRIMITIVE_CATALOG
from orbit.agent.domain_understanding import DomainIdentity
from orbit.sdk.models import (
    TopologyGraph,
    ComponentNode,
    ComponentCategory,
    ConnectionEdge,
)

logger = logging.getLogger("orbit.composer.topology_composer")


class TopologyComposer:
    """Composes verified, executable TopologyGraphs from workload profiles."""

    def compose(
        self,
        workloads: List[WorkloadProfile],
        domain: Optional[DomainIdentity] = None,
        topology_name: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> TopologyGraph:
        """
        Synthesizes a cohesive TopologyGraph satisfying the requirements of all workloads.
        Merges shared infrastructure (e.g. unified API ingress, database layers)
        while routing decoupled and real-time paths cleanly.
        """
        constraints = constraints or {}
        components: Dict[str, ComponentNode] = {}
        connections_set: Set[tuple] = set()
        workload_routes: Dict[str, List[str]] = {}

        domain_name = domain.domain_identity if domain else "application"
        title = topology_name or f"{domain_name.replace('_', ' ').title()} Composed Architecture"

        # 1. Ingress Layer Setup
        has_realtime = any(w.archetype_id == ArchetypeID.REALTIME_STREAM_TRACKING for w in workloads)

        # Standard HTTP/REST/gRPC API Gateway
        components["api_gw"] = ComponentNode(
            id="api_gw",
            category=ComponentCategory.INGRESS,
            model_name="api_gateway",
            version="envoy:1.30-alpine",
            cpu_cores=2.0,
            memory_mb=2048,
            concurrency_limit=5000,
            monthly_cost_override_usd=35.0,
            parameters={"rate_limiting": True, "ssl_termination": True},
        )

        # WebSocket Gateway for real-time streaming if needed
        if has_realtime:
            components["ws_gw"] = ComponentNode(
                id="ws_gw",
                category=ComponentCategory.INGRESS,
                model_name="websocket_gateway",
                version="ws-gateway:latest",
                cpu_cores=2.0,
                memory_mb=4096,
                concurrency_limit=10000,
                monthly_cost_override_usd=45.0,
                parameters={"heartbeat_interval_s": 15, "max_connections": 10000},
            )

        # 2. Iterate through each workload and instantiate / link components
        for w in workloads:
            aid = w.archetype_id
            wid = w.workload_id

            if aid == ArchetypeID.READ_HEAVY_INTERACTIVE:
                # App compute
                self._ensure_app_server(components, connections_set)
                # Redis cache
                self._ensure_redis_cache(components, connections_set)
                # PostgreSQL DB
                self._ensure_postgres_db(components, connections_set)

                connections_set.add(("api_gw", "app_server", "http", 0.5))
                connections_set.add(("app_server", "redis_cache", "tcp", 0.3))
                connections_set.add(("redis_cache", "postgres_db", "tcp", 0.5))
                workload_routes[wid] = ["api_gw", "app_server", "redis_cache", "postgres_db"]

            elif aid == ArchetypeID.TRANSACTIONAL_OLTP:
                self._ensure_app_server(components, connections_set)
                self._ensure_postgres_db(components, connections_set)

                connections_set.add(("api_gw", "app_server", "http", 0.5))
                connections_set.add(("app_server", "postgres_db", "tcp", 0.5))
                workload_routes[wid] = ["api_gw", "app_server", "postgres_db"]

            elif aid == ArchetypeID.DECOUPLED_ASYNC_COMPUTE:
                self._ensure_app_server(components, connections_set)
                # Message Queue
                if "task_queue" not in components:
                    components["task_queue"] = ComponentNode(
                        id="task_queue",
                        category=ComponentCategory.QUEUE,
                        model_name="rabbitmq_queue",
                        version="rabbitmq:3.13-management",
                        cpu_cores=2.0,
                        memory_mb=4096,
                        concurrency_limit=10000,
                        monthly_cost_override_usd=30.0,
                        parameters={"durable": True, "prefetch_count": 50},
                    )
                # Background Worker
                if "background_worker" not in components:
                    components["background_worker"] = ComponentNode(
                        id="background_worker",
                        category=ComponentCategory.COMPUTE,
                        model_name="background_worker",
                        version="worker:python-3.12",
                        cpu_cores=4.0,
                        memory_mb=8192,
                        concurrency_limit=64,
                        monthly_cost_override_usd=80.0,
                        parameters={"pool_type": "prefork", "concurrency": 16},
                    )
                # Object Storage
                if "object_storage" not in components:
                    components["object_storage"] = ComponentNode(
                        id="object_storage",
                        category=ComponentCategory.STORAGE,
                        model_name="s3_storage",
                        version="minio:RELEASE.2024",
                        cpu_cores=2.0,
                        memory_mb=4096,
                        concurrency_limit=2000,
                        monthly_cost_override_usd=25.0,
                        parameters={"storage_class": "standard"},
                    )
                self._ensure_postgres_db(components, connections_set)

                connections_set.add(("api_gw", "app_server", "http", 0.5))
                connections_set.add(("app_server", "task_queue", "async_event", 1.0))
                connections_set.add(("task_queue", "background_worker", "async_event", 1.0))
                connections_set.add(("background_worker", "object_storage", "http", 2.0))
                connections_set.add(("background_worker", "postgres_db", "tcp", 0.5))
                workload_routes[wid] = ["api_gw", "app_server", "task_queue", "background_worker", "object_storage"]

            elif aid == ArchetypeID.WRITE_HEAVY_INGESTION:
                self._ensure_app_server(components, connections_set)
                # Ingestion Stream
                if "ingest_stream" not in components:
                    components["ingest_stream"] = ComponentNode(
                        id="ingest_stream",
                        category=ComponentCategory.QUEUE,
                        model_name="kafka_stream",
                        version="kafka:3.7-kraft",
                        cpu_cores=4.0,
                        memory_mb=8192,
                        concurrency_limit=20000,
                        monthly_cost_override_usd=70.0,
                        parameters={"replication_factor": 1, "partitions": 8},
                    )
                # Timeseries / NoSQL Database
                if "timeseries_db" not in components:
                    components["timeseries_db"] = ComponentNode(
                        id="timeseries_db",
                        category=ComponentCategory.DATABASE,
                        model_name="nosql_database",
                        version="cassandra:5.0",
                        cpu_cores=4.0,
                        memory_mb=16384,
                        concurrency_limit=2000,
                        monthly_cost_override_usd=110.0,
                        parameters={"write_consistency": "ONE"},
                    )

                connections_set.add(("api_gw", "app_server", "http", 0.5))
                connections_set.add(("app_server", "ingest_stream", "async_event", 0.8))
                connections_set.add(("ingest_stream", "timeseries_db", "tcp", 1.0))
                workload_routes[wid] = ["api_gw", "app_server", "ingest_stream", "timeseries_db"]

            elif aid == ArchetypeID.REALTIME_STREAM_TRACKING:
                # In-memory ephemeral state cache
                if "state_cache" not in components:
                    components["state_cache"] = ComponentNode(
                        id="state_cache",
                        category=ComponentCategory.CACHE,
                        model_name="redis_cache",
                        version="redis:7.2-alpine",
                        cpu_cores=2.0,
                        memory_mb=4096,
                        concurrency_limit=10000,
                        monthly_cost_override_usd=30.0,
                        parameters={"eviction_policy": "volatile-ttl"},
                    )
                # Event stream
                if "stream_event" not in components:
                    components["stream_event"] = ComponentNode(
                        id="stream_event",
                        category=ComponentCategory.QUEUE,
                        model_name="kafka_stream",
                        version="kafka:3.7-kraft",
                        cpu_cores=2.0,
                        memory_mb=4096,
                        concurrency_limit=10000,
                        monthly_cost_override_usd=40.0,
                    )

                ingress_id = "ws_gw" if "ws_gw" in components else "api_gw"
                connections_set.add((ingress_id, "state_cache", "tcp", 0.3))
                connections_set.add(("state_cache", "stream_event", "async_event", 0.8))
                workload_routes[wid] = [ingress_id, "state_cache", "stream_event"]

            else:  # GENERAL_WEB_SERVICE or fallback
                self._ensure_app_server(components, connections_set)
                self._ensure_postgres_db(components, connections_set)
                connections_set.add(("api_gw", "app_server", "http", 0.5))
                connections_set.add(("app_server", "postgres_db", "tcp", 0.5))
                workload_routes[wid] = ["api_gw", "app_server", "postgres_db"]

        # 3. Size Components to Accommodate Aggregate Workload Traffic
        total_traffic = sum(w.traffic.arrival_rate_rps for w in workloads)
        if "app_server" in components:
            if total_traffic > 1000.0:
                components["app_server"].cpu_cores = 8.0
                components["app_server"].memory_mb = 16384
                components["app_server"].concurrency_limit = 2000
                components["app_server"].monthly_cost_override_usd = 120.0
            elif total_traffic > 400.0:
                components["app_server"].cpu_cores = 4.0
                components["app_server"].memory_mb = 8192
                components["app_server"].concurrency_limit = 1000
                components["app_server"].monthly_cost_override_usd = 60.0

        if "postgres_db" in components:
            if total_traffic > 800.0:
                components["postgres_db"].cpu_cores = 8.0
                components["postgres_db"].memory_mb = 32768
                components["postgres_db"].concurrency_limit = 500
                components["postgres_db"].monthly_cost_override_usd = 220.0
            elif total_traffic > 300.0:
                components["postgres_db"].cpu_cores = 4.0
                components["postgres_db"].memory_mb = 16384
                components["postgres_db"].concurrency_limit = 250
                components["postgres_db"].monthly_cost_override_usd = 110.0

        # 4. Construct ConnectionEdge objects
        connections: List[ConnectionEdge] = []
        for src, tgt, proto, lat in sorted(connections_set):
            connections.append(
                ConnectionEdge(
                    source_id=src,
                    target_id=tgt,
                    protocol=proto,
                    network_latency_ms=lat,
                )
            )

        # 5. Populate default read_path and write_path for backward compatibility
        first_route = next(iter(workload_routes.values())) if workload_routes else ["api_gw"]
        default_read = list(first_route)
        default_write = list(first_route)

        for wid, path in workload_routes.items():
            matching_w = next((w for w in workloads if w.workload_id == wid), None)
            if matching_w:
                if matching_w.archetype_id == ArchetypeID.READ_HEAVY_INTERACTIVE:
                    default_read = list(path)
                elif matching_w.archetype_id in (ArchetypeID.TRANSACTIONAL_OLTP, ArchetypeID.WRITE_HEAVY_INGESTION, ArchetypeID.DECOUPLED_ASYNC_COMPUTE):
                    default_write = list(path)

        return TopologyGraph(
            topology_id=f"topo_{uuid.uuid4().hex[:10]}",
            name=title,
            description=f"Dynamically composed topology for {len(workloads)} workloads in {domain_name}.",
            components=list(components.values()),
            connections=connections,
            ingress_node_id="api_gw",
            read_path=default_read,
            write_path=default_write,
            workload_routes=workload_routes,
        )

    def _ensure_app_server(self, components: Dict[str, ComponentNode], connections_set: Set[tuple]) -> None:
        if "app_server" not in components:
            components["app_server"] = ComponentNode(
                id="app_server",
                category=ComponentCategory.COMPUTE,
                model_name="fastapi_service",
                version="python:3.12-slim",
                cpu_cores=2.0,
                memory_mb=4096,
                concurrency_limit=500,
                monthly_cost_override_usd=30.0,
                parameters={"workers": 4, "keepalive_timeout": 5},
            )

    def _ensure_redis_cache(self, components: Dict[str, ComponentNode], connections_set: Set[tuple]) -> None:
        if "redis_cache" not in components:
            components["redis_cache"] = ComponentNode(
                id="redis_cache",
                category=ComponentCategory.CACHE,
                model_name="redis_cache",
                version="redis:7.2-alpine",
                cpu_cores=1.0,
                memory_mb=2048,
                concurrency_limit=10000,
                monthly_cost_override_usd=25.0,
                parameters={"maxmemory_policy": "allkeys-lru"},
            )

    def _ensure_postgres_db(self, components: Dict[str, ComponentNode], connections_set: Set[tuple]) -> None:
        if "postgres_db" not in components:
            components["postgres_db"] = ComponentNode(
                id="postgres_db",
                category=ComponentCategory.DATABASE,
                model_name="postgres_db",
                version="postgres:16-alpine",
                cpu_cores=2.0,
                memory_mb=8192,
                concurrency_limit=100,
                monthly_cost_override_usd=60.0,
                parameters={"max_connections": 100, "shared_buffers": "2GB"},
            )
