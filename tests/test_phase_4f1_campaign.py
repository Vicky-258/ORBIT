"""
Phase 4F.1 Unit Tests: Multi-Workload & Multi-Scale Empirical Campaign Harness.
Tests workload profile resolution, multi-workload execution, dynamic initialization timeouts,
checkpoint callbacks, and fail-safe container cleanup.
"""
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aads.agent.schemas import (
    AuthorizationLevel,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
)
from aads.benchmark.bounded_executor import BoundedBenchmarkExecutor
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.workload_profiles import (
    BALANCED_OLTP_TPCB,
    READ_ONLY_SELECT,
    SIMPLE_WRITE_INGEST,
    WorkloadProfileType,
    resolve_workload_profile,
)
from aads.core.schemas import ExperimentRecord
from aads.registry.component_registry import ComponentRegistry


# ---------------------------------------------------------------------------
# 1. Workload Profile Resolution Tests
# ---------------------------------------------------------------------------

def test_workload_profile_canonical_resolution():
    """Verify canonical profile lookup and attribute specifications."""
    p_read = resolve_workload_profile("read_only_select")
    assert p_read.name == "read_only_select"
    assert p_read.command_flags == ["-S"]
    assert p_read.read_statements_per_tx == 1
    assert p_read.write_statements_per_tx == 0
    assert p_read.statement_read_ratio == 1.0
    assert p_read.wal_impact == "NONE"
    assert p_read.lock_contention == "NONE"

    p_tpcb = resolve_workload_profile("balanced_oltp_tpcb")
    assert p_tpcb.name == "balanced_oltp_tpcb"
    assert p_tpcb.command_flags == []
    assert p_tpcb.read_statements_per_tx == 1
    assert p_tpcb.write_statements_per_tx == 4
    assert p_tpcb.statement_read_ratio == 0.20
    assert p_tpcb.wal_impact == "HIGH"
    assert p_tpcb.lock_contention == "HIGH"

    p_ingest = resolve_workload_profile("simple_write_ingest")
    assert p_ingest.name == "simple_write_ingest"
    assert p_ingest.command_flags == ["-N"]
    assert p_ingest.read_statements_per_tx == 1
    assert p_ingest.write_statements_per_tx == 2
    assert abs(p_ingest.statement_read_ratio - 0.333) < 0.01
    assert p_ingest.wal_impact == "MODERATE"
    assert p_ingest.lock_contention == "LOW"


def test_workload_profile_alias_resolution():
    """Verify common aliases map cleanly to canonical profiles."""
    assert resolve_workload_profile("tpcb").name == BALANCED_OLTP_TPCB.name
    assert resolve_workload_profile("standard").name == BALANCED_OLTP_TPCB.name
    assert resolve_workload_profile("select_only").name == READ_ONLY_SELECT.name
    assert resolve_workload_profile("simple_update").name == SIMPLE_WRITE_INGEST.name
    assert resolve_workload_profile("ingest").name == SIMPLE_WRITE_INGEST.name
    assert resolve_workload_profile(None).name == READ_ONLY_SELECT.name
    assert resolve_workload_profile("unknown_profile").name == READ_ONLY_SELECT.name


# ---------------------------------------------------------------------------
# 2. Schema Multi-Workload & Scale-Factor Tests
# ---------------------------------------------------------------------------

def test_experiment_proposal_multi_workload_fields():
    """Verify proposal serialization with multi-scale and multi-workload parameters."""
    proposal = ExperimentProposal(
        proposal_id="prop_test_4f1_001",
        target_component="postgresql_db",
        version="16-alpine",
        hypothesis="Testing multi-workload execution matrix.",
        unknown_being_investigated="Multi-workload empirical scaling.",
        concurrency_levels=[1, 4, 8, 16],
        scale_factors=[2, 20, 100],
        workload_profiles=["read_only_select", "balanced_oltp_tpcb", "simple_write_ingest"],
        replications=3,
    )
    d = proposal.model_dump()
    assert d["scale_factors"] == [2, 20, 100]
    assert d["workload_profiles"] == ["read_only_select", "balanced_oltp_tpcb", "simple_write_ingest"]


def test_experiment_record_workload_and_scale_fields():
    """Verify ExperimentRecord properly captures workload profile and scale factor."""
    rec = ExperimentRecord(
        experiment_id="exp_test_sf20_tpcb_001",
        component_name="postgresql_db",
        version="16-alpine",
        env_fingerprint="docker:postgres:16-alpine:cpus=1.0:mem=1024m:test",
        benchmark_framework="pgbench:16-balanced_oltp_tpcb",
        concurrency=8,
        read_ratio=0.20,
        workload_profile="balanced_oltp_tpcb",
        scale_factor=20,
        offered_rps=1500.0,
        achieved_rps=1450.0,
        p50_ms=4.5,
        p95_ms=12.8,
        p99_ms=28.4,
        cpu_pct=98.5,
        memory_mb=320.0,
        error_count=0,
        trial_replications=1,
        timestamp="2026-10-31T12:00:00+00:00",
    )
    assert rec.workload_profile == "balanced_oltp_tpcb"
    assert rec.scale_factor == 20
    assert rec.read_ratio == 0.20


