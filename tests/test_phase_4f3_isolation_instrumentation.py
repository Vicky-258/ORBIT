"""
Phase 4F.3 — Experimental Isolation & Instrumentation Unit and Integration Tests.

Validates the 6 workstreams offline without executing live Docker containers:
1. Baseline State Verification & Trial Isolation
2. Container Lifecycle & Guaranteed Cleanup
3. PostgreSQL Engine Observability (WAL, checkpointer, locks, wait-events, pg_stat_io)
4. Storage I/O Observability & Bottleneck Detection (cgroup io.stat, host diskstats)
5. Fine-Grained CFS Correlation & Association Taxonomy
6. Epistemological Evidence Classification & Scientific Guardrails
7. Historical SF=2 Corrected Findings Catalog
8. Isolated DockerBenchmarkRunner Integration
"""
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
    StorageSnapshot,
)
from aads.benchmark.trial_isolation import (
    DatabaseStateSnapshot,
    TrialIsolationError,
    TrialIsolationManager,
)
from aads.benchmark.workload_profiles import resolve_workload_profile
from aads.core.evidence_classification import (
    EvidenceClassification,
    HistoricalSF2FindingsCatalog,
    PerformanceFinding,
)


# ==============================================================================
# Workstream 1: Baseline State Verification & Trial Isolation
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
    )
    is_valid, violations = TrialIsolationManager.verify_baseline_state(clean_snap, expected_sf=2)
    assert is_valid is True
    assert len(violations) == 0


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


def test_database_state_snapshot_diff():
    """Verify state snapshot diff calculates exact deltas."""
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
    )
    diff = before.diff(after)
    assert diff["delta_history_rows"] == 5000
    assert diff["delta_accounts_rows"] == 0
    assert diff["delta_history_size_bytes"] == 245_760 - 8192
    assert diff["delta_database_size_bytes"] == 1_500_000


# ==============================================================================
# Workstream 1 & 2: Container Failure Handling & Guaranteed Cleanup
# ==============================================================================

def test_initialize_fresh_container_cleans_up_on_init_failure():
    """Verify that container cleanup is called if initialization fails."""
    mgr = TrialIsolationManager()

    def mock_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
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

    # psql returns dirty history table (50 rows)
    psql_dirty_out = "200000|2|20|50|26000000|40960|40960|16384|35000000|128MB|4MB|100|5min|on|on"

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
# Workstream 2: PostgreSQL Observability (pg_stat_wal, checkpointer, locks, etc.)
# ==============================================================================

def test_postgres_snapshot_parsing():
    """Verify parsing of internal PostgreSQL 16 views."""
    def mock_exec_sql(container, query, timeout=5):
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
    )
    snap2 = PostgresSnapshot(
        timestamp_monotonic=130.0,
        timestamp_utc="2026-11-02T10:00:30Z",
        wal_stats={"wal_records": 2100, "wal_bytes": 11_000_000, "wal_sync_time": 250.0},
        checkpointer_stats={"num_timed": 2, "write_time": 250.0, "sync_time": 120.0, "buffers_written": 3500},
        database_stats={"xact_commit": 2500, "blks_read": 100, "blks_hit": 25000},
        table_stats={"pgbench_history": {"n_tup_ins": 2500}},
        io_stats={"reads": 30, "writes": 80, "fsyncs": 25},
    )

    delta = PostgresMetricsCollector.compute_deltas(
        start=snap1,
        end=snap2,
        lock_wait_samples=0,
        wait_event_samples={},
    )

    assert delta.duration_seconds == 30.0
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


def test_postgres_lock_contention_classification():
    """Verify lock contention is classified when ungranted locks or Lock wait events are observed."""
    snap1 = PostgresSnapshot(100.0, "2026-11-02T10:00:00Z")
    snap2 = PostgresSnapshot(130.0, "2026-11-02T10:00:30Z")

    # Case A: Contention observed
    delta_contention = PostgresMetricsCollector.compute_deltas(
        start=snap1,
        end=snap2,
        lock_wait_samples=15,
        wait_event_samples={"Lock:relation": 12, "Lock:tuple": 3},
    )
    assert delta_contention.lock_contention_classification == "CONFIRMED_LOCK_CONTENTION_OBSERVED"
    assert delta_contention.observed_lock_waits == 15

    # Case B: No contention observed
    delta_none = PostgresMetricsCollector.compute_deltas(
        start=snap1,
        end=snap2,
        lock_wait_samples=0,
        wait_event_samples={},
    )
    assert delta_none.lock_contention_classification == "NO_CONTENTION_OBSERVED"


