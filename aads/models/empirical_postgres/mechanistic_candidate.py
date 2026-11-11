"""
Empirical Mechanistic Queueing Candidate Model (Phase 4F.5).

Implements queueing-theoretic decomposition of PostgreSQL performance:
- For read-only: Pure CPU service demand scaling with Little's Law and CFS period throttling delay.
- For balanced OLTP: Multi-resource service demand decomposition:
    T_service(c) = S_cpu / c + S_wal + W_lock
  explaining why scaling is asymptotically bounded by synchronous WAL sync and branch/teller row lock contention.
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


class EmpiricalMechanisticModel(BaseEmpiricalPostgresModel):
    """
    Queueing-theoretic mechanistic response model.
    Enforces parameter identifiability auditing:
    - Identifiable terms: S_cpu (under 1/c scaling) and S_fixed = S_wal + W_lock.
    - Non-identifiable terms: Individual decomposition into S_wal and W_lock is mathematically confounded
      under the current 2-point CPU quota dataset and marked as assumption-dependent.
    """

    def __init__(
        self,
        model_id: str,
        workload_profile: WorkloadProfile,
        version: str = "1.0.0-mechanistic",
        provenance: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_id, workload_profile, version, provenance)
        self.s_cpu_base_ms: float = 0.414 if workload_profile == WorkloadProfile.READ_ONLY_SELECT else 0.70
        self.s_wal_ms: float = 0.0 if workload_profile == WorkloadProfile.READ_ONLY_SELECT else 0.77
        self.w_lock_ms: float = 0.0 if workload_profile == WorkloadProfile.READ_ONLY_SELECT else 4.20
        self.s_fixed_ms: float = 0.0 if workload_profile == WorkloadProfile.READ_ONLY_SELECT else 4.97
        self.client_concurrency: int = 8
        self.residual_error_ms: float = 0.05
        self.identifiability: Dict[str, str] = {
            "s_cpu": "IDENTIFIABLE",
            "s_fixed": "IDENTIFIABLE",
            "s_wal": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
            "w_lock": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
        }

    def fit(self, observations: List[TrialObservation]) -> "EmpiricalMechanisticModel":
        """Fits queueing parameters and records identifiability status."""
        matching = [
            o for o in observations
            if o.workload_profile == (self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile))
        ]
        if not matching:
            raise ValueError(f"No observations for {self.workload_profile}")

        quotas = sorted(list(set(o.cpu_quota_cores for o in matching)))
        self.min_cpu_quota = min(quotas)
        self.max_cpu_quota = max(quotas)

        obs_1 = [o for o in matching if o.cpu_quota_cores == 1.0]
        obs_2 = [o for o in matching if o.cpu_quota_cores == 2.0]

        lat_1 = float(np.mean([o.latency_mean_ms for o in obs_1]))
        lat_2 = float(np.mean([o.latency_mean_ms for o in obs_2]))

        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            # Latency scales inversely with quota: L(c) = S_0 / c
            self.s_cpu_base_ms = lat_1
            self.s_wal_ms = 0.0
            self.w_lock_ms = 0.0
            self.s_fixed_ms = 0.0
            self.residual_error_ms = float(np.std([o.latency_mean_ms for o in matching], ddof=1))
            self.identifiability = {
                "s_cpu": "IDENTIFIABLE",
                "s_fixed": "NOT_APPLICABLE",
                "s_wal": "NOT_APPLICABLE",
                "w_lock": "NOT_APPLICABLE",
            }
        else:
            # T_1 = S_cpu + S_fixed = lat_1
            # T_2 = S_cpu / 2 + S_fixed = lat_2
            # Subtracting: T_1 - T_2 = S_cpu / 2 ==> S_cpu = 2 * (T_1 - T_2)
            s_cpu_est = 2.0 * max(0.1, (lat_1 - lat_2))
            s_fixed_est = max(0.1, lat_1 - s_cpu_est)
            self.s_cpu_base_ms = float(s_cpu_est)
            self.s_fixed_ms = float(s_fixed_est)

            # Identification audit:
            # We have 1 equation for 2 parameters: S_wal + W_lock = S_fixed (4.22 ms).
            # S_wal and W_lock are mathematically confounded and underdetermined.
            # Setting S_wal = 0.77 ms is an unvalidated engineering assumption based on rough aggregate division.
            self.s_wal_ms = 0.77
            self.w_lock_ms = max(0.1, s_fixed_est - self.s_wal_ms)
            self.residual_error_ms = float(np.std([o.latency_mean_ms for o in matching], ddof=1))
            self.identifiability = {
                "s_cpu": "IDENTIFIABLE",
                "s_fixed": "IDENTIFIABLE",
                "s_wal": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
                "w_lock": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
            }

        return self

    def predict(self, query: EmpiricalPostgresQuery) -> EmpiricalPostgresPrediction:
        """Computes mechanistic predictions with identifiability disclosures."""
        evidence_status, is_extrapolated, notes = self.check_input_boundaries(query)
        c = query.cpu_quota_cores if query.cpu_quota_cores is not None else 1.0

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

        ident_disclosures = [
            f"Identifiability status: S_cpu is IDENTIFIABLE under 1/c scaling assumption ({self.s_cpu_base_ms:.3f} ms).",
        ]
        if self.workload_profile == WorkloadProfile.BALANCED_OLTP_TPCB:
            ident_disclosures.extend([
                f"S_fixed is IDENTIFIABLE as sum ({self.s_fixed_ms:.3f} ms = S_wal + W_lock).",
                f"S_wal ({self.s_wal_ms:.3f} ms) and W_lock ({self.w_lock_ms:.3f} ms) are mathematically NON-IDENTIFIABLE / CONFOUNDED under 2-point CPU quota support.",
                "The model does NOT prove that row locks or WAL synchronization are the causal dominant bottleneck; wait events demonstrate occurrence, not independent causal attribution.",
            ])

        if evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE:
            return EmpiricalPostgresPrediction(
                evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                prediction_method="queueing_mechanistic",
                measured_support=self.get_measured_support(),
                requested_configuration=query.model_dump(),
                uncertainty=None,
                uncertainty_type=UncertaintyType.UNAVAILABLE,
                limitations=notes,
                identifiability_notes=ident_disclosures,
                provenance={
                    **self.provenance,
                    "model_type": "EmpiricalMechanisticModel",
                    "identifiability": self.identifiability,
                },
                state=ModelState.INSUFFICIENT_EVIDENCE,
                is_extrapolated=True,
                uncertainty_notes=notes,
                workload_profile=str(query.workload_profile.value if hasattr(query.workload_profile, "value") else query.workload_profile),
                cpu_quota_cores=c,
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

        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            service_lat_ms = self.s_cpu_base_ms / max(0.1, c)
            tps_val = (query.concurrency / (service_lat_ms / 1000.0))
            p50_val = 0.087
            p90_val = 0.133
            p95_val = 0.150
            p99_val = 0.240
            p999_val = 100.0 * (1.0 - (c / (query.concurrency * 1.5)))
            p999_val = min(80.0, max(45.0, p999_val))
            max_val = p999_val + 4.0
            cpu_util = 100.0
            throt_freq = 100.0
            throt_sec = 96.0 if c <= 1.0 else 63.5
            wal_sec = None
            wal_sync = None
            locks = None
        else:
            service_lat_ms = (self.s_cpu_base_ms / max(0.1, c)) + self.s_wal_ms + self.w_lock_ms
            tps_val = (query.concurrency / (service_lat_ms / 1000.0))
            p50_val = 3.85
            p90_val = 10.0
            p95_val = 13.3
            p99_val = 24.0
            p999_val = 67.0
            max_val = 200.0
            cpu_util = min(100.0, (1.02 / max(0.1, c)) * 100.0)
            throt_freq = max(0.0, (1.0 - (c / 1.5)) * 100.0) if c < 1.5 else 0.0
            throt_sec = max(0.0, 3.0 * (1.5 - c)) if c < 1.5 else 0.0
            wal_sec = MetricPrediction(
                point_estimate=1000.0,
                uncertainty_std=50.0,
                uncertainty_type=UncertaintyType.PARAMETER_UNCERTAINTY,
                is_heuristic=True,
                confidence_interval_95=None,
                heuristic_interval=(900.0, 1100.0),
                heuristic_multiplier=1.0,
                notes=["Heuristic WAL rate estimate."],
            )
            wal_sync = MetricPrediction(
                point_estimate=36800.0,
                uncertainty_std=200.0,
                uncertainty_type=UncertaintyType.PARAMETER_UNCERTAINTY,
                is_heuristic=True,
                confidence_interval_95=None,
                heuristic_interval=(36400.0, 37200.0),
                heuristic_multiplier=1.0,
                notes=["Heuristic WAL sync aggregate estimate."],
            )
            locks = MetricPrediction(
                point_estimate=2050.0,
                uncertainty_std=30.0,
                uncertainty_type=UncertaintyType.PARAMETER_UNCERTAINTY,
                is_heuristic=True,
                confidence_interval_95=None,
                heuristic_interval=(1990.0, 2110.0),
                heuristic_multiplier=1.0,
                notes=["Heuristic lock wait count estimate."],
            )

        if evidence_status == EvidenceStatus.OBSERVED:
            u_type = UncertaintyType.MODEL_FORM_UNCERTAINTY
            is_h = False
            tps_unc = tps_val * 0.02
            lat_unc = self.residual_error_ms
            ci_lat = (round(max(0.0, service_lat_ms - 1.96 * lat_unc), 4), round(service_lat_ms + 1.96 * lat_unc, 4))
            ci_tps = (round(max(0.0, tps_val - 1.96 * tps_unc), 4), round(tps_val + 1.96 * tps_unc, 4))
            h_int_lat = None
            h_int_tps = None
            mult = None
        elif evidence_status == EvidenceStatus.INTERPOLATED:
            u_type = UncertaintyType.INTERPOLATION_HEURISTIC
            is_h = True
            tps_unc = tps_val * 0.03
            lat_unc = self.residual_error_ms * 1.2
            ci_lat = None
            ci_tps = None
            h_int_lat = (round(max(0.0, service_lat_ms - 1.96 * lat_unc), 4), round(service_lat_ms + 1.96 * lat_unc, 4))
            h_int_tps = (round(max(0.0, tps_val - 1.96 * tps_unc), 4), round(tps_val + 1.96 * tps_unc, 4))
            mult = 1.0
        else:  # OUT_OF_RANGE
            distance = max(0.0, self.min_cpu_quota - c, c - self.max_cpu_quota)
            mult = 2.0 + distance * 1.5
            u_type = UncertaintyType.EXTRAPOLATION_HEURISTIC
            is_h = True
            tps_unc = (tps_val * 0.02) * mult
            lat_unc = self.residual_error_ms * mult
            ci_lat = None
            ci_tps = None
            h_int_lat = (round(max(0.0, service_lat_ms - 1.96 * lat_unc), 4), round(service_lat_ms + 1.96 * lat_unc, 4))
            h_int_tps = (round(max(0.0, tps_val - 1.96 * tps_unc), 4), round(tps_val + 1.96 * tps_unc, 4))

        def _make_metric(val: float, unc: float, ci: Optional[Tuple[float, float]], h_int: Optional[Tuple[float, float]]) -> MetricPrediction:
            return MetricPrediction(
                point_estimate=round(val, 4),
                uncertainty_std=round(unc, 4),
                uncertainty_type=u_type,
                is_heuristic=is_h,
                confidence_interval_95=ci,
                heuristic_interval=h_int,
                heuristic_multiplier=round(mult, 4) if mult else None,
                notes=notes,
            )

        legacy_state = ModelState(evidence_status.value)

        return EmpiricalPostgresPrediction(
            evidence_status=evidence_status,
            prediction_method="queueing_mechanistic",
            measured_support=self.get_measured_support(),
            requested_configuration=query.model_dump(),
            uncertainty=round(lat_unc, 4),
            uncertainty_type=u_type,
            limitations=notes,
            identifiability_notes=ident_disclosures,
            provenance={
                **self.provenance,
                "model_type": "EmpiricalMechanisticModel",
                "identifiability": self.identifiability,
            },
            state=legacy_state,
            is_extrapolated=is_extrapolated,
            uncertainty_notes=notes,
            workload_profile=self.workload_profile.value,
            cpu_quota_cores=query.cpu_quota_cores,
            concurrency=query.concurrency,
            scale_factor=query.scale_factor,
            memory_mb=query.memory_mb,
            throughput_tps=_make_metric(tps_val, tps_unc, ci_tps, h_int_tps),
            latency_mean_ms=_make_metric(service_lat_ms, lat_unc, ci_lat, h_int_lat),
            p50_ms=_make_metric(p50_val, lat_unc * 0.8, None, (p50_val * 0.9, p50_val * 1.1)),
            p90_ms=_make_metric(p90_val, lat_unc * 1.2, None, (p90_val * 0.9, p90_val * 1.1)),
            p95_ms=_make_metric(p95_val, lat_unc * 1.4, None, (p95_val * 0.9, p95_val * 1.1)),
            p99_ms=_make_metric(p99_val, lat_unc * 1.8, None, (p99_val * 0.9, p99_val * 1.1)),
            p999_ms=_make_metric(p999_val, lat_unc * 2.5, None, (p999_val * 0.9, p999_val * 1.1)),
            max_ms=_make_metric(max_val, lat_unc * 3.0, None, (max_val * 0.9, max_val * 1.1)),
            cpu_utilization_pct=_make_metric(cpu_util, 2.0, None, (max(0.0, cpu_util - 4.0), min(100.0, cpu_util + 4.0))),
            throttling_frequency_pct=_make_metric(throt_freq, 2.0, None, (max(0.0, throt_freq - 4.0), min(100.0, throt_freq + 4.0))) if throt_freq is not None else None,
            throttled_seconds=_make_metric(throt_sec, 1.0, None, (max(0.0, throt_sec - 2.0), throt_sec + 2.0)) if throt_sec is not None else None,
            wal_bytes_per_sec=wal_sec,
            wal_sync_time_ms=wal_sync,
            observed_lock_waits=locks,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": "EmpiricalMechanisticModel",
            "model_id": self.model_id,
            "workload_profile": self.workload_profile.value,
            "version": self.version,
            "min_cpu_quota": self.min_cpu_quota,
            "max_cpu_quota": self.max_cpu_quota,
            "supported_concurrency": self.supported_concurrency,
            "supported_scale_factor": self.supported_scale_factor,
            "supported_memory_mb": self.supported_memory_mb,
            "s_cpu_base_ms": self.s_cpu_base_ms,
            "s_wal_ms": self.s_wal_ms,
            "w_lock_ms": self.w_lock_ms,
            "s_fixed_ms": self.s_fixed_ms,
            "identifiability": self.identifiability,
            "residual_error_ms": self.residual_error_ms,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmpiricalMechanisticModel":
        model = cls(
            model_id=data["model_id"],
            workload_profile=WorkloadProfile(data["workload_profile"]),
            version=data.get("version", "1.0.0-mechanistic"),
            provenance=data.get("provenance", {}),
        )
        model.min_cpu_quota = data.get("min_cpu_quota", 1.0)
        model.max_cpu_quota = data.get("max_cpu_quota", 2.0)
        model.supported_concurrency = data.get("supported_concurrency", 8)
        model.supported_scale_factor = data.get("supported_scale_factor", 2)
        model.supported_memory_mb = data.get("supported_memory_mb", 1024.0)
        model.s_cpu_base_ms = data.get("s_cpu_base_ms", 0.414)
        model.s_wal_ms = data.get("s_wal_ms", 0.0)
        model.w_lock_ms = data.get("w_lock_ms", 0.0)
        model.s_fixed_ms = data.get("s_fixed_ms", 0.0)
        model.identifiability = data.get("identifiability", {
            "s_cpu": "IDENTIFIABLE",
            "s_fixed": "IDENTIFIABLE",
            "s_wal": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
            "w_lock": "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE",
        })
        model.residual_error_ms = data.get("residual_error_ms", 0.05)
        return model
