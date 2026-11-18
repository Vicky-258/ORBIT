"""
Primary Agent Interface for AADS Simulation SDK (Phase 5.3B).
Exposes 12 composable simulation tools and declarative plan execution.
Mediated by SimulationGovernanceEngine for validation, safety, and honest capability reporting.
"""
import copy
import logging
import time
from typing import Dict, List, Optional, Any, Union

from orbit.core.schemas import WorkloadSpec, SimulationResult
from orbit.registry.component_registry import ComponentRegistry
from orbit.sdk.capabilities import SimulationCapabilitiesCatalog
from orbit.sdk.governance import SimulationGovernanceEngine
from orbit.sdk.models import (
    TopologyGraph,
    ComponentNode,
    ComponentCategory,
    ConnectionEdge,
    Experiment,
    ExperimentStatus,
    Workspace,
    ExperimentPlan,
    OperationStep,
    OperationType,
    ComparisonResult,
    ComparisonDimension,
)
from orbit.sdk.store import ExperimentStore
from orbit.simulation.dynamic_simpy_engine import DynamicSimPyEngine

logger = logging.getLogger(__name__)


class SimulationSDK:
    """
    Unified Simulation SDK encapsulating workspace management, dynamic topology configuration,
    experiment branching, governed SimPy execution, and multi-experiment comparison.
    """

    def __init__(
        self,
        registry: Optional[ComponentRegistry] = None,
        store: Optional[ExperimentStore] = None,
        governance: Optional[SimulationGovernanceEngine] = None,
        engine: Optional[DynamicSimPyEngine] = None,
    ):
        self.registry = registry or ComponentRegistry()
        self.registry.seed_baseline_data()
        self.store = store or ExperimentStore()
        self.governance = governance or SimulationGovernanceEngine(registry=self.registry)
        self.engine = engine or DynamicSimPyEngine(registry=self.registry)

    # -------------------------------------------------------------------------
    # 1. Capability Discovery
    # -------------------------------------------------------------------------

    def inspect_capabilities(self, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Discovers supported component categories, calibrated models, operating envelopes,
        available metrics, and known simulation limitations in the sandbox.
        """
        catalog = SimulationCapabilitiesCatalog.discover(
            registry=self.registry,
            category_filter=category_filter,
        )
        return catalog.model_dump()

    # -------------------------------------------------------------------------
    # 2. Workspace Management
    # -------------------------------------------------------------------------

    def create_workspace(
        self,
        name: str,
        intent_summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates an isolated investigation workspace for branching experiments."""
        ws = self.store.create_workspace(name=name, intent_summary=intent_summary, metadata=metadata)
        return {
            "success": True,
            "workspace_id": ws.workspace_id,
            "name": ws.name,
            "intent_summary": ws.intent_summary,
            "created_at_utc": ws.created_at_utc,
        }

    # -------------------------------------------------------------------------
    # 3. Experiment Creation & Branching
    # -------------------------------------------------------------------------

    def create_experiment(self, workspace_id: str, label: Optional[str] = None) -> Dict[str, Any]:
        """Creates an independent DRAFT experiment in a workspace."""
        try:
            exp = self.store.create_experiment(workspace_id=workspace_id, label=label)
            return {
                "success": True,
                "experiment_id": exp.experiment_id,
                "workspace_id": exp.workspace_id,
                "branch_label": exp.branch_label,
                "status": exp.status.value,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clone_experiment(self, source_experiment_id: str, new_label: str) -> Dict[str, Any]:
        """
        Branches an experiment while preserving the immutability of the parent.
        Inherits topology and workload configurations into a fresh DRAFT experiment.
        """
        try:
            child = self.store.clone_experiment(source_experiment_id=source_experiment_id, new_label=new_label)
            return {
                "success": True,
                "experiment_id": child.experiment_id,
                "workspace_id": child.workspace_id,
                "parent_experiment_id": child.parent_experiment_id,
                "branch_label": child.branch_label,
                "status": child.status.value,
                "has_topology": child.topology is not None,
                "has_workload": child.workload is not None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------------------
    # 4. Topology & Component Configuration
    # -------------------------------------------------------------------------

    def define_topology(self, experiment_id: str, topology_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Defines or replaces the architecture topology for a DRAFT experiment.
        Validated against DAG connectivity rules and component registry availability.
        """
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}

        try:
            topo = TopologyGraph.model_validate(topology_data)
        except Exception as e:
            return {"success": False, "error": f"Topology schema validation error: {str(e)}"}

        verdict = self.governance.validate_topology(topo, exp.workload)
        if not verdict.allowed:
            return {
                "success": False,
                "error": f"Topology rejected by governance: {'; '.join(verdict.errors)}",
                "verdict": verdict.to_dict(),
            }

        exp.topology = topo
        exp.model_manifest = verdict.model_manifest
        exp.warnings = verdict.warnings
        self.store.save_experiment(exp)

        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "topology_id": topo.topology_id,
            "component_count": len(topo.components),
            "connection_count": len(topo.connections),
            "warnings": verdict.warnings,
        }

    def configure_component(
        self,
        experiment_id: str,
        component_id: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Updates sizing, limits, or parameters of an individual component in a DRAFT experiment."""
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}
        if not exp.topology:
            return {"success": False, "error": f"Experiment '{experiment_id}' has no defined topology."}

        target_node = next((c for c in exp.topology.components if c.id == component_id), None)
        if not target_node:
            return {"success": False, "error": f"Component '{component_id}' not found in topology."}

        # Apply settings
        if "cpu_cores" in settings:
            target_node.cpu_cores = float(settings["cpu_cores"])
        if "memory_mb" in settings:
            target_node.memory_mb = int(settings["memory_mb"])
        if "concurrency_limit" in settings:
            target_node.concurrency_limit = int(settings["concurrency_limit"])
        if "monthly_cost_override_usd" in settings:
            target_node.monthly_cost_override_usd = float(settings["monthly_cost_override_usd"])
        if "parameters" in settings and isinstance(settings["parameters"], dict):
            target_node.parameters.update(settings["parameters"])

        self.store.save_experiment(exp)
        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "component_id": component_id,
            "updated_settings": {
                "cpu_cores": target_node.cpu_cores,
                "memory_mb": target_node.memory_mb,
                "concurrency_limit": target_node.concurrency_limit,
                "parameters": target_node.parameters,
            },
        }

    def define_workload(self, experiment_id: str, workload_data: Dict[str, Any]) -> Dict[str, Any]:
        """Attaches traffic volume, read/write split, and SLA targets to an experiment."""
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}

        try:
            wl = WorkloadSpec.model_validate(workload_data)
        except Exception as e:
            return {"success": False, "error": f"Workload schema validation error: {str(e)}"}

        verdict = self.governance.validate_workload(wl)
        if not verdict.allowed:
            return {
                "success": False,
                "error": f"Workload rejected by governance: {'; '.join(verdict.errors)}",
                "verdict": verdict.to_dict(),
            }

        exp.workload = wl
        self.store.save_experiment(exp)

        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "request_rate_rps": wl.request_rate_rps,
            "read_ratio": wl.read_ratio,
            "p95_latency_target_ms": wl.p95_latency_target_ms,
            "warnings": verdict.warnings,
        }

    def apply_changes(self, experiment_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies incremental modifications to a DRAFT experiment's topology or workload.
        Supports: 'add_components', 'remove_components', 'add_connections', 'update_read_path', 'update_write_path'.
        """
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}
        if not exp.topology:
            return {"success": False, "error": "Cannot apply changes: experiment has no topology."}

        topo_dict = exp.topology.model_dump()

        # 1. Add components
        if "add_components" in patch:
            for c_data in patch["add_components"]:
                topo_dict["components"].append(c_data)

        # 2. Remove components
        if "remove_components" in patch:
            to_remove = set(patch["remove_components"])
            topo_dict["components"] = [c for c in topo_dict["components"] if c["id"] not in to_remove]
            topo_dict["connections"] = [
                e for e in topo_dict["connections"]
                if e["source_id"] not in to_remove and e["target_id"] not in to_remove
            ]

        # 3. Add connections
        if "add_connections" in patch:
            for edge in patch["add_connections"]:
                topo_dict["connections"].append(edge)

        # 4. Update paths
        if "update_read_path" in patch:
            topo_dict["read_path"] = patch["update_read_path"]
        if "update_write_path" in patch:
            topo_dict["write_path"] = patch["update_write_path"]

        return self.define_topology(experiment_id, topo_dict)

    # -------------------------------------------------------------------------
    # 5. Simulation Execution
    # -------------------------------------------------------------------------

    def run_simulation(
        self,
        experiment_id: str,
        duration_seconds: float = 10.0,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Executes sandboxed SimPy discrete-event simulation of the configured experiment.
        Governed by resource and duration quotas.
        """
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}

        exp.simulation_duration_seconds = duration_seconds
        exp.random_seed = random_seed

        # Pre-execution Governance Audit
        verdict = self.governance.validate_experiment(exp)
        if not verdict.allowed:
            exp.status = ExperimentStatus.FAILED
            exp.error_message = "; ".join(verdict.errors)
            exp.governance_verdict = verdict.to_dict()
            self.store.save_experiment(exp)
            return {
                "success": False,
                "status": exp.status.value,
                "error": exp.error_message,
                "verdict": verdict.to_dict(),
            }

        # Run Simulation
        t0 = time.perf_counter()
        exp.status = ExperimentStatus.RUNNING
        self.store.save_experiment(exp)

        try:
            sim_res = self.engine.simulate_topology(
                topology=exp.topology,
                workload=exp.workload,
                duration_seconds=duration_seconds,
                random_seed=random_seed,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            exp.status = ExperimentStatus.COMPLETED
            exp.results = sim_res
            exp.execution_duration_ms = round(elapsed_ms, 2)
            exp.warnings = sim_res.warnings
            exp.governance_verdict = verdict.to_dict()
            self.store.save_experiment(exp)

            return {
                "success": True,
                "experiment_id": exp.experiment_id,
                "status": exp.status.value,
                "execution_duration_ms": exp.execution_duration_ms,
                "throughput_achieved_rps": sim_res.throughput_achieved_rps,
                "p95_latency_ms": sim_res.p95_latency_ms,
                "bottleneck_component": sim_res.bottleneck_component,
                "estimated_monthly_cost_usd": sim_res.estimated_monthly_cost_usd,
                "warnings": exp.warnings,
            }
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            exp.status = ExperimentStatus.FAILED
            exp.error_message = str(exc)
            exp.execution_duration_ms = round(elapsed_ms, 2)
            self.store.save_experiment(exp)
            return {
                "success": False,
                "experiment_id": exp.experiment_id,
                "status": exp.status.value,
                "error": str(exc),
            }

    # -------------------------------------------------------------------------
    # 6. Inspection & Comparison
    # -------------------------------------------------------------------------

    def inspect_execution(self, experiment_id: str) -> Dict[str, Any]:
        """Inspects experiment execution state, duration, errors, and governance output."""
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}

        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "workspace_id": exp.workspace_id,
            "parent_experiment_id": exp.parent_experiment_id,
            "branch_label": exp.branch_label,
            "status": exp.status.value,
            "error_message": exp.error_message,
            "execution_duration_ms": exp.execution_duration_ms,
            "simulation_duration_seconds": exp.simulation_duration_seconds,
            "random_seed": exp.random_seed,
            "governance_status": exp.governance_verdict.get("status"),
            "model_manifest": exp.model_manifest,
        }

    def inspect_results(self, experiment_id: str) -> Dict[str, Any]:
        """Retrieves structured simulation metrics for a completed experiment."""
        exp = self.store.get_experiment(experiment_id)
        if not exp:
            return {"success": False, "error": f"Experiment '{experiment_id}' not found."}
        if exp.status != ExperimentStatus.COMPLETED or not exp.results:
            return {
                "success": False,
                "status": exp.status.value,
                "error": "Experiment results unavailable. Simulation has not completed successfully.",
            }

        return {
            "success": True,
            "experiment_id": exp.experiment_id,
            "topology_name": exp.topology.name if exp.topology else "Unknown",
            "results": exp.results.model_dump(),
            "warnings": exp.warnings,
            "limitations": exp.limitations,
        }

    def compare_experiments(
        self,
        experiment_ids: List[str],
        primary_metric: str = "p95_latency_ms",
    ) -> Dict[str, Any]:
        """
        Performs side-by-side comparative analysis across multiple completed experiments.
        Identifies constraint satisfaction, Pareto dominance, and trade-offs.
        """
        experiments: List[Experiment] = []
        for eid in experiment_ids:
            exp = self.store.get_experiment(eid)
            if not exp:
                return {"success": False, "error": f"Experiment '{eid}' not found."}
            if exp.status != ExperimentStatus.COMPLETED or not exp.results:
                return {"success": False, "error": f"Experiment '{eid}' has not completed successfully."}
            experiments.append(exp)

        if len(experiments) < 2:
            return {"success": False, "error": "At least 2 completed experiments are required for comparison."}

        # Compare across key dimensions
        dim_defs = [
            ("p95_latency_ms", "ms", False),
            ("p50_latency_ms", "ms", False),
            ("throughput_achieved_rps", "RPS", True),
            ("estimated_monthly_cost_usd", "USD/mo", False),
            ("error_rate_pct", "%", False),
        ]

        dimensions: List[ComparisonDimension] = []
        for metric_name, unit, higher_better in dim_defs:
            vals = {}
            for exp in experiments:
                val = getattr(exp.results, metric_name, None)
                vals[exp.experiment_id] = float(val) if val is not None else None

            # Determine winner for this dimension
            valid_vals = {k: v for k, v in vals.items() if v is not None}
            if valid_vals:
                best_id = max(valid_vals, key=valid_vals.get) if higher_better else min(valid_vals, key=valid_vals.get)
            else:
                best_id = None

            dimensions.append(
                ComparisonDimension(
                    metric_name=metric_name,
                    unit=unit,
                    higher_is_better=higher_better,
                    values_by_experiment=vals,
                    winner_experiment_id=best_id,
                )
            )

        # Pareto evaluation
        pareto_ids = []
        for i, exp_a in enumerate(experiments):
            is_dominated = False
            for j, exp_b in enumerate(experiments):
                if i == j:
                    continue
                # exp_b dominates exp_a if it is better or equal in all and strictly better in one
                b_better_p95 = exp_b.results.p95_latency_ms < exp_a.results.p95_latency_ms
                b_better_cost = exp_b.results.estimated_monthly_cost_usd < exp_a.results.estimated_monthly_cost_usd
                b_better_tp = exp_b.results.throughput_achieved_rps > exp_a.results.throughput_achieved_rps
                if (b_better_p95 and b_better_cost) or (b_better_p95 and b_better_tp and exp_b.results.estimated_monthly_cost_usd <= exp_a.results.estimated_monthly_cost_usd):
                    is_dominated = True
                    break
            if not is_dominated:
                pareto_ids.append(exp_a.experiment_id)

        # Trade-offs summary
        trade_offs = []
        for exp in experiments:
            lbl = exp.branch_label or exp.experiment_id
            trade_offs.append(
                f"[{lbl}] Achieves {exp.results.p95_latency_ms:.2f}ms p95 at ${exp.results.estimated_monthly_cost_usd:.2f}/mo (Bottleneck: {exp.results.bottleneck_component})."
            )

        comp_result = ComparisonResult(
            compared_experiment_ids=[e.experiment_id for e in experiments],
            dimensions=dimensions,
            pareto_optimal_experiment_ids=pareto_ids,
            recommended_experiment_id=pareto_ids[0] if pareto_ids else experiments[0].experiment_id,
            summary_trade_offs=trade_offs,
        )
        return comp_result.model_dump()

    # -------------------------------------------------------------------------
    # 7. Multi-Operation Plan Execution
    # -------------------------------------------------------------------------

    def execute_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a declarative multi-step ExperimentPlan in a single turn.
        Resolves inter-step variable references (e.g. '$step_1.experiment_id').
        """
        try:
            plan = ExperimentPlan.model_validate(plan_data)
        except Exception as e:
            return {"success": False, "error": f"Plan schema error: {str(e)}"}

        verdict = self.governance.validate_plan(plan)
        if not verdict.allowed:
            return {"success": False, "error": f"Plan rejected: {'; '.join(verdict.errors)}"}

        context: Dict[str, Any] = {"workspace_id": plan.workspace_id}
        step_outputs: Dict[int, Any] = {}

        for step in plan.operations:
            resolved_params = self._resolve_plan_params(step.params, step_outputs, context)
            op = step.op

            if op == OperationType.CREATE_EXPERIMENT:
                res = self.create_experiment(
                    workspace_id=resolved_params.get("workspace_id", plan.workspace_id),
                    label=resolved_params.get("label"),
                )
            elif op == OperationType.DEFINE_TOPOLOGY:
                res = self.define_topology(
                    experiment_id=resolved_params["experiment_id"],
                    topology_data=resolved_params["topology"],
                )
            elif op == OperationType.CONFIGURE_COMPONENT:
                res = self.configure_component(
                    experiment_id=resolved_params["experiment_id"],
                    component_id=resolved_params["component_id"],
                    settings=resolved_params.get("settings", {}),
                )
            elif op == OperationType.DEFINE_WORKLOAD:
                res = self.define_workload(
                    experiment_id=resolved_params["experiment_id"],
                    workload_data=resolved_params["workload"],
                )
            elif op == OperationType.APPLY_CHANGES:
                res = self.apply_changes(
                    experiment_id=resolved_params["experiment_id"],
                    patch=resolved_params.get("patch", {}),
                )
            elif op == OperationType.CLONE_EXPERIMENT:
                res = self.clone_experiment(
                    source_experiment_id=resolved_params["source_experiment_id"],
                    new_label=resolved_params.get("new_label", "branch"),
                )
            elif op == OperationType.RUN_SIMULATION:
                res = self.run_simulation(
                    experiment_id=resolved_params["experiment_id"],
                    duration_seconds=resolved_params.get("duration_seconds", 10.0),
                    random_seed=resolved_params.get("random_seed", 42),
                )
            elif op == OperationType.COMPARE_EXPERIMENTS:
                res = self.compare_experiments(
                    experiment_ids=resolved_params["experiment_ids"],
                    primary_metric=resolved_params.get("primary_metric", "p95_latency_ms"),
                )
            else:
                res = {"success": False, "error": f"Unknown operation: {op}"}

            step_outputs[step.step] = res
            if not res.get("success", False):
                return {
                    "success": False,
                    "failed_step": step.step,
                    "error": res.get("error", "Step execution failed."),
                    "partial_outputs": step_outputs,
                }

        return {
            "success": True,
            "plan_id": plan.plan_id,
            "total_steps_executed": len(plan.operations),
            "step_outputs": step_outputs,
        }

    def _resolve_plan_params(
        self,
        params: Dict[str, Any],
        step_outputs: Dict[int, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively resolves $step_N.key variables in operation parameters."""
        resolved = copy.deepcopy(params)

        def _resolve_val(val: Any) -> Any:
            if isinstance(val, str) and val.startswith("$step_"):
                parts = val.split(".", 1)
                step_idx = int(parts[0].replace("$step_", ""))
                field_name = parts[1] if len(parts) > 1 else None
                step_res = step_outputs.get(step_idx, {})
                if field_name:
                    return step_res.get(field_name, val)
                return step_res
            elif isinstance(val, dict):
                return {k: _resolve_val(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [_resolve_val(v) for v in val]
            return val

        for k, v in resolved.items():
            resolved[k] = _resolve_val(v)

        return resolved
