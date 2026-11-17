"""
Generalized Dynamic SimPy Discrete-Event Simulation Engine (Phase 5.3B).
Simulates Poisson request arrival, queueing contention, inter-process network delays,
cache-aside hit/miss short-circuiting, and asynchronous write pipelines
across arbitrary, validated TopologyGraph DAGs.
"""
import logging
import random
from typing import Dict, List, Optional, Any, Tuple
import simpy

from aads.core.schemas import WorkloadSpec, SimulationResult
from aads.registry.component_registry import ComponentRegistry
from aads.sdk.models import (
    TopologyGraph,
    ComponentNode,
    ComponentCategory,
    ConnectionEdge,
)
from aads.simulation.metrics_collector import SimulationMetricsCollector, RequestTrace

logger = logging.getLogger(__name__)


class DynamicSimPyEngine:
    """
    Generalized discrete-event simulation engine powered by SimPy.
    Traverses arbitrary validated TopologyGraph architectures under stochastic workloads.
    """

    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry or ComponentRegistry()
        self.registry.seed_baseline_data()

    def simulate_topology(
        self,
        topology: TopologyGraph,
        workload: WorkloadSpec,
        duration_seconds: float = 10.0,
        random_seed: int = 42,
    ) -> SimulationResult:
        """
        Executes discrete-event queueing simulation of the provided topology.
        """
        rng = random.Random(random_seed)
        env = simpy.Environment()
        collector = SimulationMetricsCollector(simulation_duration_s=duration_seconds)
        warnings: List[str] = []

        # 1. Component Map & Service Demand Lookup
        node_map: Dict[str, ComponentNode] = {c.id: c for c in topology.components}
        service_demands = self._resolve_service_demands(topology, workload, warnings)

        # 2. Instantiate SimPy Resources for all nodes
        resources: Dict[str, simpy.Resource] = {}
        cpu_resources: Dict[str, simpy.Resource] = {}

        for node in topology.components:
            cap = max(1, node.concurrency_limit)
            resources[node.id] = simpy.Resource(env, capacity=cap)
            collector.register_resource(node.id, cap)

            # Nodes with dedicated CPU scheduling (e.g. database, heavy compute)
            if node.category in (ComponentCategory.DATABASE, ComponentCategory.COMPUTE):
                cpu_cores = max(1, int(round(node.cpu_cores)))
                cpu_resources[node.id] = simpy.Resource(env, capacity=cpu_cores)
                collector.register_resource(f"{node.id}_cpu", cpu_cores)

        # 3. Instantiate Asynchronous Queues and Background Worker Processes
        async_queues: Dict[str, simpy.Store] = {}
        edge_map: Dict[Tuple[str, str], ConnectionEdge] = {
            (e.source_id, e.target_id): e for e in topology.connections
        }

        for edge in topology.connections:
            if edge.protocol == "async_event":
                q_key = f"{edge.source_id}->{edge.target_id}"
                q_store = simpy.Store(env, capacity=50000)
                async_queues[q_key] = q_store

                # If target is worker/compute, spawn background drain loops
                target_node = node_map.get(edge.target_id)
                if target_node and target_node.category == ComponentCategory.COMPUTE:
                    worker_cap = max(1, target_node.concurrency_limit)
                    for worker_idx in range(min(worker_cap, 16)):
                        env.process(
                            self._async_drain_process(
                                env=env,
                                worker_id=worker_idx,
                                queue_key=q_key,
                                queue_store=q_store,
                                target_node=target_node,
                                topology=topology,
                                resources=resources,
                                cpu_resources=cpu_resources,
                                service_demands=service_demands,
                                collector=collector,
                                rng=rng,
                            )
                        )

        # 4. Request Arrival Process (Poisson arrival with exponential inter-arrival times)
        arrival_rate = max(1.0, workload.request_rate_rps)

        def request_generator():
            req_id = 0
            while True:
                iat = rng.expovariate(arrival_rate)
                yield env.timeout(iat)
                req_id += 1
                is_read = rng.random() < workload.read_ratio
                path = list(topology.read_path) if is_read else list(topology.write_path)

                env.process(
                    self._handle_request(
                        env=env,
                        req_id=req_id,
                        is_read=is_read,
                        path=path,
                        topology=topology,
                        node_map=node_map,
                        edge_map=edge_map,
                        resources=resources,
                        cpu_resources=cpu_resources,
                        async_queues=async_queues,
                        service_demands=service_demands,
                        workload=workload,
                        collector=collector,
                        rng=rng,
                    )
                )

        env.process(request_generator())
        env.run(until=duration_seconds)

        # 5. Metrics Synthesis
        summary = collector.compute_summary()
        summary["warnings"] = list(set(warnings))

        # Calculate monthly infrastructure cost
        total_cost_usd = self._calculate_topology_cost(topology)

        # Bottleneck detection
        bottleneck = self._identify_bottleneck(summary.get("component_utilizations", {}), topology)

        return SimulationResult(
            architecture_id=topology.topology_id,
            architecture_name=topology.name,
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
            bottleneck_component=bottleneck,
            estimated_monthly_cost_usd=total_cost_usd,
            simulation_duration_seconds=duration_seconds,
            random_seed=random_seed,
            latency_uncertainty_p95_ms=summary["latency_uncertainty_p95_ms"],
            warnings=summary["warnings"],
        )

    def _resolve_service_demands(
        self,
        topology: TopologyGraph,
        workload: WorkloadSpec,
        warnings: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """Resolves empirical service demand baselines for all nodes from ComponentRegistry."""
        demands: Dict[str, Dict[str, float]] = {}

        for node in topology.components:
            cat = node.category
            name_lower = node.model_name.lower()

            if cat == ComponentCategory.DATABASE or "postgres" in name_lower or "mongo" in name_lower:
                # Query calibrated model in registry
                status, model, warns = self.registry.check_compatibility(node.model_name, node.version, workload)
                warnings.extend(warns)

                if model and model.model_type == "piecewise_ridge" and "intercept" in model.fitted_parameters:
                    from aads.modeling.regression_model import RegressionPerformanceModel
                    p = model.fitted_parameters
                    reg = RegressionPerformanceModel(
                        intercept=p["intercept"],
                        coef_concurrency=p["coef_concurrency"],
                        coef_log_rps=p["coef_log_rps"],
                        coef_is_write=p["coef_is_write"],
                        min_concurrency=p["min_concurrency"],
                        max_concurrency=p["max_concurrency"],
                        min_rps=p["min_rps"],
                        max_rps=p["max_rps"],
                        rmse=p["rmse"],
                    )
                    pred_r, _, _ = reg.predict_service_time_ms("read", concurrency=4, offered_rps=workload.request_rate_rps)
                    pred_w, _, _ = reg.predict_service_time_ms("write", concurrency=4, offered_rps=workload.request_rate_rps)
                    demands[node.id] = {"read_ms": max(0.5, pred_r), "write_ms": max(1.0, pred_w)}
                elif model:
                    p = model.fitted_parameters
                    demands[node.id] = {
                        "read_ms": p.get("base_read_service_ms", 2.8),
                        "write_ms": p.get("base_write_service_ms", 6.5),
                    }
                else:
                    demands[node.id] = {"read_ms": 3.0, "write_ms": 7.0}

            elif cat == ComponentCategory.CACHE or "redis" in name_lower:
                demands[node.id] = {"lookup_ms": 0.65, "write_ms": 0.75}

            elif cat in (ComponentCategory.INGRESS, ComponentCategory.COMPUTE):
                demands[node.id] = {"route_ms": 0.35, "process_ms": 1.20}

            elif cat == ComponentCategory.QUEUE:
                demands[node.id] = {"enqueue_ms": 0.45, "dequeue_ms": 0.50}

            else:
                demands[node.id] = {"default_ms": 1.0}

        return demands

    def _handle_request(
        self,
        env: simpy.Environment,
        req_id: int,
        is_read: bool,
        path: List[str],
        topology: TopologyGraph,
        node_map: Dict[str, ComponentNode],
        edge_map: Dict[Tuple[str, str], ConnectionEdge],
        resources: Dict[str, simpy.Resource],
        cpu_resources: Dict[str, simpy.Resource],
        async_queues: Dict[str, simpy.Store],
        service_demands: Dict[str, Dict[str, float]],
        workload: WorkloadSpec,
        collector: SimulationMetricsCollector,
        rng: random.Random,
    ):
        arrival_s = env.now
        is_cache_hit = None
        success = True
        error_type = None

        prev_node_id: Optional[str] = None
        path_idx = 0

        while path_idx < len(path):
            node_id = path[path_idx]
            node = node_map[node_id]
            res = resources[node_id]

            # Inter-node network hop latency
            if prev_node_id:
                edge = edge_map.get((prev_node_id, node_id))
                hop_delay_s = (edge.network_latency_ms / 1000.0) if edge else 0.0005
                yield env.timeout(hop_delay_s)

            # Asynchronous Queue Decoupling
            # If the outgoing connection to this node is an async queue, client execution returns early!
            if prev_node_id:
                q_key = f"{prev_node_id}->{node_id}"
                if q_key in async_queues:
                    # Enqueue payload and return immediate acknowledgment to client
                    q_store = async_queues[q_key]
                    enqueue_start = env.now
                    with res.request() as q_req:
                        yield q_req
                        eq_lat_s = service_demands.get(prev_node_id, {}).get("enqueue_ms", 0.45) / 1000.0
                        yield env.timeout(eq_lat_s)
                        collector.record_busy_time(prev_node_id, eq_lat_s)
                        yield q_store.put({"req_id": req_id, "timestamp": env.now, "remaining_path": path[path_idx:]})

                    # Write client receives immediate response
                    break

            # Contention: acquire node concurrency slot
            collector.record_queue_length(node_id, len(res.queue))
            with res.request() as comp_req:
                yield comp_req

                # Cache Behavior (Short-circuit on hit for reads)
                if node.category == ComponentCategory.CACHE and is_read:
                    hit_rate = workload.cache_assumed_hit_rate
                    is_cache_hit = rng.random() < hit_rate
                    collector.record_cache_access(is_cache_hit)

                    # Lookup latency in Redis (~0.65ms)
                    lookup_s = rng.uniform(0.0004, 0.0008)
                    yield env.timeout(lookup_s)
                    collector.record_busy_time(node_id, lookup_s)

                    if is_cache_hit:
                        # Cache Hit: request is completely satisfied, short-circuit remaining path!
                        break
                    else:
                        # Cache Miss: proceed down the remaining path to database
                        prev_node_id = node_id
                        path_idx += 1
                        continue

                # Database & Compute Processing
                if node.category == ComponentCategory.DATABASE:
                    demand_ms = service_demands.get(node_id, {}).get("read_ms" if is_read else "write_ms", 3.0)
                    # Exponential or log-normal variance in query execution
                    actual_demand_s = max(0.0005, rng.expovariate(1.0 / (demand_ms / 1000.0)))

                    # Database CPU resource contention
                    if node_id in cpu_resources:
                        with cpu_resources[node_id].request() as cpu_req:
                            yield cpu_req
                            yield env.timeout(actual_demand_s)
                            collector.record_busy_time(f"{node_id}_cpu", actual_demand_s)
                    else:
                        yield env.timeout(actual_demand_s)
                    collector.record_busy_time(node_id, actual_demand_s)

                elif node.category == ComponentCategory.INGRESS:
                    # Ingress JSON serialization / routing overhead
                    api_overhead_s = rng.uniform(0.0002, 0.0005)
                    yield env.timeout(api_overhead_s)
                    collector.record_busy_time(node_id, api_overhead_s)

                elif node.category == ComponentCategory.COMPUTE:
                    comp_s = rng.uniform(0.0008, 0.0020)
                    yield env.timeout(comp_s)
                    collector.record_busy_time(node_id, comp_s)

                else:
                    # Default generic node delay
                    gen_s = 0.0010
                    yield env.timeout(gen_s)
                    collector.record_busy_time(node_id, gen_s)

            prev_node_id = node_id
            path_idx += 1

        # Completed: record client end-to-end response latency
        latency_ms = max(0.1, (env.now - arrival_s) * 1000.0)
        collector.record_request(
            RequestTrace(
                request_id=req_id,
                op_type="read" if is_read else "write",
                arrival_time_s=arrival_s,
                completion_time_s=env.now,
                latency_ms=latency_ms,
                success=success,
                error_type=error_type,
                cache_hit=is_cache_hit,
            )
        )

    def _async_drain_process(
        self,
        env: simpy.Environment,
        worker_id: int,
        queue_key: str,
        queue_store: simpy.Store,
        target_node: ComponentNode,
        topology: TopologyGraph,
        resources: Dict[str, simpy.Resource],
        cpu_resources: Dict[str, simpy.Resource],
        service_demands: Dict[str, Dict[str, float]],
        collector: SimulationMetricsCollector,
        rng: random.Random,
    ):
        """Background async consumer draining message queue to persistent storage."""
        while True:
            item = yield queue_store.get()
            rem_path = item.get("remaining_path", [])

            # Execute remaining writes down to DB
            for n_id in rem_path:
                if n_id not in resources:
                    continue
                with resources[n_id].request() as comp_req:
                    yield comp_req
                    db_write_ms = service_demands.get(n_id, {}).get("write_ms", 6.0)
                    w_s = max(0.001, rng.expovariate(1.0 / (db_write_ms / 1000.0)))

                    if n_id in cpu_resources:
                        with cpu_resources[n_id].request() as cpu_req:
                            yield cpu_req
                            yield env.timeout(w_s)
                            collector.record_busy_time(f"{n_id}_cpu", w_s)
                    else:
                        yield env.timeout(w_s)
                    collector.record_busy_time(n_id, w_s)

    def _calculate_topology_cost(self, topology: TopologyGraph) -> float:
        """Computes aggregate monthly infrastructure cost from node sizing."""
        total = 0.0
        for node in topology.components:
            if node.monthly_cost_override_usd is not None:
                total += node.monthly_cost_override_usd
                continue

            # Standard cloud compute rate heuristics ($24/vCPU, $4/GB RAM)
            comp_cost = (node.cpu_cores * 24.0) + ((node.memory_mb / 1024.0) * 4.0)
            if node.category == ComponentCategory.DATABASE:
                comp_cost += 35.0  # Managed DB license/storage baseline
            elif node.category == ComponentCategory.CACHE:
                comp_cost += 15.0  # Managed in-memory cache fee
            elif node.category == ComponentCategory.QUEUE:
                comp_cost += 25.0  # Managed broker fee
            total += comp_cost

        return round(total, 2)

    def _identify_bottleneck(self, utilizations: Dict[str, float], topology: TopologyGraph) -> str:
        """Identifies primary bottleneck component from utilization metrics."""
        if not utilizations:
            return "network"
        max_id, max_util = max(utilizations.items(), key=lambda kv: kv[1])
        if max_util > 0.65:
            # Map back to human name
            clean_id = max_id.replace("_cpu", "")
            return clean_id.upper()
        return "NETWORK"
