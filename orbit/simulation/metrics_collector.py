"""
Simulation Metrics Collector.
Records per-request discrete traces, computes exact latency percentiles (p50, p90, p95, p99),
tracks resource utilization, queue lengths, cache hit statistics, and bottlenecks.
"""
import math
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field
import numpy as np


class RequestTrace(BaseModel):
    request_id: int
    op_type: str
    arrival_time_s: float
    completion_time_s: float
    latency_ms: float
    success: bool = True
    error_type: Optional[str] = None
    cache_hit: Optional[bool] = None
    queue_wait_ms: float = 0.0


class SimulationMetricsCollector:
    """Collects fine-grained discrete event records and computes system-level metrics."""

    def __init__(self, simulation_duration_s: float):
        self.simulation_duration_s = simulation_duration_s
        self.traces: List[RequestTrace] = []
        self.busy_time_s: Dict[str, float] = {}
        self.capacities: Dict[str, int] = {}
        self.queue_length_samples: Dict[str, List[int]] = {}
        self.cache_hits: int = 0
        self.cache_misses: int = 0

    def register_resource(self, name: str, capacity: int) -> None:
        self.capacities[name] = capacity
        self.busy_time_s[name] = 0.0
        self.queue_length_samples[name] = []

    def record_busy_time(self, name: str, duration_s: float) -> None:
        if name in self.busy_time_s:
            self.busy_time_s[name] += duration_s

    def record_queue_length(self, name: str, length: int) -> None:
        if name in self.queue_length_samples:
            self.queue_length_samples[name].append(length)

    def record_cache_access(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def record_request(self, trace: RequestTrace) -> None:
        self.traces.append(trace)

    def compute_summary(self) -> Dict[str, Any]:
        total_requests = len(self.traces)
        if total_requests == 0:
            return {"error": "No requests processed in simulation"}

        completed = [t for t in self.traces if t.success]
        errors = [t for t in self.traces if not t.success]
        error_count = len(errors)
        error_rate_pct = (error_count / total_requests) * 100.0

        latencies = [t.latency_ms for t in completed]
        if latencies:
            lat_arr = np.array(latencies)
            p50 = float(np.percentile(lat_arr, 50))
            p90 = float(np.percentile(lat_arr, 90))
            p95 = float(np.percentile(lat_arr, 95))
            p99 = float(np.percentile(lat_arr, 99))
            max_lat = float(np.max(lat_arr))
            mean_lat = float(np.mean(lat_arr))
            std_lat = float(np.std(lat_arr))
        else:
            p50 = p90 = p95 = p99 = max_lat = mean_lat = std_lat = 0.0

        # Throughput: completed requests divided by simulated duration
        throughput_rps = len(completed) / max(0.1, self.simulation_duration_s)

        # Component utilizations: busy_time / (capacity * total_time)
        utilizations: Dict[str, float] = {}
        for name, busy in self.busy_time_s.items():
            cap = self.capacities.get(name, 1)
            util = (busy / (cap * self.simulation_duration_s)) * 100.0
            utilizations[name] = round(min(100.0, max(0.0, util)), 1)

        # Queue length stats
        avg_q_len = 0.0
        max_q_len = 0
        all_q_samples = []
        for name, samples in self.queue_length_samples.items():
            if samples:
                all_q_samples.extend(samples)
                max_q_len = max(max_q_len, max(samples))
        if all_q_samples:
            avg_q_len = float(np.mean(all_q_samples))

        # Cache hit rate
        total_cache_ops = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache_ops) if total_cache_ops > 0 else None

        # Bottleneck component: resource with highest utilization
        bottleneck = max(utilizations.items(), key=lambda kv: kv[1])[0] if utilizations else "none"

        # Heuristic uncertainty bound around p95 using scaled standard error of sample mean.
        # NOTE: This is an engineering heuristic proxy, NOT a statistically valid 95% confidence interval
        # for p95 (which requires independent replications or batch means under autocorrelated queueing delays).
        se_margin = 1.96 * (std_lat / math.sqrt(max(1, len(latencies)))) * 1.5 if latencies else 0.5
        p95_bounds = (round(max(0.1, p95 - se_margin), 2), round(p95 + se_margin, 2))

        return {
            "total_requests": total_requests,
            "completed_requests": len(completed),
            "error_count": error_count,
            "error_rate_pct": round(error_rate_pct, 2),
            "throughput_achieved_rps": round(throughput_rps, 1),
            "p50_latency_ms": round(p50, 2),
            "p90_latency_ms": round(p90, 2),
            "p95_latency_ms": round(p95, 2),
            "p99_latency_ms": round(p99, 2),
            "max_latency_ms": round(max_lat, 2),
            "mean_latency_ms": round(mean_lat, 2),
            "component_utilizations": utilizations,
            "avg_queue_length": round(avg_q_len, 2),
            "max_queue_length": max_q_len,
            "cache_hit_rate": round(cache_hit_rate, 3) if cache_hit_rate is not None else None,
            "bottleneck_component": bottleneck,
            "latency_uncertainty_p95_ms": p95_bounds,
        }
