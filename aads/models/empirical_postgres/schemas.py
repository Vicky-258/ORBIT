"""
Schemas and Data Structures for Empirical PostgreSQL Performance Models (Phase 4F.5 / 4F.5.1).

Enforces strict epistemological boundaries, explicit prediction contracts:
- OBSERVED vs INTERPOLATED vs OUT_OF_RANGE vs INSUFFICIENT_EVIDENCE
- Categorized uncertainty types (replication, interpolation heuristic, extrapolation heuristic, unavailable)
- Explicit heuristic multipliers that are never labelled as statistical confidence intervals
- Parameter identifiability declarations
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


class EvidenceStatus(str, Enum):
    """
    Epistemological status of a prediction based on empirical support.
    Must never classify interpolated values (e.g. 1.5 vCPU) as OBSERVED or IN_RANGE.
    """
    OBSERVED = "OBSERVED"                 # Exact match to empirical measurement support
    INTERPOLATED = "INTERPOLATED"         # Between measured support points; unmeasured estimate
    OUT_OF_RANGE = "OUT_OF_RANGE"         # Outside measured support or violating environmental/workload dimensions
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE" # Unsupported workload, missing dimensions, unidentifiable parameters


class UncertaintyType(str, Enum):
    """
    Epistemological classification of uncertainty.
    Heuristic penalties must never be labelled as statistical confidence intervals.
    """
    REPLICATION_SAMPLE_STD = "REPLICATION_SAMPLE_STD"       # Measured variation across repeated trials (ddof=1)
    MEASUREMENT_LIMITATION = "MEASUREMENT_LIMITATION"       # Sensor or instrumentation limitations
    INTERPOLATION_HEURISTIC = "INTERPOLATION_HEURISTIC"     # Uncertainty between support points; heuristic assumption
    EXTRAPOLATION_HEURISTIC = "EXTRAPOLATION_HEURISTIC"     # Uncertainty outside support points; heuristic distance multiplier
    MODEL_FORM_UNCERTAINTY = "MODEL_FORM_UNCERTAINTY"       # Uncertainty from choice of functional form
    PARAMETER_UNCERTAINTY = "PARAMETER_UNCERTAINTY"         # Uncertainty in fitted model parameters
    UNAVAILABLE = "UNAVAILABLE"                             # No defensible uncertainty estimate exists (never reported as 0.0)


class ModelState(str, Enum):
    """
    Lifecycle and boundary state for candidate performance models.
    Preserved for backward compatibility while mapping to EvidenceStatus.
    """
    OBSERVED = "OBSERVED"
    INTERPOLATED = "INTERPOLATED"
    IN_RANGE = "IN_RANGE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATION_PENDING = "VALIDATION_PENDING"


class WorkloadProfile(str, Enum):
    """Empirically supported workload profiles."""
    READ_ONLY_SELECT = "read_only_select"
    BALANCED_OLTP_TPCB = "balanced_oltp_tpcb"


class EmpiricalPostgresQuery(BaseModel):
    """Target configuration query for empirical PostgreSQL prediction."""
    workload_profile: WorkloadProfile
    cpu_quota_cores: float = Field(..., description="Container CPU quota in cores (e.g. 1.0, 2.0)")
    concurrency: int = Field(default=8, description="Client connection concurrency")
    scale_factor: int = Field(default=2, description="pgbench scale factor (SF)")
    memory_mb: float = Field(default=1024.0, description="Container memory limit in MB")


class MetricPrediction(BaseModel):
    """
    A single predicted metric with explicit uncertainty bounds and epistemological categorization.
    Heuristic intervals are strictly distinguished from calibrated statistical confidence intervals.
    """
    point_estimate: Optional[float] = None
    uncertainty_std: Optional[float] = Field(
        default=None,
        description="Standard error or uncertainty estimate; None if UNAVAILABLE (never silently set to 0.0)"
    )
    uncertainty_type: UncertaintyType = Field(
        default=UncertaintyType.REPLICATION_SAMPLE_STD,
        description="Epistemological classification of the uncertainty value"
    )
    is_heuristic: bool = Field(
        default=False,
        description="True if uncertainty is based on engineering heuristics rather than formal statistical coverage"
    )
    confidence_interval_95: Optional[Tuple[float, float]] = Field(
        default=None,
        description="Approximate 95% confidence interval [lower, upper]; None if heuristic or unavailable"
    )
    heuristic_interval: Optional[Tuple[float, float]] = Field(
        default=None,
        description="Heuristic uncertainty bounds [lower, upper]; explicitly distinct from statistical confidence interval"
    )
    heuristic_multiplier: Optional[float] = Field(
        default=None,
        description="Penalty multiplier applied (e.g. 2.0 + 1.5 * distance); None if no heuristic multiplier"
    )
    notes: List[str] = Field(default_factory=list)


class EmpiricalPostgresPrediction(BaseModel):
    """
    Structured multi-metric response from an empirical PostgreSQL component model.
    Enforces Phase 4F.5.1 prediction evidence contract.
    """
    # Prediction evidence contract fields
    evidence_status: EvidenceStatus
    prediction_method: str
    measured_support: Dict[str, Any] = Field(default_factory=dict)
    requested_configuration: Dict[str, Any] = Field(default_factory=dict)
    uncertainty: Optional[float] = None
    uncertainty_type: UncertaintyType = UncertaintyType.REPLICATION_SAMPLE_STD
    limitations: List[str] = Field(default_factory=list)
    identifiability_notes: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    # Backward compatibility fields
    state: ModelState
    is_extrapolated: bool
    uncertainty_notes: List[str] = Field(default_factory=list)

    # Configuration echo
    workload_profile: str
    cpu_quota_cores: float
    concurrency: int
    scale_factor: int
    memory_mb: float

    # Core performance metrics
    throughput_tps: MetricPrediction
    latency_mean_ms: MetricPrediction
    p50_ms: MetricPrediction
    p90_ms: MetricPrediction
    p95_ms: MetricPrediction
    p99_ms: MetricPrediction
    p999_ms: MetricPrediction
    max_ms: MetricPrediction
    cpu_utilization_pct: MetricPrediction

    # Workload-specific telemetry predictions
    throttling_frequency_pct: Optional[MetricPrediction] = None
    throttled_seconds: Optional[MetricPrediction] = None
    wal_bytes_per_sec: Optional[MetricPrediction] = None
    wal_sync_time_ms: Optional[MetricPrediction] = None
    observed_lock_waits: Optional[MetricPrediction] = None


class TrialObservation(BaseModel):
    """A single reconciled trial observation from Phase 4F.4.5 empirical evidence."""
    trial_id: str
    workload_profile: str
    cpu_quota_cores: float
    replication: int
    duration_seconds: float
    throughput_tps: float
    latency_mean_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: float
    max_ms: float
    cpu_utilization_pct: float
    throttling_frequency_pct: float
    throttled_seconds: float
    wal_bytes: int
    wal_sync_time_ms: float
    observed_lock_waits: int


class EvaluationMetrics(BaseModel):
    """Replication-aware performance evaluation metrics."""
    rmse: float
    mae: float
    mape_pct: Optional[float] = None
    r2_score: Optional[float] = None
    sample_size: int
    per_condition_errors: Dict[str, float] = Field(default_factory=dict)
    replication_variability_cv: Dict[str, float] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)

