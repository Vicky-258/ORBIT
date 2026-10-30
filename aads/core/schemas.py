"""
Pydantic data schemas and contracts for AADS.
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field, model_validator


class ComponentType(str, Enum):
    API = "api"
    CACHE = "cache"
    DATABASE = "database"
    QUEUE = "queue"
    WORKER = "worker"


class InformationProvenance(str, Enum):
    USER_FACT = "user_fact"
    MEASURED_DATA = "measured_data"
    AGENT_ASSUMPTION = "agent_assumption"


class ProvenanceItem(BaseModel):
    key: str
    provenance: InformationProvenance
    value: Any
    description: str
    is_editable: bool = True


class WorkloadSpec(BaseModel):
    """Workload and performance requirements submitted by the user."""
    app_type: str = Field(default="social_media_feed", description="Application type or domain")
    request_rate_rps: float = Field(default=500.0, ge=1.0, description="Base expected request rate in RPS")
    peak_load_factor: float = Field(default=2.0, ge=1.0, description="Multiplier for peak workload")
    read_ratio: float = Field(default=0.90, ge=0.0, le=1.0, description="Ratio of read requests")
    write_ratio: float = Field(default=0.10, ge=0.0, le=1.0, description="Ratio of write requests")
    dataset_records: int = Field(default=1_000_000, ge=1000, description="Number of records in database")
    dataset_growth_monthly_pct: float = Field(default=5.0, ge=0.0, description="Expected dataset growth per month")
    
    # Hard objectives
    p95_latency_target_ms: float = Field(default=50.0, gt=0.0, description="Maximum acceptable p95 latency in ms")
    min_throughput_rps: float = Field(default=450.0, gt=0.0, description="Minimum acceptable throughput in RPS")
    max_monthly_budget_usd: float = Field(default=250.0, gt=0.0, description="Maximum allowable monthly budget in USD")
    
    # Cache parameters
    cache_assumed_hit_rate: float = Field(default=0.85, ge=0.0, le=1.0, description="Expected cache hit rate")
    cache_ttl_seconds: int = Field(default=300, ge=1, description="Cache time-to-live in seconds")
    
    # Confidence and preferences
    required_confidence_pct: float = Field(default=90.0, ge=50.0, le=99.9, description="Confidence requirement")
    hard_constraints: List[str] = Field(
        default_factory=lambda: ["p95_latency", "min_throughput", "max_budget"],
        description="List of mandatory constraints"
    )
    soft_preferences: Dict[str, float] = Field(
        default_factory=lambda: {"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        description="Weights for multi-objective trade-offs (sum to 1.0)"
    )
    
    # Metadata tracking assumptions vs user inputs
    provenance_map: Dict[str, ProvenanceItem] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ratios_and_weights(self):
        if abs((self.read_ratio + self.write_ratio) - 1.0) > 1e-4:
            raise ValueError(f"Read ratio ({self.read_ratio}) + write ratio ({self.write_ratio}) must equal 1.0")
        
        # Populate default provenance items if not provided
        if not self.provenance_map:
            self.provenance_map = {
                "app_type": ProvenanceItem(key="app_type", provenance=InformationProvenance.USER_FACT, value=self.app_type, description="User-selected application domain"),
                "request_rate_rps": ProvenanceItem(key="request_rate_rps", provenance=InformationProvenance.USER_FACT, value=self.request_rate_rps, description="User target throughput load"),
                "read_ratio": ProvenanceItem(key="read_ratio", provenance=InformationProvenance.USER_FACT, value=self.read_ratio, description="Workload read proportion"),
                "p95_latency_target_ms": ProvenanceItem(key="p95_latency_target_ms", provenance=InformationProvenance.USER_FACT, value=self.p95_latency_target_ms, description="User hard SLA threshold"),
                "max_monthly_budget_usd": ProvenanceItem(key="max_monthly_budget_usd", provenance=InformationProvenance.USER_FACT, value=self.max_monthly_budget_usd, description="User spending cap"),
                "cache_assumed_hit_rate": ProvenanceItem(key="cache_assumed_hit_rate", provenance=InformationProvenance.AGENT_ASSUMPTION, value=self.cache_assumed_hit_rate, description="Agent default estimate for social media feeds (editable)"),
                "peak_load_factor": ProvenanceItem(key="peak_load_factor", provenance=InformationProvenance.AGENT_ASSUMPTION, value=self.peak_load_factor, description="Agent assumption: standard 2x peak burst headroom"),
                "dataset_growth_monthly_pct": ProvenanceItem(key="dataset_growth_monthly_pct", provenance=InformationProvenance.AGENT_ASSUMPTION, value=self.dataset_growth_monthly_pct, description="Agent assumption: 5% monthly data growth"),
            }
        return self


class ComponentConfig(BaseModel):
    """Specification of an individual architectural component."""
    name: str
    component_type: ComponentType
    version: str
    cpu_cores: float = 1.0
    memory_mb: int = 512
    concurrency_limit: int = 20
    monthly_cost_usd: float = 25.0
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ArchitectureGraph(BaseModel):
    """Machine-readable candidate architecture representation."""
    id: str
    name: str
    description: str
    components: Dict[str, ComponentConfig]
    connections: List[Tuple[str, str]]
    read_path: List[str]
    write_path: List[str]
    queue_present: bool = False
    required_models: List[str]
    total_monthly_cost_usd: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentRecord(BaseModel):
    """Raw benchmark trial record."""
    experiment_id: str
    component_name: str
    version: str
    env_fingerprint: str
    benchmark_framework: str = "pgbench/microbench"
    concurrency: int
    read_ratio: float
    offered_rps: float
    achieved_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    cpu_pct: float
    memory_mb: float
    error_count: int = 0
    trial_replications: int = 3
    variance_ms2: float = 0.0
    is_synthetic_fixture: bool = False
    timestamp: str
    notes: Optional[str] = None
    proposal_id: Optional[str] = None
    authorization_id: Optional[str] = None
    execution_id: Optional[str] = None
    execution_mode: str = "synthetic"
    benchmark_command: Optional[str] = None
    duration_seconds: Optional[float] = None
    raw_artifact_path: Optional[str] = None
    status: str = "SUCCESS"
    error_message: Optional[str] = None


class ModelRecord(BaseModel):
    """Fitted performance model record in registry."""
    model_id: str
    component_name: str
    version: str
    env_fingerprint: str
    model_type: str = "piecewise_ridge"
    fitted_parameters: Dict[str, Any]
    min_supported_rps: float
    max_supported_rps: float
    min_supported_concurrency: int
    max_supported_concurrency: int
    validation_rmse_ms: float
    validation_mape_pct: float
    r2_score: Optional[float] = None
    is_validated: bool
    is_synthetic_fixture: bool = False
    provenance: str
    known_limitations: str
    created_at: str


class SimulationResult(BaseModel):
    """Discrete-event simulation output metrics."""
    architecture_id: str
    architecture_name: str
    throughput_achieved_rps: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    error_rate_pct: float
    total_requests: int
    completed_requests: int
    error_count: int
    avg_queue_length: float
    max_queue_length: int
    component_utilizations: Dict[str, float]
    cache_hit_rate: Optional[float] = None
    bottleneck_component: str
    estimated_monthly_cost_usd: float
    simulation_duration_seconds: float
    random_seed: int
    latency_uncertainty_p95_ms: Tuple[float, float] = Field(default=(0.0, 0.0), description="Heuristic uncertainty bounds around p95 latency. Engineering proxy, not a validated statistical confidence interval.")
    warnings: List[str] = Field(default_factory=list)


class FeasibilityStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    UNCERTAIN = "UNCERTAIN"
    INFEASIBLE = "INFEASIBLE"


class FeasibilityCheck(BaseModel):
    criterion: str
    target_value: float
    predicted_value: float
    uncertainty_range: Optional[Tuple[float, float]] = None
    status: FeasibilityStatus
    explanation: str


class CandidateEvaluation(BaseModel):
    architecture_id: str
    architecture_name: str
    feasibility_status: FeasibilityStatus
    checks: List[FeasibilityCheck]
    cost_score: float
    latency_score: float
    throughput_score: float
    complexity_score: float
    overall_score: float
    is_pareto_dominated: bool = False
    dominated_by: Optional[str] = None


class RecommendationResult(BaseModel):
    selected_architecture_id: str
    selected_architecture_name: str
    status: FeasibilityStatus
    executive_summary: str
    rationale: List[str]
    predicted_metrics: Dict[str, Any]
    evaluations: List[CandidateEvaluation]
    trade_offs_and_risks: List[str]
    assumptions_cited: List[str]
    validation_gaps: List[str]
    recommended_next_experiment: Optional[str] = None
    explanation_source: Optional[str] = "deterministic"
    structured_explanation: Optional[Dict[str, Any]] = None
