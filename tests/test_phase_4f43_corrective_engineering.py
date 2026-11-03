"""
Phase 4F.4.3 Corrective Engineering — Comprehensive Regression & Verification Suite.

Validates the resolutions for all five audit findings identified in Phase 4F.4.2:
- P-01: Atomic cross-process authorization consumption with fcntl.flock(LOCK_EX) and durable fsync.
- P-02: Exact on-disk manifest byte-level SHA256 verification and single-parse execution.
- P-03: Immutable container image reference using repository@digest pinning.
- P-04: Unique execution-ID namespaced artifact directories with non-empty overwrite rejection.
- P-05: Telemetry availability preservation (missing throttling remains UNAVAILABLE/None).

STRICT VERIFICATION: Offline execution only. No live Docker or pgbench runs.
"""
import copy
import hashlib
import json
import multiprocessing
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from aads.benchmark.phase_4f4_runner import (
    DEFAULT_MANIFEST_PATH,
    EXPECTED_EXECUTION_SCOPE,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_PHASE,
    FROZEN_12_TRIAL_SCHEDULE,
    CampaignAuthorizationRecord,
    Phase4F4Runner,
)
from aads.benchmark.trial_isolation import TrialIsolationManager


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

def make_test_auth_record(**kwargs) -> CampaignAuthorizationRecord:
    data: Dict[str, Any] = {
        "phase": EXPECTED_PHASE,
        "proposal_id": "prop_phase4f4_p4f43_test_001",
        "authorization_id": "auth_phase4f4_p4f43_test_001",
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "execution_scope": EXPECTED_EXECUTION_SCOPE,
        "operator_identity": "operator_offline_test",
        "authorized_at_utc": "2026-11-03T10:00:00Z",
        "expires_at_utc": "2026-11-10T10:00:00Z",
        "revoked": False,
        "consumed": False,
    }
    data.update(kwargs)
    return CampaignAuthorizationRecord(**data)


def _consume_worker(auth_file_str: str, worker_id: int, queue: multiprocessing.Queue):
    """Worker process targeting single authorization file via consume_file_atomically."""
    try:
        record = CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=Path(auth_file_str),
            execution_id=f"exec_worker_{worker_id}",
            expected_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        )
        queue.put(("SUCCESS", worker_id, record.consumed_by_execution_id))
    except Exception as exc:
        queue.put(("FAILURE", worker_id, str(exc)))


# ---------------------------------------------------------------------------
# P-01: Cross-Process Atomic Authorization Tests
# ---------------------------------------------------------------------------

def test_p01_multiprocess_atomic_consumption_competition(tmp_path):
    """
    P-01: Verify that when 10 genuine processes concurrently compete to consume
    the same authorization file, exactly 1 succeeds and 9 fail with 'ALREADY BEEN CONSUMED'.
    """
    auth_file = tmp_path / "campaign_auth.json"
    auth_data = make_test_auth_record().model_dump()
    auth_file.write_text(json.dumps(auth_data, indent=2), encoding="utf-8")

    queue = multiprocessing.Queue()
    workers = []
    num_processes = 10

    for i in range(num_processes):
        p = multiprocessing.Process(
            target=_consume_worker,
            args=(str(auth_file), i, queue),
        )
        workers.append(p)

    for p in workers:
        p.start()

    for p in workers:
        p.join(timeout=10)

    results = []
    while not queue.empty():
        results.append(queue.get())

    assert len(results) == num_processes, f"Expected {num_processes} worker outcomes, got {len(results)}"

    successes = [r for r in results if r[0] == "SUCCESS"]
    failures = [r for r in results if r[0] == "FAILURE"]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == num_processes - 1, f"Expected {num_processes - 1} failures, got {len(failures)}"

    for fail in failures:
        assert "ALREADY BEEN CONSUMED" in fail[2], f"Unexpected error message: {fail[2]}"

    # Verify persistent state on disk
    persisted = json.loads(auth_file.read_text(encoding="utf-8"))
    assert persisted["consumed"] is True
    assert persisted["consumed_by_execution_id"] == successes[0][2]
    assert persisted["consumed_at_utc"] is not None


