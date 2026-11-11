"""
Evidence Loader for Phase 4F.4.6 Reconciled Empirical Data.

Reads reconciled JSON artifacts, validates provenance, and structures trial observations
for candidate model training and replication-aware evaluation.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from aads.models.empirical_postgres.schemas import TrialObservation, WorkloadProfile

logger = logging.getLogger(__name__)

EXPECTED_MANIFEST_SHA256 = "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"
EXPECTED_EXECUTION_ID = "exec_p4f4_20261103_053428_525413_19491"


class ReconciledEvidenceLoader:
    """Loads and validates reconciled empirical evidence from Phase 4F.4.6."""

    def __init__(self, evidence_dir: Union[str, Path] = "artifacts/phase_4f46/reconciliation"):
        self.evidence_dir = Path(evidence_dir)
        self._summary: Optional[Dict[str, Any]] = None
        self._trials_reconciliation: Optional[List[Dict[str, Any]]] = None
        self._telemetry_window: Optional[List[Dict[str, Any]]] = None
        self._postgres_evidence: Optional[List[Dict[str, Any]]] = None
        self._condition_stats: Optional[Dict[str, Any]] = None
        self._observations: Optional[List[TrialObservation]] = None

    def verify_provenance(self) -> Tuple[bool, Dict[str, Any]]:
        """Verifies that evidence files exist and match execution ID and manifest hash."""
        summary_path = self.evidence_dir / "reconciliation_summary.json"
        if not summary_path.is_file():
            return False, {"error": f"Reconciliation summary not found: {summary_path}"}

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        matches_exec = (summary.get("execution_id") == EXPECTED_EXECUTION_ID)
        matches_manifest = (summary.get("manifest_sha256") == EXPECTED_MANIFEST_SHA256)
        status_complete = (summary.get("reconciliation_status") == "COMPLETE")

        valid = matches_exec and matches_manifest and status_complete
        provenance = {
            "execution_id": summary.get("execution_id"),
            "manifest_sha256": summary.get("manifest_sha256"),
            "manifest_verified": summary.get("manifest_verified", False),
            "reconciliation_status": summary.get("reconciliation_status"),
            "total_trials_reconciled": summary.get("total_trials_reconciled", 0),
            "total_raw_transactions": summary.get("total_raw_transactions_parsed", 0),
            "model_registry_intact": summary.get("model_registry_integrity", {}).get("intact", False),
            "is_valid": valid,
        }
        return valid, provenance

    def load_trial_observations(self) -> List[TrialObservation]:
        """Loads and cross-references all 12 reconciled trial observations."""
        if self._observations is not None:
            return self._observations

        trials_path = self.evidence_dir / "trial_reconciliation.json"
        telemetry_path = self.evidence_dir / "telemetry_window_analysis.json"
        postgres_path = self.evidence_dir / "postgres_evidence.json"

        if not trials_path.is_file() or not telemetry_path.is_file() or not postgres_path.is_file():
            raise FileNotFoundError(
                f"Required reconciliation artifacts missing in {self.evidence_dir}. "
                "Ensure Phase 4F.4.6 reconciliation was executed."
            )

        with open(trials_path, "r", encoding="utf-8") as f:
            trials_data = json.load(f)
        with open(telemetry_path, "r", encoding="utf-8") as f:
            telem_data = {t["trial_id"]: t["measurement_window"] for t in json.load(f)}
        with open(postgres_path, "r", encoding="utf-8") as f:
            pg_data = {t["trial_id"]: t["metrics_taxonomy"] for t in json.load(f)}

        observations: List[TrialObservation] = []
        for t in trials_data:
            tid = t["trial_id"]
            recalc = t["recalculated_metrics"]
            stored = t["stored_summary_metrics"]
            m_win = telem_data.get(tid, {})
            cfs = m_win.get("cgroup_cfs", {})
            pg_tax = pg_data.get(tid, {})
            wal = pg_tax.get("wal_activity", {})
            locks = pg_tax.get("concurrency_and_locks", {})

            obs = TrialObservation(
                trial_id=tid,
                workload_profile=t["workload_profile"],
                cpu_quota_cores=float(t["cpu_quota_cores"]),
                replication=int(t["replication"]),
                duration_seconds=float(m_win.get("duration_seconds", 30.0)),
                throughput_tps=float(stored["tps"]),
                latency_mean_ms=float(recalc["mean_ms"]),
                p50_ms=float(recalc["p50_ms"]),
                p90_ms=float(recalc["p90_ms"]),
                p95_ms=float(recalc["p95_ms"]),
                p99_ms=float(recalc["p99_ms"]),
                p999_ms=float(recalc["p999_ms"]),
                max_ms=float(recalc["max_ms"]),
                cpu_utilization_pct=float(m_win.get("cpu_quota_utilization_pct", 100.0)),
                throttling_frequency_pct=float(cfs.get("throttling_frequency_pct", 0.0)),
                throttled_seconds=float(cfs.get("throttled_seconds", 0.0)),
                wal_bytes=int(wal.get("delta_wal_bytes", 0)),
                wal_sync_time_ms=float(wal.get("wal_sync_time_ms", 0.0)),
                observed_lock_waits=int(locks.get("observed_lock_waits", 0)),
            )
            observations.append(obs)

        self._observations = observations
        return observations

    def get_workload_observations(
        self,
        workload_profile: Union[str, WorkloadProfile],
    ) -> List[TrialObservation]:
        """Filters observations for a specific workload profile."""
        profile_str = workload_profile.value if isinstance(workload_profile, WorkloadProfile) else str(workload_profile)
        all_obs = self.load_trial_observations()
        matching = [o for o in all_obs if o.workload_profile == profile_str]
        return matching
