"""
Data Models and Schemas for AADS Simulation SDK (Phase 5.3B).
Defines dynamic topology graphs, branchable experiments, workspaces,
declarative experiment plans, and comparison schemas.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import uuid
from pydantic import BaseModel, Field, model_validator

from aads.core.schemas import WorkloadSpec, SimulationResult, ArchitectureGraph, ComponentType


class ComponentCategory(str, Enum):
    """Architectural classification of components."""
    INGRESS = "ingress"              # API Gateway, Load Balancer, Ingress Controller
    COMPUTE = "compute"              # App Server, Microservice, Background Worker
    CACHE = "cache"                  # In-memory Key-Value Cache (Redis, Memcached)
    DATABASE = "database"            # Relational (PostgreSQL), Document (MongoDB)
    QUEUE = "queue"                  # Message Broker / Log Stream (Kafka, RabbitMQ)
    STORAGE = "storage"              # Object / Blob Storage (S3, GCS)
    EDGE = "edge"                    # CDN, Reverse Proxy, Edge Cache


class ComponentNode(BaseModel):
    """Specification of an individual component node within a topology DAG."""
    id: str = Field(description="Unique node identifier in topology, e.g. 'api_gw', 'pg_primary'")
    category: ComponentCategory = Field(description="Component architectural category")
    model_name: str = Field(description="Registry model name, e.g. 'postgres_db', 'redis_cache'")
    version: str = Field(default="latest", description="Component version tag, e.g. 'postgres:16-alpine', 'redis:7.2-alpine'")
    
    # Resource sizing
    cpu_cores: float = Field(default=2.0, ge=0.25, le=128.0, description="Virtual CPU cores allocated")
    memory_mb: int = Field(default=2048, ge=64, le=524288, description="Memory in MB allocated")
    concurrency_limit: int = Field(default=32, ge=1, le=50000, description="Max concurrent connection / thread capacity")
    
    # Component specific parameters (e.g. max_connections, cache TTL, buffer size)
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Fine-grained configuration parameters")
    
    # Cost model overrides (if None, derived from standard cloud pricing catalog)
    monthly_cost_override_usd: Optional[float] = Field(default=None, ge=0.0, description="Manual cost override in USD/month")


class ConnectionEdge(BaseModel):
    """Directed connection between two component nodes."""
    source_id: str = Field(description="Source component ID")
    target_id: str = Field(description="Target component ID")
    protocol: str = Field(default="http", description="Interaction protocol: 'http', 'tcp', 'grpc', 'async_event'")
    network_latency_ms: float = Field(default=0.5, ge=0.0, description="Inter-process / network hop latency in ms")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge properties, e.g. circuit_breaker, timeout_ms")


class TopologyGraph(BaseModel):
    """Dynamically constructed, validated architecture graph."""
    topology_id: str = Field(default_factory=lambda: f"topo_{uuid.uuid4().hex[:10]}", description="Unique topology identifier")
    name: str = Field(default="Custom Architecture", description="Human-readable topology name")
    description: Optional[str] = Field(default="", description="Architectural summary or intent")
    
    components: List[ComponentNode] = Field(min_length=1, description="Component nodes in the architecture")
    connections: List[ConnectionEdge] = Field(default_factory=list, description="Edges connecting nodes")
    
    # Explicit operational execution paths
    ingress_node_id: str = Field(description="Entry point for client traffic (e.g. 'api_gw')")
    read_path: List[str] = Field(description="Ordered node sequence traversed for read operations")
    write_path: List[str] = Field(description="Ordered node sequence traversed for write operations")

    @model_validator(mode="after")
    def validate_topology_integrity(self):
        node_ids = {c.id for c in self.components}
        if len(node_ids) != len(self.components):
            duplicates = [c.id for c in self.components if self.components.count(c) > 1]
            raise ValueError(f"Duplicate component IDs detected in topology: {duplicates}")
        
        if self.ingress_node_id not in node_ids:
            raise ValueError(f"Ingress node '{self.ingress_node_id}' does not exist in component nodes: {sorted(list(node_ids))}")
        
        for edge in self.connections:
            if edge.source_id not in node_ids:
                raise ValueError(f"Connection source '{edge.source_id}' does not exist in topology nodes.")
            if edge.target_id not in node_ids:
                raise ValueError(f"Connection target '{edge.target_id}' does not exist in topology nodes.")
        
        for r_id in self.read_path:
            if r_id not in node_ids:
                raise ValueError(f"Read path node '{r_id}' does not exist in topology nodes.")
        for w_id in self.write_path:
            if w_id not in node_ids:
                raise ValueError(f"Write path node '{w_id}' does not exist in topology nodes.")
        
        return self

    @classmethod
    def from_architecture_graph(cls, arch: ArchitectureGraph) -> "TopologyGraph":
        """Converts legacy ArchitectureGraph into validated TopologyGraph."""
        type_to_cat = {
            ComponentType.API: ComponentCategory.INGRESS,
            ComponentType.CACHE: ComponentCategory.CACHE,
            ComponentType.DATABASE: ComponentCategory.DATABASE,
            ComponentType.QUEUE: ComponentCategory.QUEUE,
            ComponentType.WORKER: ComponentCategory.COMPUTE,
        }

        components: List[ComponentNode] = []
        for comp_id, c_conf in arch.components.items():
            cat = type_to_cat.get(c_conf.component_type, ComponentCategory.COMPUTE)
            components.append(
                ComponentNode(
                    id=comp_id,
                    category=cat,
                    model_name=c_conf.name,
                    version=c_conf.version,
                    cpu_cores=c_conf.cpu_cores,
                    memory_mb=c_conf.memory_mb,
                    concurrency_limit=c_conf.concurrency_limit,
                    monthly_cost_override_usd=c_conf.monthly_cost_usd,
                    parameters=c_conf.parameters,
                )
            )

        connections: List[ConnectionEdge] = []
        for src, tgt in arch.connections:
            is_async = arch.queue_present and (src == "queue" or tgt == "worker" or src == "worker")
            connections.append(
                ConnectionEdge(
                    source_id=src,
                    target_id=tgt,
                    protocol="async_event" if is_async else "http",
                    network_latency_ms=0.5,
                )
            )

        ingress_id = "api" if "api" in arch.components else list(arch.components.keys())[0]

        return cls(
            topology_id=arch.id,
            name=arch.name,
            description=arch.description,
            components=components,
            connections=connections,
            ingress_node_id=ingress_id,
            read_path=arch.read_path,
            write_path=arch.write_path,
        )


class ExperimentStatus(str, Enum):
    """Lifecycle status of a simulation experiment."""
    DRAFT = "DRAFT"                  # Configured, not yet executed
    VALIDATED = "VALIDATED"          # Passed governance & registry checks
    RUNNING = "RUNNING"              # Simulation in progress
    COMPLETED = "COMPLETED"          # Successfully simulated, results immutable
    FAILED = "FAILED"                # Simulation or validation error
    CANCELLED = "CANCELLED"          # Interrupted by user/timeout


class Experiment(BaseModel):
    """Independent, reproducible, branchable experiment unit."""
    experiment_id: str = Field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:12]}")
    workspace_id: str = Field(description="Parent workspace identifier")
    parent_experiment_id: Optional[str] = Field(default=None, description="Lineage pointer for branched experiments")
    branch_label: Optional[str] = Field(default=None, description="Human/agent label for branch, e.g. 'add-redis-cache'")
    
    # Core Configurations
    topology: Optional[TopologyGraph] = None
    workload: Optional[WorkloadSpec] = None
    simulation_duration_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    random_seed: int = Field(default=42)
    
    # State & Execution Lifecycle
    status: ExperimentStatus = Field(default=ExperimentStatus.DRAFT)
    error_message: Optional[str] = None
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at_utc: Optional[str] = None
    execution_duration_ms: float = Field(default=0.0)
    
    # Provenance & Audit
    model_manifest: Dict[str, str] = Field(default_factory=dict, description="Component -> Model SHA256 / model_id mapping")
    governance_verdict: Dict[str, Any] = Field(default_factory=dict, description="Validation output from governance engine")
    
    # Results & Metrics (None until completed)
    results: Optional[SimulationResult] = None
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class Workspace(BaseModel):
    """Isolated session workspace containing branchable experiments."""
    workspace_id: str = Field(default_factory=lambda: f"ws_{uuid.uuid4().hex[:10]}")
    name: str = Field(default="Architecture Investigation", description="Human-readable workspace title")
    intent_summary: str = Field(default="", description="High-level description of application or workload goal")
    created_at_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    experiment_ids: List[str] = Field(default_factory=list, description="IDs of experiments created in workspace")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OperationType(str, Enum):
    """Atomic operations available in multi-step experiment plans."""
    CREATE_EXPERIMENT = "create_experiment"
    DEFINE_TOPOLOGY = "define_topology"
    CONFIGURE_COMPONENT = "configure_component"
    DEFINE_WORKLOAD = "define_workload"
    APPLY_CHANGES = "apply_changes"
    CLONE_EXPERIMENT = "clone_experiment"
    RUN_SIMULATION = "run_simulation"
    COMPARE_EXPERIMENTS = "compare_experiments"


class OperationStep(BaseModel):
    """A single declarative step in a multi-operation experiment plan."""
    step: int = Field(ge=1, description="Sequential step index")
    op: OperationType = Field(description="Operation to perform")
    params: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the operation; can reference $step_N outputs")


class ExperimentPlan(BaseModel):
    """Declarative batch experiment plan enabling complex investigations in a single turn."""
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:10]}")
    workspace_id: str = Field(description="Target workspace identifier")
    description: Optional[str] = Field(default="", description="Summary of hypothesis or investigation plan")
    operations: List[OperationStep] = Field(min_length=1, description="Ordered sequence of operations")


class ComparisonDimension(BaseModel):
    """Comparison metric across candidate experiments."""
    metric_name: str
    unit: str
    higher_is_better: bool
    values_by_experiment: Dict[str, Optional[float]]
    winner_experiment_id: Optional[str] = None


class ComparisonResult(BaseModel):
    """Side-by-side comparative evaluation of multiple experiments."""
    compared_experiment_ids: List[str]
    dimensions: List[ComparisonDimension]
    pareto_optimal_experiment_ids: List[str]
    recommended_experiment_id: Optional[str] = None
    summary_trade_offs: List[str] = Field(default_factory=list)