# ---------------------------------------------------------------------------
# 3. Docker Runner Multi-Workload Mock Execution Tests
# ---------------------------------------------------------------------------

def test_docker_runner_executes_workload_profiles_with_correct_flags(tmp_path):
    """Verify DockerBenchmarkRunner applies correct pgbench flags for each workload profile."""
    runner = DockerBenchmarkRunner()
    art_dir = tmp_path / "artifacts"
    executed_pgbench_cmds = []

    stdout_mock = (
        "transaction type: <builtin: select only>\n"
        "scaling factor: 2\n"
        "query mode: simple\n"
        "number of clients: 1\n"
        "number of threads: 1\n"
        "maximum number of tries: 1\n"
        "duration: 1 s\n"
        "number of transactions actually processed: 100\n"
        "number of failed transactions: 0 (0.000%)\n"
        "latency average = 1.000 ms\n"
        "latency stddev = 0.100 ms\n"
        "tps = 100.000000 (without initial connection time)\n"
    )
    log_mock = "\n".join([f"0 {i} 1000 0 1730000000 0 0" for i in range(25)]) + "\n"

    def mock_subprocess_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="24.0.5\n", stderr="")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_4f1\n", stderr="")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="init done\n", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            executed_pgbench_cmds.append(list(cmd))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout_mock, stderr="")
        if any("cat" in arg for arg in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=log_mock, stderr="")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_4f1", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    checkpoint_records = []
    def checkpoint_cb(rec):
        checkpoint_records.append(rec)

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        records = runner._benchmark_postgres(
            component_name="postgresql_db",
            version="16-alpine",
            concurrency_list=[1],
            replications=1,
            duration_seconds=1,
            warmup_seconds=0,
            scale_factors=[2],
            workload_profiles=["read_only_select", "balanced_oltp_tpcb", "simple_write_ingest"],
            artifacts_dir=art_dir,
            execution_id="exec_test_multi_01",
            checkpoint_callback=checkpoint_cb,
        )

        assert len(records) == 3
        assert len(checkpoint_records) == 3

        # Verify command flags for the 3 workloads
        assert len(executed_pgbench_cmds) == 3
        # Profile 1: read_only_select has "-S"
        assert "-S" in executed_pgbench_cmds[0]
        assert "-N" not in executed_pgbench_cmds[0]
        # Profile 2: balanced_oltp_tpcb has neither "-S" nor "-N"
        assert "-S" not in executed_pgbench_cmds[1]
        assert "-N" not in executed_pgbench_cmds[1]
        # Profile 3: simple_write_ingest has "-N"
        assert "-N" in executed_pgbench_cmds[2]
        assert "-S" not in executed_pgbench_cmds[2]

        # Verify records metadata
        assert records[0].workload_profile == "read_only_select"
        assert records[0].read_ratio == 1.0
        assert records[1].workload_profile == "balanced_oltp_tpcb"
        assert records[1].read_ratio == 0.20
        assert records[2].workload_profile == "simple_write_ingest"
        assert abs(records[2].read_ratio - 0.333) < 0.01


def test_docker_runner_multi_scale_container_lifecycle(tmp_path):
    """Verify independent container creation, initialization, and cleanup per scale factor."""
    runner = DockerBenchmarkRunner()
    started_containers = []
    removed_containers = []
    init_scale_factors = []

    stdout_mock = (
        "tps = 50.0\nlatency average = 2.0 ms\n"
        "number of transactions actually processed: 50\n"
        "number of failed transactions: 0 (0.000%)\n"
    )
    log_mock = "\n".join([f"0 {i} 2000 0 1730000000 0 0" for i in range(25)]) + "\n"

    def mock_lifecycle_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="24.0.5\n", stderr="")
        if cmd[0:2] == ["docker", "run"]:
            cont_name = cmd[cmd.index("--name") + 1]
            started_containers.append(cont_name)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=f"{cont_name}\n", stderr="")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok\n", stderr="")
        if "pgbench" in cmd and "-i" in cmd:
            sf_idx = cmd.index("-s") + 1
            init_scale_factors.append(int(cmd[sf_idx]))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="init done\n", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout_mock, stderr="")
        if any("cat" in arg for arg in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=log_mock, stderr="")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            removed_containers.append(cmd[3])
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=cmd[3], stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_lifecycle_run), patch("time.sleep", return_value=None):
        records = runner._benchmark_postgres(
            component_name="postgresql_db",
            version="16-alpine",
            concurrency_list=[1],
            replications=1,
            duration_seconds=1,
            warmup_seconds=0,
            scale_factors=[2, 20],
            workload_profile="read_only_select",
            artifacts_dir=tmp_path / "artifacts",
            execution_id="exec_test_scale_01",
        )

        assert len(records) == 2
        assert init_scale_factors == [2, 20]
        assert len(started_containers) == 2
        assert len(removed_containers) == 2
        assert started_containers == removed_containers