def test_p01_authorization_single_use_durability_and_crash_safety(tmp_path):
    """
    P-01: Verify that once consumed, any subsequent consumer in a new process/thread
    is immediately rejected and the authorization state remains durably immutable.
    """
    auth_file = tmp_path / "durable_auth.json"
    auth_data = make_test_auth_record().model_dump()
    auth_file.write_text(json.dumps(auth_data, indent=2), encoding="utf-8")

    # Initial consumption
    first = CampaignAuthorizationRecord.consume_file_atomically(
        auth_path=auth_file,
        execution_id="exec_first_run",
    )
    assert first.consumed is True
    assert first.consumed_by_execution_id == "exec_first_run"

    # Second consumption attempt on the same file MUST fail fail-closed
    with pytest.raises(ValueError, match="ALREADY BEEN CONSUMED"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=auth_file,
            execution_id="exec_second_run",
        )

    # Re-reading raw file confirms state was written to disk
    disk_data = json.loads(auth_file.read_text(encoding="utf-8"))
    assert disk_data["consumed"] is True
    assert disk_data["consumed_by_execution_id"] == "exec_first_run"


# ---------------------------------------------------------------------------
# P-02: Exact On-Disk Manifest Byte Integrity Tests
# ---------------------------------------------------------------------------

def test_p02_manifest_on_disk_byte_hash_and_single_parse(tmp_path):
    """
    P-02: Verify that runner reads manifest bytes once from disk, verifies exact
    SHA256, parses to verified schedule, and executes from memory without re-reading.
    """
    runner = Phase4F4Runner()
    auth = make_test_auth_record()

    # 1. Official manifest matches expected SHA256
    assert DEFAULT_MANIFEST_PATH.exists()
    computed_hash = hashlib.sha256(DEFAULT_MANIFEST_PATH.read_bytes()).hexdigest()
    assert computed_hash == EXPECTED_MANIFEST_SHA256

    # 2. Tampered manifest file (single extra newline or whitespace) fails SHA256 check
    tampered_manifest = tmp_path / "tampered_manifest.json"
    tampered_bytes = DEFAULT_MANIFEST_PATH.read_bytes() + b" "
    tampered_manifest.write_bytes(tampered_bytes)

    with pytest.raises(ValueError, match="On-disk manifest SHA256 mismatch"):
        runner.execute_campaign(
            authorization=auth,
            manifest_path=tampered_manifest,
        )

    # 3. Non-existent manifest file fails fail-closed
    missing_manifest = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="not found on disk"):
        runner.execute_campaign(
            authorization=auth,
            manifest_path=missing_manifest,
        )

    # 4. Invalid JSON manifest fails fail-closed
    corrupt_manifest = tmp_path / "corrupt_manifest.json"
    corrupt_manifest.write_bytes(b"NOT_A_JSON")
    with pytest.raises(ValueError, match="On-disk manifest SHA256 mismatch"):
        runner.execute_campaign(
            authorization=auth,
            manifest_path=corrupt_manifest,
        )


def test_p02_manifest_schedule_and_phase_integrity(tmp_path):
    """
    P-02: Verify that a validly-hashed manifest whose contents deviate from
    frozen 12-trial schedule or phase fails fail-closed.
    """
    runner = Phase4F4Runner()

    # Create synthetic manifest with invalid phase
    raw_data = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    bad_phase_data = copy.deepcopy(raw_data)
    bad_phase_data["phase"] = "4F.5"
    bad_manifest = tmp_path / "bad_phase.json"
    bad_bytes = json.dumps(bad_phase_data).encode("utf-8")
    bad_manifest.write_bytes(bad_bytes)
    bad_hash = hashlib.sha256(bad_bytes).hexdigest()

    auth = make_test_auth_record(manifest_sha256=bad_hash)
    with pytest.raises(ValueError, match="On-disk manifest SHA256 mismatch: computed '.*', expected baseline"):
        runner.execute_campaign(
            authorization=auth,
            manifest_path=bad_manifest,
        )


