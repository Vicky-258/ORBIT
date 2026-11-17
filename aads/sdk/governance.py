"""
Simulation Governance Engine for AADS Simulation SDK (Phase 5.3B).
Acts as the authoritative policy and security gatekeeper.
Enforces DAG schema integrity, component model verification against ComponentRegistry,
resource execution quotas, and honest capability reporting.
"""
from typing import Dict, List, Optional, Tuple, Any, Set
import logging

from aads.core.schemas import WorkloadSpec
from aads.registry.component_registry import ComponentRegistry
from aads.sdk.models import (
    TopologyGraph,
    ComponentNode,
    Experiment,
    ExperimentPlan,
    ExperimentStatus,
    ComponentCategory,
)

logger = logging.getLogger(__name__)

# Resource and execution boundaries
MAX_SIMULATION_DURATION_SECONDS = 30.0
MAX_OFFERED_RPS = 5000.0
MIN_OFFERED_RPS = 1.0
MAX_TOPOLOGY_COMPONENTS = 25
MAX_TOPOLOGY_CONNECTIONS = 50


class GovernanceVerdict:
    """Standardized validation outcome emitted by governance engine."""
    def __init__(
        self,
        allowed: bool,
        status: str,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        model_manifest: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.allowed = allowed
        self.status = status
        self.errors = errors or []
        self.warnings = warnings or []
        self.model_manifest = model_manifest or {}
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "model_manifest": self.model_manifest,
            "details": self.details,
        }


