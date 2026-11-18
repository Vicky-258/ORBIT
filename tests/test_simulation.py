"""
Unit tests for SimPy discrete-event simulation engine.
"""
from orbit.core.schemas import WorkloadSpec


def test_simulation_architecture_a(sim_engine, generator, default_workload):
    arch_a = generator.generate_architecture_a()
    res = sim_engine.simulate_architecture(arch_a, default_workload, duration_seconds=3.0, random_seed=42)

    assert res.total_requests > 500
    assert res.completed_requests > 500
    assert res.throughput_achieved_rps > 300.0
    assert res.p50_latency_ms > 0
    assert res.p95_latency_ms >= res.p50_latency_ms
    assert res.p99_latency_ms >= res.p95_latency_ms
    assert res.bottleneck_component == "db"
    assert res.cache_hit_rate is None


def test_simulation_architecture_b_caching(sim_engine, generator, default_workload):
    arch_b = generator.generate_architecture_b()
    res = sim_engine.simulate_architecture(arch_b, default_workload, duration_seconds=3.0, random_seed=42)

    assert res.cache_hit_rate is not None
    # Expected cache hit rate should be close to 85%
    assert 0.75 <= res.cache_hit_rate <= 0.95
    # Sub-millisecond p50 due to caching
    assert res.p50_latency_ms < 2.0
    assert "cache" in res.component_utilizations


def test_simulation_architecture_c_async(sim_engine, generator, default_workload):
    arch_c = generator.generate_architecture_c()
    res = sim_engine.simulate_architecture(arch_c, default_workload, duration_seconds=3.0, random_seed=42)

    assert res.total_requests > 500
    assert "worker" in res.component_utilizations
    # Write enqueuing provides lower write latency
    assert res.p95_latency_ms < 6.0
