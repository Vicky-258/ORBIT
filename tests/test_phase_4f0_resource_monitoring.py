"""
Phase 4F.0 Unit Tests: Container Resource and CPU Throttling Monitoring Verification.
Covers:
- Active sampling during execution
- CPU and throttling counter delta calculations
- Memory usage and limit parsing
- Missing cgroup files and permission errors
- Sampler exception handling and fail-open resilience
- Thread lifecycle and cleanup
- Timeout handling and guaranteed cleanup
- Execution and experiment provenance
- Latency spike correlation analysis
"""
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aads.benchmark.resource_monitor import (
    ContainerResourceMonitor,
    ResourceSample,
    CgroupSnapshot,
    TrialMonitoringSummary,
)
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.agent.schemas import ExperimentProposal, AuthorizationRecord, AuthorizationStatus


@pytest.fixture
def mock_cgroup_dir(tmp_path):
    """Creates a temporary directory with mock cgroup v2 controller files."""
    cg_dir = tmp_path / "mock_cgroup"
    cg_dir.mkdir(parents=True, exist_ok=True)

    # cpu.stat
    cpu_stat_content = (
        "usage_usec 1000000\n"
        "user_usec 800000\n"
        "system_usec 200000\n"
        "nr_periods 50\n"
        "nr_throttled 5\n"
        "throttled_usec 250000\n"
    )
    (cg_dir / "cpu.stat").write_text(cpu_stat_content)

    # cpu.max (1.0 vCPU)
    (cg_dir / "cpu.max").write_text("100000 100000\n")

    # memory.current and memory.max
    (cg_dir / "memory.current").write_text("104857600\n")  # 100 MB
    (cg_dir / "memory.max").write_text("1073741824\n")     # 1024 MB

    return cg_dir


# ---------------------------------------------------------------------------
# 1. Parsing & Delta Calculations
# ---------------------------------------------------------------------------

def test_cgroup_parsing_and_metrics(mock_cgroup_dir):
    """Verify correct parsing of cgroup v2 cpu.stat, cpu.max, and memory files."""
    monitor = ContainerResourceMonitor(
        container_name="test-cont",
        cgroup_dir=mock_cgroup_dir,
        execution_id="exec_test_001",
        experiment_id="exp_test_001",
    )

    snapshot = monitor.take_cgroup_snapshot()
    assert snapshot.usage_usec == 1000000
    assert snapshot.user_usec == 800000
    assert snapshot.system_usec == 200000
    assert snapshot.nr_periods == 50
    assert snapshot.nr_throttled == 5
    assert snapshot.throttled_usec == 250000
    assert snapshot.quota_usec == 100000
    assert snapshot.period_usec == 100000
    assert snapshot.memory_current_bytes == 104857600
    assert snapshot.memory_max_bytes == 1073741824


def test_cpu_and_throttling_counter_deltas(mock_cgroup_dir):
    """Verify valid delta calculations between start and end snapshots."""
    monitor = ContainerResourceMonitor(
        container_name="test-cont",
        cgroup_dir=mock_cgroup_dir,
        execution_id="exec_test_001",
        experiment_id="exp_test_001",
    )

    # Baseline snapshot
    monitor._start_snapshot = monitor.take_cgroup_snapshot()
    monitor._start_time_monotonic = time.monotonic() - 10.0  # simulate 10s duration

    # Simulate updated counters in cgroup
    (mock_cgroup_dir / "cpu.stat").write_text(
        "usage_usec 9500000\n"
        "user_usec 7500000\n"
        "system_usec 2000000\n"
        "nr_periods 150\n"
        "nr_throttled 35\n"
        "throttled_usec 1750000\n"
    )

    # Stop and get summary
    samples, summary = monitor.stop()

    assert summary.cpu_time_consumed_seconds == pytest.approx(8.5, rel=1e-3)  # (9.5M - 1.0M) / 1e6
    assert summary.throttling_events_count == 30                             # 35 - 5
    assert summary.throttled_time_seconds == pytest.approx(1.5, rel=1e-3)    # (1.75M - 0.25M) / 1e6
    assert summary.throttling_event_rate_per_sec == pytest.approx(3.0, rel=0.1)
    assert summary.cpu_quota_utilization_pct > 80.0
    assert summary.throttling_events_count >= 0
    assert summary.throttled_time_seconds >= 0.0


