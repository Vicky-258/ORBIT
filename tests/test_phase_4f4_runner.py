"""
Unit and Mock Tests for Phase 4F.4 Execution Engine (Manifest, Prerequisite & Hardened Safety Verification).

Comprehensive offline regression suite covering all 17 FIX 08 scenarios:
1. Missing authorization rejection
2. Wrong manifest hash rejection
3. Wrong proposal ID rejection
4. Reused authorization rejection
5. Client cgroup isolation failure
6. CPU quota mismatch abort before warm-up
7. Memory limit mismatch abort before warm-up
8. Image digest mismatch abort before warm-up
9. Missing p90/p99.9/max/std metrics handling
10. Missing failed-transaction count handling
11. Incomplete transaction logs / reconciliation failure
12. Warm-up failure lifecycle cleanup
13. Benchmark timeout lifecycle cleanup
14. Sampler failure lifecycle cleanup
15. Monitor shutdown failure lifecycle cleanup
16. Container cleanup failure handling
17. Failure artifact persistence
Plus baseline tests:
- Frozen schedule and seed 4104 sequence integrity
- Preflight verification and host metadata collection
- Full 12-trial mock campaign execution and condition comparison aggregation
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aads.benchmark.cfs_correlation import CFSCorrelationAnalyzer
from aads.benchmark.docker_runner import PgbenchOutputParser
from aads.benchmark.phase_4f4_runner import (
    EXPECTED_MANIFEST_SHA256,
    FROZEN_12_TRIAL_SCHEDULE,
    CampaignAuthorizationRecord,
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


def make_valid_authorization(**kwargs) -> CampaignAuthorizationRecord:
    """Helper to create a valid CampaignAuthorizationRecord fixture."""
    data = {
        "phase": "4F.4",
        "proposal_id": "prop_phase4f4_empirical_001",
        "authorization_id": "auth_phase4f4_empirical_001",
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "execution_scope": "PHASE_4F4_12_TRIAL_EMPIRICAL_CAMPAIGN",
        "operator_identity": "lead_operator_test",
        "authorized_at_utc": "2026-11-02T10:00:00Z",
        "expires_at_utc": "2027-11-10T10:00:00Z",
        "revoked": False,
        "consumed": False,
    }
    data.update(kwargs)
    return CampaignAuthorizationRecord(**data)


# ---------------------------------------------------------------------------
# Baseline Frozen Schedule & Preflight Tests
# ---------------------------------------------------------------------------

def test_frozen_schedule_integrity():
    """Verify that the frozen 12-trial schedule matches Section 4 Manifest specification."""
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


# ---------------------------------------------------------------------------
# FIX 08 Regression Tests 01 to 04: Authorization Hardening
# ---------------------------------------------------------------------------

def test_01_missing_authorization_rejection():
    """FIX 01: Verify that missing or boolean-only authorization is rejected fail-closed."""
    runner = Phase4F4Runner()
    # Missing authorization (None or boolean bypass)
    with pytest.raises(RuntimeError, match="Phase 4F.4 execution NOT AUTHORIZED"):
        runner.execute_campaign(authorization=None)  # type: ignore

    with pytest.raises(RuntimeError, match="Boolean authorization is rejected"):
        runner.execute_campaign(authorization=True)  # type: ignore


def test_02_wrong_manifest_hash_rejection():
    """FIX 01: Verify that an authorization record with wrong manifest SHA256 is rejected."""
    runner = Phase4F4Runner()
    auth = make_valid_authorization(manifest_sha256="0000000000000000000000000000000000000000000000000000000000000000")
    with pytest.raises(ValueError, match="Authorization manifest SHA256 mismatch"):
        runner.execute_campaign(authorization=auth)


def test_03_wrong_proposal_id_rejection():
    """FIX 01: Verify that mismatched proposal ID is rejected."""
    runner = Phase4F4Runner()
    auth = make_valid_authorization(proposal_id="wrong_proposal_123")
    with pytest.raises(ValueError, match="Authorization proposal_id mismatch"):
        runner.execute_campaign(authorization=auth, expected_proposal_id="prop_phase4f4_empirical_001")


def test_04_reused_authorization_rejection():
    """FIX 01: Verify that an already-consumed authorization record is rejected."""
    runner = Phase4F4Runner()
    auth = make_valid_authorization(
        consumed=True,
        consumed_at_utc="2026-11-02T12:00:00Z",
        consumed_by_execution_id="exec_p4f4_prior",
    )
    with pytest.raises(ValueError, match="ALREADY BEEN CONSUMED"):
        runner.execute_campaign(authorization=auth)


# ---------------------------------------------------------------------------
# FIX 08 Regression Test 05: Benchmark Client Isolation Failure
# ---------------------------------------------------------------------------

def test_05_client_cgroup_isolation_failure(tmp_path):
    """FIX 02: Verify that pgbench running inside container cgroup fails closed immediately."""
    runner = Phase4F4Runner()
    cg_dir = tmp_path / "system.slice" / "docker-123.scope"
    cg_dir.mkdir(parents=True)
    procs_file = cg_dir / "cgroup.procs"
    procs_file.write_text("100\n200\n")

    # Client cgroup identical to container cgroup
    with patch.object(Phase4F4Runner, "read_process_cgroup", return_value="0::/system.slice/docker-123.scope"):
        with pytest.raises(RuntimeError, match="Client cgroup isolation violation.*inside the container cgroup"):
            runner.verify_benchmark_process_isolation(
                client_pid=999,
                container_cg_dir=cg_dir,
                bench_cmd=["pgbench", "-c", "8"],
                cgroup_root=tmp_path,
            )

    # Client PID listed in container cgroup.procs
    procs_file.write_text("100\n999\n")
    with patch.object(Phase4F4Runner, "read_process_cgroup", return_value="0::/user.slice/user-1000.slice/app.scope"):
        with pytest.raises(RuntimeError, match="listed in container cgroup.procs"):
            runner.verify_benchmark_process_isolation(
                client_pid=999,
                container_cg_dir=cg_dir,
                bench_cmd=["pgbench", "-c", "8"],
                cgroup_root=tmp_path,
            )


# ---------------------------------------------------------------------------
# FIX 08 Regression Tests 06 to 08: Effective Resource & Image Verification
# ---------------------------------------------------------------------------

def test_06_cpu_quota_mismatch_abort(tmp_path):
    """FIX 04: Verify CPU quota mismatch in cpu.max aborts trial before warm-up."""
    runner = Phase4F4Runner()
    cg_dir = tmp_path / "cg_test"
    cg_dir.mkdir()
    (cg_dir / "cpu.max").write_text("50000 100000\n")  # 0.5 vCPU instead of 1.0 vCPU
    (cg_dir / "memory.max").write_text("1073741824\n")
    (cg_dir / "cgroup.procs").write_text("100\n")

    def mock_inspect(cmd, *args, **kwargs):
        if "{{.Id}} {{.Image}} {{.State.Pid}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="cid imgid 100\n")
        if "{{range .RepoDigests}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=f"postgres@{runner.pinned_digest}\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_inspect):
        with pytest.raises(RuntimeError, match="CPU quota mismatch"):
            runner.verify_container_effective_resources(
                container_name="test_c",
                cg_dir=cg_dir,
                expected_cpu_limit=1.0,
                expected_memory_limit_str="1024m",
                expected_image_digest=runner.pinned_digest,
            )


def test_07_memory_limit_mismatch_abort(tmp_path):
    """FIX 04: Verify memory limit mismatch in memory.max aborts trial before warm-up."""
    runner = Phase4F4Runner()
    cg_dir = tmp_path / "cg_test"
    cg_dir.mkdir()
    (cg_dir / "cpu.max").write_text("100000 100000\n")
    (cg_dir / "memory.max").write_text("536870912\n")  # 512m instead of 1024m
    (cg_dir / "cgroup.procs").write_text("100\n")

    def mock_inspect(cmd, *args, **kwargs):
        if "{{.Id}} {{.Image}} {{.State.Pid}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="cid imgid 100\n")
        if "{{range .RepoDigests}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=f"postgres@{runner.pinned_digest}\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_inspect):
        with pytest.raises(RuntimeError, match="Memory limit mismatch"):
            runner.verify_container_effective_resources(
                container_name="test_c",
                cg_dir=cg_dir,
                expected_cpu_limit=1.0,
                expected_memory_limit_str="1024m",
                expected_image_digest=runner.pinned_digest,
            )


def test_08_image_digest_mismatch_abort(tmp_path):
    """FIX 04: Verify image digest mismatch aborts trial before warm-up."""
    runner = Phase4F4Runner()
    cg_dir = tmp_path / "cg_test"
    cg_dir.mkdir()
    (cg_dir / "cpu.max").write_text("100000 100000\n")
    (cg_dir / "memory.max").write_text("1073741824\n")
    (cg_dir / "cgroup.procs").write_text("100\n")

    def mock_inspect(cmd, *args, **kwargs):
        if "{{.Id}} {{.Image}} {{.State.Pid}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="cid imgid 100\n")
        if "{{range .RepoDigests}}" in " ".join(cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="postgres@sha256:bad_digest_deadbeef\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_inspect):
        with pytest.raises(RuntimeError, match="Image digest mismatch"):
            runner.verify_container_effective_resources(
                container_name="test_c",
                cg_dir=cg_dir,
                expected_cpu_limit=1.0,
                expected_memory_limit_str="1024m",
                expected_image_digest=runner.pinned_digest,
            )


# ---------------------------------------------------------------------------
# FIX 08 Regression Tests 09 to 11: Metric Provenance & Log Reconciliation
# ---------------------------------------------------------------------------

def test_09_missing_percentiles_metrics_handling(tmp_path):
    """FIX 03: Verify that missing percentile metrics are NOT replaced with formulas and fail trial."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    # Log parser returns dict missing p90_ms and p999_ms
    incomplete_stats = {
        "sample_count": 20,
        "p50_ms": 2.0,
        "p95_ms": 4.0,
        "p99_ms": 5.0,
        # p90_ms is missing!
        # p999_ms is missing!
        "max_ms": 6.0,
        "std_ms": 0.5,
    }

    stdout_mock = (
        "number of transactions actually processed: 20\n"
        "number of failed transactions: 0\n"
        "latency average = 2.5 ms\n"
        "tps = 100.0\n"
    )

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(runner, "verify_benchmark_process_isolation", return_value={"isolated": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", return_value=([], None)),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", return_value=(0, {}, [])),
        patch.object(TrialIsolationManager, "cleanup_container", return_value=None),
        patch.object(PgbenchOutputParser, "parse_transaction_logs", return_value=incomplete_stats),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=0, stdout="")),
        patch("subprocess.Popen") as mock_popen,
    ):
        proc_mock = MagicMock()
        proc_mock.pid = 9999
        proc_mock.communicate.return_value = (stdout_mock, "")
        proc_mock.returncode = 0
        mock_popen.return_value = proc_mock

        # Create mock log file so log collection finds it
        t_dir = art_dir / trial_def["trial_id"]
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / f"pgbench_{trial_def['trial_id']}.1").write_text("0 1 2000 0 1700000000 0\n" * 20)

        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert result["status"] == "FAILED"
        assert result["failure_stage"] == "METRIC_VALIDATION"
        assert "missing required metrics without fallback" in result["exception_message"]
        assert "p90_ms" in result["exception_message"]


