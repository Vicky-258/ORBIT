"""
Empirical Linear Regression Candidate Model (Phase 4F.5).

Fits parametric ordinary least squares linear response models for performance metrics
as a function of CPU quota across the 6 empirical replications for each workload.
Computes analytical slopes, intercepts, and prediction standard errors.
"""
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from aads.models.empirical_postgres.base import BaseEmpiricalPostgresModel
from aads.models.empirical_postgres.schemas import (
    EmpiricalPostgresPrediction,
    EmpiricalPostgresQuery,
    MetricPrediction,
    ModelState,
    TrialObservation,
    WorkloadProfile,
)


class EmpiricalLinearRegressionModel(BaseEmpiricalPostgresModel):
    """
    Parametric linear regression performance model.
    """

    def __init__(
        self,
        model_id: str,
        workload_profile: WorkloadProfile,
        version: str = "1.0.0-linear",
        provenance: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model_id, workload_profile, version, provenance)
        self.equations: Dict[str, Dict[str, float]] = {}
        self.x_mean: float = 1.5
        self.ss_x: float = 1.5  # sum((x - x_mean)^2) for [1,1,1, 2,2,2]
        self.n_samples: int = 6

    def fit(self, observations: List[TrialObservation]) -> "EmpiricalLinearRegressionModel":
        """Fits OLS linear equations for all performance metrics against CPU quota."""
        matching = [
            o for o in observations
            if o.workload_profile == (self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile))
        ]
        if len(matching) < 2:
            raise ValueError(f"Need at least 2 observations to fit linear regression for {self.workload_profile}")

        self.n_samples = len(matching)
        x_vals = np.array([o.cpu_quota_cores for o in matching], dtype=np.float64)
        self.x_mean = float(np.mean(x_vals))
        self.ss_x = float(np.sum((x_vals - self.x_mean) ** 2))
        if self.ss_x <= 0:
            raise ValueError("All CPU quota observations are identical; cannot fit regression slope.")

        metrics_keys = [
            "throughput_tps", "latency_mean_ms", "p50_ms", "p90_ms", "p95_ms",
            "p99_ms", "p999_ms", "max_ms", "cpu_utilization_pct", "throttling_frequency_pct",
            "throttled_seconds", "wal_bytes", "wal_sync_time_ms", "observed_lock_waits",
        ]

        self.equations = {}
        for k in metrics_keys:
            y_vals = np.array([getattr(o, k) for o in matching], dtype=np.float64)
            y_mean = float(np.mean(y_vals))

            # Slope beta_1 = sum((x - x_bar)(y - y_bar)) / sum((x - x_bar)^2)
            slope = float(np.sum((x_vals - self.x_mean) * (y_vals - y_mean)) / self.ss_x)
            intercept = y_mean - slope * self.x_mean

            # Residual standard error
            preds = intercept + slope * x_vals
            residuals = y_vals - preds
            dof = max(1, self.n_samples - 2)
            residual_std = float(np.sqrt(np.sum(residuals ** 2) / dof))

            self.equations[k] = {
                "slope": slope,
                "intercept": intercept,
                "residual_std": residual_std,
                "r2_training": float(1.0 - (np.sum(residuals ** 2) / max(1e-9, np.sum((y_vals - y_mean) ** 2)))),
            }

        self.min_cpu_quota = float(np.min(x_vals))
        self.max_cpu_quota = float(np.max(x_vals))
        return self

    def _predict_metric(self, key: str, cpu_quota: float, is_extrapolated: bool) -> MetricPrediction:
        """Evaluates linear regression equation with prediction standard error."""
        eq = self.equations[key]
        slope = eq["slope"]
        intercept = eq["intercept"]
        s_e = eq["residual_std"]

        point = intercept + slope * cpu_quota
        point = max(0.0, point)

        # Standard error of prediction at x_0: s_e * sqrt(1 + 1/N + (x_0 - x_bar)^2 / SS_x)
        leverage = (1.0 / self.n_samples) + (((cpu_quota - self.x_mean) ** 2) / max(0.001, self.ss_x))
        se_pred = max(0.001, s_e * math.sqrt(1.0 + leverage))

        if is_extrapolated:
            distance = max(0.0, self.min_cpu_quota - cpu_quota, cpu_quota - self.max_cpu_quota)
            penalty_factor = 2.0 + (distance * 1.5)
            se_pred *= penalty_factor

        ci_lower = max(0.0, point - 1.96 * se_pred)
        ci_upper = point + 1.96 * se_pred

        return MetricPrediction(
            point_estimate=round(point, 4),
            uncertainty_std=round(se_pred, 4),
            confidence_interval_95=(round(ci_lower, 4), round(ci_upper, 4)),
        )

    def predict(self, query: EmpiricalPostgresQuery) -> EmpiricalPostgresPrediction:
        """Executes linear model prediction with boundary enforcement."""
        if not self.equations:
            raise RuntimeError("Model must be fitted before calling predict().")

        state, is_extrapolated, notes = self.check_input_boundaries(query)

        tps = self._predict_metric("throughput_tps", query.cpu_quota_cores, is_extrapolated)
        lat_mean = self._predict_metric("latency_mean_ms", query.cpu_quota_cores, is_extrapolated)
        p50 = self._predict_metric("p50_ms", query.cpu_quota_cores, is_extrapolated)
        p90 = self._predict_metric("p90_ms", query.cpu_quota_cores, is_extrapolated)
        p95 = self._predict_metric("p95_ms", query.cpu_quota_cores, is_extrapolated)
        p99 = self._predict_metric("p99_ms", query.cpu_quota_cores, is_extrapolated)
        p999 = self._predict_metric("p999_ms", query.cpu_quota_cores, is_extrapolated)
        max_lat = self._predict_metric("max_ms", query.cpu_quota_cores, is_extrapolated)
        cpu_util = self._predict_metric("cpu_utilization_pct", query.cpu_quota_cores, is_extrapolated)

        throt_freq = None
        throt_sec = None
        wal_sec = None
        wal_sync = None
        locks = None

        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            throt_freq = self._predict_metric("throttling_frequency_pct", query.cpu_quota_cores, is_extrapolated)
            throt_sec = self._predict_metric("throttled_seconds", query.cpu_quota_cores, is_extrapolated)
        else:
            wal_bytes = self._predict_metric("wal_bytes", query.cpu_quota_cores, is_extrapolated)
            wal_sec = MetricPrediction(
                point_estimate=round(wal_bytes.point_estimate / 30.0, 2),
                uncertainty_std=round(wal_bytes.uncertainty_std / 30.0, 2),
                confidence_interval_95=(
                    round(wal_bytes.confidence_interval_95[0] / 30.0, 2),
                    round(wal_bytes.confidence_interval_95[1] / 30.0, 2),
                ),
            )
            wal_sync = self._predict_metric("wal_sync_time_ms", query.cpu_quota_cores, is_extrapolated)
            locks = self._predict_metric("observed_lock_waits", query.cpu_quota_cores, is_extrapolated)

        return EmpiricalPostgresPrediction(
            state=state,
            is_extrapolated=is_extrapolated,
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
            provenance={
                **self.provenance,
                "model_type": "EmpiricalLinearRegressionModel",
                "n_samples": self.n_samples,
            },
            uncertainty_notes=notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_type": "EmpiricalLinearRegressionModel",
            "model_id": self.model_id,
            "workload_profile": self.workload_profile.value,
            "version": self.version,
            "min_cpu_quota": self.min_cpu_quota,
            "max_cpu_quota": self.max_cpu_quota,
            "supported_concurrency": self.supported_concurrency,
            "supported_scale_factor": self.supported_scale_factor,
            "supported_memory_mb": self.supported_memory_mb,
            "equations": self.equations,
            "x_mean": self.x_mean,
            "ss_x": self.ss_x,
            "n_samples": self.n_samples,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmpiricalLinearRegressionModel":
        model = cls(
            model_id=data["model_id"],
            workload_profile=WorkloadProfile(data["workload_profile"]),
            version=data.get("version", "1.0.0-linear"),
            provenance=data.get("provenance", {}),
        )
        model.min_cpu_quota = data.get("min_cpu_quota", 1.0)
        model.max_cpu_quota = data.get("max_cpu_quota", 2.0)
        model.supported_concurrency = data.get("supported_concurrency", 8)
        model.supported_scale_factor = data.get("supported_scale_factor", 2)
        model.supported_memory_mb = data.get("supported_memory_mb", 1024.0)
        model.equations = data.get("equations", {})
        model.x_mean = data.get("x_mean", 1.5)
        model.ss_x = data.get("ss_x", 1.5)
        model.n_samples = data.get("n_samples", 6)
        return model
