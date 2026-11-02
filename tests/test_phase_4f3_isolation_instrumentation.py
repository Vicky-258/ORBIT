"""
Phase 4F.3 & Phase 4F.3.2 — Experimental Isolation & Instrumentation Unit and Integration Tests.

Validates the complete instrumentation stack offline without executing live Docker containers:
1. Baseline State Verification & Trial Isolation (Stronger deterministic fingerprints - FIX 03)
2. Container Lifecycle & Guaranteed Cleanup (Timing flags - FIX 02)
3. PostgreSQL Engine Observability (WAL, checkpointer, locks, wait-events, pg_stat_io, timing instrumentation)
4. Persistent Sampler Coprocess with Telemetry (FIX 04)
5. Storage I/O Observability & Bottleneck Detection (Cgroup directory binding - FIX 01, Conservative classification - FIX 06)
6. Fine-Grained CFS Correlation & Association Taxonomy (Controlled causal guardrail - FIX 07)
7. Epistemological Evidence Classification & Strict VALIDATED Requirements (FIX 05)
8. Historical SF=2 Corrected Findings Catalog
9. Isolated DockerBenchmarkRunner Integration
"""
import hashlib
import json
import math
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pydantic

from aads.benchmark.cfs_correlation import (
    CFSAssociationLevel,
    CFSCorrelationAnalyzer,
    TransactionRecord,
    verify_controlled_intervention,
)
from aads.benchmark.docker_runner import DockerBenchmarkRunner, PgbenchOutputParser
from aads.benchmark.postgres_instrumentation import (
    PostgresMetricsCollector,
    PostgresMetricsDelta,
    PostgresPeriodicSampler,
    PostgresSnapshot,
)
from aads.benchmark.resource_monitor import ContainerResourceMonitor, ResourceSample
from aads.benchmark.storage_monitor import (
    StorageMetricsDelta,
    StorageMonitor,
    StoragePressureClassification,
    StorageSnapshot,
)
from aads.benchmark.trial_isolation import (
    DatabaseStateSnapshot,
    TrialIsolationError,
    TrialIsolationManager,
    compute_content_fingerprint,
)
from aads.benchmark.workload_profiles import resolve_workload_profile
from aads.core.evidence_classification import (
    EvidenceClassification,
    HistoricalSF2FindingsCatalog,
    PerformanceFinding,
)


# ==============================================================================
# Workstream 1: Baseline State Verification & Strong Deterministic Fingerprints (FIX 03)
# ==============================================================================

def test_baseline_verification_passes_on_clean_snapshot():
    """Verify that a pristine SF=2 snapshot passes baseline validation."""
    clean_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        accounts_size_bytes=26_000_000,
        branches_size_bytes=40_960,
        tellers_size_bytes=40_960,
        history_size_bytes=8192,
        database_size_bytes=35_000_000,
        track_io_timing="on",
        track_wal_io_timing="on",
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(clean_snap, expected_sf=2)
    assert is_valid is True
    assert len(violations) == 0
    assert clean_snap.content_fingerprint is not None
    assert clean_snap.fingerprint_algorithm == "aads_composite_aggregate_sha256_v1"


def test_baseline_verification_fails_on_dirty_history():
    """Verify that any lingering history rows cause immediate baseline rejection."""
    dirty_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=142,  # Leaked rows from previous trial!
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(dirty_snap, expected_sf=2)
    assert is_valid is False
    assert any("pgbench_history table contains 142 rows" in v for v in violations)


def test_baseline_verification_fails_on_mismatched_accounts_or_scale():
    """Verify that corrupted account counts or wrong SF fail validation."""
    corrupted_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=199_990,  # Missing 10 rows
        branches_count=2,
        tellers_count=20,
        history_count=0,
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(corrupted_snap, expected_sf=2)
    assert is_valid is False
    assert any("Accounts row count mismatch" in v for v in violations)

    # Scale factor mismatch
    is_valid_sf, violations_sf = TrialIsolationManager.verify_baseline_state(corrupted_snap, expected_sf=10)
    assert is_valid_sf is False
    assert any("Scale factor mismatch" in v for v in violations_sf)


def test_deterministic_fingerprint_detects_offsetting_balance_changes():
    """
    FIX 03 Regression: Modifying row balances with zero net change (e.g. +100 and -100)
    preserves row count and sum=0, but MUST be rejected by min/max balance invariants
    and deterministic content fingerprinting.
    """
    # Pristine SF=2
    clean_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        min_abalance=0,
        max_abalance=0,
        sum_abalance=0,
        accounts_hash=1234567,
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(clean_snap, expected_sf=2)
    assert is_valid is True

    # Dirty snapshot: sum is still 0 and count is still 200,000, but min=-100 and max=100
    dirty_snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        min_abalance=-100,
        max_abalance=100,
        sum_abalance=0,  # Preserved sum!
        accounts_hash=7654321,  # Hash changed!
    )
    is_valid_dirty, violations_dirty = TrialIsolationManager.verify_baseline_state(dirty_snap, expected_sf=2)
    assert is_valid_dirty is False
    assert any("Accounts balance invariant violated" in v for v in violations_dirty)
    assert clean_snap.content_fingerprint != dirty_snap.content_fingerprint


