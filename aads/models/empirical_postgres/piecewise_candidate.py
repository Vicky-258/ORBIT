"""
Empirical Piecewise Linear and Threshold Candidate Model (Phase 4F.5).

Models resource saturation knee points:
- For read-only: Models compute-bound scaling where CPU saturation and 100% throttling persist across [1.0, 2.0].
- For balanced OLTP: Models the CPU-to-concurrency transition knee (~1.25 vCPU) where CPU throttling ceases (0%)
  and throughput plateaus due to row lock serialization and WAL commit sync bottlenecks.
"""
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from aads.models.empirical_postgres.base import BaseEmpiricalPostgresModel
from aads.models.empirical_postgres.schemas import (
    EmpiricalPostgresPrediction,
    EmpiricalPostgresQuery,
    EvidenceStatus,
    MetricPrediction,
    ModelState,
    TrialObservation,
    UncertaintyType,
    WorkloadProfile,
)


class EmpiricalPiecewiseModel(BaseEmpiricalPostgresModel):
    """
    Piecewise linear threshold model with saturation knee points.
    """

    def __init__(
        self,
        model_id: str,
        workload_profile: WorkloadProfile,
        version: str = "1.0.0-piecewise",
        provenance: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_id, workload_profile, version, provenance)
        self.knee_cpu: float = 1.25 if workload_profile == WorkloadProfile.BALANCED_OLTP_TPCB else 2.0
        self.segment1_params: Dict[str, Dict[str, float]] = {}
        self.segment2_params: Dict[str, Dict[str, float]] = {}
        self.anchors: Dict[float, Dict[str, Dict[str, float]]] = {}

    def fit(self, observations: List[TrialObservation]) -> "EmpiricalPiecewiseModel":
        """Fits piecewise parameters from empirical observations."""
        matching = [
            o for o in observations
            if o.workload_profile == (self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile))
        ]
        if not matching:
            raise ValueError(f"No observations for {self.workload_profile}")

        quotas = sorted(list(set(o.cpu_quota_cores for o in matching)))
        self.min_cpu_quota = min(quotas)
        self.max_cpu_quota = max(quotas)

        # Baseline anchor stats at 1.0 and 2.0
        metrics_keys = [
            "throughput_tps", "latency_mean_ms", "p50_ms", "p90_ms", "p95_ms",
            "p99_ms", "p999_ms", "max_ms", "cpu_utilization_pct", "throttling_frequency_pct",
            "throttled_seconds", "wal_bytes", "wal_sync_time_ms", "observed_lock_waits",
        ]
        self.anchors = {}
        for q in quotas:
            q_obs = [o for o in matching if o.cpu_quota_cores == q]
            self.anchors[q] = {}
            for k in metrics_keys:
                vals = [getattr(o, k) for o in q_obs]
                self.anchors[q][k] = {
                    "mean": float(np.mean(vals)),
                    "sample_std": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                }

        # Knee estimation:
        # In TPC-B, CPU demand is ~1.02 cores total.
        # When quota > 1.02, CPU is no longer 100% utilized and throttling drops to 0.
        # Estimated knee is where CPU quota equals peak core demand (~1.25 vCPU).
        if self.workload_profile == WorkloadProfile.BALANCED_OLTP_TPCB:
            self.knee_cpu = 1.25
        else:
            self.knee_cpu = 2.0  # Read-only remains CPU-bound throughout

        return self

    def _predict_piecewise(
        self,
        key: str,
        cpu_quota: float,
        evidence_status: EvidenceStatus,
        is_extrapolated: bool,
    ) -> MetricPrediction:
        """Evaluates piecewise linear curve with knee saturation and explicit uncertainty types."""
        if evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return MetricPrediction(
                point_estimate=None,
                uncertainty_std=None,
                uncertainty_type=UncertaintyType.UNAVAILABLE,
                is_heuristic=False,
                confidence_interval_95=None,
                notes=["Prediction unavailable due to insufficient evidence."],
            )

        q1 = self.min_cpu_quota
        q2 = self.max_cpu_quota
        v1 = self.anchors[q1][key]["mean"]
        v2 = self.anchors[q2][key]["mean"]
        s1 = self.anchors[q1][key]["sample_std"]
        s2 = self.anchors[q2][key]["sample_std"]

        metric_notes: List[str] = []

        if evidence_status == EvidenceStatus.OBSERVED:
            q_matched = q1 if abs(cpu_quota - q1) < 1e-4 else q2
            val = self.anchors[q_matched][key]["mean"]
            s_obs = self.anchors[q_matched][key]["sample_std"]
            ci_lower = max(0.0, val - 1.96 * s_obs)
            ci_upper = val + 1.96 * s_obs
            return MetricPrediction(
                point_estimate=round(val, 4),
                uncertainty_std=round(s_obs, 4),
                uncertainty_type=UncertaintyType.REPLICATION_SAMPLE_STD,
                is_heuristic=False,
                confidence_interval_95=(round(ci_lower, 4), round(ci_upper, 4)),
                heuristic_interval=None,
                heuristic_multiplier=None,
                notes=["Replication uncertainty measured from N=3 independent trials (ddof=1)."],
            )

        # Interpolated or Extrapolated
        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            alpha = (cpu_quota - q1) / max(0.001, (q2 - q1))
            val = (1.0 - alpha) * v1 + alpha * v2
            uncertainty = math.sqrt(((1.0 - alpha) ** 2) * (s1 ** 2) + (alpha ** 2) * (s2 ** 2))
        else:
            knee = self.knee_cpu
            v_knee = v1 + 0.70 * (v2 - v1)
            s_knee = math.sqrt(0.5 * s1 ** 2 + 0.5 * s2 ** 2)

            if cpu_quota <= knee:
                alpha = (cpu_quota - q1) / max(0.001, (knee - q1))
                val = (1.0 - alpha) * v1 + alpha * v_knee
                uncertainty = math.sqrt(((1.0 - alpha) ** 2) * (s1 ** 2) + (alpha ** 2) * (s_knee ** 2))
            else:
                alpha = (cpu_quota - knee) / max(0.001, (q2 - knee))
                val = (1.0 - alpha) * v_knee + alpha * v2
                uncertainty = math.sqrt(((1.0 - alpha) ** 2) * (s_knee ** 2) + (alpha ** 2) * (s2 ** 2))

        val = max(0.0, val)

        if evidence_status == EvidenceStatus.INTERPOLATED:
            h_lower = max(0.0, val - 1.96 * uncertainty)
            h_upper = val + 1.96 * uncertainty
            metric_notes.append(
                f"Interpolated estimate with hypothesized knee at {self.knee_cpu:.2f} vCPU. Not a calibrated statistical confidence interval."
            )
            return MetricPrediction(
                point_estimate=round(val, 4),
                uncertainty_std=round(uncertainty, 4),
                uncertainty_type=UncertaintyType.INTERPOLATION_HEURISTIC,
                is_heuristic=True,
                confidence_interval_95=None,
                heuristic_interval=(round(h_lower, 4), round(h_upper, 4)),
                heuristic_multiplier=1.0,
                notes=metric_notes,
            )

        else:  # OUT_OF_RANGE
            distance = max(0.0, q1 - cpu_quota, cpu_quota - q2)
            penalty_factor = 2.0 + distance * 1.5
            uncertainty *= penalty_factor
            h_lower = max(0.0, val - 1.96 * uncertainty)
            h_upper = val + 1.96 * uncertainty
            metric_notes.append(
                f"Extrapolated estimate outside measured support. Applied heuristic distance multiplier ({penalty_factor:.2f}x). Not a statistical confidence interval."
            )
            return MetricPrediction(
                point_estimate=round(val, 4),
                uncertainty_std=round(uncertainty, 4),
                uncertainty_type=UncertaintyType.EXTRAPOLATION_HEURISTIC,
                is_heuristic=True,
                confidence_interval_95=None,
                heuristic_interval=(round(h_lower, 4), round(h_upper, 4)),
                heuristic_multiplier=round(penalty_factor, 4),
                notes=metric_notes,
            )

    def predict(self, query: EmpiricalPostgresQuery) -> EmpiricalPostgresPrediction:
        """Executes piecewise model prediction."""
        if not self.anchors:
            raise RuntimeError("Model must be fitted before calling predict().")

        evidence_status, is_extrapolated, notes = self.check_input_boundaries(query)

        def _empty_metric() -> MetricPrediction:
            return MetricPrediction(
                point_estimate=None,
                uncertainty_std=None,
                uncertainty_type=UncertaintyType.UNAVAILABLE,
                is_heuristic=False,
                confidence_interval_95=None,
                heuristic_interval=None,
                notes=notes,
            )

        if evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return EmpiricalPostgresPrediction(
                evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                prediction_method="piecewise_linear",
                measured_support=self.get_measured_support(),
                requested_configuration=query.model_dump(),
                uncertainty=None,
                uncertainty_type=UncertaintyType.UNAVAILABLE,
                limitations=notes,
                identifiability_notes=["Piecewise saturation model; knee point is an unvalidated engineering hypothesis."],
                provenance={
                    **self.provenance,
                    "model_type": "EmpiricalPiecewiseModel",
                },
                state=ModelState.INSUFFICIENT_EVIDENCE,
                is_extrapolated=True,
                uncertainty_notes=notes,
                workload_profile=str(query.workload_profile.value if hasattr(query.workload_profile, "value") else query.workload_profile),
                cpu_quota_cores=query.cpu_quota_cores if query.cpu_quota_cores is not None else 0.0,
                concurrency=query.concurrency,
                scale_factor=query.scale_factor,
                memory_mb=query.memory_mb,
                throughput_tps=_empty_metric(),
                latency_mean_ms=_empty_metric(),
                p50_ms=_empty_metric(),
                p90_ms=_empty_metric(),
                p95_ms=_empty_metric(),
                p99_ms=_empty_metric(),
                p999_ms=_empty_metric(),
                max_ms=_empty_metric(),
                cpu_utilization_pct=_empty_metric(),
            )

        tps = self._predict_piecewise("throughput_tps", query.cpu_quota_cores, evidence_status, is_extrapolated)
        lat_mean = self._predict_piecewise("latency_mean_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p50 = self._predict_piecewise("p50_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p90 = self._predict_piecewise("p90_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p95 = self._predict_piecewise("p95_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p99 = self._predict_piecewise("p99_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p999 = self._predict_piecewise("p999_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        max_lat = self._predict_piecewise("max_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        cpu_util = self._predict_piecewise("cpu_utilization_pct", query.cpu_quota_cores, evidence_status, is_extrapolated)

        throt_freq = None
        throt_sec = None
        wal_sec = None
        wal_sync = None
        locks = None

        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            throt_freq = self._predict_piecewise("throttling_frequency_pct", query.cpu_quota_cores, evidence_status, is_extrapolated)
            throt_sec = self._predict_piecewise("throttled_seconds", query.cpu_quota_cores, evidence_status, is_extrapolated)
        else:
            wal_bytes = self._predict_piecewise("wal_bytes", query.cpu_quota_cores, evidence_status, is_extrapolated)
            wal_sec = MetricPrediction(
                point_estimate=round(wal_bytes.point_estimate / 30.0, 2) if wal_bytes.point_estimate is not None else None,
                uncertainty_std=round(wal_bytes.uncertainty_std / 30.0, 2) if wal_bytes.uncertainty_std is not None else None,
                uncertainty_type=wal_bytes.uncertainty_type,
                is_heuristic=wal_bytes.is_heuristic,
                confidence_interval_95=(
                    round(wal_bytes.confidence_interval_95[0] / 30.0, 2),
                    round(wal_bytes.confidence_interval_95[1] / 30.0, 2),
                ) if wal_bytes.confidence_interval_95 else None,
                heuristic_interval=(
                    round(wal_bytes.heuristic_interval[0] / 30.0, 2),
                    round(wal_bytes.heuristic_interval[1] / 30.0, 2),
                ) if wal_bytes.heuristic_interval else None,
                heuristic_multiplier=wal_bytes.heuristic_multiplier,
                notes=wal_bytes.notes,
            )
            wal_sync = self._predict_piecewise("wal_sync_time_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
            locks = self._predict_piecewise("observed_lock_waits", query.cpu_quota_cores, evidence_status, is_extrapolated)

        legacy_state = ModelState(evidence_status.value)

        return EmpiricalPostgresPrediction(
            evidence_status=evidence_status,
            prediction_method="piecewise_linear",
            measured_support=self.get_measured_support(),
            requested_configuration=query.model_dump(),
            uncertainty=lat_mean.uncertainty_std,
            uncertainty_type=lat_mean.uncertainty_type,
            limitations=notes,
            identifiability_notes=[
                f"Piecewise model with knee at {self.knee_cpu:.2f} vCPU. Note: Knee location is an engineering hypothesis; "
                "the 2-point empirical dataset cannot distinguish linear from piecewise transition shapes."
            ],
            provenance={
                **self.provenance,
                "model_type": "EmpiricalPiecewiseModel",
                "knee_cpu": self.knee_cpu,
            },
            state=legacy_state,
            is_extrapolated=is_extrapolated,
            uncertainty_notes=notes,
            workload_profile=self.workload_profile.value,
            cpu_quota_cores=query.cpu_quota_cores,
            concurrency=query.concurrency,
            scale_factor=query.scale_factor,
            memory_mb=query.memory_mb,
            throughput_tps=tps,
            latency_mean_ms=lat_mean,
            p50_ms=p50,
            p90_ms=p90,
            p95_ms=p95,
            p99_ms=p99,
            p999_ms=p999,
            max_ms=max_lat,
            cpu_utilization_pct=cpu_util,
            throttling_frequency_pct=throt_freq,
            throttled_seconds=throt_sec,
            wal_bytes_per_sec=wal_sec,
            wal_sync_time_ms=wal_sync,
            observed_lock_waits=locks,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": "EmpiricalPiecewiseModel",
            "model_id": self.model_id,
            "workload_profile": self.workload_profile.value,
            "version": self.version,
            "min_cpu_quota": self.min_cpu_quota,
            "max_cpu_quota": self.max_cpu_quota,
            "supported_concurrency": self.supported_concurrency,
            "supported_scale_factor": self.supported_scale_factor,
            "supported_memory_mb": self.supported_memory_mb,
            "knee_cpu": self.knee_cpu,
            "anchors": self.anchors,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmpiricalPiecewiseModel":
        model = cls(
            model_id=data["model_id"],
            workload_profile=WorkloadProfile(data["workload_profile"]),
            version=data.get("version", "1.0.0-piecewise"),
            provenance=data.get("provenance", {}),
        )
        model.min_cpu_quota = data.get("min_cpu_quota", 1.0)
        model.max_cpu_quota = data.get("max_cpu_quota", 2.0)
        model.supported_concurrency = data.get("supported_concurrency", 8)
        model.supported_scale_factor = data.get("supported_scale_factor", 2)
        model.supported_memory_mb = data.get("supported_memory_mb", 1024.0)
        model.knee_cpu = data.get("knee_cpu", 1.25)
        model.anchors = {float(k): v for k, v in data.get("anchors", {}).items()}
        return model