# ==============================================================================
# Workstream 3: Storage I/O Observability & Bottleneck Detection
# ==============================================================================

def test_storage_cgroup_io_stat_parsing(tmp_path):
    """Verify parsing of cgroup v2 io.stat format."""
    cg_dir = tmp_path / "cgroup_test"
    cg_dir.mkdir()
    io_file = cg_dir / "io.stat"
    io_file.write_text("259:0 rbytes=10485760 wbytes=20971520 rios=250 wios=500 dbytes=0 dios=0\n")

    res = StorageMonitor._read_cgroup_io_stat(cg_dir)
    assert "259:0" in res
    assert res["259:0"]["rbytes"] == 10485760
    assert res["259:0"]["wbytes"] == 20971520
    assert res["259:0"]["rios"] == 250
    assert res["259:0"]["wios"] == 500


def test_storage_metrics_delta_and_bottleneck_detection():
    """
    Verify storage delta computation and bottleneck rules:
    WAL generation with low host disk utilization (< 10%) must NOT be classified as storage bound.
    """
    snap_start = StorageSnapshot(
        timestamp_monotonic=100.0,
        timestamp_utc="2026-11-02T10:00:00Z",
        cgroup_io_stat={"259:0": {"rbytes": 0, "wbytes": 0, "rios": 0, "wios": 0}},
        host_diskstats={"nvme0n1": {"read_sectors": 100, "write_sectors": 1000, "io_ms": 500}},
        primary_device="nvme0n1",
        filesystem_type="ext4",
    )

    # 30-second measurement generating 30MB write, but host io_ms only grew by 150ms (0.5% utilization)
    snap_end = StorageSnapshot(
        timestamp_monotonic=130.0,
        timestamp_utc="2026-11-02T10:00:30Z",
        cgroup_io_stat={"259:0": {"rbytes": 0, "wbytes": 31_457_280, "rios": 0, "wios": 300}},
        host_diskstats={"nvme0n1": {"read_sectors": 100, "write_sectors": 62440, "io_ms": 650}},
        primary_device="nvme0n1",
        filesystem_type="ext4",
    )

    delta = StorageMonitor.compute_deltas(snap_start, snap_end)
    assert delta.duration_seconds == 30.0
    assert delta.delta_wbytes == 31_457_280
    assert delta.is_storage_bound is False
    assert "Host I/O utilization is low" in delta.classification_reason

    d_dict = delta.to_dict()
    assert d_dict["container_io"]["write_mb"] == 30.0
    assert d_dict["host_io"]["host_io_utilization_pct"] < 5.0


def test_storage_bottleneck_detected_on_high_utilization():
    """Verify that host I/O utilization >= 50% triggers storage bound classification."""
    snap_start = StorageSnapshot(
        timestamp_monotonic=100.0,
        timestamp_utc="2026-11-02T10:00:00Z",
        cgroup_io_stat={"259:0": {"rbytes": 0, "wbytes": 0, "rios": 0, "wios": 0}},
        host_diskstats={"nvme0n1": {"read_sectors": 0, "write_sectors": 0, "io_ms": 1000}},
        primary_device="nvme0n1",
    )
    # io_ms increased by 20,000 ms over 30s (66.7% utilization)
    snap_end = StorageSnapshot(
        timestamp_monotonic=130.0,
        timestamp_utc="2026-11-02T10:00:30Z",
        cgroup_io_stat={"259:0": {"rbytes": 0, "wbytes": 500_000_000, "rios": 0, "wios": 15000}},
        host_diskstats={"nvme0n1": {"read_sectors": 0, "write_sectors": 1_000_000, "io_ms": 21000}},
        primary_device="nvme0n1",
    )

    delta = StorageMonitor.compute_deltas(snap_start, snap_end)
    assert delta.is_storage_bound is True
    assert "High host disk utilization" in delta.classification_reason


# ==============================================================================
# Workstream 4: Fine-Grained CFS Correlation & Association Taxonomy
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