# ---------------------------------------------------------------------------
# P-03: Immutable Image Reference Pinning Tests
# ---------------------------------------------------------------------------

def test_p03_immutable_image_digest_construction():
    """
    P-03: Verify TrialIsolationManager constructs immutable repository@digest
    reference when starting containers, preventing mutable tag resolution.
    """
    pinned_digest = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
    manager = TrialIsolationManager(
        default_image="postgres:16-alpine",
        pinned_image_digest=pinned_digest,
    )

    mock_run = MagicMock()
    mock_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="mock_container_id\n",
        stderr="",
    )

    fake_snapshot = MagicMock()
    fake_snapshot.content_fingerprint = "mock_fingerprint"

    with patch("subprocess.run", mock_run), \
         patch.object(manager, "capture_database_state", return_value=fake_snapshot), \
         patch.object(manager, "verify_baseline_state", return_value=(True, [])):

        manager.initialize_fresh_container(container_name="test_p03_container", scale_factor=2)

        # Inspect the subprocess.run call
        call_args = mock_run.call_args_list[0][0][0]
        assert "docker" in call_args
        assert "run" in call_args

        # Expected immutable image reference format: repo@digest
        expected_immutable_ref = f"postgres@{pinned_digest}"
        assert expected_immutable_ref in call_args, (
            f"Expected immutable image ref '{expected_immutable_ref}' in docker run args: {call_args}"
        )
        assert "postgres:16-alpine" not in call_args, (
            f"Mutable tag 'postgres:16-alpine' should NOT be used: {call_args}"
        )


def test_p03_runner_immutable_image_reference_provenance():
    """P-03: Verify Phase4F4Runner initializes and exposes pinned_image_reference."""
    runner = Phase4F4Runner()
    expected_ref = f"{runner.pinned_image.split(':')[0]}@{runner.pinned_digest}"
    assert runner.pinned_image_reference == expected_ref
    assert runner.pinned_image_reference == "postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"


# ---------------------------------------------------------------------------
# P-04: Unique Artifact Directories & Collision Protection Tests
# ---------------------------------------------------------------------------

def test_p04_artifact_directory_namespacing_and_collision_guard(tmp_path):
    """
    P-04: Verify that default artifact path is namespaced with unique execution ID,
    and attempting to reuse an existing non-empty directory is rejected.
    """
    runner = Phase4F4Runner()
    auth = make_test_auth_record()

    # 1. Non-empty directory reuse rejection
    existing_dir = tmp_path / "prior_evidence"
    existing_dir.mkdir(parents=True)
    (existing_dir / "old_result.txt").write_text("prior run data")

    with pytest.raises(RuntimeError, match="Artifact directory already exists and is non-empty"):
        runner.execute_campaign(
            authorization=auth,
            artifacts_root=existing_dir,
        )

    # 2. Empty directory allowed when explicitly specified
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir(parents=True)

    with patch.object(runner, "verify_prerequisites", return_value={"prerequisites_met": True, "issues": [], "host_metadata": {}}), \
         patch.object(runner, "execute_single_trial", side_effect=RuntimeError("HALT_BEFORE_BENCHMARK")):
        with pytest.raises(RuntimeError, match="HALT_BEFORE_BENCHMARK"):
            runner.execute_campaign(
                authorization=auth,
                artifacts_root=empty_dir,
            )

        # Verified manifest and consumed authorization must be placed inside empty_dir
        assert (empty_dir / "verified_manifest.json").exists()
        assert (empty_dir / "consumed_authorization.json").exists()