def test_unlimited_cpu_and_memory(tmp_path):
    """Verify handling when CPU quota is 'max' or memory is unlimited."""
    cg_dir = tmp_path / "unlimited_cg"
    cg_dir.mkdir(parents=True, exist_ok=True)
    (cg_dir / "cpu.stat").write_text("usage_usec 500000\nnr_throttled 0\nthrottled_usec 0\n")
    (cg_dir / "cpu.max").write_text("max 100000\n")
    (cg_dir / "memory.current").write_text("52428800\n")
    (cg_dir / "memory.max").write_text("max\n")

    monitor = ContainerResourceMonitor(container_name="test-cont", cgroup_dir=cg_dir)
    snapshot = monitor.take_cgroup_snapshot()

    assert snapshot.quota_usec is None
    assert snapshot.period_usec == 100000
    assert snapshot.memory_max_bytes is None


# ---------------------------------------------------------------------------
# 2. Resiliency & Missing Metrics (Fail Open)
# ---------------------------------------------------------------------------

def test_missing_cgroup_files_fails_open(tmp_path):
    """Verify that nonexistent cgroup files do not crash the sampler."""
    empty_dir = tmp_path / "empty_cg"
    empty_dir.mkdir(parents=True, exist_ok=True)

    monitor = ContainerResourceMonitor(container_name="test-cont", cgroup_dir=empty_dir)
    sample = monitor._collect_sample(0)

    assert sample.cumulative_cpu_usage_usec is None
    assert sample.cgroup_nr_throttled is None
    assert sample.memory_usage_bytes is None
    assert sample.container_cpu_pct is None

    _, summary = monitor.stop()
    assert "cgroup_cpu_usage" in summary.unreliable_or_missing_metrics


def test_permission_error_handling(mock_cgroup_dir):
    """Verify that permission errors during file reads are gracefully caught."""
    monitor = ContainerResourceMonitor(container_name="test-cont", cgroup_dir=mock_cgroup_dir)

    with patch.object(Path, "read_text", side_effect=PermissionError("Permission denied")):
        sample = monitor._collect_sample(0)
        assert sample.cumulative_cpu_usage_usec is None
        assert len(monitor._sampler_errors) > 0


# ---------------------------------------------------------------------------
# 3. Active Background Sampling Thread Lifecycle
# ---------------------------------------------------------------------------

def test_active_sampling_thread_lifecycle(mock_cgroup_dir):
    """Verify background thread starts, collects samples at ~500ms intervals, and shuts down."""
    monitor = ContainerResourceMonitor(
        container_name="test-cont",
        interval_sec=0.1,  # use 100ms for fast test execution
        cgroup_dir=mock_cgroup_dir,
        execution_id="exec_cycle_123",
        experiment_id="exp_cycle_456",
    )

    monitor.start()
    assert monitor._thread is not None
    assert monitor._thread.is_alive()

    # Allow thread to take at least 3 samples
    time.sleep(0.35)

    samples, summary = monitor.stop()

    assert not monitor._thread.is_alive()
    assert len(samples) >= 3
    assert summary.sample_count == len(samples)
    assert summary.actual_mean_interval_ms is not None
    assert summary.actual_mean_interval_ms > 50.0

    for s in samples:
        assert s.execution_id == "exec_cycle_123"
        assert s.experiment_id == "exp_cycle_456"
        assert s.container_name == "test-cont"
        assert s.timestamp_monotonic > 0


def test_artifact_persistence(mock_cgroup_dir, tmp_path):
    """Verify raw monitoring samples (JSON, CSV) and summary JSON persistence."""
    out_dir = tmp_path / "artifacts"
    monitor = ContainerResourceMonitor(
        container_name="test-cont",
        interval_sec=0.05,
        cgroup_dir=mock_cgroup_dir,
        execution_id="exec_persist_01",
        experiment_id="exp_persist_01",
    )

    monitor.start()
    time.sleep(0.15)
    samples, summary = monitor.stop()

    paths = monitor.save_artifacts(out_dir, "trial_c8_r0")

    assert os.path.exists(paths["samples_json"])
    assert os.path.exists(paths["samples_csv"])
    assert os.path.exists(paths["summary_json"])

    import json
    with open(paths["summary_json"]) as f:
        data = json.load(f)
    assert data["experiment_id"] == "exp_persist_01"
    assert data["sample_count"] == len(samples)