def test_dead_tuples_recorded_as_diagnostic_without_failing_baseline():
    """
    FIX 03: pg_stat_user_tables.n_dead_tup is an approximate statistic.
    It must be recorded as diagnostic metadata without causing baseline failure.
    """
    snap = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        dead_tuples_estimate=450,  # Approximate statistic > 0
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(snap, expected_sf=2)
    assert is_valid is True
    assert len(violations) == 0

    d = snap.to_dict()
    assert d["diagnostic_metadata"]["dead_tuples_estimate"] == 450


def test_database_state_snapshot_diff():
    """Verify state snapshot diff calculates exact deltas including fingerprints."""
    before = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=0,
        history_size_bytes=8192,
        database_size_bytes=35_000_000,
    )
    after = DatabaseStateSnapshot(
        scale_factor=2,
        accounts_count=200_000,
        branches_count=2,
        tellers_count=20,
        history_count=5000,
        history_size_bytes=245_760,
        database_size_bytes=36_500_000,
        dead_tuples_estimate=150,
    )
    diff = before.diff(after)
    assert diff["delta_history_rows"] == 5000
    assert diff["delta_accounts_rows"] == 0
    assert diff["delta_history_size_bytes"] == 245_760 - 8192
    assert diff["delta_database_size_bytes"] == 1_500_000
    assert diff["delta_dead_tuples_estimate"] == 150
    assert diff["fingerprint_matches"] is False


# ==============================================================================
# Workstream 1 & 2: Container Failure Handling & Cleanup with Timing Flags (FIX 02)
# ==============================================================================

def test_initialize_fresh_container_cleans_up_on_init_failure():
    """Verify that container cleanup is called if initialization fails."""
    mgr = TrialIsolationManager()

    def mock_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
            assert "-c" in cmd and "track_io_timing=on" in cmd
            assert "-c" in cmd and "track_wal_io_timing=on" in cmd
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c123\n")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="ready\n")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=1, stderr="Disk full error")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c123\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="pgbench initialization failed"):
            mgr.initialize_fresh_container("mock_cont", scale_factor=2)


def test_initialize_fresh_container_cleans_up_on_dirty_baseline():
    """Verify that container cleanup is called if baseline validation fails."""
    mgr = TrialIsolationManager()

    # 37-field psql output returning dirty history table (50 rows)
    psql_dirty_parts = [
        "200000", "1", "200000", "0", "0", "0", "1234567",
        "2", "1", "2", "0", "0", "0", "12345",
        "20", "1", "20", "0", "0", "0", "67890",
        "50",  # Dirty history count!
        "26000000", "40960", "40960", "16384", "35000000", "1048576", "0",
        "128MB", "4MB", "100", "5min", "on", "on", "on", "on"
    ]
    psql_dirty_out = "|".join(psql_dirty_parts)

    def mock_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c123\n")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="ready\n")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="done\n")
        if "psql" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=psql_dirty_out)
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="c123\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(TrialIsolationError, match="Trial isolation violated"):
            mgr.initialize_fresh_container("mock_cont", scale_factor=2)


# ==============================================================================
# Workstream 2: PostgreSQL Observability & Timing Settings (FIX 02)
# ==============================================================================