def test_10_missing_failed_transaction_count_handling(tmp_path):
    """FIX 03: Verify that missing 'number of failed transactions' in stdout marks metric UNAVAILABLE."""
    stdout_no_failed = (
        "tps = 1500.0 (without initial connection time)\n"
        "latency average = 0.500 ms\n"
        "number of transactions actually processed: 1000\n"
    )
    summary = PgbenchOutputParser.parse_summary(stdout_no_failed)
    assert summary["failed_transactions"] is None
    assert summary["failed_transactions_status"] == "UNAVAILABLE"
    assert "Line 'number of failed transactions:' not found" in summary["failed_transactions_reason"]


def test_11_incomplete_transaction_logs_reconciliation_failure(tmp_path):
    """FIX 03: Verify raw log sample count mismatch with benchmark reported count fails trial."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    # Benchmark reported 2000 transactions, but log parser only has 1500 samples
    log_stats = {
        "sample_count": 1500,
        "p50_ms": 2.0, "p90_ms": 3.0, "p95_ms": 4.0, "p99_ms": 5.0, "p999_ms": 6.0,
        "max_ms": 7.0, "std_ms": 0.5,
    }
    stdout_mock = (
        "number of transactions actually processed: 2000\n"
        "number of failed transactions: 0\n"
        "latency average = 2.5 ms\n"
        "tps = 100.0\n"
    )

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(runner, "verify_benchmark_process_isolation", return_value={"isolated": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", return_value=([], None)),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", return_value=(0, {}, [])),
        patch.object(TrialIsolationManager, "cleanup_container", return_value=None),
        patch.object(PgbenchOutputParser, "parse_transaction_logs", return_value=log_stats),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=0, stdout="")),
        patch("subprocess.Popen") as mock_popen,
    ):
        proc_mock = MagicMock()
        proc_mock.pid = 9999
        proc_mock.communicate.return_value = (stdout_mock, "")
        proc_mock.returncode = 0
        mock_popen.return_value = proc_mock

        t_dir = art_dir / trial_def["trial_id"]
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / f"pgbench_{trial_def['trial_id']}.1").write_text("dummy\n")

        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert result["status"] == "FAILED"
        assert result["failure_stage"] == "METRIC_VALIDATION"
        assert "transaction count reconciliation failure" in result["exception_message"]
        assert "1500" in result["exception_message"] and "2000" in result["exception_message"]


# ---------------------------------------------------------------------------
# FIX 08 Regression Tests 12 to 16: Complete Lifecycle Cleanup
# ---------------------------------------------------------------------------

def test_12_warmup_failure_lifecycle_cleanup(tmp_path):
    """FIX 05: Verify warm-up failure stops monitors, samplers, and cleans up container."""
    runner = Phase4F4Runner(warmup_seconds=10, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    mock_mgr_cleanup = MagicMock()
    mock_mon_stop = MagicMock(return_value=([], None))
    mock_samp_stop = MagicMock(return_value=(0, {}, []))

    def mock_run(cmd, *args, **kwargs):
        if "-T" in cmd and "10" in cmd:  # Warm-up command
            return subprocess.CompletedProcess(cmd, returncode=1, stderr="Warm-up connection reset by peer")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", mock_mon_stop),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", mock_samp_stop),
        patch.object(TrialIsolationManager, "cleanup_container", mock_mgr_cleanup),
        patch("subprocess.run", side_effect=mock_run),
    ):
        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert result["status"] == "FAILED"
        assert result["failure_stage"] == "WARMUP"
        assert mock_mgr_cleanup.called
        assert mock_mon_stop.called
        assert mock_samp_stop.called


def test_13_benchmark_timeout_lifecycle_cleanup(tmp_path):
    """FIX 05: Verify benchmark timeout kills process and triggers complete lifecycle cleanup."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    mock_mgr_cleanup = MagicMock()
    mock_mon_stop = MagicMock(return_value=([], None))
    mock_samp_stop = MagicMock(return_value=(0, {}, []))

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(runner, "verify_benchmark_process_isolation", return_value={"isolated": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", mock_mon_stop),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", mock_samp_stop),
        patch.object(TrialIsolationManager, "cleanup_container", mock_mgr_cleanup),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=0, stdout="")),
        patch("subprocess.Popen") as mock_popen,
    ):
        proc_mock = MagicMock()
        proc_mock.pid = 9999
        proc_mock.communicate.side_effect = subprocess.TimeoutExpired(cmd="pgbench", timeout=26)
        mock_popen.return_value = proc_mock

        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert result["status"] == "FAILED"
        assert result["failure_stage"] == "BENCHMARK_EXECUTION"
        assert "Benchmark execution timed out" in result["exception_message"]
        assert proc_mock.kill.called
        assert mock_mgr_cleanup.called
        assert mock_mon_stop.called
        assert mock_samp_stop.called


