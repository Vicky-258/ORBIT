"""
Regression Performance Model.
Fitted parametric regression model isolating pure service demand from external queueing.
"""
import math
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from aads.modeling.model_interface import ComponentPerformanceModel
from aads.core.schemas import ExperimentRecord


class RegressionPerformanceModel(ComponentPerformanceModel):
    """Ridge regression model for component service time."""

    def __init__(
        self,
        intercept: float,
        coef_concurrency: float,
        coef_log_rps: float,
        coef_is_write: float,
        min_concurrency: int,
        max_concurrency: int,
        min_rps: float,
        max_rps: float,
        rmse: float,
    ):
        self.intercept = intercept
        self.coef_concurrency = coef_concurrency
        self.coef_log_rps = coef_log_rps
        self.coef_is_write = coef_is_write
        self.min_concurrency = min_concurrency
        self.max_concurrency = max_concurrency
        self.min_rps = min_rps
        self.max_rps = max_rps
        self.rmse = rmse

    def get_supported_ranges(self) -> Dict[str, Tuple[float, float]]:
        return {
            "concurrency": (float(self.min_concurrency), float(self.max_concurrency)),
            "rps": (float(self.min_rps), float(self.max_rps)),
        }

    def predict_service_time_ms(
        self,
        op_type: str,
        concurrency: int = 1,
        offered_rps: float = 100.0,
    ) -> Tuple[float, float, bool]:
        is_extrapolated = (
            concurrency < self.min_concurrency
            or concurrency > self.max_concurrency
            or offered_rps < self.min_rps
            or offered_rps > self.max_rps
        )

        is_write = 1.0 if op_type == "write" else 0.0
        log_rps = math.log(max(1.0, offered_rps))

        pred = (
            self.intercept
            + self.coef_concurrency * concurrency
            + self.coef_log_rps * log_rps
            + self.coef_is_write * is_write
        )

        service_ms = max(0.1, pred)
        uncertainty = self.rmse
        if is_extrapolated:
            uncertainty *= 2.5

        return (round(service_ms, 2), round(uncertainty, 2), is_extrapolated)

    @classmethod
    def fit_from_experiments(cls, experiments: List[ExperimentRecord]) -> "RegressionPerformanceModel":
        from sklearn.linear_model import Ridge

        if len(experiments) < 2:
            raise ValueError("Need at least 2 experiment records to fit regression model")

        X = []
        y = []

        concurrencies = [e.concurrency for e in experiments]
        rps_vals = [e.achieved_rps for e in experiments]

        for e in experiments:
            # Service demand decomposition
            base_service = (e.concurrency / max(1.0, e.achieved_rps)) * 1000.0
            isolated_service = min(e.p50_ms, max(0.2, base_service))
            
            # Read sample
            X.append([e.concurrency, math.log(max(1.0, e.achieved_rps)), 0.0])
            y.append(isolated_service)

            # Write sample (estimated from read/write penalty)
            X.append([e.concurrency, math.log(max(1.0, e.achieved_rps)), 1.0])
            y.append(isolated_service * 2.2)

        X_mat = np.array(X)
        y_vec = np.array(y)

        ridge = Ridge(alpha=1.0)
        ridge.fit(X_mat, y_vec)

        preds = ridge.predict(X_mat)
        residuals = y_vec - preds
        rmse = float(np.sqrt(np.mean(residuals**2)))

        return cls(
            intercept=float(ridge.intercept_),
            coef_concurrency=float(ridge.coef_[0]),
            coef_log_rps=float(ridge.coef_[1]),
            coef_is_write=float(ridge.coef_[2]),
            min_concurrency=min(concurrencies),
            max_concurrency=max(concurrencies),
            min_rps=min(rps_vals),
            max_rps=max(rps_vals),
            rmse=rmse,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intercept": self.intercept,
            "coef_concurrency": self.coef_concurrency,
            "coef_log_rps": self.coef_log_rps,
            "coef_is_write": self.coef_is_write,
            "min_concurrency": self.min_concurrency,
            "max_concurrency": self.max_concurrency,
            "min_rps": self.min_rps,
            "max_rps": self.max_rps,
            "rmse": self.rmse,
        }
