"""
Unit tests for Phase 4F.2 SF=2 Evidence Audit.
Verifies the machine-readable audit summary, raw evidence reconciliation,
anomaly classification, trial isolation tracking, and environment provenance.
"""
import json
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIT_SUMMARY_PATH = BASE_DIR / "artifacts" / "benchmarks" / "phase_4f1_sf2" / "phase_4f2_sf2_audit_summary.json"


def test_phase_4f2_audit_summary_exists():
    """Verify that the machine-readable audit summary exists and has valid structure."""
    assert AUDIT_SUMMARY_PATH.exists(), f"Audit summary not found at {AUDIT_SUMMARY_PATH}"
    data = json.loads(AUDIT_SUMMARY_PATH.read_text())

    assert data["audit_phase"] == "Phase 4F.2"
    assert data["total_trials_audited"] == 36
    assert data["total_pooled_configurations_audited"] == 12
    assert data["total_transactions_reconciled"] == 11079871
    assert data["discrepancies_count"] == 0
    assert data["reconciliation_verdict"] == "VERIFIED_BITWISE_INTEGRITY"


def test_phase_4f2_anomaly_investigation():
    """Verify that the 3.15s TPC-B stall is accurately classified and corrected."""
    data = json.loads(AUDIT_SUMMARY_PATH.read_text())
    anomaly = data["anomaly_investigation"]

    assert anomaly["actual_trial_in_manifest"] == "sf2_balanced_oltp_tpcb_c4_r1"
    assert anomaly["max_latency_ms"] == 3152.95
    assert anomaly["simultaneously_stalled_clients_count"] == 4
    assert anomaly["classification"] == "UNVERIFIED"
    assert anomaly["retained_postgresql_logs_available"] is False
    assert anomaly["retained_checkpoint_stats_available"] is False


def test_phase_4f2_environment_audit():
    """Verify that environment audit identifies the genuine host and classifies the kernel suffix."""
    data = json.loads(AUDIT_SUMMARY_PATH.read_text())
    env = data["environment_audit"]

    assert "Intel" in env["verified_cpu_model"]
    assert env["verified_architecture"] == "x86_64"
    assert env["verified_kernel_release"] == "6.18.59-1-lts"
    assert env["discrepancy_investigation"]["reported_suffix"] == "rpt-rpi-2712"
    assert env["discrepancy_investigation"]["status"] == "DOCUMENTATION_ERRATUM"


def test_phase_4f2_storage_and_wal_audit():
    """Verify that uninstrumented storage metrics and unsupported claims are identified."""
    data = json.loads(AUDIT_SUMMARY_PATH.read_text())
    storage = data["storage_and_wal_audit"]

    assert len(storage["metrics_collected"]) >= 5
    assert len(storage["metrics_not_collected"]) >= 3
    assert len(storage["unsupported_historical_claims"]) >= 2


def test_phase_4f2_trial_isolation():
    """Verify that trial isolation tracks cumulative row growth in pgbench_history."""
    data = json.loads(AUDIT_SUMMARY_PATH.read_text())
    isolation = data["trial_isolation_audit"]

    assert isolation["inter_trial_reset"] == "NONE. Database was neither dropped, truncated, nor re-initialized between trials."
    assert isolation["table_growth"]["final_history_rows_after_simple_write"] == 1387048
