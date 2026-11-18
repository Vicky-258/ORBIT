"""
SimPy Discrete-Event Simulation Engine.
Models individual synthetic requests routed through component resources,
queuing contention, cache hit/miss behavior, and background async pipelines.
"""
import random
import simpy
from typing import Dict, List, Optional, Tuple, Any

from orbit.core.schemas import (
    ArchitectureGraph,
    WorkloadSpec,
    SimulationResult,
    ComponentType,
)
from orbit.registry.component_registry import ComponentRegistry
from orbit.simulation.metrics_collector import SimulationMetricsCollector, RequestTrace


class SimPyEngine:
    """Discrete-event simulation engine powered by SimPy."""

    def __init__(self, registry: ComponentRegistry):
        self.registry = registry

    def simulate_architecture(
        self,
        architecture: ArchitectureGraph,
        workload: WorkloadSpec,
        duration_seconds: float = 10.0,
        random_seed: int = 42,
    ) -> SimulationResult:
        rng = random.Random(random_seed)
        env = simpy.Environment()
        collector = SimulationMetricsCollector(simulation_duration_s=duration_seconds)
        warnings: List[str] = []

        # 1. Retrieve component performance models from registry
        # Dynamically lookup DB component model (PostgreSQL, MongoDB, etc.)
        db_conf = architecture.components.get("db")
        db_name = db_conf.name if db_conf else "postgres_db"
        db_ver = db_conf.version if db_conf else "postgres:16-alpine"
        db_status, db_model, db_warn = self.registry.check_compatibility(db_name, db_ver, workload)
        warnings.extend(db_warn)
        if db_model:
            db_params = db_model.fitted_parameters
            if db_model.model_type == "piecewise_ridge" and "intercept" in db_params:
                from orbit.modeling.regression_model import RegressionPerformanceModel
                reg_m = RegressionPerformanceModel(
                    intercept=db_params["intercept"],
                    coef_concurrency=db_params["coef_concurrency"],
                    coef_log_rps=db_params["coef_log_rps"],
                    coef_is_write=db_params["coef_is_write"],
                    min_concurrency=db_params["min_concurrency"],
                    max_concurrency=db_params["max_concurrency"],
                    min_rps=db_params["min_rps"],
                    max_rps=db_params["max_rps"],
                    rmse=db_params["rmse"],
                )
                pred_r, _, _ = reg_m.predict_service_time_ms("read", concurrency=4, offered_rps=workload.request_rate_rps)
                pred_w, _, _ = reg_m.predict_service_time_ms("write", concurrency=4, offered_rps=workload.request_rate_rps)
                pg_base_read_ms = max(0.5, pred_r)
                pg_base_write_ms = max(1.0, pred_w)
            else:
                pg_base_read_ms = db_params.get("base_read_service_ms", 2.8)
                pg_base_write_ms = db_params.get("base_write_service_ms", 6.5)
        else:
            pg_base_read_ms = 3.0
            pg_base_write_ms = 7.0
            warnings.append(f"Using fallback uncalibrated {db_name} parameters.")

        # Redis model
        redis_base_hit_ms = 0.55
        if "cache" in architecture.components:
            _, redis_model, redis_warn = self.registry.check_compatibility("redis_cache", "redis:7.2-alpine", workload)
            warnings.extend(redis_warn)
            if redis_model:
                redis_base_hit_ms = redis_model.fitted_parameters.get("base_hit_latency_ms", 0.65)

        # 2. Instantiate SimPy Resources based on component concurrency limits
        api_conf = architecture.components.get("api")
        api_capacity = api_conf.concurrency_limit if api_conf else 32
        api_resource = simpy.Resource(env, capacity=api_capacity)
        collector.register_resource("api", api_capacity)

        db_conf = architecture.components.get("db")
        db_capacity = db_conf.concurrency_limit if db_conf else 25
        db_resource = simpy.Resource(env, capacity=db_capacity)
        db_cpu_cores = max(1, int(round(db_conf.cpu_cores if db_conf else 2.0)))
        db_cpu = simpy.Resource(env, capacity=db_cpu_cores)
        collector.register_resource("db", db_cpu_cores)

        cache_resource = None
        if "cache" in architecture.components:
            c_conf = architecture.components["cache"]
            cache_cap = c_conf.concurrency_limit
            cache_resource = simpy.Resource(env, capacity=cache_cap)
            collector.register_resource("cache", cache_cap)

        queue_store = None
        worker_resource = None
        if architecture.queue_present:
            queue_store = simpy.Store(env, capacity=1000)
            w_conf = architecture.components.get("worker")
            w_cap = w_conf.concurrency_limit if w_conf else 8
            worker_resource = simpy.Resource(env, capacity=w_cap)
            collector.register_resource("worker", w_cap)

            # Start background async worker processes
            for worker_id in range(w_cap):
                env.process(
                    self._async_worker_process(
                        env=env,
                        worker_id=worker_id,
                        queue_store=queue_store,
                        db_resource=db_resource,
                        db_cpu=db_cpu,
                        pg_base_write_ms=pg_base_write_ms,
                        collector=collector,
                        rng=rng,
                    )
                )

        # 3. Request Generator Process (Poisson arrival process)
        arrival_rate_lambda = workload.request_rate_rps

        def request_generator():
            req_id = 0
            while True:
                # Inter-arrival time ~ Exp(lambda) in seconds
                iat = rng.expovariate(arrival_rate_lambda)
                yield env.timeout(iat)
                req_id += 1
                op_type = "read" if rng.random() < workload.read_ratio else "write"
                
                env.process(
                    self._handle_request(
                        env=env,
                        req_id=req_id,
                        op_type=op_type,
                        architecture=architecture,
                        workload=workload,
                        api_resource=api_resource,
                        db_resource=db_resource,
                        db_cpu=db_cpu,
                        cache_resource=cache_resource,
                        queue_store=queue_store,
                        pg_base_read_ms=pg_base_read_ms,
                        pg_base_write_ms=pg_base_write_ms,
                        redis_base_hit_ms=redis_base_hit_ms,
                        collector=collector,
                        rng=rng,
                    )
                )

        env.process(request_generator())
        env.run(until=duration_seconds)

        summary = collector.compute_summary()
        summary["warnings"] = list(set(warnings))

        return SimulationResult(
            architecture_id=architecture.id,
            architecture_name=architecture.name,
            throughput_achieved_rps=summary["throughput_achieved_rps"],
            p50_latency_ms=summary["p50_latency_ms"],
            p90_latency_ms=summary["p90_latency_ms"],
            p95_latency_ms=summary["p95_latency_ms"],
            p99_latency_ms=summary["p99_latency_ms"],
            max_latency_ms=summary["max_latency_ms"],
            error_rate_pct=summary["error_rate_pct"],
            total_requests=summary["total_requests"],
            completed_requests=summary["completed_requests"],
            error_count=summary["error_count"],
            avg_queue_length=summary["avg_queue_length"],
            max_queue_length=summary["max_queue_length"],
            component_utilizations=summary["component_utilizations"],
            cache_hit_rate=summary["cache_hit_rate"],
            bottleneck_component=summary["bottleneck_component"],
            estimated_monthly_cost_usd=architecture.total_monthly_cost_usd,
            simulation_duration_seconds=duration_seconds,
            random_seed=random_seed,
            latency_uncertainty_p95_ms=summary["latency_uncertainty_p95_ms"],
            warnings=summary["warnings"],
        )

    def _handle_request(
        self,
        env: simpy.Environment,
        req_id: int,
        op_type: str,
        architecture: ArchitectureGraph,
        workload: WorkloadSpec,
        api_resource: simpy.Resource,
        db_resource: simpy.Resource,
        db_cpu: simpy.Resource,
        cache_resource: Optional[simpy.Resource],
        queue_store: Optional[simpy.Store],
        pg_base_read_ms: float,
        pg_base_write_ms: float,
        redis_base_hit_ms: float,
        collector: SimulationMetricsCollector,
        rng: random.Random,
    ):
        arrival_s = env.now
        is_cache_hit = None
        success = True
        error_type = None

        # Sample queue length at arrival
        collector.record_queue_length("api", len(api_resource.queue))

        # 1. API Service Contention
        with api_resource.request() as api_req:
            yield api_req
            api_start_s = env.now
            # API processing overhead: JSON serialization / routing (~0.3 ms)
            api_overhead_s = rng.uniform(0.0002, 0.0004)
            yield env.timeout(api_overhead_s)
            collector.record_busy_time("api", api_overhead_s)

            # Routing based on Architecture
            if architecture.id in ("arch_a_simple", "arch_mongo_unregistered"):
                # Direct DB access for both reads and writes
                collector.record_queue_length("db", len(db_resource.queue))
                with db_resource.request() as db_req:
                    yield db_req
                    with db_cpu.request() as d_cpu:
                        yield d_cpu
                        db_start_s = env.now
                        base_ms = pg_base_read_ms if op_type == "read" else pg_base_write_ms
                        service_ms = base_ms * rng.uniform(0.90, 1.15)
                        service_s = service_ms / 1000.0
                        yield env.timeout(service_s)
                        collector.record_busy_time("db", service_s)

            elif architecture.id == "arch_b_cached":
                if op_type == "read":
                    # Check cache first
                    is_cache_hit = rng.random() < workload.cache_assumed_hit_rate
                    collector.record_cache_access(is_cache_hit)

                    if is_cache_hit:
                        collector.record_queue_length("cache", len(cache_resource.queue))
                        with cache_resource.request() as c_req:
                            yield c_req
                            c_s = (redis_base_hit_ms * rng.uniform(0.85, 1.15)) / 1000.0
                            yield env.timeout(c_s)
                            collector.record_busy_time("cache", c_s)
                    else:
                        # Cache miss: query DB then populate cache
                        with cache_resource.request() as c_req:
                            yield c_req
                            c_s = 0.0002
                            yield env.timeout(c_s)
                            collector.record_busy_time("cache", c_s)

                        collector.record_queue_length("db", len(db_resource.queue))
                        with db_resource.request() as db_req:
                            yield db_req
                            with db_cpu.request() as d_cpu:
                                yield d_cpu
                                service_s = (pg_base_read_ms * rng.uniform(0.90, 1.15)) / 1000.0
                                yield env.timeout(service_s)
                                collector.record_busy_time("db", service_s)
                else:
                    # Write: write to DB and invalidate/update cache
                    collector.record_queue_length("db", len(db_resource.queue))
                    with db_resource.request() as db_req:
                        yield db_req
                        with db_cpu.request() as d_cpu:
                            yield d_cpu
                            service_s = (pg_base_write_ms * rng.uniform(0.90, 1.20)) / 1000.0
                            yield env.timeout(service_s)
                            collector.record_busy_time("db", service_s)

            elif architecture.id == "arch_c_async":
                if op_type == "read":
                    # Same cached read path as Architecture B
                    is_cache_hit = rng.random() < workload.cache_assumed_hit_rate
                    collector.record_cache_access(is_cache_hit)
                    if is_cache_hit:
                        with cache_resource.request() as c_req:
                            yield c_req
                            c_s = (redis_base_hit_ms * rng.uniform(0.85, 1.15)) / 1000.0
                            yield env.timeout(c_s)
                            collector.record_busy_time("cache", c_s)
                    else:
                        with db_resource.request() as db_req:
                            yield db_req
                            with db_cpu.request() as d_cpu:
                                yield d_cpu
                                service_s = (pg_base_read_ms * rng.uniform(0.90, 1.15)) / 1000.0
                                yield env.timeout(service_s)
                                collector.record_busy_time("db", service_s)
                else:
                    # Write: Enqueue task into queue and acknowledge immediately!
                    # Synchronous path: enqueueing overhead ~0.5ms
                    enqueue_s = rng.uniform(0.0004, 0.0008)
                    yield env.timeout(enqueue_s)
                    collector.record_busy_time("api", enqueue_s)
                    yield queue_store.put({"req_id": req_id, "enqueued_at": env.now})

        completion_s = env.now
        latency_ms = (completion_s - arrival_s) * 1000.0

        # Request SLA timeout check (1.5 seconds)
        if latency_ms > 1500.0:
            success = False
            error_type = "TIMEOUT"

        collector.record_request(
            RequestTrace(
                request_id=req_id,
                op_type=op_type,
                arrival_time_s=arrival_s,
                completion_time_s=completion_s,
                latency_ms=latency_ms,
                success=success,
                error_type=error_type,
                cache_hit=is_cache_hit,
            )
        )

    def _async_worker_process(
        self,
        env: simpy.Environment,
        worker_id: int,
        queue_store: simpy.Store,
        db_resource: simpy.Resource,
        db_cpu: simpy.Resource,
        pg_base_write_ms: float,
        collector: SimulationMetricsCollector,
        rng: random.Random,
    ):
        """Background worker process continuously draining asynchronous write jobs."""
        while True:
            item = yield queue_store.get()
            collector.record_queue_length("worker", len(db_resource.queue))
            # Claim DB connection and CPU core, then write asynchronously
            with db_resource.request() as db_req:
                yield db_req
                with db_cpu.request() as d_cpu:
                    yield d_cpu
                    service_s = (pg_base_write_ms * rng.uniform(0.90, 1.25)) / 1000.0
                    yield env.timeout(service_s)
                    collector.record_busy_time("worker", service_s)
                    collector.record_busy_time("db", service_s)

    def simulate_topology(
        self,
        topology: Any,
        workload: WorkloadSpec,
        duration_seconds: float = 10.0,
        random_seed: int = 42,
    ) -> SimulationResult:
        """Simulates dynamic TopologyGraph using DynamicSimPyEngine (Phase 5.3B)."""
        from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine
        engine = DynamicSimPyEngine(registry=self.registry)
        return engine.simulate_topology(
            topology=topology,
            workload=workload,
            duration_seconds=duration_seconds,
            random_seed=random_seed,
        )
