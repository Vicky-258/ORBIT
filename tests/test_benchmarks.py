"""
Unit tests for Benchmarks and Experiment Management.
"""
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.experiment_manager import AdaptiveExperimentManager


def test_synthetic_runner_variance_and_labels(synthetic_runner):
    exps = synthetic_runner.run_benchmark_matrix(
        component_name="postgres_db",
        version="postgres:16-alpine",
        concurrency_levels=[1, 4, 16],
        replications=3,
    )
    assert len(exps) == 3
    for e in exps:
        assert e.is_synthetic_fixture is True
        assert e.trial_replications == 3
        assert e.variance_ms2 >= 0.0
        assert e.achieved_rps > 0.0
        assert e.p95_ms > e.p50_ms


def test_docker_runner_health():
    runner = DockerBenchmarkRunner()
    health = runner.health_check()
    assert "runner_type" in health
    assert "docker_available" in health


def test_adaptive_experiment_manager(registry, default_workload):
    exp_mgr = AdaptiveExperimentManager(registry=registry)
    campaign = exp_mgr.run_campaign(
        component_name="postgres_db",
        version="postgres:16-alpine",
        workload=default_workload,
        budget_runs=6,
        force_synthetic=True,
    )
    assert campaign["total_experiments"] >= 4
    assert len(campaign["iterations"]) >= 1
    assert len(campaign["experiments"]) == campaign["total_experiments"]
