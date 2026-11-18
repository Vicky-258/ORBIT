"""
Scenario Explorer & Stress Testing for ORBIT (Phase: Hybrid Workload Intelligence).
Executes parametric stress scenarios (traffic scaling, burst spikes, cache degradation)
to find failure thresholds and evaluate architectural robustness.

Design Principle:
Architecture evaluation must test resilience under degradation and load multipliers,
not just ideal steady-state conditions.
"""
import copy
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

from orbit.catalog.workload_profile import WorkloadProfile
from orbit.sdk.models import TopologyGraph
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine
from orbit.core.schemas import SimulationResult

logger = logging.getLogger("orbit.composer.scenario_explorer")


class ScenarioOutcome(BaseModel):
    """Result of a specific stress or sensitivity scenario."""
    scenario_name: str
    description: str
    simulation_result: SimulationResult
    throughput_achieved_rps: float
    p95_latency_ms: float
    p95_latency_change_pct: float
    error_rate_pct: float
    bottleneck_component: str
    sla_violations_count: int
    is_saturated: bool


class ScenarioComparison(BaseModel):
    """Comparison matrix across multiple evaluated scenarios."""
    baseline: SimulationResult
    scenarios: List[ScenarioOutcome]
    max_sustainable_rps: float
    headroom_factor: float
    primary_failure_mode: str
    recommendations: List[str]


class ScenarioExplorer:
    """Explores parametric variations and stress tests on composed architectures."""

    def __init__(self, engine: Optional[DynamicSimPyEngine] = None):
        self.engine = engine or DynamicSimPyEngine()

    def explore(
        self,
        topology: TopologyGraph,
        workloads: List[WorkloadProfile],
        multipliers: Optional[List[float]] = None,
        test_cache_degradation: bool = True,
        duration_seconds: float = 5.0,
        random_seed: int = 42,
    ) -> ScenarioComparison:
        """
        Runs baseline and a series of stress scenarios:
        1. Baseline steady-state
        2. Traffic spikes (e.g. 2x, 4x load)
        3. Cache degradation (e.g. cold-cache / 50% drop)
        """
        multipliers = multipliers or [2.0, 4.0]

        # 1. Baseline Run
        baseline_res = self.engine.simulate_multi_workload(
            topology=topology,
            workloads=workloads,
            duration_seconds=duration_seconds,
            random_seed=random_seed,
        )

        scenarios: List[ScenarioOutcome] = []
        base_p95 = max(0.1, baseline_res.p95_latency_ms)

        # 2. Traffic Multiplier Scenarios
        for mult in multipliers:
            scaled_workloads = self._scale_workloads(workloads, multiplier=mult)
            s_res = self.engine.simulate_multi_workload(
                topology=topology,
                workloads=scaled_workloads,
                duration_seconds=duration_seconds,
                random_seed=random_seed + int(mult * 10),
            )

            lat_change = ((s_res.p95_latency_ms - base_p95) / base_p95) * 100.0
            sla_violations = sum(
                1 for wstat in s_res.workload_metrics.values() if wstat.get("sla_compliant") is False
            )
            # Saturation check: bottleneck utilization > 85% or queue length > 10
            max_util = max(s_res.component_utilizations.values()) if s_res.component_utilizations else 0.0
            is_sat = max_util > 85.0 or s_res.max_queue_length > 15 or s_res.error_rate_pct > 2.0

            scenarios.append(
                ScenarioOutcome(
                    scenario_name=f"Traffic Spike {mult}x",
                    description=f"Multiplies all workload request rates by {mult}x.",
                    simulation_result=s_res,
                    throughput_achieved_rps=s_res.throughput_achieved_rps,
                    p95_latency_ms=s_res.p95_latency_ms,
                    p95_latency_change_pct=round(lat_change, 1),
                    error_rate_pct=s_res.error_rate_pct,
                    bottleneck_component=s_res.bottleneck_component,
                    sla_violations_count=sla_violations,
                    is_saturated=is_sat,
                )
            )

        # 3. Cache Degradation Scenario (if cache present in topology)
        has_cache = any(c.id == "redis_cache" for c in topology.components)
        if test_cache_degradation and has_cache:
            degraded_workloads = self._degrade_cache(workloads, reduction_factor=0.5)
            s_res = self.engine.simulate_multi_workload(
                topology=topology,
                workloads=degraded_workloads,
                duration_seconds=duration_seconds,
                random_seed=random_seed + 99,
            )
            lat_change = ((s_res.p95_latency_ms - base_p95) / base_p95) * 100.0
            sla_violations = sum(
                1 for wstat in s_res.workload_metrics.values() if wstat.get("sla_compliant") is False
            )
            max_util = max(s_res.component_utilizations.values()) if s_res.component_utilizations else 0.0
            is_sat = max_util > 85.0 or s_res.max_queue_length > 15

            scenarios.append(
                ScenarioOutcome(
                    scenario_name="Cache Degradation (50% Miss)",
                    description="Simulates cold cache / stampede by dropping cache hit rates by 50%.",
                    simulation_result=s_res,
                    throughput_achieved_rps=s_res.throughput_achieved_rps,
                    p95_latency_ms=s_res.p95_latency_ms,
                    p95_latency_change_pct=round(lat_change, 1),
                    error_rate_pct=s_res.error_rate_pct,
                    bottleneck_component=s_res.bottleneck_component,
                    sla_violations_count=sla_violations,
                    is_saturated=is_sat,
                )
            )

        # Synthesis
        sustainable_rps = baseline_res.throughput_achieved_rps
        headroom = 1.0
        for s in scenarios:
            if not s.is_saturated and s.sla_violations_count == 0:
                if s.throughput_achieved_rps > sustainable_rps:
                    sustainable_rps = s.throughput_achieved_rps
                    headroom = sustainable_rps / max(1.0, baseline_res.throughput_achieved_rps)

        recs = []
        saturated_scenarios = [s for s in scenarios if s.is_saturated]
        if saturated_scenarios:
            first_sat = saturated_scenarios[0]
            failure_mode = f"Queueing explosion at component '{first_sat.bottleneck_component}' under {first_sat.scenario_name}"
            recs.append(f"Scale out '{first_sat.bottleneck_component}' (increase concurrency limit or replica count).")
        else:
            failure_mode = "System showed high headroom across evaluated multipliers without queueing collapse."
            recs.append("Current infrastructure sizing has sufficient headroom for 2x-4x demand bursts.")

        return ScenarioComparison(
            baseline=baseline_res,
            scenarios=scenarios,
            max_sustainable_rps=round(sustainable_rps, 1),
            headroom_factor=round(headroom, 2),
            primary_failure_mode=failure_mode,
            recommendations=recs,
        )

    def _scale_workloads(self, workloads: List[WorkloadProfile], multiplier: float) -> List[WorkloadProfile]:
        scaled = []
        for w in workloads:
            w_copy = copy.deepcopy(w)
            w_copy.traffic.arrival_rate_rps = round(w.traffic.arrival_rate_rps * multiplier, 2)
            scaled.append(w_copy)
        return scaled

    def _degrade_cache(self, workloads: List[WorkloadProfile], reduction_factor: float) -> List[WorkloadProfile]:
        degraded = []
        for w in workloads:
            w_copy = copy.deepcopy(w)
            w_copy.data.cacheability = round(w.data.cacheability * reduction_factor, 2)
            degraded.append(w_copy)
        return degraded
