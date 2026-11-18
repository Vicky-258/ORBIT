"""
Adaptive Experiment Manager.
Orchestrates fixed-baseline followed by adaptive high-value experiment trials.
"""
from typing import Dict, List, Optional, Any
from orbit.benchmark.runner_interface import BenchmarkRunner
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from orbit.benchmark.docker_runner import DockerBenchmarkRunner
from orbit.core.schemas import WorkloadSpec, ExperimentRecord, ModelRecord
from orbit.registry.component_registry import ComponentRegistry


class AdaptiveExperimentManager:
    """
    Executes a fixed baseline matrix, evaluates model fit, and adaptively prioritizes
    follow-up trials based on uncertainty and decision relevance within budget.
    """

    def __init__(
        self,
        registry: ComponentRegistry,
        docker_runner: Optional[DockerBenchmarkRunner] = None,
        synthetic_runner: Optional[SyntheticBenchmarkRunner] = None,
    ):
        self.registry = registry
        self.docker_runner = docker_runner or DockerBenchmarkRunner()
        self.synthetic_runner = synthetic_runner or SyntheticBenchmarkRunner()

    def select_runner(self, force_synthetic: bool = False) -> BenchmarkRunner:
        if force_synthetic:
            return self.synthetic_runner
        check = self.docker_runner.health_check()
        if check["docker_available"]:
            return self.docker_runner
        return self.synthetic_runner

    def run_campaign(
        self,
        component_name: str,
        version: str,
        workload: WorkloadSpec,
        budget_runs: int = 8,
        force_synthetic: bool = False,
    ) -> Dict[str, Any]:
        runner = self.select_runner(force_synthetic=force_synthetic)
        is_synthetic = getattr(runner, "health_check", lambda: {})().get("is_synthetic", False) or force_synthetic

        # 1. Baseline fixed matrix (4 configurations)
        baseline_concurrencies = [1, 4, 8, 16]
        all_experiments: List[ExperimentRecord] = []

        baseline_runs = runner.run_benchmark_matrix(
            component_name=component_name,
            version=version,
            concurrency_levels=baseline_concurrencies,
            read_ratios=[workload.read_ratio],
            replications=3,
        )
        all_experiments.extend(baseline_runs)
        for exp in baseline_runs:
            self.registry.save_experiment(exp)

        remaining_budget = max(0, budget_runs - len(baseline_concurrencies))
        iterations = [{"phase": "baseline", "concurrencies": baseline_concurrencies, "count": len(baseline_runs)}]

        # 2. Adaptive follow-up selection
        # Candidate points to consider for social feed workload
        candidate_concurrencies = [2, 12, 24, 32]
        
        while remaining_budget > 0 and candidate_concurrencies:
            # Score candidate points:
            # Higher score for points near peak load concurrency or high uncertainty
            target_peak_concurrency = int(max(4, min(32, workload.request_rate_rps * workload.peak_load_factor / 30.0)))
            
            # Prioritize candidate closest to peak concurrency or boundary
            best_candidate = None
            best_score = -1.0

            for cand in candidate_concurrencies:
                # Relevance: distance to peak concurrency
                distance = abs(cand - target_peak_concurrency)
                relevance = 1.0 / (1.0 + distance)
                # Uncertainty factor: higher for large concurrency
                uncertainty = 1.0 + (cand / 32.0)
                score = relevance * uncertainty
                if score > best_score:
                    best_score = score
                    best_candidate = cand

            if best_candidate is None:
                break

            candidate_concurrencies.remove(best_candidate)
            remaining_budget -= 1

            # Run single adaptive experiment point
            followup_runs = runner.run_benchmark_matrix(
                component_name=component_name,
                version=version,
                concurrency_levels=[best_candidate],
                read_ratios=[workload.read_ratio],
                replications=3,
            )
            all_experiments.extend(followup_runs)
            for exp in followup_runs:
                self.registry.save_experiment(exp)

            iterations.append({
                "phase": "adaptive_step",
                "concurrency": best_candidate,
                "score": round(best_score, 3),
                "achieved_rps": followup_runs[0].achieved_rps if followup_runs else 0.0,
            })

        return {
            "component_name": component_name,
            "version": version,
            "total_experiments": len(all_experiments),
            "is_synthetic_fixture": is_synthetic,
            "runner_type": type(runner).__name__,
            "budget_exhausted": remaining_budget == 0,
            "remaining_budget": remaining_budget,
            "iterations": iterations,
            "experiments": all_experiments,
        }
