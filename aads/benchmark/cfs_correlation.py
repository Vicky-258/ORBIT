"""
Fine-Grained CFS Throttling and Transaction Alignment Analysis (Phase 4F.3 - Workstream 4).

Performs microsecond-resolution offline correlation between pgbench transaction logs
and high-frequency cgroup v2 cpu.stat measurements:
- Identifies periodic 100ms CFS quota boundaries
- Analyzes simultaneous multi-client transaction stalls
- Computes temporal alignment and overlap metrics
- Strictly avoids dividing aggregate throttled_usec by client count
- Guardrail: requires verifiable paired intervention evidence for CONTROLLED_CAUSAL_EVIDENCE (Phase 4F.3.2 FIX 07)
- Classifies evidence into:
  * NO_DETECTABLE_ASSOCIATION
  * TEMPORAL_ASSOCIATION
  * STRONG_TEMPORAL_ASSOCIATION
  * CONTROLLED_CAUSAL_EVIDENCE
"""
import json
import logging
import math
import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class CFSAssociationLevel(str, Enum):
    """Rigorous classification of temporal association and causality between CFS throttling and latency spikes."""
    NO_DETECTABLE_ASSOCIATION = "NO_DETECTABLE_ASSOCIATION"
    TEMPORAL_ASSOCIATION = "TEMPORAL_ASSOCIATION"
    STRONG_TEMPORAL_ASSOCIATION = "STRONG_TEMPORAL_ASSOCIATION"
    CONTROLLED_CAUSAL_EVIDENCE = "CONTROLLED_CAUSAL_EVIDENCE"


class TransactionRecord:
    """Parsed single transaction record from pgbench -l log."""

    def __init__(
        self,
        client_id: int,
        transaction_no: int,
        latency_ms: float,
        epoch_timestamp_sec: float,
    ):
        self.client_id = client_id
        self.transaction_no = transaction_no
        self.latency_ms = latency_ms
        self.epoch_timestamp_sec = epoch_timestamp_sec