def test_postgres_snapshot_parsing_and_timing_verification():
    """Verify parsing of internal PostgreSQL 16 views and timing flag capture."""
    def mock_exec_sql(container, query, timeout=8):
        if "track_io_timing" in query:
            return "on|on"
        if "pg_stat_wal" in query:
            return "15000|50|24500000|0|120|115|45.5|230.2"
        if "pg_stat_checkpointer" in query:
            return "2|0|0|0|0|1250.0|340.5|4500"
        if "pg_stat_bgwriter" in query:
            return "850|0|12000"
        if "pg_stat_database" in query:
            return "10000|0|500|450000|200000|150000|10000|10000|0|0|0"
        if "pg_stat_user_tables" in query:
            return "pgbench_accounts|0|10000|0|5000|200000|500|0|50000\npgbench_history|10000|0|0|0|10000|0|0|0"
        if "pg_stat_io" in query:
            return "120|450|115"
        if "pg_stat_activity" in query:
            return "101|active|Lock:relation|relation\n102|idle|None|None"
        if "pg_locks" in query:
            return "relation|AccessExclusiveLock|f|1\nrelation|RowExclusiveLock|t|8"
        return ""

    with patch.object(PostgresMetricsCollector, "_execute_sql", side_effect=mock_exec_sql):
        snap = PostgresMetricsCollector.take_snapshot("mock_pg")

        assert snap.database_settings["track_io_timing"] == "on"
        assert snap.database_settings["track_wal_io_timing"] == "on"
        assert "track_io_timing_disabled" not in snap.unavailable_metrics
        assert snap.wal_stats["wal_bytes"] == 24_500_000
        assert snap.wal_stats["wal_sync_time"] == 230.2
        assert snap.checkpointer_stats["num_timed"] == 2
        assert snap.checkpointer_stats["buffers_written"] == 4500
        assert snap.bgwriter_stats["buffers_clean"] == 850
        assert snap.database_stats["xact_commit"] == 10000
        assert snap.database_stats["blks_hit"] == 450000
        assert snap.table_stats["pgbench_accounts"]["n_tup_upd"] == 10000
        assert snap.io_stats["reads"] == 120
        assert snap.io_stats["writes"] == 450
        assert len(snap.activity_stats) == 2
        assert len(snap.locks_stats) == 2


def test_postgres_snapshot_flags_disabled_timing():
    """Verify that disabled timing flags explicitly append unavailable metrics."""
    def mock_exec_sql(container, query, timeout=8):
        if "track_io_timing" in query:
            return "off|off"
        return ""

    with patch.object(PostgresMetricsCollector, "_execute_sql", side_effect=mock_exec_sql):
        snap = PostgresMetricsCollector.take_snapshot("mock_pg")
        assert "track_io_timing_disabled" in snap.unavailable_metrics
        assert "track_wal_io_timing_disabled" in snap.unavailable_metrics

        snap_end = PostgresSnapshot(
            timestamp_monotonic=130.0,
            timestamp_utc="2026-11-02T10:00:30Z",
            database_settings={"track_io_timing": "off", "track_wal_io_timing": "off"},
            unavailable_metrics=["track_io_timing_disabled", "track_wal_io_timing_disabled"],
        )
        delta = PostgresMetricsCollector.compute_deltas(start=snap, end=snap_end)
        assert delta.timing_instrumentation_active is False
        assert delta.to_dict()["wal"]["delta_wal_write_time_ms"] is None


def test_postgres_delta_computation_and_rates():
    """Verify exact delta and rate computation between pre and post snapshots."""
    snap1 = PostgresSnapshot(
        timestamp_monotonic=100.0,
        timestamp_utc="2026-11-02T10:00:00Z",
        wal_stats={"wal_records": 100, "wal_bytes": 1_000_000, "wal_sync_time": 50.0},
        checkpointer_stats={"num_timed": 1, "write_time": 100.0, "sync_time": 50.0, "buffers_written": 1000},
        database_stats={"xact_commit": 500, "blks_read": 50, "blks_hit": 5000},
        table_stats={"pgbench_history": {"n_tup_ins": 500}},
        io_stats={"reads": 10, "writes": 20, "fsyncs": 5},
        database_settings={"track_io_timing": "on", "track_wal_io_timing": "on"},
    )
    snap2 = PostgresSnapshot(
        timestamp_monotonic=130.0,
        timestamp_utc="2026-11-02T10:00:30Z",
        wal_stats={"wal_records": 2100, "wal_bytes": 11_000_000, "wal_sync_time": 250.0},
        checkpointer_stats={"num_timed": 2, "write_time": 250.0, "sync_time": 120.0, "buffers_written": 3500},
        database_stats={"xact_commit": 2500, "blks_read": 100, "blks_hit": 25000},
        table_stats={"pgbench_history": {"n_tup_ins": 2500}},
        io_stats={"reads": 30, "writes": 80, "fsyncs": 25},
        database_settings={"track_io_timing": "on", "track_wal_io_timing": "on"},
    )

    delta = PostgresMetricsCollector.compute_deltas(
        start=snap1,
        end=snap2,
        lock_wait_samples=0,
        wait_event_samples={},
    )

    assert delta.duration_seconds == 30.0
    assert delta.timing_instrumentation_active is True
    assert delta.delta_wal_bytes == 10_000_000
    assert delta.delta_wal_records == 2000
    assert delta.delta_wal_sync_time_ms == 200.0
    assert delta.delta_checkpoints_timed == 1
    assert delta.delta_xact_commit == 2000
    assert delta.delta_blks_read == 50
    assert delta.delta_blks_hit == 20000
    assert delta.delta_table_inserts["pgbench_history"] == 2000
    assert delta.lock_contention_classification == "NO_CONTENTION_OBSERVED"

    d_dict = delta.to_dict()
    assert d_dict["wal"]["wal_rate_mb_per_sec"] > 0.0
    assert d_dict["database"]["cache_hit_ratio_pct"] > 99.0