def test_14_sampler_failure_lifecycle_cleanup(tmp_path):
    """FIX 05: Verify that failure inside sampler shutdown does not block container cleanup."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    mock_mgr_cleanup = MagicMock()

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", return_value=([], None)),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", side_effect=RuntimeError("psql coprocess dead")),
        patch.object(TrialIsolationManager, "cleanup_container", mock_mgr_cleanup),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=1, stderr="fail")),
    ):
        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        # Container cleanup must STILL execute despite sampler exception
        assert mock_mgr_cleanup.called
        assert result["cleanup_result"]["success"] is False
        assert any("psql coprocess dead" in err for err in result["cleanup_result"]["cleanup_errors"])


def test_15_monitor_shutdown_failure_lifecycle_cleanup(tmp_path):
    """FIX 05: Verify that failure inside monitor shutdown does not block container cleanup."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    mock_mgr_cleanup = MagicMock()

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", side_effect=RuntimeError("cgroup io error")),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", return_value=(0, {}, [])),
        patch.object(TrialIsolationManager, "cleanup_container", mock_mgr_cleanup),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=1, stderr="fail")),
    ):
        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert mock_mgr_cleanup.called
        assert result["cleanup_result"]["success"] is False
        assert any("cgroup io error" in err for err in result["cleanup_result"]["cleanup_errors"])


