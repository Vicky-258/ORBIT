"""
Workload Profile and Parameter Provenance Models for ORBIT (Phase: Hybrid Workload Intelligence).
Converts classified workloads into measurable, simulation-executable parameters
while rigorously tracking the epistemic provenance and confidence of every value.
"""
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
from pydantic import BaseModel, Field, model_validator

from orbit.catalog.archetypes import (
    ArchetypeID,
    SystemArchetype,
    get_archetype,
    SYSTEM_ARCHETYPE_CATALOG,
)


class ParameterProvenanceSource(str, Enum):
    """Rigorous epistemic origin tracking for every numerical parameter."""
    USER_PROVIDED = "USER_PROVIDED"          # Stated explicitly in the prompt by the user
    DOMAIN_INFERRED = "DOMAIN_INFERRED"      # Inferred from domain context (e.g. hotel booking -> strict consistency)
    ARCHETYPE_DEFAULT = "ARCHETYPE_DEFAULT"  # Calibrated prior from the System Archetype catalog
    SYSTEM_ESTIMATED = "SYSTEM_ESTIMATED"    # Heuristic estimation (e.g. DAU -> RPS derivation)
    BENCHMARK_CALIBRATED = "BENCHMARK_CALIBRATED" # Empirically measured in real container benchmark


class ParameterProvenanceItem(BaseModel):
    """Metadata detailing the origin and confidence of an individual parameter."""
    key: str
    value: Any
    source: ParameterProvenanceSource
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score in [0.0, 1.0]")
    is_assumed: bool = Field(description="True if parameter is an assumption rather than user fact")
    explanation: Optional[str] = None


class TrafficProfile(BaseModel):
    """Traffic generation dynamics for discrete-event simulation."""
    arrival_rate_rps: float = Field(gt=0.0, description="Mean offered requests per second")
    arrival_distribution: str = Field(default="poisson", description="Arrival distribution: poisson, uniform, bursty")
    burst_multiplier: float = Field(default=2.0, ge=1.0, description="Peak load multiplier for burst headroom")


class OperationsProfile(BaseModel):
    """Read vs. write division of the workload."""
    read_ratio: float = Field(ge=0.0, le=1.0, description="Proportion of read operations (0.0 to 1.0)")
    write_ratio: float = Field(ge=0.0, le=1.0, description="Proportion of write operations (0.0 to 1.0)")

    @model_validator(mode="after")
    def validate_sum(self):
        if abs((self.read_ratio + self.write_ratio) - 1.0) > 1e-4:
            raise ValueError(f"Read ratio ({self.read_ratio}) + write ratio ({self.write_ratio}) must equal 1.0")
        return self


class DataProfile(BaseModel):
    """Payload sizes and caching characteristics."""
    request_size_kb: float = Field(default=2.0, ge=0.0)
    response_size_kb: float = Field(default=10.0, ge=0.0)
    cacheability: float = Field(default=0.0, ge=0.0, le=1.0, description="Theoretical fraction of requests that can be served from cache")


class PerformanceProfile(BaseModel):
    """Service level agreements and latency objectives."""
    p95_latency_target_ms: float = Field(gt=0.0, description="Target p95 latency threshold in milliseconds")
    latency_sensitivity: str = Field(default="normal_interactive", description="critical_low_latency, normal_interactive, asynchronous_delayed")


class RequirementsProfile(BaseModel):
    """Consistency and transactional requirements."""
    consistency: str = Field(default="eventual", description="strict_acid, eventual, read_your_writes")
    isolation_level: Optional[str] = Field(default=None, description="read_committed, serializable")


class ComputationProfile(BaseModel):
    """Computational and execution complexity."""
    compute_intensity: str = Field(default="medium", description="low, medium, high")
    task_duration_ms: Optional[float] = Field(default=None, description="Worker execution time for asynchronous jobs (ms)")
    connection_count: Optional[int] = Field(default=None, description="Active persistent sockets for realtime streaming")


