"""
Typed LangChain Tool Layer for ORBIT.
Wraps existing deterministic ORBIT modules into safe, typed tools.
Enforces component whitelisting, timeout boundaries, and input validation.
"""
from typing import Dict, List, Any, Optional
from langchain_core.tools import tool

from orbit.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    ModelRecord,
    ExperimentRecord,
)
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.registry.component_registry import ComponentRegistry
from orbit.benchmark.experiment_manager import AdaptiveExperimentManager
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from orbit.benchmark.docker_runner import DockerBenchmarkRunner
from orbit.modeling.model_trainer import ModelTrainer
from orbit.simulation.simpy_engine import SimPyEngine
from orbit.evaluation.recommender import ArchitectureRecommender

ALLOWED_BENCHMARK_COMPONENTS = {"postgres_db", "redis_cache", "mongodb_cluster"}


@tool("validate_workload")
def validate_workload(workload_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and normalizes workload parameters against ORBIT engineering constraints."""
    try:
        spec = WorkloadSpec(**workload_data)
        return {
            "valid": True,
            "errors": [],
            "workload": spec.model_dump(),
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [str(e)],
            "workload": None,
        }


@tool("generate_architecture_candidates")
def generate_architecture_candidates(
    include_async: bool = True,
    include_unsupported: bool = False,
) -> Dict[str, Any]:
    """Generates candidate architecture graphs and validates their topology."""
    try:
        gen = ArchitectureGenerator()
        candidates = gen.generate_candidates(
            include_async=include_async,
            include_unsupported=include_unsupported,
        )
        errors = []
        for c in candidates:
            try:
                gen.validate_graph(c)
            except Exception as e:
                errors.append(f"Validation failed for {c.id}: {str(e)}")

        return {
            "is_valid": len(errors) == 0,
            "candidates": [c.model_dump() for c in candidates],
            "errors": errors,
        }
    except Exception as e:
        return {
            "is_valid": False,
            "candidates": [],
            "errors": [str(e)],
        }


@tool("check_component_models")
def check_component_models(
    candidates_data: List[Dict[str, Any]],
    workload_data: Dict[str, Any],
    registry: Optional[ComponentRegistry] = None,
) -> Dict[str, Any]:
    """Inspects component registry for valid performance models across candidate architectures."""
    reg = registry or ComponentRegistry()
    reg.seed_baseline_data()
    workload = WorkloadSpec(**workload_data)

    all_keys = []
    for c_dict in candidates_data:
        c = ArchitectureGraph.model_validate(c_dict)
        all_keys.extend(c.required_models)
    all_keys = sorted(list(set(all_keys)))

    missing = []
    statuses = {}
    for key in all_keys:
        comp_name, version = key.split(":", 1) if ":" in key else (key, "latest")
        status, model, warnings = reg.check_compatibility(comp_name, version, workload)
        statuses[key] = {
            "status": status,
            "is_validated": model.is_validated if model else False,
            "is_synthetic": model.is_synthetic_fixture if model else None,
            "warnings": warnings,
        }
        if status == "MISSING":
            missing.append(key)

    return {
        "missing_models": missing,
        "statuses": statuses,
    }


@tool("run_benchmark")
def run_benchmark(
    component_name: str,
    version: str,
    workload_data: Dict[str, Any],
    budget_runs: int = 6,
    force_synthetic: bool = True,
    seed: int = 42,
    registry: Optional[ComponentRegistry] = None,
) -> Dict[str, Any]:
    """Executes a bounded benchmark campaign for a whitelisted component."""
    # Safety boundary: only whitelisted benchmark targets allowed
    clean_name = component_name.strip().lower()
    if clean_name not in ALLOWED_BENCHMARK_COMPONENTS:
        return {
            "success": False,
            "error": f"Component '{component_name}' not in allowed benchmark catalog ({list(ALLOWED_BENCHMARK_COMPONENTS)})",
            "provenance": "unknown",
            "experiments": [],
        }

    try:
        reg = registry or ComponentRegistry()
        workload = WorkloadSpec(**workload_data)
        syn_runner = SyntheticBenchmarkRunner(seed=seed)
        exp_mgr = AdaptiveExperimentManager(registry=reg, synthetic_runner=syn_runner)

        campaign = exp_mgr.run_campaign(
            component_name=clean_name,
            version=version,
            workload=workload,
            budget_runs=min(budget_runs, 8),
            force_synthetic=force_synthetic,
        )
        return {
            "success": True,
            "component_name": clean_name,
            "version": version,
            "total_experiments": campaign["total_experiments"],
            "provenance": "synthetic" if campaign["is_synthetic_fixture"] else "measured",
            "experiments": [e.model_dump() for e in campaign["experiments"]],
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "provenance": "unknown",
            "experiments": [],
        }


@tool("fit_and_validate_model")
def fit_and_validate_model(
    component_name: str,
    version: str,
    experiments_data: List[Dict[str, Any]],
    registry: Optional[ComponentRegistry] = None,
) -> Dict[str, Any]:
    """Fits performance model using group-based held-out validation and registers it."""
    try:
        reg = registry or ComponentRegistry()
        experiments = [ExperimentRecord(**d) for d in experiments_data]
        model_rec, metrics = ModelTrainer.train_and_validate(component_name, version, experiments)

        if model_rec.is_validated:
            reg.register_model(model_rec)

        return {
            "success": True,
            "is_validated": model_rec.is_validated,
            "model_id": model_rec.model_id,
            "model_type": model_rec.model_type,
            "r2_score": model_rec.r2_score,
            "rmse_ms": model_rec.validation_rmse_ms,
            "metrics": metrics,
        }
    except Exception as e:
        return {
            "success": False,
            "is_validated": False,
            "error": str(e),
        }


@tool("simulate_architecture")
def simulate_architecture(
    architecture_data: Dict[str, Any],
    workload_data: Dict[str, Any],
    duration_seconds: float = 5.0,
    random_seed: int = 42,
    registry: Optional[ComponentRegistry] = None,
) -> Dict[str, Any]:
    """Simulates a candidate architecture in SimPy with contention and queue modeling."""
    try:
        reg = registry or ComponentRegistry()
        arch = ArchitectureGraph.model_validate(architecture_data)
        workload = WorkloadSpec(**workload_data)
        sim_engine = SimPyEngine(registry=reg)

        sim_res = sim_engine.simulate_architecture(
            architecture=arch,
            workload=workload,
            duration_seconds=duration_seconds,
            random_seed=random_seed,
        )
        return {
            "success": True,
            "result": sim_res.model_dump(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "result": None,
        }


@tool("evaluate_candidates")
def evaluate_candidates(
    workload_data: Dict[str, Any],
    simulation_results_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Applies SLA feasibility filtering, Pareto dominance, and preference scoring."""
    try:
        workload = WorkloadSpec(**workload_data)
        sim_results = [SimulationResult.model_validate(d) for d in simulation_results_data]

        rec = ArchitectureRecommender.evaluate_and_recommend(
            workload=workload,
            sim_results=sim_results,
        )
        return {
            "success": True,
            "recommendation": rec.model_dump(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "recommendation": None,
        }