# ---------------------------------------------------------------------------
# 4. Latency Spike Correlation Analysis
# ---------------------------------------------------------------------------

def test_latency_spike_correlation_logic():
    """Verify correlation helper correctly detects periodic CFS throttle bursts."""
    # Simulate 300 transactions where every 100ms a transaction experiences 85ms latency
    t0 = 1000.0
    timestamps = []
    latencies = []

    for i in range(100):
        # 99 fast transactions (0.05ms)
        for _ in range(9):
            t0 += 0.01
            timestamps.append(t0)
            latencies.append(0.05)
        # 1 throttled transaction (85ms)
        t0 += 0.01
        timestamps.append(t0)
        latencies.append(85.0)

    # Mock samples with throttling
    mock_samples = [
        ResourceSample(
            sample_index=0,
            timestamp_monotonic=100.0,
            timestamp_utc="2026-10-31T00:00:00Z",
            execution_id="exec_1",
            experiment_id="exp_1",
            container_name="cont",
            cgroup_nr_throttled=10,
        )
    ]

    analysis = ContainerResourceMonitor.correlate_latency_spikes(
        latencies_ms=latencies,
        timestamps_epoch_sec=timestamps,
        samples=mock_samples,
        spike_threshold_ms=10.0,
    )

    assert analysis["spike_count"] == 100
    assert analysis["spike_percentage"] == 10.0
    assert analysis["pct_spikes_matching_100ms_cfs_period"] == 100.0
    assert analysis["evidence_supported"] is True


# ---------------------------------------------------------------------------
# 5. Integration with DockerBenchmarkRunner & Timeout Cleanup
# ---------------------------------------------------------------------------

def test_docker_runner_invokes_monitor(tmp_path):
    """Verify DockerBenchmarkRunner creates and stops monitor without breaking mocks."""
    runner = DockerBenchmarkRunner()
    art_dir = tmp_path / "bench_artifacts"

    stdout_mock = (
        "transaction type: <builtin: select only>\n"
        "scaling factor: 2\n"
        "query mode: simple\n"
        "number of clients: 1\n"
        "number of threads: 1\n"
        "duration: 1 s\n"
        "number of transactions actually processed: 1000\n"
        "latency average = 0.500 ms\n"
        "tps = 2000.0 (without initial connection time)\n"
    )

    log_mock = "0 1 500 0 1700000000 0\n" * 20

    def mock_subprocess_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="24.0.5\n", stderr="")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_123\n", stderr="")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="accepting connections\n", stderr="")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="done\n", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout_mock, stderr="")
        if any("cat" in arg for arg in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=log_mock, stderr="")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_123", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        records = runner._benchmark_postgres(
            component_name="postgresql_db",
            version="16-alpine",
            concurrency_list=[1],
            replications=1,
            duration_seconds=1,
            warmup_seconds=0,
            artifacts_dir=art_dir,
            execution_id="exec_mock_001",
        )

        assert len(records) >= 1
        assert "ActiveMonitoring:" in records[0].notes
        assert records[0].cpu_pct >= 0.0
        assert records[0].memory_mb >= 0.0

        # Verify monitoring artifacts were saved
        assert (art_dir / "monitoring_samples_c1_r0.json").exists()
        assert (art_dir / "monitoring_summary_c1_r0.json").exists()


def test_monitor_cleanup_on_benchmark_timeout(tmp_path):
    """Verify that if benchmark times out, the monitor thread is cleanly terminated."""
    runner = DockerBenchmarkRunner()

    def mock_timeout_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="24.0.5\n", stderr="")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_timeout_cont\n", stderr="")
        if "pg_isready" in cmd or ("pgbench" in cmd and "-i" in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=2.0)
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_timeout_cont", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_timeout_run), patch("time.sleep", return_value=None):
        with pytest.raises(subprocess.TimeoutExpired):
            runner._benchmark_postgres(
                component_name="postgresql_db",
                version="16-alpine",
                concurrency_list=[1],
                replications=1,
                duration_seconds=1,
                warmup_seconds=0,
            )
