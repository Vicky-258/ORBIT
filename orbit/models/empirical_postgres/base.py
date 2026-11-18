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

from orbit.modeling.model_interface import ComponentPerformanceModel
from orbit.models.empirical_postgres.schemas import (
    EmpiricalPostgresPrediction,
    EmpiricalPostgresQuery,
    EvidenceStatus,
    MetricPrediction,
    ModelState,
    TrialObservation,
    UncertaintyType,
    WorkloadProfile,
)

logger = logging.getLogger(__name__)


class ServiceTimeResult(tuple):
    """
    Backward-compatible 3-tuple (service_time_ms, uncertainty_std_ms, is_extrapolated)
    extended with explicit evidence_status attribute for Phase 4F.5.1 prediction contract.
    """
    def __new__(cls, service_time_ms: float, uncertainty_std_ms: float, is_extrapolated: bool, evidence_status: str = "OBSERVED"):
        instance = super().__new__(cls, (service_time_ms, uncertainty_std_ms, is_extrapolated))
        instance.service_time_ms = service_time_ms
        instance.uncertainty_std_ms = uncertainty_std_ms
        instance.is_extrapolated = is_extrapolated
        instance.evidence_status = evidence_status
        return instance


class BaseEmpiricalPostgresModel(ComponentPerformanceModel):
    """
    Abstract base class for all empirical PostgreSQL candidate performance models.
    Enforces Phase 4F.5.1 scientific prediction evidence contracts.
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

    def get_measured_support(self) -> Dict[str, Any]:
        """Returns the exact empirical support envelope for this model."""
        return {
            "workload_profile": self.workload_profile.value if hasattr(self.workload_profile, "value") else str(self.workload_profile),
            "cpu_quotas": [self.min_cpu_quota, self.max_cpu_quota],
            "concurrency": self.supported_concurrency,
            "scale_factor": self.supported_scale_factor,
            "memory_mb": self.supported_memory_mb,
            "postgres_version": "16.15-alpine",
            "image_digest": "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685",
            "replications_per_condition": 3,
            "measurement_duration_seconds": 30.0,
            "warmup_duration_seconds": 10.0,
        }

    def check_input_boundaries(self, query: EmpiricalPostgresQuery) -> Tuple[EvidenceStatus, bool, List[str]]:
        """
        Validates input configuration against empirical pilot boundaries.
        Explicitly distinguishes:
        - OBSERVED: Exact match to empirical support endpoints (1.0 or 2.0 vCPU).
        - INTERPOLATED: Between support endpoints (e.g. 1.5 vCPU); NEVER OBSERVED or IN_RANGE.
        - OUT_OF_RANGE: Beyond measured support or violating environmental dimensions.
        - INSUFFICIENT_EVIDENCE: Missing required fields or unsupported workload.
        Returns:
            (evidence_status, is_extrapolated, boundary_notes)
        """
        notes: List[str] = []
        is_extrapolated = False

        # 1. Workload profile check
        expected_profile = self.workload_profile.value if isinstance(self.workload_profile, WorkloadProfile) else str(self.workload_profile)
        actual_profile = query.workload_profile.value if isinstance(query.workload_profile, WorkloadProfile) else str(query.workload_profile)
        if actual_profile != expected_profile:
            notes.append(f"Workload profile '{actual_profile}' unsupported by model '{self.model_id}' (supports '{expected_profile}').")
            return EvidenceStatus.INSUFFICIENT_EVIDENCE, True, notes

        # 2. Required CPU dimension check
        if query.cpu_quota_cores is None:
            notes.append("Required dimension 'cpu_quota_cores' is missing.")
            return EvidenceStatus.INSUFFICIENT_EVIDENCE, True, notes

        # 3. CPU quota range check
        if query.cpu_quota_cores < self.min_cpu_quota or query.cpu_quota_cores > self.max_cpu_quota:
            notes.append(
                f"CPU quota {query.cpu_quota_cores:.2f} is outside empirically validated range [{self.min_cpu_quota:.1f}, {self.max_cpu_quota:.1f}] vCPU."
            )
            is_extrapolated = True

        # 4. Concurrency check
        if query.concurrency != self.supported_concurrency:
            notes.append(
                f"Concurrency {query.concurrency} deviates from benchmarked concurrency {self.supported_concurrency}."
            )
            is_extrapolated = True

        # 5. Scale factor check
        if query.scale_factor != self.supported_scale_factor:
            notes.append(
                f"Scale factor SF{query.scale_factor} deviates from benchmarked scale SF{self.supported_scale_factor}."
            )
            is_extrapolated = True

        # 6. Memory check
        if abs(query.memory_mb - self.supported_memory_mb) > 1.0:
            notes.append(
                f"Memory {query.memory_mb:.1f} MB deviates from benchmarked container memory {self.supported_memory_mb:.1f} MB."
            )
            is_extrapolated = True

        if is_extrapolated:
            return EvidenceStatus.OUT_OF_RANGE, True, notes

        # Within envelope: check whether directly observed or interpolated
        is_exact_anchor = (
            abs(query.cpu_quota_cores - self.min_cpu_quota) < 1e-4 or
            abs(query.cpu_quota_cores - self.max_cpu_quota) < 1e-4
        )
        if is_exact_anchor:
            return EvidenceStatus.OBSERVED, False, notes

        # Strictly interpolated between measured anchors
        notes.append(
            f"CPU quota {query.cpu_quota_cores:.2f} is interpolated between observed support endpoints "
            f"[{self.min_cpu_quota:.1f}, {self.max_cpu_quota:.1f}] vCPU. This is an unmeasured interpolation estimate."
        )
        return EvidenceStatus.INTERPOLATED, False, notes

    # --------------------------------------------------------------------------
    # ComponentPerformanceModel Interface Implementation (Simulation Engine)
    # --------------------------------------------------------------------------
    def get_supported_ranges(self) -> Dict[str, Tuple[float, float]]:
        """Returns supported ranges compatible with AADS ComponentPerformanceModel."""
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

        IMPORTANT — Queueing Double-Counting Guard:
        SimPy simulates queueing and contention delays explicitly via simpy.Resource.
        To avoid double-counting queueing delays, this method outputs pure service demand
        (p50 per transaction / concurrency), NOT end-to-end queued latency.
        Analytical queries needing end-to-end percentiles should call model.predict() directly.

        Returns:
            ServiceTimeResult(service_time_ms, uncertainty_std_ms, is_extrapolated, evidence_status)
        """
        cpu_quota = 2.0
        query = EmpiricalPostgresQuery(
            workload_profile=self.workload_profile,
            cpu_quota_cores=cpu_quota,
            concurrency=concurrency,
            scale_factor=self.supported_scale_factor,
            memory_mb=self.supported_memory_mb,
        )
        pred = self.predict(query)

        # In SimPyEngine, pure service time corresponds to p50 / mean service demand
        service_time_ms = pred.p50_ms.point_estimate or 1.0
        uncertainty_ms = pred.p50_ms.uncertainty_std or 0.1

        # Adjust for write ops if called in mixed context
        if op_type == "write" and self.workload_profile == WorkloadProfile.READ_ONLY_SELECT:
            service_time_ms *= 2.2
            uncertainty_ms *= 2.2

        is_extrapolated = pred.is_extrapolated or (concurrency != self.supported_concurrency)
        if is_extrapolated:
            uncertainty_ms *= 2.0

        return ServiceTimeResult(
            round(service_time_ms, 3),
            round(uncertainty_ms, 3),
            is_extrapolated,
            pred.evidence_status.value,
        )

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
