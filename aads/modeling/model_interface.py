"""
Performance Model Interface.
Predicts intrinsic component service time (excluding external queue waiting time)
along with uncertainty estimates and out-of-range extrapolation flags.
"""
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class ComponentPerformanceModel(ABC):
    """Abstract base class for component service demand models."""

    @abstractmethod
    def predict_service_time_ms(
        self,
        op_type: str,
        concurrency: int = 1,
        offered_rps: float = 100.0,
    ) -> Tuple[float, float, bool]:
        """
        Predict service time in milliseconds.
        Returns:
            service_time_ms: estimated pure service duration for the discrete event
            uncertainty_std_ms: standard error / confidence interval half-width
            is_extrapolated: boolean flag indicating if query is outside supported operating bounds
        """
        pass

    @abstractmethod
    def get_supported_ranges(self) -> Dict[str, Tuple[float, float]]:
        """Return min and max supported operating ranges for (rps, concurrency)."""
        pass