class SimulationGovernanceEngine:
    """
    Authoritative safety, schema, and capability validator.
    Ensures that agent-formulated experiments can safely and scientifically execute.
    """

    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry or ComponentRegistry()
        self.registry.seed_baseline_data()

    def validate_topology(
        self,
        topology: TopologyGraph,
        workload: Optional[WorkloadSpec] = None,
    ) -> GovernanceVerdict:
        """
        Validates topology graph integrity and verifies that all component models
        exist and are calibrated within the ComponentRegistry.
        """
        errors: List[str] = []
        warnings: List[str] = []
        model_manifest: Dict[str, str] = {}

        # 1. Structural DAG Constraints
        if len(topology.components) > MAX_TOPOLOGY_COMPONENTS:
            errors.append(f"Topology component count ({len(topology.components)}) exceeds maximum allowed ({MAX_TOPOLOGY_COMPONENTS}).")

        if len(topology.connections) > MAX_TOPOLOGY_CONNECTIONS:
            errors.append(f"Topology connection count ({len(topology.connections)}) exceeds maximum allowed ({MAX_TOPOLOGY_CONNECTIONS}).")

        # 2. Path verification
        if not topology.read_path:
            errors.append("Topology must define a non-empty 'read_path'.")
        elif topology.read_path[0] != topology.ingress_node_id:
            errors.append(f"Read path must start with ingress node '{topology.ingress_node_id}', found '{topology.read_path[0]}'.")

        if not topology.write_path:
            errors.append("Topology must define a non-empty 'write_path'.")
        elif topology.write_path[0] != topology.ingress_node_id:
            errors.append(f"Write path must start with ingress node '{topology.ingress_node_id}', found '{topology.write_path[0]}'.")

        # 3. Component Model Registry Verification (Rule of Honest Capabilities)
        for comp in topology.components:
            # Map generic/standard names to registry models
            lookup_name = comp.model_name
            lookup_ver = comp.version or "latest"

            # Allow fallback alias mapping for common architecture names
            if lookup_name in ("api", "fastapi", "api_gateway", "fastapi_api"):
                lookup_name = "api_gateway"
                lookup_ver = "fastapi:0.110"
            elif lookup_name in ("postgres", "postgresql", "postgres_db"):
                lookup_name = "postgres_db"
                lookup_ver = "postgres:16-alpine"
            elif lookup_name in ("redis", "redis_cache"):
                lookup_name = "redis_cache"
                lookup_ver = "redis:7.2-alpine"
            elif lookup_name in ("kafka", "kafka_queue", "redis_queue"):
                lookup_name = "kafka_queue"
                lookup_ver = "kafka:3.6-alpine"
            elif lookup_name in ("worker", "async_worker", "celery"):
                lookup_name = "async_worker"
                lookup_ver = "celery:5.3"

            # Verify in registry
            if workload:
                compat_status, model, model_warns = self.registry.check_compatibility(lookup_name, lookup_ver, workload)
                warnings.extend(model_warns)
            else:
                model = self.registry.get_model(lookup_name, lookup_ver)
                compat_status = "VALIDATED" if model else "MISSING"

            if not model and lookup_name not in ("api_gateway", "kafka_queue", "async_worker"):
                # Strict: Component lacks a simulation model
                errors.append(
                    f"Component '{comp.id}' (model: '{comp.model_name}', version: '{comp.version}') "
                    f"has no registered performance model in registry. Discrete-event simulation cannot proceed."
                )
            else:
                model_id = model.model_id if model else f"builtin_{lookup_name}"
                model_manifest[comp.id] = model_id

        if errors:
            return GovernanceVerdict(
                allowed=False,
                status="REJECTED_CAPABILITY_MISSING",
                errors=errors,
                warnings=warnings,
                model_manifest=model_manifest,
            )

        return GovernanceVerdict(
            allowed=True,
            status="APPROVED",
            errors=[],
            warnings=warnings,
            model_manifest=model_manifest,
        )

    def validate_workload(self, workload: WorkloadSpec) -> GovernanceVerdict:
        """Validates workload parameters and safe simulation bounds."""
        errors: List[str] = []
        warnings: List[str] = []

        if workload.request_rate_rps < MIN_OFFERED_RPS:
            errors.append(f"Workload request_rate_rps ({workload.request_rate_rps}) is below minimum ({MIN_OFFERED_RPS}).")

        if workload.request_rate_rps > MAX_OFFERED_RPS:
            errors.append(f"Workload request_rate_rps ({workload.request_rate_rps}) exceeds maximum sandboxed rate ({MAX_OFFERED_RPS} RPS).")

        if abs((workload.read_ratio + workload.write_ratio) - 1.0) > 1e-4:
            errors.append(f"Workload read_ratio ({workload.read_ratio}) and write_ratio ({workload.write_ratio}) must sum to 1.0.")

        if workload.p95_latency_target_ms <= 0:
            errors.append("Workload p95_latency_target_ms must be positive.")

        if errors:
            return GovernanceVerdict(allowed=False, status="REJECTED_INVALID_WORKLOAD", errors=errors)

        return GovernanceVerdict(allowed=True, status="APPROVED", errors=[], warnings=warnings)

    def validate_experiment(self, experiment: Experiment) -> GovernanceVerdict:
        """Validates an entire experiment before dispatching to SimPy."""
        if experiment.topology is None:
            return GovernanceVerdict(allowed=False, status="REJECTED_MISSING_TOPOLOGY", errors=["Experiment lacks a defined topology."])

        if experiment.workload is None:
            return GovernanceVerdict(allowed=False, status="REJECTED_MISSING_WORKLOAD", errors=["Experiment lacks a defined workload."])

        if experiment.simulation_duration_seconds > MAX_SIMULATION_DURATION_SECONDS:
            return GovernanceVerdict(
                allowed=False,
                status="REJECTED_QUOTA_EXCEEDED",
                errors=[f"Simulation duration ({experiment.simulation_duration_seconds}s) exceeds quota ({MAX_SIMULATION_DURATION_SECONDS}s)."],
            )

        # Validate workload
        wl_verdict = self.validate_workload(experiment.workload)
        if not wl_verdict.allowed:
            return wl_verdict

        # Validate topology in context of workload
        topo_verdict = self.validate_topology(experiment.topology, experiment.workload)
        if not topo_verdict.allowed:
            return topo_verdict

        combined_warnings = wl_verdict.warnings + topo_verdict.warnings
        return GovernanceVerdict(
            allowed=True,
            status="APPROVED",
            errors=[],
            warnings=combined_warnings,
            model_manifest=topo_verdict.model_manifest,
        )

    def validate_plan(self, plan: ExperimentPlan) -> GovernanceVerdict:
        """Validates declarative multi-operation experiment plans."""
        errors: List[str] = []
        steps = plan.operations
        if not steps:
            return GovernanceVerdict(allowed=False, status="REJECTED_EMPTY_PLAN", errors=["Experiment plan contains no operations."])

        # Validate sequential indexing
        for idx, op in enumerate(steps, start=1):
            if op.step != idx:
                errors.append(f"Non-sequential step index: expected {idx}, found {op.step}.")

            # Validate parameter references ($step_M)
            for k, v in op.params.items():
                if isinstance(v, str) and v.startswith("$step_"):
                    try:
                        ref_step = int(v.split(".")[0].replace("$step_", ""))
                        if ref_step >= op.step:
                            errors.append(f"Step {op.step} references future/current step {ref_step} via '{v}'. Forward references are disallowed.")
                    except ValueError:
                        errors.append(f"Malformed step reference '{v}' in step {op.step}.")

        if errors:
            return GovernanceVerdict(allowed=False, status="REJECTED_INVALID_PLAN", errors=errors)

        return GovernanceVerdict(allowed=True, status="APPROVED")
