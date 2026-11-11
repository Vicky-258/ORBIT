"""
Empirical Lookup and Table Interpolation Candidate Model (Phase 4F.5).

Non-parametric baseline model that indexes empirical observation distributions at 1.0 and 2.0 vCPU,
providing exact sample means and sample standard deviations (ddof=1) with linear interpolation
between verified operating points and explicit extrapolation penalties.
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


class EmpiricalLookupModel(BaseEmpiricalPostgresModel):
    """
    Non-parametric lookup and bounded interpolation performance model.
    """

    def __init__(
        self,
        model_id: str,
        workload_profile: WorkloadProfile,
        version: str = "1.0.0-lookup",
        provenance: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_id, workload_profile, version, provenance)
        self.anchors: Dict[float, Dict[str, Dict[str, float]]] = {}
        self.observations_count: int = 0

    def fit(self, observations: List[TrialObservation]) -> "EmpiricalLookupModel":
        """Aggregates empirical observations into 1.0 and 2.0 vCPU anchor statistics."""
        matching = [
            o for o in observations
            if o.workload_profile == (self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile))
        ]
        if not matching:
            raise ValueError(f"No matching observations for workload profile '{self.workload_profile}'")

        self.observations_count = len(matching)
        quotas = sorted(list(set(o.cpu_quota_cores for o in matching)))

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
                mean_val = float(np.mean(vals))
                sample_std = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                self.anchors[q][k] = {
                    "mean": mean_val,
                    "sample_std": sample_std,
                    "min": float(np.min(vals)),
                    "max": float(np.max(vals)),
                    "replications": len(vals),
                }

        self.min_cpu_quota = min(quotas)
        self.max_cpu_quota = max(quotas)
        return self

    def _interpolate_metric(
        self,
        key: str,
        cpu_quota: float,
        evidence_status: EvidenceStatus,
        is_extrapolated: bool,
    ) -> MetricPrediction:
        """
        Interpolates metric between 1.0 and 2.0 anchors with epistemological uncertainty typing.
        - OBSERVED: Sample std (ddof=1) across replications with formal small-sample confidence bounds.
        - INTERPOLATED: Heuristic interpolation uncertainty; NEVER labelled statistical confidence interval.
        - OUT_OF_RANGE: Heuristic distance multiplier; NEVER labelled statistical confidence interval.
        - INSUFFICIENT_EVIDENCE: Returns UNAVAILABLE (None) uncertainty.
        """
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
        stats1 = self.anchors[q1][key]
        stats2 = self.anchors[q2][key]

        m1, s1 = stats1["mean"], stats1["sample_std"]
        m2, s2 = stats2["mean"], stats2["sample_std"]

        # Linear interpolation factor
        alpha = (cpu_quota - q1) / max(0.0001, (q2 - q1))
        point = (1.0 - alpha) * m1 + alpha * m2
        point = max(0.0, point)

        metric_notes: List[str] = []

        if evidence_status == EvidenceStatus.OBSERVED:
            # Exact anchor match: variance is directly measured sample variance
            q_matched = q1 if abs(cpu_quota - q1) < 1e-4 else q2
            s_obs = self.anchors[q_matched][key]["sample_std"]
            ci_lower = max(0.0, point - 1.96 * s_obs)
            ci_upper = point + 1.96 * s_obs
            return MetricPrediction(
                point_estimate=round(point, 4),
                uncertainty_std=round(s_obs, 4),
                uncertainty_type=UncertaintyType.REPLICATION_SAMPLE_STD,
                is_heuristic=False,
                confidence_interval_95=(round(ci_lower, 4), round(ci_upper, 4)),
                heuristic_interval=None,
                heuristic_multiplier=None,
                notes=["Replication uncertainty measured from N=3 independent trials (ddof=1)."],
            )

        elif evidence_status == EvidenceStatus.INTERPOLATED:
            # Interpolation uncertainty: heuristic linear variance interpolation
            base_var = ((1.0 - alpha) ** 2) * (s1 ** 2) + (alpha ** 2) * (s2 ** 2)
            uncertainty = math.sqrt(max(1e-6, base_var))
            h_lower = max(0.0, point - 1.96 * uncertainty)
            h_upper = point + 1.96 * uncertainty
            metric_notes.append(
                "Interpolation assumption between observed endpoints. Heuristic uncertainty bounds; not a calibrated statistical confidence interval."
            )
            return MetricPrediction(
                point_estimate=round(point, 4),
                uncertainty_std=round(uncertainty, 4),
                uncertainty_type=UncertaintyType.INTERPOLATION_HEURISTIC,
                is_heuristic=True,
                confidence_interval_95=None,  # Never label heuristic intervals as statistical CIs
                heuristic_interval=(round(h_lower, 4), round(h_upper, 4)),
                heuristic_multiplier=1.0,
                notes=metric_notes,
            )

        else:  # OUT_OF_RANGE
            base_var = ((1.0 - alpha) ** 2) * (s1 ** 2) + (alpha ** 2) * (s2 ** 2)
            base_unc = math.sqrt(max(1e-6, base_var))
            distance = max(0.0, q1 - cpu_quota, cpu_quota - q2)
            penalty_factor = 2.0 + (distance * 1.5)
            uncertainty = base_unc * penalty_factor
            h_lower = max(0.0, point - 1.96 * uncertainty)
            h_upper = point + 1.96 * uncertainty
            metric_notes.append(
                f"Extrapolated estimate outside measured support. Applied heuristic distance multiplier ({penalty_factor:.2f}x). Not a statistical confidence interval."
            )
            return MetricPrediction(
                point_estimate=round(point, 4),
                uncertainty_std=round(uncertainty, 4),
                uncertainty_type=UncertaintyType.EXTRAPOLATION_HEURISTIC,
                is_heuristic=True,
                confidence_interval_95=None,  # Never label heuristic multipliers as statistical CIs
                heuristic_interval=(round(h_lower, 4), round(h_upper, 4)),
                heuristic_multiplier=round(penalty_factor, 4),
                notes=metric_notes,
            )

    def predict(self, query: EmpiricalPostgresQuery) -> EmpiricalPostgresPrediction:
        """Executes lookup prediction enforcing Phase 4F.5.1 prediction contract."""
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
                prediction_method="lookup_table",
                measured_support=self.get_measured_support(),
                requested_configuration=query.model_dump(),
                uncertainty=None,
                uncertainty_type=UncertaintyType.UNAVAILABLE,
                limitations=notes,
                identifiability_notes=["Non-parametric lookup candidate model."],
                provenance={
                    **self.provenance,
                    "model_type": "EmpiricalLookupModel",
                    "observations_count": self.observations_count,
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

        # Generate core predictions
        tps = self._interpolate_metric("throughput_tps", query.cpu_quota_cores, evidence_status, is_extrapolated)
        lat_mean = self._interpolate_metric("latency_mean_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p50 = self._interpolate_metric("p50_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p90 = self._interpolate_metric("p90_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p95 = self._interpolate_metric("p95_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p99 = self._interpolate_metric("p99_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        p999 = self._interpolate_metric("p999_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        max_lat = self._interpolate_metric("max_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
        cpu_util = self._interpolate_metric("cpu_utilization_pct", query.cpu_quota_cores, evidence_status, is_extrapolated)

        # Workload-specific telemetry
        throt_freq = None
        throt_sec = None
        wal_sec = None
        wal_sync = None
        locks = None

        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            throt_freq = self._interpolate_metric("throttling_frequency_pct", query.cpu_quota_cores, evidence_status, is_extrapolated)
            throt_sec = self._interpolate_metric("throttled_seconds", query.cpu_quota_cores, evidence_status, is_extrapolated)
        else:
            wal_bytes = self._interpolate_metric("wal_bytes", query.cpu_quota_cores, evidence_status, is_extrapolated)
            # Duration is 30.0s for WAL rate calculation
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
            wal_sync = self._interpolate_metric("wal_sync_time_ms", query.cpu_quota_cores, evidence_status, is_extrapolated)
            locks = self._interpolate_metric("observed_lock_waits", query.cpu_quota_cores, evidence_status, is_extrapolated)

        # Map state to ModelState enum for backward compatibility
        legacy_state = ModelState(evidence_status.value)

        return EmpiricalPostgresPrediction(
            evidence_status=evidence_status,
            prediction_method="lookup_table",
            measured_support=self.get_measured_support(),
            requested_configuration=query.model_dump(),
            uncertainty=lat_mean.uncertainty_std,
            uncertainty_type=lat_mean.uncertainty_type,
            limitations=notes,
            identifiability_notes=["Non-parametric lookup model directly indexes empirical distribution means and sample variances."],
            provenance={
                **self.provenance,
                "model_type": "EmpiricalLookupModel",
                "observations_count": self.observations_count,
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
            "model_type": "EmpiricalLookupModel",
            "model_id": self.model_id,
            "workload_profile": self.workload_profile.value,
            "version": self.version,
            "min_cpu_quota": self.min_cpu_quota,
            "max_cpu_quota": self.max_cpu_quota,
            "supported_concurrency": self.supported_concurrency,
            "supported_scale_factor": self.supported_scale_factor,
            "supported_memory_mb": self.supported_memory_mb,
            "anchors": self.anchors,
            "observations_count": self.observations_count,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmpiricalLookupModel":
        model = cls(
            model_id=data["model_id"],
            workload_profile=WorkloadProfile(data["workload_profile"]),
            version=data.get("version", "1.0.0-lookup"),
            provenance=data.get("provenance", {}),
        )
        model.min_cpu_quota = data.get("min_cpu_quota", 1.0)
        model.max_cpu_quota = data.get("max_cpu_quota", 2.0)
        model.supported_concurrency = data.get("supported_concurrency", 8)
        model.supported_scale_factor = data.get("supported_scale_factor", 2)
        model.supported_memory_mb = data.get("supported_memory_mb", 1024.0)
        # Reconstruct float keys for anchors dictionary
        model.anchors = {float(k): v for k, v in data.get("anchors", {}).items()}
        model.observations_count = data.get("observations_count", 0)
        return model