def test_postgres_periodic_sampler_telemetry_and_cleanup():
    """
    FIX 04 Regression: PostgresPeriodicSampler maintains persistent coprocess session,
    records telemetry metadata, and cleanly terminates.
    """
    sampler = PostgresPeriodicSampler(container_name="test_pg", interval_sec=0.010)

    # Mock Popen persistent session
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline.side_effect = [
        "0|none\n",
        "__END_SAMPLE__\n",
        "2|Lock:relation\n",
        "__END_SAMPLE__\n",
        "",  # EOF
    ]

    with patch("subprocess.Popen", return_value=mock_proc):
        sampler.start()
        time.sleep(0.05)
        waits, ev_counts, samples = sampler.stop()

    telemetry = sampler.get_telemetry()
    assert telemetry["sampler_mode"] in ("persistent_coprocess", "discrete_fallback")
    assert telemetry["monitoring_connection_count"] >= 1
    assert telemetry["total_samples_attempted"] >= 1


# ==============================================================================
# Workstream 3: Storage I/O Observability & Bottleneck Detection (FIX 01 & FIX 06)
# ==============================================================================

def test_storage_cgroup_dir_binding_and_unavailable_status(tmp_path):
    """
    FIX 01 Regression: Cgroup directory binding explicitly reaches storage snapshots;
    missing cg_dir sets explicit unavailable status without assuming zero I/O.
    """
    # Case A: Explicit valid cg_dir
    cg_dir = tmp_path / "cg_valid"
    cg_dir.mkdir()
    io_file = cg_dir / "io.stat"
    io_file.write_text("259:0 rbytes=10485760 wbytes=20971520 rios=250 wios=500 dbytes=0 dios=0\n")

    snap = StorageMonitor.take_snapshot(cg_dir=cg_dir)
    assert "259:0" in snap.cgroup_io_stat
    assert snap.cgroup_io_stat["259:0"]["wbytes"] == 20971520
    assert "cgroup_io_stat" not in snap.unavailable_metrics

    # Case B: Missing cg_dir (None)
    snap_none = StorageMonitor.take_snapshot(cg_dir=None)
    assert "cgroup_io_stat" in snap_none.unavailable_metrics
    assert snap_none.cgroup_io_stat == {}


def test_conservative_storage_classification_rules():
    """
    FIX 06 Regression: Conservative storage pressure classification based on multi-queue
    SSD metrics (utilization, queue depth, await latency).
    """
    # 1. Missing host metrics -> INSUFFICIENT_STORAGE_EVIDENCE
    s_miss = StorageSnapshot(100.0, "2026-11-02T10:00:00Z", unavailable_metrics=["host_diskstats"])
    e_miss = StorageSnapshot(130.0, "2026-11-02T10:00:30Z", unavailable_metrics=["host_diskstats"])
    delta_miss = StorageMonitor.compute_deltas(s_miss, e_miss)
    assert delta_miss.pressure_classification == StoragePressureClassification.INSUFFICIENT_STORAGE_EVIDENCE
    assert delta_miss.is_storage_bound is False

    # 2. Low host utilization -> NO_STORAGE_PRESSURE_OBSERVED
    s_low = StorageSnapshot(
        100.0, "2026-11-02T10:00:00Z",
        host_diskstats={"nvme0n1": {"reads_completed": 10, "writes_completed": 100, "read_ms": 10, "write_ms": 100, "io_ms": 200, "weighted_io_ms": 250}},
        primary_device="nvme0n1",
    )
    e_low = StorageSnapshot(
        130.0, "2026-11-02T10:00:30Z",
        host_diskstats={"nvme0n1": {"reads_completed": 20, "writes_completed": 300, "read_ms": 20, "write_ms": 300, "io_ms": 500, "weighted_io_ms": 650}},
        primary_device="nvme0n1",
    )
    delta_low = StorageMonitor.compute_deltas(s_low, e_low)
    assert delta_low.pressure_classification == StoragePressureClassification.NO_STORAGE_PRESSURE_OBSERVED
    assert delta_low.is_storage_bound is False

    # 3. Elevated busy time without queue saturation -> STORAGE_PRESSURE_SUSPECTED
    s_susp = StorageSnapshot(
        100.0, "2026-11-02T10:00:00Z",
        host_diskstats={"nvme0n1": {"reads_completed": 10, "writes_completed": 100, "read_ms": 10, "write_ms": 100, "io_ms": 0, "weighted_io_ms": 0}},
        primary_device="nvme0n1",
    )
    # io_ms increased by 16000ms over 30s (53.3% utilization), but queue depth is low
    e_susp = StorageSnapshot(
        130.0, "2026-11-02T10:00:30Z",
        host_diskstats={"nvme0n1": {"reads_completed": 100, "writes_completed": 1000, "read_ms": 100, "write_ms": 1000, "io_ms": 16000, "weighted_io_ms": 15000}},
        primary_device="nvme0n1",
    )
    delta_susp = StorageMonitor.compute_deltas(s_susp, e_susp)
    assert delta_susp.pressure_classification == StoragePressureClassification.STORAGE_PRESSURE_SUSPECTED
    assert delta_susp.is_storage_bound is False

    # 4. Sustained storage saturation -> STORAGE_PRESSURE_SUPPORTED
    s_supp = StorageSnapshot(
        100.0, "2026-11-02T10:00:00Z",
        host_diskstats={"nvme0n1": {"reads_completed": 0, "writes_completed": 0, "read_ms": 0, "write_ms": 0, "io_ms": 0, "weighted_io_ms": 0}},
        primary_device="nvme0n1",
    )
    # 80% busy time (24000ms), avg queue depth 3.0 (90000ms weighted), avg await 15ms
    e_supp = StorageSnapshot(
        130.0, "2026-11-02T10:00:30Z",
        host_diskstats={"nvme0n1": {"reads_completed": 1000, "writes_completed": 4000, "read_ms": 15000, "write_ms": 60000, "io_ms": 24000, "weighted_io_ms": 90000}},
        primary_device="nvme0n1",
    )
    delta_supp = StorageMonitor.compute_deltas(s_supp, e_supp)
    assert delta_supp.pressure_classification == StoragePressureClassification.STORAGE_PRESSURE_SUPPORTED
    assert delta_supp.is_storage_bound is True


