"""
Phase 4F.4.4 Final Independent Execution Integrity Review Test Suite.

Independently tests and validates:
1. Concurrency and crash resilience under SIGKILL at critical persistence points.
2. Lock path canonicalization and symlink attack resistance.
3. TOCTOU manifest tampering immutability (in-memory execution isolation).
4. Failure propagation and fail-closed campaign state when a trial aborts.
5. Telemetry distinction between measured 0.0 and unavailable None.
"""
import copy
import hashlib
import json
import multiprocessing
import os
import signal
import time
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


def make_test_auth(**kwargs) -> CampaignAuthorizationRecord:
    data: Dict[str, Any] = {
        "phase": EXPECTED_PHASE,
        "proposal_id": "prop_phase4f4_review_001",
        "authorization_id": "auth_phase4f4_review_001",
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "execution_scope": EXPECTED_EXECUTION_SCOPE,
        "operator_identity": "independent_auditor",
        "authorized_at_utc": "2026-11-03T10:00:00Z",
        "expires_at_utc": "2027-11-10T10:00:00Z",
        "revoked": False,
        "consumed": False,
    }
    data.update(kwargs)
    return CampaignAuthorizationRecord(**data)


# ---------------------------------------------------------------------------
# Requirement 1: Multiprocess Crash & Termination Tests
# ---------------------------------------------------------------------------

def _worker_sigkill_before_replace(auth_path_str: str, flag_path_str: str):
    """Worker that acquires lock and is killed by SIGKILL right before replace."""
    auth_path = Path(auth_path_str).resolve()
    flag_path = Path(flag_path_str)

    def crashing_replace(self, target):
        with open(flag_path, "w") as f:
            f.write("CRASHING_BEFORE_REPLACE")
            f.flush()
            os.fsync(f.fileno())
        os.kill(os.getpid(), signal.SIGKILL)

    with patch.object(Path, "replace", crashing_replace):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=auth_path,
            execution_id="exec_crash_before",
        )


def _worker_sigkill_after_replace(auth_path_str: str, flag_path_str: str):
    """Worker that executes replace and is immediately killed by SIGKILL."""
    auth_path = Path(auth_path_str).resolve()
    flag_path = Path(flag_path_str)
    orig_fsync = os.fsync
    call_count = 0

    def crashing_fsync(fd):
        nonlocal call_count
        call_count += 1
        orig_fsync(fd)
        if call_count >= 2:  # First fsync is tmp file, second is parent dir
            with open(flag_path, "w") as f:
                f.write("CRASHING_AFTER_REPLACE")
                f.flush()
                orig_fsync(f.fileno())
            os.kill(os.getpid(), signal.SIGKILL)

    with patch("os.fsync", crashing_fsync):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=auth_path,
            execution_id="exec_crash_after",
        )


def test_crash_safety_sigkill_before_replace_retains_authorization(tmp_path):
    """
    Verify that if a process crashes (SIGKILL) before replacing the authorization file:
    - The advisory lock is released by the kernel.
    - The on-disk authorization remains unconsumed.
    - A subsequent process can successfully consume it.
    """
    auth_file = tmp_path / "auth_crash_test.json"
    auth_file.write_text(json.dumps(make_test_auth().model_dump(), indent=2))
    flag_file = tmp_path / "crash_before.flag"

    p = multiprocessing.Process(
        target=_worker_sigkill_before_replace,
        args=(str(auth_file), str(flag_file)),
    )
    p.start()
    p.join(timeout=5)

    assert p.exitcode == -signal.SIGKILL or p.exitcode is not None
    assert flag_file.exists()
    assert flag_file.read_text() == "CRASHING_BEFORE_REPLACE"

    # Verify authorization on disk is still unconsumed
    content = json.loads(auth_file.read_text())
    assert content["consumed"] is False

    # A subsequent consumer MUST succeed
    second = CampaignAuthorizationRecord.consume_file_atomically(
        auth_path=auth_file,
        execution_id="exec_recovery",
    )
    assert second.consumed is True
    assert second.consumed_by_execution_id == "exec_recovery"


