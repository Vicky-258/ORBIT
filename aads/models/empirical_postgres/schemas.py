"""
Schemas and Data Structures for Empirical PostgreSQL Performance Models (Phase 4F.5).

Enforces strict epistemological boundaries, explicit model states, out-of-range detection,
and comprehensive prediction uncertainty reporting.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ModelState(str, Enum):
    """Lifecycle and boundary state for candidate performance models."""
    EXPERIMENTAL = "EXPERIMENTAL"
    IN_RANGE = "IN_RANGE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
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
    """A single predicted metric with explicit uncertainty bounds."""
    point_estimate: float
    uncertainty_std: float = Field(description="Standard error / standard deviation of prediction")
    confidence_interval_95: Tuple[float, float] = Field(
        description="Approximate 95% confidence interval [lower, upper]"
    )


class EmpiricalPostgresPrediction(BaseModel):
    """Structured multi-metric response from an empirical PostgreSQL component model."""
    state: ModelState
    is_extrapolated: bool
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

    # Provenance and scientific integrity controls
    provenance: Dict[str, Any] = Field(default_factory=dict)
    uncertainty_notes: List[str] = Field(default_factory=list)


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