def verify_controlled_intervention(intervention: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Validates paired controlled experiment evidence for causal promotion.
    Requires distinct control and treatment records, verifiable quota variation,
    comparable baselines, and measurable response.
    """
    if not intervention or not isinstance(intervention, dict):
        return False, "No controlled intervention evidence provided."

    ctrl_id = str(intervention.get("control_experiment_id", "")).strip()
    treat_id = str(intervention.get("treatment_experiment_id", "")).strip()
    if not ctrl_id or not treat_id:
        return False, "Missing control_experiment_id or treatment_experiment_id."
    if ctrl_id == treat_id:
        return False, f"Control and treatment IDs are identical ('{ctrl_id}')."

    ctrl_rep = re.search(r'_(?:r|rep)\d+', ctrl_id)
    treat_rep = re.search(r'_(?:r|rep)\d+', treat_id)
    if ctrl_rep and treat_rep:
        ctrl_prefix = re.sub(r'_(?:r|rep)\d+.*', '', ctrl_id)
        treat_prefix = re.sub(r'_(?:r|rep)\d+.*', '', treat_id)
        if ctrl_prefix == treat_prefix:
            return False, f"Paired duplicate replications ('{ctrl_id}' vs '{treat_id}') do not constitute a controlled intervention."

    ctrl_quota = intervention.get("control_quota_cores")
    treat_quota = intervention.get("treatment_quota_cores")
    if ctrl_quota is None or treat_quota is None:
        return False, "Missing control_quota_cores or treatment_quota_cores in intervention."
    try:
        ctrl_q = float(ctrl_quota)
        treat_q = float(treat_quota)
        if treat_q <= ctrl_q:
            return False, f"Treatment quota ({treat_q}) must differ from and exceed control quota ({ctrl_q})."
    except (ValueError, TypeError):
        return False, "Invalid numeric quota values in intervention."

    if not intervention.get("comparable_baseline_confirmed", False):
        return False, "Comparable baseline starting conditions were not confirmed."

    ctrl_outcome = intervention.get("control_outcome") or {}
    treat_outcome = intervention.get("treatment_outcome") or {}
    if not ctrl_outcome or not treat_outcome:
        return False, "Missing control_outcome or treatment_outcome metrics in intervention."

    ctrl_tps = ctrl_outcome.get("tps") or ctrl_outcome.get("achieved_tps") or 0.0
    treat_tps = treat_outcome.get("tps") or treat_outcome.get("achieved_tps") or 0.0
    if treat_tps <= ctrl_tps and ctrl_tps > 0:
        return False, f"Observed outcome does not demonstrate expected response: treatment TPS ({treat_tps}) did not exceed control TPS ({ctrl_tps})."

    return True, "Controlled intervention verified: quota manipulated holding baseline parameters constant with demonstrated outcome response."


class CFSCorrelationAnalyzer:
    """
    Offline analyzer correlating fine-grained cgroup v2 samples with transaction-level logs.
    """

    def __init__(
        self,
        cfs_period_ms: float = 100.0,
        spike_threshold_ms: float = 10.0,
        tolerance_ms: float = 5.0,
    ):
        self.cfs_period_ms = cfs_period_ms
        self.spike_threshold_ms = spike_threshold_ms
        self.tolerance_ms = tolerance_ms

    @staticmethod
    def parse_pgbench_log_records(log_content: str) -> List[TransactionRecord]:
        """Parses pgbench transaction log content into structured TransactionRecord objects."""
        records: List[TransactionRecord] = []
        for line in log_content.splitlines():
            parts = line.strip().split()
            if len(parts) >= 6:
                try:
                    client = int(parts[0])
                    tx_no = int(parts[1])
                    lat_ms = float(parts[2]) / 1000.0
                    sec = int(parts[4])
                    usec = int(parts[5])
                    t = sec + usec / 1e6
                    records.append(TransactionRecord(client, tx_no, lat_ms, t))
                except (ValueError, IndexError):
                    continue
        return records

    def analyze(
        self,
        transactions: List[TransactionRecord],
        cgroup_samples: List[Dict[str, Any]],
        controlled_intervention: Optional[Dict[str, Any]] = None,
        has_controlled_experiment_confirmation: bool = False,
    ) -> Dict[str, Any]:
        """
        Correlates transaction latency spikes against cgroup throttling telemetry.
        Enforces strict causal guardrails: requires verifiable controlled intervention data
        to assign CONTROLLED_CAUSAL_EVIDENCE (Phase 4F.3.2 FIX 07).
        """
        if not transactions:
            return {
                "association_level": CFSAssociationLevel.NO_DETECTABLE_ASSOCIATION.value,
                "reason": "No transaction records provided for analysis.",
                "total_transactions": 0,
                "spike_count": 0,
            }

        total_tx = len(transactions)
        spikes = [tx for tx in transactions if tx.latency_ms >= self.spike_threshold_ms]
        spike_count = len(spikes)
        spike_pct = (spike_count / total_tx * 100.0) if total_tx > 0 else 0.0

        if spike_count == 0:
            return {
                "association_level": CFSAssociationLevel.NO_DETECTABLE_ASSOCIATION.value,
                "reason": f"No latency spikes exceeding {self.spike_threshold_ms}ms observed.",
                "total_transactions": total_tx,
                "spike_count": 0,
                "spike_percentage": 0.0,
            }

        # 1. Cluster Spikes by Timestamp to detect simultaneous multi-client stalls
        spikes_sorted = sorted(spikes, key=lambda x: x.epoch_timestamp_sec)

        clusters: List[List[TransactionRecord]] = []
        curr_cluster: List[TransactionRecord] = [spikes_sorted[0]]

        for i in range(1, len(spikes_sorted)):
            tx = spikes_sorted[i]
            if (tx.epoch_timestamp_sec - curr_cluster[0].epoch_timestamp_sec) * 1000.0 <= 1.5:
                curr_cluster.append(tx)
            else:
                clusters.append(curr_cluster)
                curr_cluster = [tx]
        if curr_cluster:
            clusters.append(curr_cluster)

        # 2. Inter-cluster intervals (time between successive throttling releases)
        cluster_times = [float(np.mean([tx.epoch_timestamp_sec for tx in c])) for c in clusters]
        inter_cluster_intervals_ms = [
            (cluster_times[i] - cluster_times[i - 1]) * 1000.0
            for i in range(1, len(cluster_times))
        ]

        median_interval_ms = (
            float(np.median(inter_cluster_intervals_ms)) if inter_cluster_intervals_ms else 0.0
        )

        matching_period_count = sum(
            1 for iv in inter_cluster_intervals_ms
            if abs(iv - self.cfs_period_ms) <= self.tolerance_ms
        )
        period_alignment_pct = (
            (matching_period_count / len(inter_cluster_intervals_ms) * 100.0)
            if inter_cluster_intervals_ms
            else 0.0
        )

        distinct_clients_in_tx = len(set(tx.client_id for tx in transactions))
        synchronized_clusters = sum(
            1 for c in clusters
            if len(set(tx.client_id for tx in c)) >= min(distinct_clients_in_tx, 2)
        )
        sync_cluster_pct = (
            (synchronized_clusters / len(clusters) * 100.0)
            if clusters
            else 0.0
        )

        # 3. Correlation with Cgroup Throttling Telemetry
        throttling_events_total = 0
        samples_with_throttling = 0
        if cgroup_samples:
            for s in cgroup_samples:
                throt = s.get("cgroup_nr_throttled", 0) or 0
                if throt > 0:
                    samples_with_throttling += 1
            if len(cgroup_samples) >= 2:
                s0 = cgroup_samples[0].get("cgroup_nr_throttled", 0) or 0
                s1 = cgroup_samples[-1].get("cgroup_nr_throttled", 0) or 0
                throttling_events_total = max(0, s1 - s0)

        # 4. Rigorous Association Classification with Controlled Causal Guardrail (FIX 07)
        intervention_valid, intervention_reason = verify_controlled_intervention(controlled_intervention)

        if has_controlled_experiment_confirmation and not intervention_valid:
            logger.debug(
                f"CFSCorrelationAnalyzer: has_controlled_experiment_confirmation=True provided without valid "
                f"controlled_intervention ({intervention_reason}). Retaining correlation-only classification."
            )

        association_level = CFSAssociationLevel.NO_DETECTABLE_ASSOCIATION
        justification = ""

        if period_alignment_pct >= 90.0 and sync_cluster_pct >= 80.0:
            if intervention_valid:
                association_level = CFSAssociationLevel.CONTROLLED_CAUSAL_EVIDENCE
                justification = (
                    f"Strong temporal alignment ({period_alignment_pct:.1f}% matching 100ms period) and multi-client "
                    f"synchronization ({sync_cluster_pct:.1f}%) combined with verified controlled variable manipulation "
                    f"({intervention_reason}) establishes demonstrated causal mechanism."
                )
            else:
                association_level = CFSAssociationLevel.STRONG_TEMPORAL_ASSOCIATION
                justification = (
                    f"Observed spikes align with 100ms CFS period ({period_alignment_pct:.1f}% match) and "
                    f"demonstrate simultaneous multi-client thread freezes ({sync_cluster_pct:.1f}% synchronized). "
                    f"Establishes strong temporal association. Causal validation requires verified controlled quota manipulation: {intervention_reason}"
                )
        elif period_alignment_pct >= 50.0 or (samples_with_throttling > 0 and spike_count > 0):
            association_level = CFSAssociationLevel.TEMPORAL_ASSOCIATION
            justification = (
                f"Latency spikes coincide with periods of cgroup throttling ({samples_with_throttling} throttled samples), "
                f"but lack strict 100ms periodicity ({period_alignment_pct:.1f}% match) or client synchronization."
            )
        else:
            association_level = CFSAssociationLevel.NO_DETECTABLE_ASSOCIATION
            justification = (
                f"Spikes do not exhibit 100ms CFS periodicity ({period_alignment_pct:.1f}% match) and do not "
                f"correlate with cgroup throttling event progression."
            )

        return {
            "association_level": association_level.value,
            "justification": justification,
            "total_transactions": total_tx,
            "spike_count": spike_count,
            "spike_percentage": round(spike_pct, 3),
            "cluster_count": len(clusters),
            "multi_client_cluster_count": synchronized_clusters,
            "median_inter_cluster_interval_ms": round(median_interval_ms, 2),
            "period_alignment_pct": round(period_alignment_pct, 1),
            "synchronized_multi_client_cluster_pct": round(sync_cluster_pct, 1),
            "throttling_telemetry": {
                "cgroup_samples_count": len(cgroup_samples),
                "samples_with_throttling": samples_with_throttling,
                "delta_throttling_events": throttling_events_total,
            },
            "controlled_intervention_evaluation": {
                "verified": intervention_valid,
                "reason": intervention_reason,
            },
            "methodological_guards": {
                "individual_client_waiting_time_inferred_from_aggregate": False,
                "aggregate_throttled_usec_divided_by_client_count": False,
            },
        }