class WorkloadProfile(BaseModel):
    """Complete, validated, simulation-executable profile for a single workload."""
    workload_id: str
    operation_name: str
    description: str
    archetype_id: ArchetypeID
    
    traffic: TrafficProfile
    operations: OperationsProfile
    data: DataProfile
    performance: PerformanceProfile
    requirements: RequirementsProfile
    computation: ComputationProfile
    
    provenance_map: Dict[str, ParameterProvenanceItem] = Field(default_factory=dict)

    def get_parameter_value(self, key: str) -> Any:
        """Retrieves parameter value by key, checking across sub-profiles."""
        if hasattr(self.traffic, key):
            return getattr(self.traffic, key)
        if hasattr(self.operations, key):
            return getattr(self.operations, key)
        if hasattr(self.data, key):
            return getattr(self.data, key)
        if hasattr(self.performance, key):
            return getattr(self.performance, key)
        if hasattr(self.requirements, key):
            return getattr(self.requirements, key)
        if hasattr(self.computation, key):
            return getattr(self.computation, key)
        return None


def generate_workload_profile(
    workload_id: str,
    operation_name: str,
    description: str,
    archetype_id: ArchetypeID,
    user_facts: Optional[Dict[str, Any]] = None,
    domain_hints: Optional[Dict[str, Any]] = None,
) -> WorkloadProfile:
    """
    Constructs a validated, executable WorkloadProfile for a decomposed workload.
    Applies user-provided facts first, then domain inferences, falling back to
    calibrated archetype priors with explicit provenance tracking.
    """
    user_facts = user_facts or {}
    domain_hints = domain_hints or {}
    archetype = get_archetype(archetype_id) or SYSTEM_ARCHETYPE_CATALOG[ArchetypeID.GENERAL_WEB_SERVICE]
    priors = archetype.baseline_assumptions
    prov: Dict[str, ParameterProvenanceItem] = {}

    # 1. Traffic Profile
    # Check user-stated arrival rate
    if "arrival_rate_rps" in user_facts:
        rps = float(user_facts["arrival_rate_rps"])
        prov["arrival_rate_rps"] = ParameterProvenanceItem(
            key="arrival_rate_rps",
            value=rps,
            source=ParameterProvenanceSource.USER_PROVIDED,
            confidence=1.0,
            is_assumed=False,
            explanation="Explicitly specified by user prompt",
        )
    elif "request_rate_rps" in user_facts:
        rps = float(user_facts["request_rate_rps"])
        prov["arrival_rate_rps"] = ParameterProvenanceItem(
            key="arrival_rate_rps",
            value=rps,
            source=ParameterProvenanceSource.USER_PROVIDED,
            confidence=1.0,
            is_assumed=False,
            explanation="Explicitly specified by user prompt",
        )
    elif "arrival_rate_rps" in domain_hints:
        rps = float(domain_hints["arrival_rate_rps"])
        prov["arrival_rate_rps"] = ParameterProvenanceItem(
            key="arrival_rate_rps",
            value=rps,
            source=ParameterProvenanceSource.DOMAIN_INFERRED,
            confidence=0.75,
            is_assumed=True,
            explanation="Inferred from application domain traffic estimates",
        )
    else:
        # Default archetype RPS
        rps = 100.0 if archetype_id != ArchetypeID.WRITE_HEAVY_INGESTION else 500.0
        prov["arrival_rate_rps"] = ParameterProvenanceItem(
            key="arrival_rate_rps",
            value=rps,
            source=ParameterProvenanceSource.ARCHETYPE_DEFAULT,
            confidence=0.50,
            is_assumed=True,
            explanation=f"Default baseline for {archetype.name}",
        )

    burst_mult = float(user_facts.get("burst_multiplier", priors.default_burst_multiplier))
    prov["burst_multiplier"] = ParameterProvenanceItem(
        key="burst_multiplier",
        value=burst_mult,
        source=ParameterProvenanceSource.USER_PROVIDED if "burst_multiplier" in user_facts else ParameterProvenanceSource.ARCHETYPE_DEFAULT,
        confidence=1.0 if "burst_multiplier" in user_facts else 0.80,
        is_assumed="burst_multiplier" not in user_facts,
    )

    traffic = TrafficProfile(
        arrival_rate_rps=rps,
        arrival_distribution=priors.default_arrival_distribution,
        burst_multiplier=burst_mult,
    )

    # 2. Operations Profile (Read/Write ratios)
    if "read_ratio" in user_facts and "write_ratio" in user_facts:
        rr = float(user_facts["read_ratio"])
        wr = float(user_facts["write_ratio"])
        op_source = ParameterProvenanceSource.USER_PROVIDED
        op_conf = 1.0
        op_assumed = False
    elif "read_ratio" in user_facts:
        rr = float(user_facts["read_ratio"])
        wr = round(1.0 - rr, 4)
        op_source = ParameterProvenanceSource.USER_PROVIDED
        op_conf = 1.0
        op_assumed = False
    else:
        rr = priors.default_read_ratio
        wr = priors.default_write_ratio
        op_source = ParameterProvenanceSource.ARCHETYPE_DEFAULT
        op_conf = 0.85
        op_assumed = True

    prov["read_ratio"] = ParameterProvenanceItem(
        key="read_ratio",
        value=rr,
        source=op_source,
        confidence=op_conf,
        is_assumed=op_assumed,
        explanation="Stated ratio" if not op_assumed else f"Archetype baseline for {archetype.name}",
    )
    prov["write_ratio"] = ParameterProvenanceItem(
        key="write_ratio",
        value=wr,
        source=op_source,
        confidence=op_conf,
        is_assumed=op_assumed,
        explanation="Stated ratio" if not op_assumed else f"Archetype baseline for {archetype.name}",
    )
    operations = OperationsProfile(read_ratio=rr, write_ratio=wr)

    # 3. Data Profile
    cacheability = float(user_facts.get("cacheability", priors.default_cacheability))
    prov["cacheability"] = ParameterProvenanceItem(
        key="cacheability",
        value=cacheability,
        source=ParameterProvenanceSource.USER_PROVIDED if "cacheability" in user_facts else ParameterProvenanceSource.ARCHETYPE_DEFAULT,
        confidence=1.0 if "cacheability" in user_facts else 0.75,
        is_assumed="cacheability" not in user_facts,
    )
    data = DataProfile(
        request_size_kb=float(user_facts.get("request_size_kb", 2.0)),
        response_size_kb=float(user_facts.get("response_size_kb", 10.0)),
        cacheability=cacheability,
    )

    # 4. Performance Profile (SLA)
    if "p95_latency_target_ms" in user_facts:
        p95 = float(user_facts["p95_latency_target_ms"])
        sla_source = ParameterProvenanceSource.USER_PROVIDED
        sla_conf = 1.0
        sla_assumed = False
    elif "p95_latency_target_ms" in domain_hints:
        p95 = float(domain_hints["p95_latency_target_ms"])
        sla_source = ParameterProvenanceSource.DOMAIN_INFERRED
        sla_conf = 0.80
        sla_assumed = True
    else:
        p95 = priors.default_p95_sla_ms
        sla_source = ParameterProvenanceSource.ARCHETYPE_DEFAULT
        sla_conf = 0.70
        sla_assumed = True

    prov["p95_latency_target_ms"] = ParameterProvenanceItem(
        key="p95_latency_target_ms",
        value=p95,
        source=sla_source,
        confidence=sla_conf,
        is_assumed=sla_assumed,
        explanation="User-specified SLA" if not sla_assumed else f"Archetype default target for {archetype.name}",
    )
    performance = PerformanceProfile(
        p95_latency_target_ms=p95,
        latency_sensitivity=priors.latency_sensitivity,
    )

    # 5. Requirements Profile
    consistency = user_facts.get("consistency", priors.default_consistency)
    prov["consistency"] = ParameterProvenanceItem(
        key="consistency",
        value=consistency,
        source=ParameterProvenanceSource.USER_PROVIDED if "consistency" in user_facts else ParameterProvenanceSource.ARCHETYPE_DEFAULT,
        confidence=1.0 if "consistency" in user_facts else 0.85,
        is_assumed="consistency" not in user_facts,
    )
    requirements = RequirementsProfile(consistency=consistency)

    # 6. Computation Profile
    task_dur = None
    if archetype_id == ArchetypeID.DECOUPLED_ASYNC_COMPUTE:
        task_dur = float(user_facts.get("task_duration_ms", 2500.0))  # 2.5s typical worker execution
    conn_count = None
    if archetype_id == ArchetypeID.REALTIME_STREAM_TRACKING:
        conn_count = int(user_facts.get("connection_count", int(rps * 10)))

    computation = ComputationProfile(
        compute_intensity=priors.default_compute_intensity,
        task_duration_ms=task_dur,
        connection_count=conn_count,
    )

    return WorkloadProfile(
        workload_id=workload_id,
        operation_name=operation_name,
        description=description,
        archetype_id=archetype_id,
        traffic=traffic,
        operations=operations,
        data=data,
        performance=performance,
        requirements=requirements,
        computation=computation,
        provenance_map=prov,
    )