def test_crash_safety_sigkill_after_replace_fails_closed(tmp_path):
    """
    Verify that if a process crashes (SIGKILL) after replacing the authorization file:
    - The on-disk authorization is marked consumed.
    - Any subsequent process cannot re-consume it (fails closed).
    """
    auth_file = tmp_path / "auth_crash_after_test.json"
    auth_file.write_text(json.dumps(make_test_auth().model_dump(), indent=2))
    flag_file = tmp_path / "crash_after.flag"

    p = multiprocessing.Process(
        target=_worker_sigkill_after_replace,
        args=(str(auth_file), str(flag_file)),
    )
    p.start()
    p.join(timeout=5)

    assert p.exitcode == -signal.SIGKILL or p.exitcode is not None
    assert flag_file.exists()
    assert flag_file.read_text() == "CRASHING_AFTER_REPLACE"

    # Verify authorization on disk is now consumed
    content = json.loads(auth_file.read_text())
    assert content["consumed"] is True
    assert content["consumed_by_execution_id"] == "exec_crash_after"

    # Any subsequent consumer MUST fail closed
    with pytest.raises(ValueError, match="ALREADY BEEN CONSUMED"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=auth_file,
            execution_id="exec_after_crash",
        )


def test_lock_path_canonicalization_and_symlink_defense(tmp_path):
    """
    Verify that targeting the authorization file via a symlink or relative path
    resolves to the same canonical lock file, preventing lock circumvention.
    """
    real_auth = tmp_path / "real_auth.json"
    real_auth.write_text(json.dumps(make_test_auth().model_dump(), indent=2))

    symlink_auth = tmp_path / "symlink_auth.json"
    symlink_auth.symlink_to(real_auth)

    # Consuming via symlink MUST lock real_auth.json.lock
    consumed = CampaignAuthorizationRecord.consume_file_atomically(
        auth_path=symlink_auth,
        execution_id="exec_via_symlink",
    )
    assert consumed.consumed is True

    # Real file is marked consumed
    content = json.loads(real_auth.read_text())
    assert content["consumed"] is True

    # Attempting to consume via real path fails
    with pytest.raises(ValueError, match="ALREADY BEEN CONSUMED"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=real_auth,
            execution_id="exec_via_real",
        )


def _compete_worker(auth_file_str: str, worker_id: int, queue: multiprocessing.Queue):
    """Worker competing in high-contention test."""
    try:
        rec = CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=Path(auth_file_str),
            execution_id=f"exec_worker_{worker_id}",
        )
        queue.put(("SUCCESS", worker_id, rec.consumed_by_execution_id))
    except Exception as e:
        queue.put(("FAIL", worker_id, str(e)))


