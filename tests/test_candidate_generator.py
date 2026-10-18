"""
Unit tests for Architecture Candidate Generator.
"""
import pytest
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.core.schemas import ArchitectureGraph, ComponentType, ComponentConfig


def test_generate_candidates_count(generator):
    candidates = generator.generate_candidates(include_async=True, include_unsupported=True)
    assert len(candidates) == 4
    ids = [c.id for c in candidates]
    assert "arch_a_simple" in ids
    assert "arch_b_cached" in ids
    assert "arch_c_async" in ids
    assert "arch_mongo_unregistered" in ids


def test_candidate_a_topology(generator):
    arch_a = generator.generate_architecture_a()
    assert arch_a.id == "arch_a_simple"
    assert "api" in arch_a.components
    assert "db" in arch_a.components
    assert not arch_a.queue_present
    assert arch_a.read_path == ["api", "db"]
    assert arch_a.write_path == ["api", "db"]


def test_candidate_b_topology(generator):
    arch_b = generator.generate_architecture_b()
    assert "cache" in arch_b.components
    assert "redis_cache:redis:7.2-alpine" in arch_b.required_models
    assert arch_b.total_monthly_cost_usd > 133.0


def test_candidate_c_async_topology(generator):
    arch_c = generator.generate_architecture_c()
    assert arch_c.queue_present
    assert "queue" in arch_c.components
    assert "worker" in arch_c.components
    assert "worker" in arch_c.write_path


def test_invalid_graph_rejected(generator):
    invalid_arch = ArchitectureGraph(
        id="invalid_arch",
        name="Invalid",
        description="Missing API",
        components={"db": ComponentConfig(name="db", component_type=ComponentType.DATABASE, version="pg:16")},
        connections=[],
        read_path=["db"],
        write_path=["db"],
        required_models=["pg:16"],
        total_monthly_cost_usd=50.0,
    )
    with pytest.raises(ValueError, match="missing API entrypoint"):
        generator.validate_graph(invalid_arch)