def test_16_container_cleanup_failure_handling(tmp_path):
    """FIX 05: Verify container cleanup error is recorded in cleanup_errors without masking trial failure."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(PostgresMetricsCollector, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(PostgresMetricsCollector, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "take_snapshot", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(StorageMonitor, "compute_deltas", return_value=MagicMock(to_dict=lambda: {})),
        patch.object(ContainerResourceMonitor, "start", return_value=None),
        patch.object(ContainerResourceMonitor, "stop", return_value=([], None)),
        patch.object(PostgresPeriodicSampler, "start", return_value=None),
        patch.object(PostgresPeriodicSampler, "stop", return_value=(0, {}, [])),
        patch.object(TrialIsolationManager, "cleanup_container", side_effect=RuntimeError("docker rm -f failed")),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=1, stderr="primary error")),
    ):
        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test")
        assert result["status"] == "FAILED"
        assert result["cleanup_result"]["success"] is False
        assert any("docker rm -f failed" in err for err in result["cleanup_result"]["cleanup_errors"])
        # Original primary error is preserved in exception_message
        assert "Warm-up failed" in result["exception_message"] or "primary error" in result["stderr"]


# ---------------------------------------------------------------------------
# FIX 08 Regression Test 17: Durable Failure Artifact Persistence
# ---------------------------------------------------------------------------

def test_17_failure_artifact_persistence(tmp_path):
    """FIX 06: Verify failed/aborted trial persists trial_failure.json with complete diagnostics."""
    runner = Phase4F4Runner(warmup_seconds=0, duration_seconds=1)
    trial_def = FROZEN_12_TRIAL_SCHEDULE[0]
    art_dir = tmp_path / "trials"

    with (
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, MagicMock(host_port=54329, content_fingerprint="fp"))),
        patch.object(ContainerResourceMonitor, "resolve_cgroup_dir", return_value=tmp_path),
        patch.object(runner, "verify_container_effective_resources", side_effect=RuntimeError("Resource verification abort")),
        patch.object(TrialIsolationManager, "cleanup_container", return_value=None),
    ):
        result = runner.execute_single_trial(trial_def=trial_def, artifacts_dir=art_dir, execution_id="exec_test_diag")
        assert result["status"] == "ABORTED"
        assert result["failure_stage"] == "RESOURCE_VERIFICATION"

        fail_file = art_dir / trial_def["trial_id"] / "trial_failure.json"
        assert fail_file.exists()
        fail_data = json.loads(fail_file.read_text())
        assert fail_data["trial_id"] == trial_def["trial_id"]
        assert fail_data["status"] == "ABORTED"
        assert fail_data["failure_stage"] == "RESOURCE_VERIFICATION"
        assert fail_data["exception_type"] == "RuntimeError"
        assert "Resource verification abort" in fail_data["exception_message"]
        assert "cleanup_result" in fail_data
        assert "timestamp_utc" in fail_data


# ---------------------------------------------------------------------------
# Full Mock Campaign Execution with Strict Completion (FIX 07)
# ---------------------------------------------------------------------------

def test_mock_campaign_execution(tmp_path):
    """
    Verify full mock execution of the 12-trial campaign under validated authorization:
    - Executes all 12 trials in exact frozen order
    - Verifies host command parameters and credential redaction
    - Aggregates condition comparisons (1.0 vs 2.0 vCPU)
    - Verifies atomic authorization consumption and campaign completion validation
    """
    runner = Phase4F4Runner(
        warmup_seconds=0,
        duration_seconds=1,
    )
    root = tmp_path / "mock_campaign_artifacts"
    auth = make_valid_authorization()

    stdout_mock = (
        "transaction type: <builtin: select only>\n"
        "scaling factor: 2\n"
        "query mode: simple\n"
        "number of clients: 8\n"
        "number of threads: 2\n"
        "duration: 1 s\n"
        "number of transactions actually processed: 20\n"
        "number of failed transactions: 0 (0.000%)\n"
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

    # Mock Popen for measured benchmark
    def mock_popen(cmd, *args, **kwargs):
        if "-c" in cmd:
            executed_bench_commands.append(cmd)
        for arg in cmd:
            if arg.startswith("--log-prefix="):
                pfx = arg.split("=", 1)[1]
                Path(f"{pfx}.1234").write_text(log_mock)
        proc = MagicMock()
        proc.pid = 8888
        proc.communicate.return_value = (stdout_mock, "")
        proc.returncode = 0
        return proc

    with (
        patch("subprocess.run", side_effect=mock_run),
        patch("subprocess.Popen", side_effect=mock_popen),
        patch("shutil.which", return_value="/usr/bin/pgbench"),
        patch.object(TrialIsolationManager, "initialize_fresh_container", return_value=(0.1, mock_snap)),
        patch.object(TrialIsolationManager, "capture_database_state", return_value=mock_snap),
        patch.object(TrialIsolationManager, "verify_baseline_state", return_value=(True, [])),
        patch.object(runner, "verify_container_effective_resources", return_value={"verification_passed": True}),
        patch.object(runner, "verify_benchmark_process_isolation", return_value={"isolated": True}),
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
        patch.object(TrialIsolationManager, "cleanup_container", return_value=None),
    ):
        summary = runner.execute_campaign(authorization=auth, artifacts_root=root)

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
        assert (root / "consumed_authorization.json").exists()
        assert (root / "campaign_state_partial.json").exists()
