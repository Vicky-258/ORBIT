"""
Lookup and Interpolation Performance Model.
Baseline non-parametric model using nearest-neighbor / inverse-distance weighting.
"""
import math
from typing import List, Tuple, Dict, Any
from orbit.modeling.model_interface import ComponentPerformanceModel
from orbit.core.schemas import ExperimentRecord


class LookupInterpolationModel(ComponentPerformanceModel):
    """Baseline lookup and inverse-distance weighted interpolation model."""

    def __init__(self, experiments: List[ExperimentRecord]):
        self.experiments = [e for e in experiments if e.achieved_rps > 0]
        if not self.experiments:
            raise ValueError("Cannot construct LookupModel with empty experiment list")

        self.concurrencies = [e.concurrency for e in self.experiments]
        self.rps_values = [e.achieved_rps for e in self.experiments]

        self.min_concurrency = min(self.concurrencies)
        self.max_concurrency = max(self.concurrencies)
        self.min_rps = min(self.rps_values)
        self.max_rps = max(self.rps_values)

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

        # Separate read vs write service demand scaling
        op_mult = 1.0 if op_type == "read" else 2.2

        # Weighted inverse distance to benchmarked operating points
        weights = []
        estimates = []
        for exp in self.experiments:
            # Normalized Euclidean distance in (concurrency, rps) space
            d_conc = (concurrency - exp.concurrency) / max(1.0, float(self.max_concurrency))
            d_rps = (offered_rps - exp.achieved_rps) / max(1.0, float(self.max_rps))
            dist = math.sqrt(d_conc**2 + d_rps**2) + 1e-5
            w = 1.0 / dist
            weights.append(w)

            # In benchmark, p50 includes some internal queuing;
            # service demand is bounded by Little's Law S <= N / X
            base_service = (exp.concurrency / max(1.0, exp.achieved_rps)) * 1000.0
            # Blend bounded Little's service with measured p50
            est = min(exp.p50_ms, max(0.2, base_service)) * op_mult
            estimates.append(est)

        total_weight = sum(weights)
        pred_service = sum(w * e for w, e in zip(weights, estimates)) / total_weight

        # Uncertainty: base residual standard error + extrapolation penalty
        std_err = 0.15 * pred_service
        if is_extrapolated:
            std_err *= 2.5

        return (max(0.1, round(pred_service, 2)), max(0.05, round(std_err, 2)), is_extrapolated)
