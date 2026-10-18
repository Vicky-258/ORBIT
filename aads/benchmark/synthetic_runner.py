"""
Synthetic Benchmark Runner.
Generates controlled, reproducible synthetic fixture measurements with explicit variance.
Clearly labeled: is_synthetic_fixture = True.
"""
import math
import random
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from aads.benchmark.runner_interface import BenchmarkRunner
from aads.core.schemas import ExperimentRecord


class SyntheticBenchmarkRunner(BenchmarkRunner):
    """
    Deterministic fixture benchmark runner for offline validation and CI testing.
    All outputs are explicitly labeled as synthetic fixtures.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def health_check(self) -> Dict[str, Any]:
        return {
            "runner_type": "SyntheticBenchmarkRunner",
            "status": "READY",
            "is_synthetic": True,
            "environment": "synthetic-controlled-simulation",
            "docker_available": False,
        }

    def run_benchmark_matrix(
        self,
        component_name: str,
        version: str,
        concurrency_levels: Optional[List[int]] = None,
        read_ratios: Optional[List[float]] = None,
        target_rps_levels: Optional[List[float]] = None,
        replications: int = 3,
    ) -> List[ExperimentRecord]:
        concurrency_list = concurrency_levels or [1, 4, 8, 16, 24, 32]
        read_ratio_list = read_ratios or [0.90]
        
        experiments: List[ExperimentRecord] = []
        now = datetime.now(timezone.utc).isoformat()

        # Component parameter profile
        if "postgres" in component_name.lower():
            base_read_ms = 2.6
            base_write_ms = 6.2
            sat_rps = 600.0
            env_fp = "fixture:simulated-2cpu-2048mb"
        elif "redis" in component_name.lower():
            base_read_ms = 0.5
            base_write_ms = 0.8
            sat_rps = 7500.0
            env_fp = "fixture:simulated-1cpu-1024mb"
        elif "mongo" in component_name.lower():
            base_read_ms = 3.2
            base_write_ms = 4.8
            sat_rps = 520.0
            env_fp = "fixture:simulated-2cpu-2048mb"
        else:
            base_read_ms = 4.0
            base_write_ms = 8.0
            sat_rps = 400.0
            env_fp = "fixture:simulated-default"

        for conc in concurrency_list:
            for rr in read_ratio_list:
                wr = 1.0 - rr
                nominal_service_ms = (rr * base_read_ms) + (wr * base_write_ms)

                # Throughput under concurrency
                # Little's Law / queuing saturation approximation with randomized noise
                max_sustainable_rps = (conc / (nominal_service_ms / 1000.0))
                effective_rps = min(sat_rps * (conc / (conc + 4.0)), max_sustainable_rps * 0.92)

                trial_p50s = []
                trial_p95s = []
                trial_p99s = []
                trial_rps = []

                for _ in range(replications):
                    noise_factor = self.rng.uniform(0.96, 1.04)
                    rep_achieved_rps = effective_rps * noise_factor

                    # Congestion scaling
                    congestion_ratio = min(0.98, rep_achieved_rps / sat_rps)
                    queue_mult = 1.0 + (0.5 * (congestion_ratio ** 2) / max(0.02, (1.0 - congestion_ratio)))

                    p50 = nominal_service_ms * queue_mult * self.rng.uniform(0.97, 1.03)
                    p95 = p50 * 1.85 * (1.0 + 0.15 * (conc / 32.0))
                    p99 = p95 * 1.45

                    trial_p50s.append(p50)
                    trial_p95s.append(p95)
                    trial_p99s.append(p99)
                    trial_rps.append(rep_achieved_rps)

                mean_p50 = sum(trial_p50s) / replications
                mean_p95 = sum(trial_p95s) / replications
                mean_p99 = sum(trial_p99s) / replications
                mean_rps = sum(trial_rps) / replications

                # Sample variance across replications
                if replications > 1:
                    variance = sum((x - mean_p95) ** 2 for x in trial_p95s) / (replications - 1)
                else:
                    variance = 0.0

                cpu_pct = min(98.5, max(12.0, (mean_rps / sat_rps) * 100.0 + self.rng.uniform(-3, 3)))
                memory_mb = 180.0 + (conc * 4.5) + self.rng.uniform(-5, 5)

                exp = ExperimentRecord(
                    experiment_id=f"exp_syn_{uuid.uuid4().hex[:10]}",
                    component_name=component_name,
                    version=version,
                    env_fingerprint=env_fp,
                    benchmark_framework="synthetic_calibrated_fixture",
                    concurrency=conc,
                    read_ratio=rr,
                    offered_rps=round(effective_rps * 1.1, 1),
                    achieved_rps=round(mean_rps, 1),
                    p50_ms=round(mean_p50, 2),
                    p95_ms=round(mean_p95, 2),
                    p99_ms=round(mean_p99, 2),
                    cpu_pct=round(cpu_pct, 1),
                    memory_mb=round(memory_mb, 1),
                    error_count=0 if congestion_ratio < 0.95 else int(self.rng.randint(1, 5)),
                    trial_replications=replications,
                    variance_ms2=round(variance, 4),
                    is_synthetic_fixture=True,
                    timestamp=now,
                    notes=f"Synthetic controlled trial matrix run with {replications} replications per configuration.",
                )
                experiments.append(exp)

        return experiments