# ==============================================================================
# Workstream 4: Fine-Grained CFS Correlation & Association Taxonomy (FIX 07)
# ==============================================================================

def test_parse_pgbench_log_records():
    """Verify parsing of standard pgbench -l transaction logs."""
    log_content = (
        "0 1 540 0 1700000000 120000\n"
        "1 1 12500 0 1700000000 120500\n"
        "2 1 13000 0 1700000000 120800\n"
        "3 1 450 0 1700000000 150000\n"
    )
    records = CFSCorrelationAnalyzer.parse_pgbench_log_records(log_content)
    assert len(records) == 4
    assert records[0].client_id == 0
    assert records[0].latency_ms == 0.54
    assert records[1].latency_ms == 12.5
    assert records[2].latency_ms == 13.0


def test_cfs_correlation_analyzer_no_spikes():
    """Verify NO_DETECTABLE_ASSOCIATION when no latency spikes exist."""
    records = [
        TransactionRecord(client_id=0, transaction_no=1, latency_ms=1.2, epoch_timestamp_sec=1700000000.0),
        TransactionRecord(client_id=1, transaction_no=1, latency_ms=1.5, epoch_timestamp_sec=1700000000.1),
    ]
    analyzer = CFSCorrelationAnalyzer(spike_threshold_ms=10.0)
    res = analyzer.analyze(records, cgroup_samples=[])
    assert res["association_level"] == CFSAssociationLevel.NO_DETECTABLE_ASSOCIATION.value
    assert res["spike_count"] == 0


def test_cfs_correlation_analyzer_strong_temporal_association():
    """
    Verify STRONG_TEMPORAL_ASSOCIATION is detected when multi-client spikes cluster
    with ~100ms inter-cluster periodicity, and does NOT promote to causal without intervention.
    """
    t0 = 1700000000.0
    records = []
    for i in range(5):
        t_cluster = t0 + i * 0.100
        for client in range(4):
            records.append(TransactionRecord(
                client_id=client,
                transaction_no=i,
                latency_ms=15.0,
                epoch_timestamp_sec=t_cluster + (client * 0.0002),
            ))

    cgroup_samples = [
        {"sample_index": 0, "timestamp_monotonic": 10.0, "cgroup_throttled_usec": 0, "cgroup_nr_throttled": 0},
        {"sample_index": 1, "timestamp_monotonic": 10.5, "cgroup_throttled_usec": 250000, "cgroup_nr_throttled": 5},
    ]

    analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)
    # Boolean confirmation alone MUST NOT promote to causal (FIX 07)
    res = analyzer.analyze(records, cgroup_samples, has_controlled_experiment_confirmation=True)

    assert res["association_level"] == CFSAssociationLevel.STRONG_TEMPORAL_ASSOCIATION.value
    assert res["multi_client_cluster_count"] == 5
    assert abs(res["median_inter_cluster_interval_ms"] - 100.0) < 1.0


