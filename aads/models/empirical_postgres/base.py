"""
Base Class for Empirical PostgreSQL Performance Models (Phase 4F.5).

Inherits from ComponentPerformanceModel to preserve full compatibility with AADS
simulation engine (SimPyEngine) and component registry interfaces.
Enforces explicit boundary validation, out-of-range detection, and uncertainty tracking.
"""
from abc import abstractmethod
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from aads.modeling.model_interface import ComponentPerformanceModel
from aads.models.empirical_postgres.schemas import (
    EmpiricalPostgresPrediction,
    EmpiricalPostgresQuery,
    MetricPrediction,
    ModelState,
    TrialObservation,
    WorkloadProfile,
)

logger = logging.getLogger(__name__)


class BaseEmpiricalPostgresModel(ComponentPerformanceModel):
    """
    Abstract base class for all empirical PostgreSQL candidate performance models.
    """

    def __init__(
        self,
        model_id: str,
        workload_profile: WorkloadProfile,
        version: str = "1.0.0-candidate",
        provenance: Optional[Dict[str, Any]] = None,
    ):
        self.model_id = model_id
        self.workload_profile = workload_profile
        self.version = version
        self.provenance = provenance or {}

        # Validated empirical boundaries
        self.min_cpu_quota: float = 1.0
        self.max_cpu_quota: float = 2.0
        self.supported_concurrency: int = 8
        self.supported_scale_factor: int = 2
        self.supported_memory_mb: float = 1024.0

    @abstractmethod
    def fit(self, observations: List[TrialObservation]) -> "BaseEmpiricalPostgresModel":
        """Fits candidate model parameters from empirical observations."""
        pass

    @abstractmethod
    def predict(self, query: EmpiricalPostgresQuery) -> EmpiricalPostgresPrediction:
        """Computes full multi-metric performance prediction with uncertainty bounds."""
        pass

    def check_input_boundaries(self, query: EmpiricalPostgresQuery) -> Tuple[ModelState, bool, List[str]]:
        """
        Validates input configuration against empirical pilot boundaries.
        Returns:
            (model_state, is_extrapolated, boundary_notes)
        """
        notes: List[str] = []
        is_extrapolated = False

        # 1. Workload profile check
        expected_profile = self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile)
        actual_profile = query.workload_profile.value if isinstance(query.workload_profile, WorkloadProfile) else str(query.workload_profile)
        if actual_profile != expected_profile:
            notes.append(f"Workload profile '{actual_profile}' unsupported by model '{self.model_id}' (supports '{expected_profile}').")
            return ModelState.INSUFFICIENT_EVIDENCE, True, notes

        # 2. CPU quota check
        if query.cpu_quota_cores < self.min_cpu_quota or query.cpu_quota_cores > self.max_cpu_quota:
            notes.append(
                f"CPU quota {query.cpu_quota_cores:.2f} is outside empirically validated range [{self.min_cpu_quota:.1f}, {self.max_cpu_quota:.1f}] vCPU."
            )
            is_extrapolated = True

        # 3. Concurrency check
        if query.concurrency != self.supported_concurrency:
            notes.append(
                f"Concurrency {query.concurrency} deviates from benchmarked concurrency {self.supported_concurrency}."
            )
            is_extrapolated = True

        # 4. Scale factor check
        if query.scale_factor != self.supported_scale_factor:
            notes.append(
                f"Scale factor SF{query.scale_factor} deviates from benchmarked scale SF{self.supported_scale_factor}."
            )
            is_extrapolated = True

        # 5. Memory check
        if abs(query.memory_mb - self.supported_memory_mb) > 1.0:
            notes.append(
                f"Memory {query.memory_mb:.1f} MB deviates from benchmarked container memory {self.supported_memory_mb:.1f} MB."
            )
            is_extrapolated = True

        state = ModelState.OUT_OF_RANGE if is_extrapolated else ModelState.IN_RANGE
        return state, is_extrapolated, notes

    # --------------------------------------------------------------------------
    # ComponentPerformanceModel Interface Implementation (Simulation Engine)
    # --------------------------------------------------------------------------
    def get_supported_ranges(self) -> Dict[str, Tuple[float, float]]:
        """Returns supported ranges compatible with AADS ComponentPerformanceModel."""
        # For read_only_select, throughput range is approx [18,000, 39,000] RPS
        # For balanced_oltp_tpcb, throughput range is approx [1,200, 1,700] RPS
        if self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            rps_range = (18000.0, 39000.0)
        else:
            rps_range = (1200.0, 1700.0)

        return {
            "concurrency": (float(self.supported_concurrency), float(self.supported_concurrency)),
            "rps": rps_range,
            "cpu_cores": (self.min_cpu_quota, self.max_cpu_quota),
        }

    def predict_service_time_ms(
        self,
        op_type: str,
        concurrency: int = 8,
        offered_rps: float = 100.0,
    ) -> Tuple[float, float, bool]:
        """
        Predicts discrete event service time in milliseconds.
        Compatible with SimPy discrete-event simulation engine.
        Returns:
            (service_time_ms, uncertainty_std_ms, is_extrapolated)
        """
        # Determine CPU quota equivalent or default to 2.0 vCPU
        cpu_quota = 2.0
        query = EmpiricalPostgresQuery(
            workload_profile=self.workload_profile,
            cpu_quota_cores=cpu_quota,
            concurrency=concurrency,
            scale_factor=self.supported_scale_factor,
            memory_mb=self.supported_memory_mb,
        )
        pred = self.predict(query)

        # In SimPyEngine, pure service time per discrete event corresponds to p50 / mean service demand
        service_time_ms = pred.p50_ms.point_estimate
        uncertainty_ms = pred.p50_ms.uncertainty_std

        # Adjust for write ops if called in mixed context
        if op_type == "write" and self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            service_time_ms *= 2.2
            uncertainty_ms *= 2.2

        is_extrapolated = pred.is_extrapolated or (concurrency != self.supported_concurrency)
        if is_extrapolated:
            uncertainty_ms *= 2.0

        return (round(service_time_ms, 3), round(uncertainty_ms, 3), is_extrapolated)

    # --------------------------------------------------------------------------
    # Serialization and Persistence
    # --------------------------------------------------------------------------
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serializes candidate model state and parameters to dictionary."""
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseEmpiricalPostgresModel":
        """Reconstructs candidate model from serialized dictionary."""
        pass

    def save_json(self, path: Union[str, Path]) -> str:
        """Saves model to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(p)

    @classmethod
    def load_json(cls, path: Union[str, Path]) -> "BaseEmpiricalPostgresModel":
        """Loads model from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
