"""
Pytest fixtures for AADS test suite.
"""
import pytest
from aads.core.schemas import WorkloadSpec
from aads.registry.component_registry import ComponentRegistry
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.simulation.simpy_engine import SimPyEngine
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner


@pytest.fixture
def default_workload():
    return WorkloadSpec(
        request_rate_rps=400.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=350.0,
        max_monthly_budget_usd=250.0,
        cache_assumed_hit_rate=0.85,
    )


@pytest.fixture
def registry(tmp_path):
    db_path = tmp_path / "test_registry.db"
    reg = ComponentRegistry(db_path=db_path)
    reg.seed_baseline_data(force=True)
    return reg


@pytest.fixture
def generator():
    return ArchitectureGenerator()


@pytest.fixture
def synthetic_runner():
    return SyntheticBenchmarkRunner(seed=123)


@pytest.fixture
def sim_engine(registry):
    return SimPyEngine(registry=registry)
