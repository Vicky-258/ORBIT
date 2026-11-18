"""
Abstract Benchmark Runner Interface.
Defines contracts for both real Docker-based and synthetic fixture benchmark runners.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from orbit.core.schemas import ExperimentRecord


class BenchmarkRunner(ABC):
    """Abstract base class for executing component benchmark matrices."""

    @abstractmethod
    def run_benchmark_matrix(
        self,
        component_name: str,
        version: str,
        concurrency_levels: Optional[List[int]] = None,
        read_ratios: Optional[List[float]] = None,
        target_rps_levels: Optional[List[float]] = None,
        replications: int = 3,
    ) -> List[ExperimentRecord]:
        """
        Execute controlled measurement trials over a matrix of parameters.
        Returns a list of ExperimentRecord items with empirical measurements and variance.
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Verify environment availability and isolation status."""
        pass