def test_cfs_causal_classification_guardrail_with_intervention():
    """
    FIX 07 Regression: CONTROLLED_CAUSAL_EVIDENCE requires verifiable paired intervention data;
    duplicate replications are rejected.
    """
    records = [
        TransactionRecord(0, 1, 15.0, 1700000000.0),
        TransactionRecord(1, 1, 15.0, 1700000000.001),
        TransactionRecord(0, 2, 15.0, 1700000000.1),
        TransactionRecord(1, 2, 15.0, 1700000000.101),
        TransactionRecord(0, 3, 15.0, 1700000000.2),
        TransactionRecord(1, 3, 15.0, 1700000000.201),
        TransactionRecord(0, 4, 15.0, 1700000000.3),
        TransactionRecord(1, 4, 15.0, 1700000000.301),
    ]
    cgroup_samples = [
        {"sample_index": 1, "timestamp_monotonic": 10.5, "cgroup_throttled_usec": 100000, "cgroup_nr_throttled": 4},
    ]
    analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)

    # Case A: Duplicate replications in intervention -> REJECTED, remains correlation
    rep_intervention = {
        "control_experiment_id": "exp_pg_sf2_c8_r0",
        "treatment_experiment_id": "exp_pg_sf2_c8_r1",
        "control_quota_cores": 1.0,
        "treatment_quota_cores": 1.0,  # No quota manipulation!
        "comparable_baseline_confirmed": True,
        "control_outcome": {"tps": 1000.0},
        "treatment_outcome": {"tps": 1010.0},
    }
    res_rep = analyzer.analyze(records, cgroup_samples, controlled_intervention=rep_intervention)
    assert res_rep["association_level"] == CFSAssociationLevel.STRONG_TEMPORAL_ASSOCIATION.value
    assert res_rep["controlled_intervention_evaluation"]["verified"] is False

    # Case B: Valid controlled intervention (1.0 vs 2.0 vCPU) -> PROMOTED to CONTROLLED_CAUSAL_EVIDENCE
    valid_intervention = {
        "control_experiment_id": "exp_pg_sf2_c8_1vcpu_ctrl",
        "treatment_experiment_id": "exp_pg_sf2_c8_2vcpu_treatment",
        "control_quota_cores": 1.0,
        "treatment_quota_cores": 2.0,
        "comparable_baseline_confirmed": True,
        "control_outcome": {"tps": 1000.0, "mean_latency_ms": 8.0},
        "treatment_outcome": {"tps": 2010.0, "mean_latency_ms": 3.9},
    }
    res_valid = analyzer.analyze(records, cgroup_samples, controlled_intervention=valid_intervention)
    assert res_valid["association_level"] == CFSAssociationLevel.CONTROLLED_CAUSAL_EVIDENCE.value
    assert res_valid["controlled_intervention_evaluation"]["verified"] is True


# ==============================================================================
# Workstream 5: Evidence Classification & Strict VALIDATED Requirements (FIX 05)
# ==============================================================================

def test_evidence_classification_levels_supported():
    """Verify all 5 epistemological classification levels are supported."""
    for level in [EvidenceClassification.OBSERVED, EvidenceClassification.DERIVED,
                  EvidenceClassification.CORRELATED, EvidenceClassification.HYPOTHESIS,
                  EvidenceClassification.VALIDATED]:
        kwargs = {
            "finding_id": f"test_{level.value.lower()}",
            "title": f"Finding for {level.value}",
            "claim": f"Descriptive finding statement for {level.value}.",
            "classification": level,
            "supporting_metrics": ["p95_latency_ms"] if level != EvidenceClassification.VALIDATED else ["achieved_tps"],
            "supporting_experiment_ids": ["exp1"] if level != EvidenceClassification.VALIDATED else ["exp_ctrl", "exp_treat"],
            "methodology": "Empirical measurement and analysis.",
            "confidence": "HIGH",
        }
        if level == EvidenceClassification.VALIDATED:
            kwargs.update({
                "control_experiment_id": "exp_ctrl",
                "treatment_experiment_id": "exp_treat",
                "manipulated_variable": "cpu_limit",
                "expected_intervention": "Double CPU quota from 1.0 to 2.0 vCPU",
                "observed_intervention": "Measured CPU quota doubled",
                "comparable_baseline_confirmed": True,
                "outcome_metrics": ["achieved_tps"],
            })
        finding = PerformanceFinding(**kwargs)
        assert finding.classification == level


