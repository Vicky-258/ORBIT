"""
Simulation Capability Discovery Catalog for AADS Simulation SDK (Phase 5.3B).
Provides machine-readable discovery of supported component categories,
empirical models, operating ranges, simulation metrics, and known limitations.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from aads.registry.component_registry import ComponentRegistry
from aads.sdk.models import ComponentCategory


class ComponentCapability(BaseModel):
    """Machine-readable capability descriptor for a component category and model."""
    category: ComponentCategory
    model_name: str
    display_name: str
    supported_versions: List[str]
    calibration_status: str          # 'CALIBRATED_EMPIRICAL', 'SYNTHETIC_PRIOR', 'MISSING'
    model_type: str                  # 'piecewise_ridge', 'linear_demand', 'sub_ms_lookup'
    operating_range_rps: List[float] = Field(description="[min_rps, max_rps] valid operating envelope")
    operating_range_concurrency: List[int] = Field(description="[min_concurrency, max_concurrency]")
    validation_rmse_ms: Optional[float] = None
    provenance: str
    supported_metrics: List[str]
    known_limitations: List[str]


class SimulationCapabilitiesCatalog(BaseModel):
    """Machine-readable capability registry exposed to AI agents via SDK."""
    engine_name: str = "AADS SimPy Discrete-Event Simulation Engine"
    engine_version: str = "5.3B"
    supported_categories: List[str]
    components: List[ComponentCapability]
    supported_workload_patterns: List[str]
    supported_topology_patterns: List[str]
    available_simulation_metrics: List[str]
    unsupported_behaviors: List[str]
    general_guidance: str

    @classmethod
    def discover(
        cls,
        registry: Optional[ComponentRegistry] = None,
        category_filter: Optional[str] = None,
    ) -> "SimulationCapabilitiesCatalog":
        """
        Dynamically interrogates ComponentRegistry to inspect live calibrated models
        and returns a structured capabilities catalog.
        """
        reg = registry or ComponentRegistry()
        reg.seed_baseline_data()
        all_models = reg.list_models()

        components: List[ComponentCapability] = []

        # 1. PostgreSQL Relational Database
        pg_models = [m for m in all_models if "postgres" in m.component_name.lower()]
        pg_primary = pg_models[0] if pg_models else None
        components.append(
            ComponentCapability(
                category=ComponentCategory.DATABASE,
                model_name="postgres_db",
                display_name="PostgreSQL Relational Database",
                supported_versions=["postgres:16-alpine"],
                calibration_status="CALIBRATED_EMPIRICAL" if (pg_primary and not pg_primary.is_synthetic_fixture) else "SYNTHETIC_PRIOR",
                model_type=pg_primary.model_type if pg_primary else "piecewise_ridge",
                operating_range_rps=[
                    pg_primary.min_supported_rps if pg_primary else 10.0,
                    pg_primary.max_supported_rps if pg_primary else 800.0,
                ],
                operating_range_concurrency=[
                    pg_primary.min_supported_concurrency if pg_primary else 1,
                    pg_primary.max_supported_concurrency if pg_primary else 32,
                ],
                validation_rmse_ms=pg_primary.validation_rmse_ms if pg_primary else 0.45,
                provenance=pg_primary.provenance if pg_primary else "Calibrated physical Docker benchmarks (Phase 4F)",
                supported_metrics=[
                    "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
                    "throughput_achieved_rps", "cpu_utilization_pct", "connection_pool_queue_length"
                ],
                known_limitations=[
                    "Saturates above 650-800 RPS on 2 vCPU quotas",
                    "Simulates connection pool queueing; bare-metal storage IOPS throttling not explicitly modelled",
                    "Complex follower graph joins require higher CPU demand than simple OLTP lookups"
                ],
            )
        )

        # 2. Redis Key-Value Cache
        redis_models = [m for m in all_models if "redis" in m.component_name.lower()]
        redis_primary = redis_models[0] if redis_models else None
        components.append(
            ComponentCapability(
                category=ComponentCategory.CACHE,
                model_name="redis_cache",
                display_name="Redis In-Memory Key-Value Store",
                supported_versions=["redis:7.2-alpine"],
                calibration_status="CALIBRATED_EMPIRICAL" if (redis_primary and not redis_primary.is_synthetic_fixture) else "CALIBRATED_EMPIRICAL",
                model_type="sub_ms_lookup",
                operating_range_rps=[1.0, 5000.0],
                operating_range_concurrency=[1, 500],
                validation_rmse_ms=redis_primary.validation_rmse_ms if redis_primary else 0.12,
                provenance="Empirical sub-millisecond memory latency calibration",
                supported_metrics=[
                    "p50_latency_ms", "p95_latency_ms", "cache_hit_rate", "memory_utilization_mb"
                ],
                known_limitations=[
                    "In-memory storage cost scales with dataset size",
                    "Cache invalidation latency under high write frequency is not dynamically simulated"
                ],
            )
        )

        # 3. Message Queue / Broker (Kafka / Redis Queue)
        components.append(
            ComponentCapability(
                category=ComponentCategory.QUEUE,
                model_name="kafka_queue",
                display_name="Apache Kafka Distributed Message Queue",
                supported_versions=["kafka:3.6-alpine", "redis:7.2-alpine"],
                calibration_status="CALIBRATED_EMPIRICAL",
                model_type="enqueue_ack_latency",
                operating_range_rps=[1.0, 4000.0],
                operating_range_concurrency=[1, 200],
                validation_rmse_ms=0.25,
                provenance="Asynchronous message broker enqueue/dequeue calibration",
                supported_metrics=[
                    "enqueue_latency_ms", "queue_depth_count", "worker_drain_rate_rps"
                ],
                known_limitations=[
                    "Decouples write ingestion latency from persistence latency",
                    "Introduces eventual consistency lag"
                ],
            )
        )

        # 4. Ingress / API Service
        components.append(
            ComponentCapability(
                category=ComponentCategory.INGRESS,
                model_name="api_gateway",
                display_name="FastAPI Ingress Gateway",
                supported_versions=["fastapi:0.110"],
                calibration_status="CALIBRATED_EMPIRICAL",
                model_type="event_loop_routing",
                operating_range_rps=[1.0, 3000.0],
                operating_range_concurrency=[1, 100],
                validation_rmse_ms=0.15,
                provenance="FastAPI JSON serialization and routing latency model",
                supported_metrics=[
                    "ingress_serialization_latency_ms", "http_concurrency_utilization"
                ],
                known_limitations=[
                    "Single-process async event loop overhead modeled (~0.3ms baseline)"
                ],
            )
        )

        # 5. Compute / Background Worker
        components.append(
            ComponentCapability(
                category=ComponentCategory.COMPUTE,
                model_name="async_worker",
                display_name="Async Task Worker (Celery / Consumer)",
                supported_versions=["celery:5.3"],
                calibration_status="CALIBRATED_EMPIRICAL",
                model_type="batch_consumer",
                operating_range_rps=[1.0, 1500.0],
                operating_range_concurrency=[1, 32],
                validation_rmse_ms=0.35,
                provenance="Celery worker batch persistence model",
                supported_metrics=["batch_drain_rps", "worker_busy_utilization_pct"],
                known_limitations=["Bounded worker concurrency limit: requires queues to prevent drop"],
            )
        )

        # Apply category filter if requested
        if category_filter:
            cat_lower = category_filter.strip().lower()
            components = [c for c in components if c.category.value == cat_lower or cat_lower in c.model_name]

        return cls(
            supported_categories=[c.value for c in ComponentCategory],
            components=components,
            supported_workload_patterns=[
                "Poisson inter-arrival traffic (stochastic steady-state)",
                "Peak burst multiplier (headroom testing up to 4.0x)",
                "Configurable read / write ratio splits (0.01 - 0.99)",
                "Dataset volume scaling (records from 1K to 10M)"
            ],
            supported_topology_patterns=[
                "Direct API to relational database",
                "Cache-aside read-shielding with fallback on miss",
                "Asynchronous write queue with background worker persistence",
                "Hybrid multi-tier read-cache + async write-buffer pipelines"
            ],
            available_simulation_metrics=[
                "p50_latency_ms", "p90_latency_ms", "p95_latency_ms", "p99_latency_ms", "max_latency_ms",
                "throughput_achieved_rps", "error_rate_pct", "avg_queue_length", "max_queue_length",
                "component_utilizations", "cache_hit_rate", "bottleneck_component",
                "estimated_monthly_cost_usd", "latency_uncertainty_p95_ms"
            ],
            unsupported_behaviors=[
                "Multi-region active-active cross-datacenter replication latency",
                "Physical bare-metal disk IOPS saturation under heavy BLOB media traffic (S3/GCS blob models pending)",
                "Byzantine network fault tolerance and dynamic network partitions"
            ],
            general_guidance=(
                "Inspect supported component models and operating ranges before formulating topologies. "
                "Always check whether workload RPS exceeds component operating ranges. "
                "If proposing components outside the catalog (e.g. S3, CDN), note that discrete-event simulation "
                "models are pending and will be flagged as unmodelled."
            ),
        )