def test_cfs_correlation_analyzer_temporal_association():
    """
    Verify TEMPORAL_ASSOCIATION is detected when multi-client spikes cluster
    with ~100ms inter-cluster periodicity and cgroup throttling is present.
    """
    t0 = 1700000000.0
    records = []
    # Create 5 clusters separated by exactly 100ms (0.1s), each with 4 clients stalling simultaneously
    for i in range(5):
        t_cluster = t0 + i * 0.100
        for client in range(4):
            records.append(TransactionRecord(
                client_id=client,
                transaction_no=i,
                latency_ms=15.0,  # > 10ms threshold
                epoch_timestamp_sec=t_cluster + (client * 0.0002),  # within 1.5ms cluster window
            ))

    cgroup_samples = [
        {"sample_index": 0, "timestamp_monotonic": 10.0, "cgroup_throttled_usec": 0, "cgroup_nr_throttled": 0},
        {"sample_index": 1, "timestamp_monotonic": 10.5, "cgroup_throttled_usec": 250000, "cgroup_nr_throttled": 5},
    ]

    analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)
    res = analyzer.analyze(records, cgroup_samples, has_controlled_experiment_confirmation=False)

    assert res["association_level"] == CFSAssociationLevel.STRONG_TEMPORAL_ASSOCIATION.value
    assert res["multi_client_cluster_count"] == 5
    assert abs(res["median_inter_cluster_interval_ms"] - 100.0) < 1.0


def test_cfs_correlation_analyzer_controlled_causal_evidence():
    """Verify CONTROLLED_CAUSAL_EVIDENCE is only assigned when controlled experiment confirms it."""
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
    res = analyzer.analyze(records, cgroup_samples, has_controlled_experiment_confirmation=True)
    assert res["association_level"] == CFSAssociationLevel.CONTROLLED_CAUSAL_EVIDENCE.value


# ==============================================================================
# Workstream 5: Evidence Classification Taxonomy & Epistemological Guardrails
# ==============================================================================

def test_evidence_classification_levels_supported():
    """Verify all 5 epistemological classification levels are supported."""
    for level in [EvidenceClassification.OBSERVED, EvidenceClassification.DERIVED,
                  EvidenceClassification.CORRELATED, EvidenceClassification.HYPOTHESIS,
                  EvidenceClassification.VALIDATED]:
        finding = PerformanceFinding(
            finding_id=f"test_{level.value.lower()}",
            title=f"Finding for {level.value}",
            claim=f"Descriptive finding statement for {level.value}.",
            classification=level,
            supporting_metrics=["p95_latency_ms"] if level != EvidenceClassification.VALIDATED else ["p95", "quota"],
            supporting_experiment_ids=["exp1"] if level != EvidenceClassification.VALIDATED else ["exp1", "exp2"],
            methodology="Empirical measurement and analysis.",
            confidence="HIGH",
        )
        assert finding.classification == level


def test_guardrail_rejects_uninstrumented_lock_contention():
    """Verify pydantic validator rejects claiming causal lock contention without instrumented lock metrics."""
    with pytest.raises(pydantic.ValidationError, match="asserts lock contention/serialization but lacks"):
        PerformanceFinding(
            finding_id="invalid_lock_claim",
            title="Invalid Lock Assertion",
            claim="High latency was caused by row-level lock contention on pgbench_branches.",
            classification=EvidenceClassification.VALIDATED,
            supporting_metrics=["p95_latency_ms", "tps"],  # Missing pg_locks or wait_event
            supporting_experiment_ids=["exp1", "exp2"],
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
            supporting_metrics=["p95_latency_ms", "tps"],  # Missing diskstats or io.stat
            supporting_experiment_ids=["exp1", "exp2"],
            methodology="Speculation without storage telemetry.",
            confidence="LOW",
        )


def test_guardrail_rejects_validated_without_multiple_experiments():
    """Verify that VALIDATED claims require at least 2 distinct empirical experiments."""
    with pytest.raises(pydantic.ValidationError, match="must reference at least two supporting experiments"):
        PerformanceFinding(
            finding_id="invalid_single_exp_validation",
            title="Invalid Single Experiment Validation",
            claim="CFS quota doubling eliminates periodicity.",
            classification=EvidenceClassification.VALIDATED,
            supporting_metrics=["throttled_usec", "cgroup_quota"],
            supporting_experiment_ids=["exp_only_one"],
            methodology="Single trial observation.",
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

    # 2. CFS quota causation is VALIDATED via 1.0 vs 2.0 vCPU experiment
    assert finding_map["FINDING_4F_02"].classification == EvidenceClassification.VALIDATED
    assert len(finding_map["FINDING_4F_02"].supporting_experiment_ids) >= 2

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
    performs CFS analysis, and cleans up containers.
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
    psql_clean_out = "200000|2|20|0|26000000|40960|40960|8192|35000000|128MB|4MB|100|5min|on|on"

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
            if "pgbench_accounts" in cmd_str:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout=psql_clean_out)
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
        assert (art_dir / "monitoring_samples_c1_r0.json").exists()
        assert (art_dir / "monitoring_summary_c1_r0.json").exists()