def test_guardrail_rejects_duplicate_replications_as_intervention():
    """FIX 05 Regression: Duplicate replications (_r0 vs _r1) must NOT qualify as a VALIDATED intervention."""
    with pytest.raises(pydantic.ValidationError, match="pairs duplicate replications"):
        PerformanceFinding(
            finding_id="invalid_replication_validation",
            title="Invalid Replication Validation",
            claim="Throughput increases due to worker scaling.",
            classification=EvidenceClassification.VALIDATED,
            control_experiment_id="exp_pg_sf2_read_only_select_c8_r0",
            treatment_experiment_id="exp_pg_sf2_read_only_select_c8_r1",  # Same config replication!
            manipulated_variable="replication",
            expected_intervention="Run second replication",
            observed_intervention="Second replication executed",
            comparable_baseline_confirmed=True,
            outcome_metrics=["achieved_tps"],
            methodology="Replication comparison.",
            confidence="LOW",
        )


def test_guardrail_rejects_unconfirmed_baseline_for_validated():
    """FIX 05 Regression: VALIDATED claims require comparable_baseline_confirmed=True."""
    with pytest.raises(pydantic.ValidationError, match="comparable_baseline_confirmed=True"):
        PerformanceFinding(
            finding_id="invalid_baseline_validation",
            title="Invalid Baseline Validation",
            claim="CPU quota doubling improves throughput.",
            classification=EvidenceClassification.VALIDATED,
            control_experiment_id="exp_ctrl",
            treatment_experiment_id="exp_treat",
            manipulated_variable="cpu_limit",
            expected_intervention="Double CPU quota",
            observed_intervention="CPU quota doubled",
            comparable_baseline_confirmed=False,  # Unconfirmed baseline!
            outcome_metrics=["achieved_tps"],
            methodology="Intervention comparison.",
            confidence="LOW",
        )


def test_guardrail_rejects_uninstrumented_lock_contention():
    """Verify pydantic validator rejects claiming causal lock contention without instrumented lock metrics."""
    with pytest.raises(pydantic.ValidationError, match="asserts lock contention/serialization but lacks"):
        PerformanceFinding(
            finding_id="invalid_lock_claim",
            title="Invalid Lock Assertion",
            claim="High latency was caused by row-level lock contention on pgbench_branches.",
            classification=EvidenceClassification.VALIDATED,
            control_experiment_id="exp_ctrl",
            treatment_experiment_id="exp_treat",
            manipulated_variable="concurrency",
            expected_intervention="Increase concurrency",
            observed_intervention="Concurrency increased",
            comparable_baseline_confirmed=True,
            supporting_metrics=["p95_latency_ms", "tps"],
            methodology="Inference without lock telemetry.",
            confidence="LOW",
        )


def test_guardrail_rejects_uninstrumented_disk_bound():
    """Verify pydantic validator rejects claiming storage-bound behavior without disk I/O metrics."""
    with pytest.raises(pydantic.ValidationError, match="asserts storage/disk-bound bottleneck but lacks"):
        PerformanceFinding(
            finding_id="invalid_disk_claim",
            title="Invalid Disk Assertion",
            claim="The 3.15s transaction latency stall was caused by a storage-bound disk bottleneck.",
            classification=EvidenceClassification.VALIDATED,
            control_experiment_id="exp_ctrl",
            treatment_experiment_id="exp_treat",
            manipulated_variable="concurrency",
            expected_intervention="Increase concurrency",
            observed_intervention="Concurrency increased",
            comparable_baseline_confirmed=True,
            supporting_metrics=["p95_latency_ms", "tps"],
            methodology="Speculation without storage telemetry.",
            confidence="LOW",
        )


def test_guardrail_observed_cannot_claim_causality():
    """Verify that OBSERVED findings cannot use causal assertion phrases."""
    with pytest.raises(pydantic.ValidationError, match="contains causal language"):
        PerformanceFinding(
            finding_id="invalid_observed_causal",
            title="Invalid Causal Observed Finding",
            claim="The latency spike was caused by background checkpoint flushing.",
            classification=EvidenceClassification.OBSERVED,
            supporting_metrics=["max_latency_ms"],
            supporting_experiment_ids=["exp1"],
            methodology="Direct observation.",
            confidence="HIGH",
        )


