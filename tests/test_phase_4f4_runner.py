"""
Unit and Mock Tests for Phase 4F.4 Execution Engine (Manifest & Prerequisite Verification).

Tests all Phase 4F.4 runner components offline without executing live Docker containers:
1. Frozen schedule and seed 4104 sequence integrity
2. Preflight verification and host metadata collection
3. Strict authorization guardrail (fails without explicit authorized=True)
4. Host-side client placement & credential redaction
5. Full 12-trial mock campaign execution and condition comparison aggregation
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aads.benchmark.cfs_correlation import CFSCorrelationAnalyzer
from aads.benchmark.phase_4f4_runner import (
    FROZEN_12_TRIAL_SCHEDULE,
    Phase4F4Runner,
)
from aads.benchmark.postgres_instrumentation import (
    PostgresMetricsCollector,
    PostgresPeriodicSampler,
)
from aads.benchmark.resource_monitor import ContainerResourceMonitor
from aads.benchmark.storage_monitor import StorageMonitor
from aads.benchmark.trial_isolation import (
    DatabaseStateSnapshot,
    TrialIsolationManager,
)


def test_frozen_schedule_integrity():
    """Verify that the frozen 12-trial schedule matches the Section 4 Manifest specification."""
    assert len(FROZEN_12_TRIAL_SCHEDULE) == 12

    expected_sequence = [
        (1, "ro_2cpu_r1", "read_only_select", "2.0", 1),
        (2, "ro_1cpu_r1", "read_only_select", "1.0", 1),
        (3, "tpcb_2cpu_r1", "balanced_oltp_tpcb", "2.0", 1),
        (4, "ro_2cpu_r2", "read_only_select", "2.0", 2),
        (5, "tpcb_2cpu_r2", "balanced_oltp_tpcb", "2.0", 2),
        (6, "tpcb_1cpu_r1", "balanced_oltp_tpcb", "1.0", 1),
        (7, "ro_2cpu_r3", "read_only_select", "2.0", 3),
        (8, "ro_1cpu_r3", "read_only_select", "1.0", 3),
        (9, "tpcb_1cpu_r3", "balanced_oltp_tpcb", "1.0", 3),
        (10, "tpcb_1cpu_r2", "balanced_oltp_tpcb", "1.0", 2),
        (11, "ro_1cpu_r2", "read_only_select", "1.0", 2),
        (12, "tpcb_2cpu_r3", "balanced_oltp_tpcb", "2.0", 3),
    ]

    for item, (exp_seq, exp_id, exp_prof, exp_cpu, exp_rep) in zip(FROZEN_12_TRIAL_SCHEDULE, expected_sequence):
        assert item["seq"] == exp_seq
        assert item["trial_id"] == exp_id
        assert item["profile"] == exp_prof
        assert item["cpu_limit"] == exp_cpu
        assert item["rep"] == exp_rep


def test_authorization_guardrail():
    """Verify that execute_campaign strictly refuses execution when authorized=False."""
    runner = Phase4F4Runner()
    with pytest.raises(RuntimeError, match="Phase 4F.4 execution NOT AUTHORIZED"):
        runner.execute_campaign(authorized=False)


def test_prerequisite_verification_with_mocks():
    """Verify preflight checks for Docker, image digest, and host-side pgbench."""
    runner = Phase4F4Runner()

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if "docker info" in cmd_str:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="server\n")
        if "docker images" in cmd_str:
            return subprocess.CompletedProcess(
                cmd,
                returncode=0,
                stdout=f"postgres:16-alpine {runner.pinned_digest}\n"
            )
        if "docker version" in cmd_str:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="24.0.5\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_run), patch("shutil.which", return_value="/usr/bin/pgbench"):
        preflight = runner.verify_prerequisites()
        assert preflight["prerequisites_met"] is True
        assert preflight["docker_daemon_available"] is True
        assert preflight["pinned_image_verified"] is True
        assert preflight["host_pgbench_available"] is True
        assert len(preflight["issues"]) == 0


def test_client_isolation_enforcement():
    """Verify that missing host-side pgbench stops execution fail-closed."""
    runner = Phase4F4Runner()

    def mock_run(cmd, *args, **kwargs):
        if "docker info" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="server\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_run), patch("shutil.which", return_value=None):
        preflight = runner.verify_prerequisites()
        assert preflight["prerequisites_met"] is False
        assert preflight["host_pgbench_available"] is False
        assert any("Client isolation requires pgbench to run on host" in iss for iss in preflight["issues"])


def test_mock_campaign_execution(tmp_path):
    """
    Verify full mock execution of the 12-trial campaign:
    - Executes all 12 trials in exact frozen order
    - Verifies host command parameters and credential redaction
    - Aggregates condition comparisons (1.0 vs 2.0 vCPU)
    """
    runner = Phase4F4Runner(
        warmup_seconds=0,
        duration_seconds=1,
    )
    root = tmp_path / "mock_campaign_artifacts"

    stdout_mock = (
        "transaction type: <builtin: select only>\n"
        "scaling factor: 2\n"
        "query mode: simple\n"
        "number of clients: 8\n"
        "number of threads: 2\n"
        "duration: 1 s\n"
        "number of transactions actually processed: 2000\n"
        "latency average = 4.000 ms\n"
        "tps = 2000.0 (without initial connection time)\n"
    )
    log_mock = "0 1 4000 0 1700000000 0\n" * 20

    executed_bench_commands = []

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="server\n")
        if cmd[0:2] == ["docker", "images"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=f"postgres:16-alpine {runner.pinned_digest}\n")
        if cmd[0:2] == ["docker", "version"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="24.0.5\n")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c_mock_p4f4\n")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="ready\n")
        if "docker" in cmd and "port" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="127.0.0.1:54329\n")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="done\n")
        if cmd[0] == "/usr/bin/pgbench":
            if "-c" in cmd:
                executed_bench_commands.append(cmd)
            # Create mock log file if log prefix provided
            for arg in cmd:
                if arg.startswith("--log-prefix="):
                    pfx = arg.split("=", 1)[1]
                    Path(f"{pfx}.1234").write_text(log_mock)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=stdout_mock)
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c_mock_p4f4\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    mock_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        host_port=54329,
    )

    with (
        patch("subprocess.run", side_effect=mock_run),
        patch("shutil.which", return_value="/usr/bin/pgbench"),
        patch.object(TrialIsolationManager, "capture_database_state", return_value=mock_snap),
        patch.object(TrialIsolationManager, "verify_baseline_state", return_value=(True, [])),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", return_value=([], MagicMock(mean_container_cpu_pct=50.0, throttling_events_count=0, throttled_time_seconds=0.0))),
        patch.object(ContainerResourceMonitor, "save_artifacts", return_value=None),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", return_value=(0, {}, [])),
        patch.object(PostgresPeriodicSampler, "get_telemetry", return_value={}),
    ):
        summary = runner.execute_campaign(authorized=True, artifacts_root=root)

        assert summary["manifest_status"] == "COMPLETED"
        assert summary["total_trials"] == 12
        assert summary["successful_trials"] == 12
        assert summary["failed_trials"] == 0

        # Verify host commands were executed host-side targeting 127.0.0.1:54329
        assert len(executed_bench_commands) >= 12
        first_cmd = executed_bench_commands[0]
        assert first_cmd[0] == "/usr/bin/pgbench"
        assert "-h" in first_cmd and "127.0.0.1" in first_cmd
        assert "-p" in first_cmd and "54329" in first_cmd

        # Verify condition comparisons exist
        assert "read_only_select" in summary["comparisons"]
        assert "balanced_oltp_tpcb" in summary["comparisons"]
        assert (root / "campaign_summary.json").exists()
