"""
FastAPI Routes for AADS.
Provides clean REST API endpoints for every stage of the architecture design & simulation pipeline.
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    ModelRecord,
    ExperimentRecord,
    DemoWorkflowResponse,
)
from aads.core.demo_response_builder import build_demo_workflow_response
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.registry.component_registry import ComponentRegistry
from aads.benchmark.experiment_manager import AdaptiveExperimentManager
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.modeling.model_trainer import ModelTrainer
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender

router = APIRouter(prefix="/api")

# Shared singletons for API instance
registry = ComponentRegistry()
registry.seed_baseline_data()
generator = ArchitectureGenerator()
sim_engine = SimPyEngine(registry)
docker_runner = DockerBenchmarkRunner()
synthetic_runner = SyntheticBenchmarkRunner()
exp_manager = AdaptiveExperimentManager(
    registry=registry,
    docker_runner=docker_runner,
    synthetic_runner=synthetic_runner,
)


class BenchmarkRequest(BaseModel):
    component_name: str
    version: str
    workload: WorkloadSpec
    budget_runs: int = 6
    force_synthetic: bool = False


class WorkflowRequest(BaseModel):
    workload: WorkloadSpec
    include_async: bool = True
    include_unsupported: bool = False
    max_investigation_rounds: int = 3
    investigation_budget_seconds: float = 60.0
    simulation_duration_seconds: float = 8.0
    auto_benchmark_missing: bool = True
    force_synthetic: bool = False


@router.post("/workload/validate")
def validate_workload(workload: WorkloadSpec) -> Dict[str, Any]:
    """Validate user workload specification and return labeled assumptions and facts."""
    return {
        "workload": workload,
        "facts": [p for p in workload.provenance_map.values() if p.provenance == "user_fact"],
        "assumptions": [p for p in workload.provenance_map.values() if p.provenance == "agent_assumption"],
        "is_valid": True,
    }


@router.get("/candidates")
def get_candidates(
    include_async: bool = True,
    include_unsupported: bool = False,
) -> List[ArchitectureGraph]:
    """Generate architecture candidates with validated topology."""
    return generator.generate_candidates(
        include_async=include_async,
        include_unsupported=include_unsupported,
    )


@router.get("/registry/models")
def list_models() -> List[ModelRecord]:
    """List all registered component performance models."""
    return registry.list_models()


@router.get("/registry/experiments")
def list_experiments(
    component_name: Optional[str] = None,
    version: Optional[str] = None,
) -> List[ExperimentRecord]:
    """List benchmark experiment records."""
    if component_name and version:
        return registry.get_experiments(component_name, version)
    return registry.list_all_experiments()


@router.post("/registry/check-compatibility")
def check_compatibility(
    component_name: str,
    version: str,
    workload: WorkloadSpec,
) -> Dict[str, Any]:
    """Check if component model is available and covers the requested operating range."""
    status, model, warnings = registry.check_compatibility(component_name, version, workload)
    return {
        "status": status,
        "model": model,
        "warnings": warnings,
        "requires_benchmark": status in ("MISSING", "UNVALIDATED", "OUT_OF_RANGE"),
    }


@router.post("/benchmark/run")
def run_benchmark(req: BenchmarkRequest) -> Dict[str, Any]:
    """Run controlled benchmark trials (real Docker or synthetic fixture)."""
    campaign = exp_manager.run_campaign(
        component_name=req.component_name,
        version=req.version,
        workload=req.workload,
        budget_runs=req.budget_runs,
        force_synthetic=req.force_synthetic,
    )

    # Fit and validate model from benchmark results
    model_record, metrics = ModelTrainer.train_and_validate(
        component_name=req.component_name,
        version=req.version,
        experiments=campaign["experiments"],
    )

    # If validated, register model
    if model_record.is_validated:
        registry.register_model(model_record)

    return {
        "campaign": campaign,
        "fitted_model": model_record,
        "validation_metrics": metrics,
        "registered": model_record.is_validated,
    }


@router.post("/simulate")
def simulate(
    workload: WorkloadSpec,
    include_async: bool = True,
    duration_seconds: float = 8.0,
    random_seed: int = 42,
) -> List[SimulationResult]:
    """Simulate candidate architectures under the same workload with SimPy."""
    candidates = generator.generate_candidates(include_async=include_async)
    results = [
        sim_engine.simulate_architecture(
            architecture=c,
            workload=workload,
            duration_seconds=duration_seconds,
            random_seed=random_seed,
        )
        for c in candidates
    ]
    return results


@router.post("/evaluate")
def evaluate(
    workload: WorkloadSpec,
    sim_results: List[SimulationResult],
) -> RecommendationResult:
    """Execute two-stage feasibility filtering and trade-off recommendation."""
    return ArchitectureRecommender.evaluate_and_recommend(
        workload=workload,
        sim_results=sim_results,
    )


@router.post("/workflow/run")
def run_end_to_end_workflow(req: WorkflowRequest) -> Dict[str, Any]:
    """
    Execute complete end-to-end workflow:
    1. Validate workload
    2. Generate candidates
    3. Check model discovery & benchmark if missing
    4. Simulate all architectures in SimPy
    5. Evaluate & recommend
    """
    # 1. Candidates
    candidates = generator.generate_candidates(
        include_async=req.include_async,
        include_unsupported=req.include_unsupported,
    )

    # 2. Check models & discover missing
    model_status: Dict[str, Any] = {}
    benchmark_campaigns: List[Dict[str, Any]] = []

    for cand in candidates:
        for model_key in cand.required_models:
            comp_name, version = model_key.split(":", 1) if ":" in model_key else (model_key, "latest")
            status, model, warnings = registry.check_compatibility(comp_name, version, req.workload)
            model_status[model_key] = {"status": status, "model": model, "warnings": warnings}

            if status == "MISSING" and req.auto_benchmark_missing:
                # Run benchmark campaign & model training
                campaign = exp_manager.run_campaign(
                    component_name=comp_name,
                    version=version,
                    workload=req.workload,
                    budget_runs=6,
                    force_synthetic=req.force_synthetic,
                )
                model_rec, metrics = ModelTrainer.train_and_validate(
                    component_name=comp_name,
                    version=version,
                    experiments=campaign["experiments"],
                )
                if model_rec.is_validated:
                    registry.register_model(model_rec)
                benchmark_campaigns.append({
                    "component": model_key,
                    "campaign": campaign,
                    "model": model_rec,
                    "metrics": metrics,
                })

    # 3. Filter to simulated candidates (only architectures with valid models)
    simulatable = [c for c in candidates if c.id != "arch_mongo_unregistered" or not req.include_unsupported]

    # 4. Simulate
    sim_results = [
        sim_engine.simulate_architecture(
            architecture=c,
            workload=req.workload,
            duration_seconds=req.simulation_duration_seconds,
            random_seed=42,
        )
        for c in simulatable
    ]

    # 5. Evaluate and Recommend
    recommendation = ArchitectureRecommender.evaluate_and_recommend(
        workload=req.workload,
        sim_results=sim_results,
    )

    return {
        "workload": req.workload,
        "candidates": candidates,
        "model_status": model_status,
        "benchmark_campaigns": benchmark_campaigns,
        "simulation_results": sim_results,
        "recommendation": recommendation,
    }


class AgentPromptRequest(BaseModel):
    prompt: str
    auto_benchmark_missing: bool = True
    force_synthetic: bool = True
    simulation_duration_seconds: float = 5.0
    random_seed: int = 42
    include_async: bool = True
    include_unsupported: bool = False
    max_investigation_rounds: int = 3
    investigation_budget_seconds: float = 60.0


@router.post("/agent/run")
def run_agent_workflow(req: AgentPromptRequest) -> Dict[str, Any]:
    """
    Natural-language architecture design & simulation agent endpoint.
    Orchestrates LangChain parsing, SimPy simulation, bounded investigation,
    and returns both backward-compatible fields and standardized Sections A-E.
    """
    from aads.agent.orchestrator import AADSOrchestrator
    orchestrator = AADSOrchestrator(registry=registry)
    state = orchestrator.run(
        request_text=req.prompt,
        auto_benchmark_missing=req.auto_benchmark_missing,
        force_synthetic=req.force_synthetic,
        simulation_duration_seconds=req.simulation_duration_seconds,
        random_seed=req.random_seed,
        include_async=req.include_async,
        include_unsupported=req.include_unsupported,
        max_investigation_rounds=req.max_investigation_rounds,
        investigation_budget_seconds=req.investigation_budget_seconds,
    )
    demo_resp = build_demo_workflow_response(state)
    resp_dict = demo_resp.model_dump()
    raw_rec = state.get("recommendation")
    if raw_rec is not None:
        rec_val = demo_resp.recommendation.model_dump()
        rec_val.update({
            "status": raw_rec.status.value if hasattr(raw_rec.status, "value") else str(raw_rec.status),
            "rationale": raw_rec.rationale,
            "predicted_metrics": raw_rec.predicted_metrics,
            "trade_offs_and_risks": raw_rec.trade_offs_and_risks,
            "assumptions_cited": raw_rec.assumptions_cited,
            "validation_gaps": raw_rec.validation_gaps,
            "recommended_next_experiment": raw_rec.recommended_next_experiment,
        })
    else:
        rec_val = None

    resp_dict.update({
        "workflow_status": state.get("workflow_status"),
        "execution_mode": state.get("execution_mode"),
        "workload_spec": state.get("workload_spec"),
        "clarification_questions": state.get("clarification_questions", []),
        "assumptions": state.get("assumptions", []),
        "candidates": state.get("candidate_architectures", []),
        "validation_results": state.get("validation_results", {}),
        "missing_models": state.get("missing_models", []),
        "benchmark_results": state.get("benchmark_results", []),
        "model_fit_results": state.get("model_fit_results", []),
        "simulation_results": state.get("simulation_results", []),
        "recommendation": rec_val,
        "provenance": state.get("provenance", {}),
        "errors": state.get("errors", []),
        "explanation_source": state.get("explanation_source"),
        "structured_explanation": state.get("structured_explanation"),
        "investigation_trace": state.get("investigation_trace", []),
        "investigation_rounds": state.get("investigation_round", 0),
        "benchmark_proposals": state.get("benchmark_proposals", []),
        "demo_response": demo_resp.model_dump(),
    })
    return resp_dict


@router.post("/demo/run", response_model=DemoWorkflowResponse)
def run_demo_workflow(req: AgentPromptRequest) -> DemoWorkflowResponse:
    """
    Direct Phase 5.0 Demo endpoint returning strictly validated DemoWorkflowResponse
    containing Sections A through E.
    """
    from aads.agent.orchestrator import AADSOrchestrator
    orchestrator = AADSOrchestrator(registry=registry)
    state = orchestrator.run(
        request_text=req.prompt,
        auto_benchmark_missing=req.auto_benchmark_missing,
        force_synthetic=req.force_synthetic,
        simulation_duration_seconds=req.simulation_duration_seconds,
        random_seed=req.random_seed,
        include_async=req.include_async,
        include_unsupported=req.include_unsupported,
        max_investigation_rounds=req.max_investigation_rounds,
        investigation_budget_seconds=req.investigation_budget_seconds,
    )
    return build_demo_workflow_response(state)
