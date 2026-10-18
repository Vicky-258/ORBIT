"""
Unit tests for Component and Model Registry.
"""
from aads.core.schemas import WorkloadSpec, ModelRecord


def test_registry_seed_and_query(registry):
    models = registry.list_models()
    assert len(models) == 2
    comp_names = [m.component_name for m in models]
    assert "postgres_db" in comp_names
    assert "redis_cache" in comp_names


def test_registry_compatibility_validated(registry, default_workload):
    status, model, warnings = registry.check_compatibility("postgres_db", "postgres:16-alpine", default_workload)
    assert status == "VALIDATED"
    assert model is not None
    assert len(warnings) == 0


def test_registry_compatibility_missing_model(registry, default_workload):
    status, model, warnings = registry.check_compatibility("mongodb_cluster", "mongodb:7.0-cluster", default_workload)
    assert status == "MISSING"
    assert model is None
    assert any("Benchmarking required" in w for w in warnings)


def test_registry_out_of_range_detection(registry):
    extreme_workload = WorkloadSpec(request_rate_rps=10000.0)  # beyond max supported RPS
    status, model, warnings = registry.check_compatibility("postgres_db", "postgres:16-alpine", extreme_workload)
    assert status == "OUT_OF_RANGE"
    assert model is not None
    assert any("outside model supported range" in w for w in warnings)
