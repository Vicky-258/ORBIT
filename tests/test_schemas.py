"""
Unit tests for data contracts and schemas.
"""
import pytest
from orbit.core.schemas import (
    WorkloadSpec,
    ComponentConfig,
    ComponentType,
    ArchitectureGraph,
    InformationProvenance,
)


def test_workload_spec_validation():
    w = WorkloadSpec(request_rate_rps=500.0, read_ratio=0.85, write_ratio=0.15)
    assert w.request_rate_rps == 500.0
    assert w.read_ratio == 0.85
    assert w.write_ratio == 0.15
    assert len(w.provenance_map) > 0


def test_workload_invalid_ratios():
    with pytest.raises(ValueError, match="must equal 1.0"):
        WorkloadSpec(read_ratio=0.70, write_ratio=0.20)


def test_provenance_tracking():
    w = WorkloadSpec(request_rate_rps=600.0)
    user_facts = [p for p in w.provenance_map.values() if p.provenance == InformationProvenance.USER_FACT]
    assumptions = [p for p in w.provenance_map.values() if p.provenance == InformationProvenance.AGENT_ASSUMPTION]

    assert len(user_facts) >= 4
    assert len(assumptions) >= 3
    assert any(a.key == "cache_assumed_hit_rate" for a in assumptions)


def test_component_config_creation():
    comp = ComponentConfig(
        name="test_db",
        component_type=ComponentType.DATABASE,
        version="postgres:16-alpine",
        cpu_cores=2.0,
        memory_mb=2048,
    )
    assert comp.name == "test_db"
    assert comp.component_type == ComponentType.DATABASE