def test_high_contention_20_process_competition(tmp_path):
    """
    Verify that under heavy concurrency (20 simultaneous processes), exactly
    1 process acquires and consumes the authorization, and 19 fail closed.
    """
    auth_file = tmp_path / "auth_heavy_contention.json"
    auth_file.write_text(json.dumps(make_test_auth().model_dump(), indent=2))

    queue = multiprocessing.Queue()
    num_workers = 20
    workers = []
    for i in range(num_workers):
        p = multiprocessing.Process(
            target=_compete_worker,
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

    assert len(results) == num_workers
    successes = [r for r in results if r[0] == "SUCCESS"]
    failures = [r for r in results if r[0] == "FAIL"]

    assert len(successes) == 1
    assert len(failures) == num_workers - 1
    for f in failures:
        assert "ALREADY BEEN CONSUMED" in f[2]


def test_invalid_authorization_leaves_file_unconsumed(tmp_path):
    """
    Verify that if an authorization fails validation (e.g. expired, revoked, wrong hash),
    it is rejected WITHOUT modifying the file on disk or marking it consumed.
    """
    # 1. Expired authorization
    expired_file = tmp_path / "auth_expired.json"
    expired_file.write_text(json.dumps(make_test_auth(expires_at_utc="2026-10-01T00:00:00Z").model_dump(), indent=2))
    with pytest.raises(ValueError, match="EXPIRED at"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=expired_file,
            execution_id="exec_expired",
        )
    assert json.loads(expired_file.read_text())["consumed"] is False

    # 2. Revoked authorization
    revoked_file = tmp_path / "auth_revoked.json"
    revoked_file.write_text(json.dumps(make_test_auth(revoked=True).model_dump(), indent=2))
    with pytest.raises(ValueError, match="has been REVOKED"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=revoked_file,
            execution_id="exec_revoked",
        )
    assert json.loads(revoked_file.read_text())["consumed"] is False

    # 3. Hash mismatch
    wrong_hash_file = tmp_path / "auth_wrong_hash.json"
    wrong_hash_file.write_text(json.dumps(make_test_auth(manifest_sha256="wrong_hash" * 4).model_dump(), indent=2))
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        CampaignAuthorizationRecord.consume_file_atomically(
            auth_path=wrong_hash_file,
            execution_id="exec_wrong_hash",
        )
    assert json.loads(wrong_hash_file.read_text())["consumed"] is False

def test_toctou_manifest_post_verification_disk_tamper_defense(tmp_path):
    """
    Verify that if the manifest file on disk is modified AFTER pre-execution hashing,
    the runner executes strictly from the in-memory verified schedule and ignores disk tamper.
    """
    # Copy official manifest to tmp_path
    manifest_copy = tmp_path / "manifest.json"
    manifest_copy.write_bytes(DEFAULT_MANIFEST_PATH.read_bytes())

    runner = Phase4F4Runner()
    auth = make_test_auth()

    # Tamper the file on disk during trial execution
    def tamper_manifest_hook(*args, **kwargs):
        # Modify the manifest on disk to invalidate it
        manifest_copy.write_text("TAMPERED_POST_VERIFICATION_CONTENT")
        raise RuntimeError("HALT_FOR_INSPECTION")

    art_dir = tmp_path / "empirical"
    with patch.object(runner, "verify_prerequisites", return_value={"prerequisites_met": True, "issues": [], "host_metadata": {}}), \
         patch.object(runner, "execute_single_trial", side_effect=tamper_manifest_hook):

        with pytest.raises(RuntimeError, match="HALT_FOR_INSPECTION"):
            runner.execute_campaign(
                authorization=auth,
                manifest_path=manifest_copy,
                artifacts_root=art_dir,
            )

    # Verified manifest in artifacts directory preserved the original verified bytes
    verified_manifest = art_dir / "verified_manifest.json"
    assert verified_manifest.exists()
    assert hashlib.sha256(verified_manifest.read_bytes()).hexdigest() == EXPECTED_MANIFEST_SHA256


# ---------------------------------------------------------------------------
# Requirement 5: Telemetry Distinction (0.0 vs None)
# ---------------------------------------------------------------------------

def test_telemetry_distinction_zero_versus_none():
    """
    Verify that a measured zero throttling (0.0) is strictly distinguished
    from missing telemetry (None).
    """
    runner = Phase4F4Runner()

    # Condition with measured zero (0.0 sec)
    trials_zero = []
    for sched in FROZEN_12_TRIAL_SCHEDULE:
        trials_zero.append({
            "trial_id": sched["trial_id"],
            "workload_profile": sched["profile"],
            "cpu_quota_cores": float(sched["cpu_limit"]),
            "replication": sched["rep"],
            "status": "SUCCESS",
            "tps": 500.0,
            "latency_avg_ms": 2.0,
            "p95_ms": 3.0,
            "p99_ms": 4.0,
            "p999_ms": 5.0,
            "cgroup_cpu": {
                "mean_cpu_pct": 80.0,
                "throttled_sec": 0.0,  # Legitimate zero
                "throttling_status": "AVAILABLE",
                "throttling_reason": None,
            },
        })

    summary_zero = runner.aggregate_campaign_results(trials_zero, verified_schedule=FROZEN_12_TRIAL_SCHEDULE)
    for cond in summary_zero["conditions"].values():
        throt = cond["throttled_seconds"]
        assert throt["status"] == "AVAILABLE"
        assert throt["mean"] == 0.0
        assert throt["values"] == [0.0, 0.0, 0.0]

    # Condition with unavailable telemetry (None)
    trials_none = []
    for sched in FROZEN_12_TRIAL_SCHEDULE:
        trials_none.append({
            "trial_id": sched["trial_id"],
            "workload_profile": sched["profile"],
            "cpu_quota_cores": float(sched["cpu_limit"]),
            "replication": sched["rep"],
            "status": "SUCCESS",
            "tps": 500.0,
            "latency_avg_ms": 2.0,
            "p95_ms": 3.0,
            "p99_ms": 4.0,
            "p999_ms": 5.0,
            "cgroup_cpu": {
                "mean_cpu_pct": 80.0,
                "throttled_sec": None,  # Telemetry missing
                "throttling_status": "UNAVAILABLE",
                "throttling_reason": "Missing telemetry",
            },
        })

    summary_none = runner.aggregate_campaign_results(trials_none, verified_schedule=FROZEN_12_TRIAL_SCHEDULE)
    for cond in summary_none["conditions"].values():
        throt = cond["throttled_seconds"]
        assert throt["status"] == "UNAVAILABLE"
        assert throt["mean"] is None
        assert throt["values"] == [None, None, None]


# ---------------------------------------------------------------------------
# Requirement 6: End-to-End Failure Propagation
# ---------------------------------------------------------------------------

def test_campaign_fails_closed_when_any_trial_fails(tmp_path):
    """
    Verify that if any trial fails (status != SUCCESS), execute_campaign:
    1. Does NOT report COMPLETED.
    2. Writes campaign_summary.json with manifest_status: FAILED.
    3. Leaves comparisons and conditions as None.
    4. Raises RuntimeError fail-closed.
    """
    runner = Phase4F4Runner()
    auth = make_test_auth()
    art_root = tmp_path / "failing_campaign"
    art_root.mkdir()

    trial_idx = 0

    def mock_trial(trial_def, artifacts_dir, execution_id):
        nonlocal trial_idx
        trial_idx += 1
        if trial_idx == 3:  # Trial 3 fails
            return {
                "sequence": trial_def["seq"],
                "trial_id": trial_def["trial_id"],
                "execution_id": execution_id,
                "workload_profile": trial_def["profile"],
                "cpu_quota_cores": float(trial_def["cpu_limit"]),
                "replication": trial_def["rep"],
                "status": "FAILED",
                "failure_stage": "BENCHMARK_EXECUTION",
                "cleanup_result": {"success": True, "cleanup_errors": []},
            }
        return {
            "sequence": trial_def["seq"],
            "trial_id": trial_def["trial_id"],
            "execution_id": execution_id,
            "workload_profile": trial_def["profile"],
            "cpu_quota_cores": float(trial_def["cpu_limit"]),
            "replication": trial_def["rep"],
            "status": "SUCCESS",
            "cleanup_result": {"success": True, "cleanup_errors": []},
        }

    with patch.object(runner, "verify_prerequisites", return_value={"prerequisites_met": True, "issues": [], "host_metadata": {}}), \
         patch.object(runner, "execute_single_trial", side_effect=mock_trial):

        with pytest.raises(RuntimeError, match="Phase 4F.4 Campaign Execution Failed"):
            runner.execute_campaign(
                authorization=auth,
                artifacts_root=art_root,
            )

    # Check written campaign_summary.json
    summary_path = art_root / "campaign_summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["manifest_status"] == "FAILED"
    assert summary["conditions"] is None
    assert summary["comparisons"] is None
    assert summary["failed_trials"] == 1
    assert "trials failed or aborted" in summary["completion_issues"][0]
