"""
Architecture Candidate Generator.
Produces valid, validated candidate architectures for the social-media feed scenario.
"""
from typing import Dict, List, Optional
from orbit.core.schemas import (
    ArchitectureGraph,
    ComponentConfig,
    ComponentType,
    WorkloadSpec,
)
from orbit.core.config import settings


class ArchitectureGenerator:
    """Generates candidate architectures and validates topology."""

    @staticmethod
    def calculate_component_cost(component: ComponentConfig) -> float:
        """Deterministic monthly cost calculation based on pricing config."""
        p = settings.pricing
        cost = (component.cpu_cores * p.vcpu_monthly_usd) + ((component.memory_mb / 1024.0) * p.memory_gb_monthly_usd)
        if component.component_type == ComponentType.CACHE:
            cost += p.redis_base_instance_monthly_usd
        elif component.component_type == ComponentType.DATABASE:
            cost += p.postgres_base_instance_monthly_usd
        return round(cost, 2)

    def generate_architecture_a(self) -> ArchitectureGraph:
        """Architecture A: Simple (API -> PostgreSQL)"""
        api = ComponentConfig(
            name="api_service",
            component_type=ComponentType.API,
            version="fastapi:0.110",
            cpu_cores=2.0,
            memory_mb=1024,
            concurrency_limit=32,
            monthly_cost_usd=0.0,
        )
        api.monthly_cost_usd = self.calculate_component_cost(api)

        postgres = ComponentConfig(
            name="postgres_db",
            component_type=ComponentType.DATABASE,
            version="postgres:16-alpine",
            cpu_cores=2.0,
            memory_mb=2048,
            concurrency_limit=25,
            monthly_cost_usd=0.0,
            parameters={"max_connections": 50, "shared_buffers_mb": 512},
        )
        postgres.monthly_cost_usd = self.calculate_component_cost(postgres)

        components = {"api": api, "db": postgres}
        connections = [("api", "db")]
        total_cost = round(api.monthly_cost_usd + postgres.monthly_cost_usd, 2)

        arch = ArchitectureGraph(
            id="arch_a_simple",
            name="Architecture A — Simple (API → PostgreSQL)",
            description="Direct database queries for all reads and writes. Simple operations, low complexity, but database bound under high load.",
            components=components,
            connections=connections,
            read_path=["api", "db"],
            write_path=["api", "db"],
            queue_present=False,
            required_models=["postgres_db:postgres:16-alpine"],
            total_monthly_cost_usd=total_cost,
            metadata={"complexity_score": 1.0, "stateful_components": 1},
        )
        self.validate_graph(arch)
        return arch

    def generate_architecture_b(self) -> ArchitectureGraph:
        """Architecture B: Cached reads (API -> Redis Cache -> PostgreSQL on miss)"""
        api = ComponentConfig(
            name="api_service",
            component_type=ComponentType.API,
            version="fastapi:0.110",
            cpu_cores=2.0,
            memory_mb=1024,
            concurrency_limit=32,
            monthly_cost_usd=0.0,
        )
        api.monthly_cost_usd = self.calculate_component_cost(api)

        cache = ComponentConfig(
            name="redis_cache",
            component_type=ComponentType.CACHE,
            version="redis:7.2-alpine",
            cpu_cores=1.0,
            memory_mb=1024,
            concurrency_limit=100,
            monthly_cost_usd=0.0,
            parameters={"maxmemory_policy": "allkeys-lru", "ttl_seconds": 300},
        )
        cache.monthly_cost_usd = self.calculate_component_cost(cache)

        postgres = ComponentConfig(
            name="postgres_db",
            component_type=ComponentType.DATABASE,
            version="postgres:16-alpine",
            cpu_cores=2.0,
            memory_mb=2048,
            concurrency_limit=25,
            monthly_cost_usd=0.0,
            parameters={"max_connections": 50, "shared_buffers_mb": 512},
        )
        postgres.monthly_cost_usd = self.calculate_component_cost(postgres)

        components = {"api": api, "cache": cache, "db": postgres}
        connections = [("api", "cache"), ("api", "db"), ("db", "cache")]
        total_cost = round(api.monthly_cost_usd + cache.monthly_cost_usd + postgres.monthly_cost_usd, 2)

        arch = ArchitectureGraph(
            id="arch_b_cached",
            name="Architecture B — Cached Reads (API → Redis → PostgreSQL)",
            description="In-memory cache for feed reads. Sub-millisecond cache hits shield the primary database from read-heavy spikes.",
            components=components,
            connections=connections,
            read_path=["api", "cache", "db"],
            write_path=["api", "db", "cache"],
            queue_present=False,
            required_models=["redis_cache:redis:7.2-alpine", "postgres_db:postgres:16-alpine"],
            total_monthly_cost_usd=total_cost,
            metadata={"complexity_score": 2.0, "stateful_components": 2},
        )
        self.validate_graph(arch)
        return arch

    def generate_architecture_c(self) -> ArchitectureGraph:
        """Architecture C: Async write queue (API -> Queue -> Worker -> PostgreSQL, with Redis cache)"""
        api = ComponentConfig(
            name="api_service",
            component_type=ComponentType.API,
            version="fastapi:0.110",
            cpu_cores=2.0,
            memory_mb=1024,
            concurrency_limit=32,
            monthly_cost_usd=0.0,
        )
        api.monthly_cost_usd = self.calculate_component_cost(api)

        cache = ComponentConfig(
            name="redis_cache",
            component_type=ComponentType.CACHE,
            version="redis:7.2-alpine",
            cpu_cores=1.0,
            memory_mb=1024,
            concurrency_limit=100,
            monthly_cost_usd=0.0,
        )
        cache.monthly_cost_usd = self.calculate_component_cost(cache)

        queue = ComponentConfig(
            name="redis_queue",
            component_type=ComponentType.QUEUE,
            version="redis:7.2-alpine",
            cpu_cores=0.5,
            memory_mb=512,
            concurrency_limit=200,
            monthly_cost_usd=0.0,
        )
        queue.monthly_cost_usd = self.calculate_component_cost(queue)

        worker = ComponentConfig(
            name="async_worker",
            component_type=ComponentType.WORKER,
            version="celery:5.3",
            cpu_cores=1.0,
            memory_mb=512,
            concurrency_limit=8,
            monthly_cost_usd=0.0,
        )
        worker.monthly_cost_usd = self.calculate_component_cost(worker)

        postgres = ComponentConfig(
            name="postgres_db",
            component_type=ComponentType.DATABASE,
            version="postgres:16-alpine",
            cpu_cores=2.0,
            memory_mb=2048,
            concurrency_limit=25,
            monthly_cost_usd=0.0,
        )
        postgres.monthly_cost_usd = self.calculate_component_cost(postgres)

        components = {
            "api": api,
            "cache": cache,
            "queue": queue,
            "worker": worker,
            "db": postgres,
        }
        connections = [
            ("api", "cache"),
            ("api", "queue"),
            ("queue", "worker"),
            ("worker", "db"),
            ("api", "db"),
        ]
        total_cost = round(sum(c.monthly_cost_usd for c in components.values()), 2)

        arch = ArchitectureGraph(
            id="arch_c_async",
            name="Architecture C — Async Processing (API → Queue → Worker → PostgreSQL)",
            description="Decoupled write pipeline using an asynchronous queue and background worker, alongside cached reads. Rapid write acknowledgements.",
            components=components,
            connections=connections,
            read_path=["api", "cache", "db"],
            write_path=["api", "queue", "worker", "db"],
            queue_present=True,
            required_models=["redis_cache:redis:7.2-alpine", "postgres_db:postgres:16-alpine"],
            total_monthly_cost_usd=total_cost,
            metadata={"complexity_score": 3.5, "stateful_components": 3},
        )
        self.validate_graph(arch)
        return arch

    def generate_unsupported_candidate(self) -> ArchitectureGraph:
        """Demonstration candidate with an intentionally unsupported component (MongoDB 7.0)."""
        api = ComponentConfig(
            name="api_service",
            component_type=ComponentType.API,
            version="fastapi:0.110",
            cpu_cores=2.0,
            memory_mb=1024,
            concurrency_limit=32,
            monthly_cost_usd=52.0,
        )
        mongodb = ComponentConfig(
            name="mongodb_cluster",
            component_type=ComponentType.DATABASE,
            version="mongodb:7.0-cluster",
            cpu_cores=2.0,
            memory_mb=2048,
            concurrency_limit=25,
            monthly_cost_usd=75.0,
        )
        components = {"api": api, "db": mongodb}
        connections = [("api", "db")]
        arch = ArchitectureGraph(
            id="arch_mongo_unregistered",
            name="Architecture M — Document Store (API → MongoDB 7.0)",
            description="Alternative candidate with MongoDB 7.0 document store. Used to demonstrate missing-model discovery.",
            components=components,
            connections=connections,
            read_path=["api", "db"],
            write_path=["api", "db"],
            queue_present=False,
            required_models=["mongodb_cluster:mongodb:7.0-cluster"],
            total_monthly_cost_usd=127.0,
            metadata={"complexity_score": 1.5, "stateful_components": 1},
        )
        self.validate_graph(arch)
        return arch

    def generate_candidates(self, include_async: bool = True, include_unsupported: bool = False) -> List[ArchitectureGraph]:
        """Generate set of candidates for evaluation."""
        candidates = [self.generate_architecture_a(), self.generate_architecture_b()]
        if include_async:
            candidates.append(self.generate_architecture_c())
        if include_unsupported:
            candidates.append(self.generate_unsupported_candidate())
        return candidates

    def validate_graph(self, arch: ArchitectureGraph) -> None:
        """Validate architecture DAG, connectivity, and component specs."""
        if not arch.components:
            raise ValueError(f"Architecture {arch.id} has no components")

        api_nodes = [k for k, c in arch.components.items() if c.component_type == ComponentType.API]
        if not api_nodes:
            raise ValueError(f"Architecture {arch.id} missing API entrypoint component")

        db_nodes = [k for k, c in arch.components.items() if c.component_type == ComponentType.DATABASE]
        if not db_nodes:
            raise ValueError(f"Architecture {arch.id} missing Database component")

        for src, dst in arch.connections:
            if src not in arch.components:
                raise ValueError(f"Connection source '{src}' not found in components of {arch.id}")
            if dst not in arch.components:
                raise ValueError(f"Connection destination '{dst}' not found in components of {arch.id}")

        for node in arch.read_path:
            if node not in arch.components:
                raise ValueError(f"Read path node '{node}' not found in components of {arch.id}")
        for node in arch.write_path:
            if node not in arch.components:
                raise ValueError(f"Write path node '{node}' not found in components of {arch.id}")

        if arch.queue_present:
            queue_nodes = [k for k, c in arch.components.items() if c.component_type == ComponentType.QUEUE]
            worker_nodes = [k for k, c in arch.components.items() if c.component_type == ComponentType.WORKER]
            if not queue_nodes or not worker_nodes:
                raise ValueError(f"Architecture {arch.id} has queue_present=True but missing queue or worker")
