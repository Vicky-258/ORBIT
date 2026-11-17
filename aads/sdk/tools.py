"""
LangChain Typed Tool Wrappers for AADS Simulation SDK (Phase 5.3B).
Exposes the 12 composable SDK operations as typed @tool functions for LangGraph agents.
"""
from typing import Dict, List, Any, Optional
from langchain_core.tools import tool

from aads.sdk.interface import SimulationSDK

# Global default instance for stateless tool invocations
_default_sdk = SimulationSDK()


def get_simulation_sdk() -> SimulationSDK:
    return _default_sdk


@tool("sdk_inspect_capabilities")
def sdk_inspect_capabilities(category_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Discovers supported component categories, empirical models, operating envelopes,
    metrics, and known limitations in the simulation sandbox.
    """
    return get_simulation_sdk().inspect_capabilities(category_filter=category_filter)


@tool("sdk_create_workspace")
def sdk_create_workspace(name: str, intent_summary: str = "") -> Dict[str, Any]:
    """Creates an isolated investigation workspace for branching experiments."""
    return get_simulation_sdk().create_workspace(name=name, intent_summary=intent_summary)


@tool("sdk_create_experiment")
def sdk_create_experiment(workspace_id: str, label: Optional[str] = None) -> Dict[str, Any]:
    """Creates an independent DRAFT experiment in a workspace."""
    return get_simulation_sdk().create_experiment(workspace_id=workspace_id, label=label)


@tool("sdk_define_topology")
def sdk_define_topology(experiment_id: str, topology_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Defines or replaces the architecture topology for a DRAFT experiment.
    Must specify 'components', 'connections', 'ingress_node_id', 'read_path', and 'write_path'.
    """
    return get_simulation_sdk().define_topology(experiment_id=experiment_id, topology_data=topology_data)


@tool("sdk_configure_component")
def sdk_configure_component(experiment_id: str, component_id: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Updates sizing, limits, or parameters of an individual component in a DRAFT experiment."""
    return get_simulation_sdk().configure_component(
        experiment_id=experiment_id,
        component_id=component_id,
        settings=settings,
    )


@tool("sdk_define_workload")
def sdk_define_workload(experiment_id: str, workload_data: Dict[str, Any]) -> Dict[str, Any]:
    """Attaches traffic volume (RPS), read/write split, and SLA targets to an experiment."""
    return get_simulation_sdk().define_workload(experiment_id=experiment_id, workload_data=workload_data)


@tool("sdk_apply_changes")
def sdk_apply_changes(experiment_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies incremental modifications to a DRAFT experiment's topology.
    Supports 'add_components', 'remove_components', 'add_connections', 'update_read_path', 'update_write_path'.
    """
    return get_simulation_sdk().apply_changes(experiment_id=experiment_id, patch=patch)


@tool("sdk_clone_experiment")
def sdk_clone_experiment(source_experiment_id: str, new_label: str) -> Dict[str, Any]:
    """
    Branches an experiment while preserving the immutability of the parent.
    Inherits topology and workload configurations into a fresh DRAFT experiment with parent lineage.
    """
    return get_simulation_sdk().clone_experiment(source_experiment_id=source_experiment_id, new_label=new_label)


@tool("sdk_run_simulation")
def sdk_run_simulation(
    experiment_id: str,
    duration_seconds: float = 10.0,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Executes sandboxed SimPy discrete-event simulation of the configured experiment."""
    return get_simulation_sdk().run_simulation(
        experiment_id=experiment_id,
        duration_seconds=duration_seconds,
        random_seed=random_seed,
    )


@tool("sdk_inspect_execution")
def sdk_inspect_execution(experiment_id: str) -> Dict[str, Any]:
    """Inspects experiment execution state, duration, errors, and governance validation outputs."""
    return get_simulation_sdk().inspect_execution(experiment_id=experiment_id)


@tool("sdk_inspect_results")
def sdk_inspect_results(experiment_id: str) -> Dict[str, Any]:
    """Retrieves structured simulation metrics (p50, p95, p99, throughput, bottleneck, cost) for a completed experiment."""
    return get_simulation_sdk().inspect_results(experiment_id=experiment_id)


@tool("sdk_compare_experiments")
def sdk_compare_experiments(experiment_ids: List[str], primary_metric: str = "p95_latency_ms") -> Dict[str, Any]:
    """Performs side-by-side comparative analysis and Pareto dominance evaluation across multiple completed experiments."""
    return get_simulation_sdk().compare_experiments(
        experiment_ids=experiment_ids,
        primary_metric=primary_metric,
    )


@tool("sdk_execute_plan")
def sdk_execute_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a declarative multi-step ExperimentPlan in a single turn.
    Resolves inter-step variable references (e.g. '$step_1.experiment_id').
    """
    return get_simulation_sdk().execute_plan(plan_data=plan_data)


def get_sdk_tools() -> List[Any]:
    """Returns all 13 SDK tool definitions for agent registration."""
    return [
        sdk_inspect_capabilities,
        sdk_create_workspace,
        sdk_create_experiment,
        sdk_define_topology,
        sdk_configure_component,
        sdk_define_workload,
        sdk_apply_changes,
        sdk_clone_experiment,
        sdk_run_simulation,
        sdk_inspect_execution,
        sdk_inspect_results,
        sdk_compare_experiments,
        sdk_execute_plan,
    ]