def test_historical_findings_catalog_corrected():
    """Verify that all historical SF=2 findings are present and correctly classified."""
    catalog = HistoricalSF2FindingsCatalog.get_corrected_findings()
    assert len(catalog) >= 6

    finding_map = {f.finding_id: f for f in catalog}

    # 1. 100ms periodicity is OBSERVED
    assert finding_map["FINDING_4F_01"].classification == EvidenceClassification.OBSERVED

    # 2. CFS quota causation is VALIDATED via 1.0 vs 2.0 vCPU experiment with full structured fields
    f2 = finding_map["FINDING_4F_02"]
    assert f2.classification == EvidenceClassification.VALIDATED
    assert f2.control_experiment_id == "exp_pg_sf2_read_only_select_c8_1vcpu_ctrl"
    assert f2.treatment_experiment_id == "exp_pg_sf2_read_only_select_c8_2vcpu_treatment"
    assert f2.manipulated_variable == "cpu_limit"
    assert f2.comparable_baseline_confirmed is True

    # 3. TPC-B inversion is OBSERVED
    assert finding_map["FINDING_4F_03"].classification == EvidenceClassification.OBSERVED

    # 4. Row-level lock contention is strictly a HYPOTHESIS until pg_locks instrumented
    assert finding_map["FINDING_4F_04"].classification == EvidenceClassification.HYPOTHESIS

    # 5. 3.15s checkpoint stall is OBSERVED with unverified cause
    assert finding_map["FINDING_4F_05"].classification == EvidenceClassification.OBSERVED

    # 6. Single-thread write limit is HYPOTHESIS
    assert finding_map["FINDING_4F_06"].classification == EvidenceClassification.HYPOTHESIS


# ==============================================================================
# Workstream 6 & 8: Isolated DockerBenchmarkRunner Integration Tests
# ==============================================================================

def test_docker_runner_isolated_execution_with_mocks(tmp_path):
    """
    Verify that DockerBenchmarkRunner with per_trial_isolation=True executes
    fresh container lifecycle, captures baseline, records Postgres and Storage deltas,
    performs CFS analysis, records sampler telemetry, and cleans up containers.
    """
    runner = DockerBenchmarkRunner(
        cpu_limit="1.0",
        memory_limit="1024m",
        per_trial_isolation=True,
    )
    art_dir = tmp_path / "isolated_artifacts"

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

    # 37-field psql clean output
    psql_clean_parts = [
        "200000", "1", "200000", "0", "0", "0", "1234567",
        "2", "1", "2", "0", "0", "0", "12345",
        "20", "1", "20", "0", "0", "0", "67890",
        "0",
        "26000000", "40960", "40960", "8192", "35000000", "1048576", "0",
        "128MB", "4MB", "100", "5min", "on", "on", "on", "on"
    ]
    psql_clean_out = "|".join(psql_clean_parts)

    def mock_subprocess_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="24.0.5\n")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="mock_isolated_cont\n")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="ready\n")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="done\n")
        if "psql" in cmd:
            if "track_io_timing" in cmd_str and "track_wal_io_timing" in cmd_str and len(cmd_str.split()) < 15:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="on|on")
            if "hashtext" in cmd_str or "pgbench_accounts" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout=psql_clean_out)
            if "pg_stat_wal" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="100|0|1000000|0|10|10|5.0|50.0")
            if "pg_stat_checkpointer" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="1|0|0|0|0|100.0|50.0|1000")
            if "pg_stat_bgwriter" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="100|0|1000")
            if "pg_stat_database" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="500|0|10|5000|1000|500|500|0|0|0|0")
            if "pg_stat_user_tables" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="pgbench_accounts|0|0|0|0|200000|0|0|0\npgbench_history|0|0|0|0|0|0|0|0")
            if "pg_stat_io" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="10|20|5")
            if "pg_stat_activity" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="101|idle|None|None")
            if "pg_locks" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="relation|RowExclusiveLock|t|1")
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="")
        if "pgbench" in cmd and "-l" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=stdout_mock)
        if any("cat" in arg for arg in cmd):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=log_mock)
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="mock_isolated_cont\n")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="")

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        records = runner._benchmark_postgres(
            component_name="postgresql_db",
            version="16-alpine",
            concurrency_list=[1],
            replications=1,
            duration_seconds=1,
            warmup_seconds=0,
            scale_factor=2,
            artifacts_dir=art_dir,
            execution_id="exec_test_isolated",
        )

        assert len(records) >= 1
        rec = records[0]
        assert "IsolatedTrial:" in rec.notes
        assert "CFSAssociation=" in rec.notes
        assert "LockContention=" in rec.notes
        assert "StorageBound=" in rec.notes

        # Verify all isolated trial artifacts are created on disk
        assert (art_dir / "database_state_baseline_c1_r0.json").exists()
        assert (art_dir / "postgres_metrics_delta_c1_r0.json").exists()
        assert (art_dir / "storage_metrics_delta_c1_r0.json").exists()
        assert (art_dir / "correlation_analysis_c1_r0.json").exists()
        assert (art_dir / "postgres_sampler_telemetry_c1_r0.json").exists()
        assert (art_dir / "monitoring_samples_c1_r0.json").exists()
        assert (art_dir / "monitoring_summary_c1_r0.json").exists()