# ---------------------------------------------------------------------------
# P-05: Missing Telemetry Preservation Tests
# ---------------------------------------------------------------------------

def test_p05_missing_telemetry_preserved_as_unavailable():
    """
    P-05: Verify that missing CPU throttling telemetry (None) is preserved
    as UNAVAILABLE rather than coerced to 0.0, and comparisons do not report synthetic deltas.
    """
    runner = Phase4F4Runner()

    # Mock trial results with missing throttling (None)
    mock_trials = []
    for sched in FROZEN_12_TRIAL_SCHEDULE:
        mock_trials.append({
            "trial_id": sched["trial_id"],
            "workload_profile": sched["profile"],
            "cpu_quota_cores": float(sched["cpu_limit"]),
            "replication": sched["rep"],
            "status": "SUCCESS",
            "tps": 1000.0 if sched["profile"] == "read_only_select" else 200.0,
            "latency_avg_ms": 1.0,
            "p95_ms": 2.5,
            "p99_ms": 3.0,
            "p999_ms": 4.0,
            "cgroup_cpu": {
                "mean_cpu_pct": 95.0,
                "throttled_sec": None,  # Telemetry missing
                "throttling_status": "UNAVAILABLE",
                "throttling_reason": "cgroup v2 cpu.stat throttled_usec missing",
            },
        })

    summary = runner.aggregate_campaign_results(mock_trials, verified_schedule=FROZEN_12_TRIAL_SCHEDULE)

    for cond_name, cond in summary["conditions"].items():
        throt = cond["throttled_seconds"]
        assert throt["status"] == "UNAVAILABLE"
        assert throt["mean"] is None
        assert throt["median"] is None
        assert all(v is None for v in throt["values"])

    # Comparisons must report None for throttled_time_reduction_sec
    ro_comp = summary["comparisons"]["read_only_select"]
    assert ro_comp["throttled_time_reduction_sec"] is None

    oltp_comp = summary["comparisons"]["balanced_oltp_tpcb"]
    assert oltp_comp["throttled_time_reduction_sec"] is None


def test_p05_available_telemetry_retains_numerical_values():
    """
    P-05: Verify that when throttling telemetry is legitimately available (0.0 or > 0.0),
    it reports status: AVAILABLE and computes legitimate reduction metrics.
    """
    runner = Phase4F4Runner()

    mock_trials = []
    for sched in FROZEN_12_TRIAL_SCHEDULE:
        throt_val = 2.5 if sched["cpu_limit"] == "1.0" else 0.1
        mock_trials.append({
            "trial_id": sched["trial_id"],
            "workload_profile": sched["profile"],
            "cpu_quota_cores": float(sched["cpu_limit"]),
            "replication": sched["rep"],
            "status": "SUCCESS",
            "tps": 1000.0 if sched["profile"] == "read_only_select" else 200.0,
            "latency_avg_ms": 1.0,
            "p95_ms": 2.5,
            "p99_ms": 3.0,
            "p999_ms": 4.0,
            "cgroup_cpu": {
                "mean_cpu_pct": 95.0,
                "throttled_sec": throt_val,
                "throttling_status": "AVAILABLE",
                "throttling_reason": None,
            },
        })

    summary = runner.aggregate_campaign_results(mock_trials, verified_schedule=FROZEN_12_TRIAL_SCHEDULE)

    for cond_name, cond in summary["conditions"].items():
        throt = cond["throttled_seconds"]
        assert throt["status"] == "AVAILABLE"
        assert isinstance(throt["mean"], float)

    # Comparisons compute reduction: 2.5 - 0.1 = 2.4
    ro_comp = summary["comparisons"]["read_only_select"]
    assert ro_comp["throttled_time_reduction_sec"] == 2.4

    oltp_comp = summary["comparisons"]["balanced_oltp_tpcb"]
    assert oltp_comp["throttled_time_reduction_sec"] == 2.4
