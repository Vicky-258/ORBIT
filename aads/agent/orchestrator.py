"""
LangGraph Orchestrator for AADS.
Coordinates natural-language parsing, candidate generation, registry model checking,
adaptive benchmarking, discrete-event simulation, and explainable recommendation.
"""
import logging
from typing import Dict, Any, Optional, List
from langgraph.graph import StateGraph, START, END

from aads.agent.state import AgentWorkflowState
from aads.agent.provider import LLMProviderManager, ExecutionMode
from aads.agent.architecture_agent import ArchitectureAgent
from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    FeasibilityStatus,
)
from aads.registry.component_registry import ComponentRegistry
from aads.agent.tools import (
    validate_workload,
    generate_architecture_candidates,
    check_component_models,
    run_benchmark,
    fit_and_validate_model,
    simulate_architecture,
    evaluate_candidates,
)

logger = logging.getLogger("aads.agent.orchestrator")


class AADSOrchestrator:
    """
    Main LangGraph workflow orchestrator.
    Controls execution sequence and handles conditional routing for ambiguities,
    missing models, tool failures, and constraint evaluations.
    """

    def __init__(
        self,
        registry: Optional[ComponentRegistry] = None,
        provider_mgr: Optional[LLMProviderManager] = None,
    ):
        self.registry = registry or ComponentRegistry()
        self.registry.seed_baseline_data()
        self.provider_mgr = provider_mgr or LLMProviderManager()
        self.agent = ArchitectureAgent(provider_mgr=self.provider_mgr)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentWorkflowState)

        # 1. Register Nodes
        builder.add_node("parse_workload", self._parse_workload_node)
        builder.add_node("generate_candidates", self._generate_candidates_node)
        builder.add_node("check_models", self._check_models_node)
        builder.add_node("benchmark_and_train", self._benchmark_and_train_node)
        builder.add_node("simulate", self._simulate_node)
        builder.add_node("evaluate_and_recommend", self._evaluate_and_recommend_node)

        # 2. Register Edges
        builder.add_edge(START, "parse_workload")

        builder.add_conditional_edges(
            "parse_workload",
            self._route_after_parse,
            {
                "clarification": END,
                "failed": END,
                "proceed": "generate_candidates",
            },
        )

        builder.add_conditional_edges(
            "generate_candidates",
            self._route_after_candidates,
            {
                "failed": END,
                "proceed": "check_models",
            },
        )

        builder.add_conditional_edges(
            "check_models",
            self._route_after_check_models,
            {
                "simulate": "simulate",
                "benchmark": "benchmark_and_train",
                "unresolved": END,
            },
        )

        builder.add_conditional_edges(
            "benchmark_and_train",
            self._route_after_benchmark,
            {
                "simulate": "simulate",
                "unresolved": END,
            },
        )

        builder.add_edge("simulate", "evaluate_and_recommend")
        builder.add_edge("evaluate_and_recommend", END)

        return builder.compile()

    # --- Node Implementations ---

    def _parse_workload_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        req_text = state.get("request_text", "")
        spec, questions, assumptions, mode = self.agent.parse_request(req_text)
        
        errors = list(state.get("errors", []))
        provenance = dict(state.get("provenance", {}))
        provenance["request_parsing"] = "user_fact" if mode == ExecutionMode.LLM else "agent_assumption"

        if spec is not None:
            # Pass through existing AADS schema validation tool
            val_res = validate_workload.invoke({"workload_data": spec.model_dump()})
            if not val_res.get("valid", True):
                errors.extend(val_res.get("errors", []))
                status = "FAILED"
            elif questions:
                status = "NEEDS_CLARIFICATION"
            else:
                status = "WORKLOAD_PARSED"
        else:
            status = "NEEDS_CLARIFICATION" if questions else "FAILED"

        return {
            "workload_spec": spec,
            "clarification_questions": questions,
            "assumptions": assumptions,
            "execution_mode": mode.value,
            "errors": errors,
            "provenance": provenance,
            "workflow_status": status,
        }

    def _generate_candidates_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        include_async = state.get("include_async", True)
        include_unsupported = state.get("include_unsupported", False)
        
        candidates_raw, val_meta = self.agent.generate_and_validate_candidates(
            include_async=include_async,
            include_unsupported=include_unsupported,
        )

        errors = list(state.get("errors", []))
        if not val_meta.get("valid", True):
            errors.extend(val_meta.get("errors", []))
            status = "FAILED"
        else:
            status = "CANDIDATES_GENERATED"

        return {
            "candidate_architectures": candidates_raw,
            "validation_results": val_meta,
            "errors": errors,
            "workflow_status": status,
        }

    def _check_models_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        candidates = state.get("candidate_architectures", [])
        workload = state.get("workload_spec")
        if not workload or not candidates:
            return {"workflow_status": "FAILED", "errors": ["Missing candidates or workload for model checking"]}

        res = check_component_models.invoke({
            "candidates_data": [c.model_dump() for c in candidates],
            "workload_data": workload.model_dump(),
            "registry": self.registry,
        })

        missing = res.get("missing_models", [])
        status = "MODELS_CHECKED" if not missing else ("BENCHMARKING" if state.get("auto_benchmark_missing", True) else "UNRESOLVED")

        return {
            "missing_models": missing,
            "workflow_status": status,
        }

    def _benchmark_and_train_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        workload = state.get("workload_spec")
        missing = state.get("missing_models", [])
        force_syn = state.get("force_synthetic", True)
        seed = state.get("random_seed", 42)

        benchmark_results = []
        model_fit_results = []
        provenance = dict(state.get("provenance", {}))
        errors = list(state.get("errors", []))

        for model_key in missing:
            comp_name, version = model_key.split(":", 1) if ":" in model_key else (model_key, "latest")
            # 1. Run controlled benchmark tool
            bench_res = run_benchmark.invoke({
                "component_name": comp_name,
                "version": version,
                "workload_data": workload.model_dump(),
                "budget_runs": 6,
                "force_synthetic": force_syn,
                "seed": seed,
                "registry": self.registry,
            })
            benchmark_results.append(bench_res)
            provenance[f"benchmark_{comp_name}"] = bench_res.get("provenance", "synthetic")

            if not bench_res.get("success", False):
                errors.append(f"Benchmarking failed for {comp_name}: {bench_res.get('error')}")
                continue

            # 2. Fit and validate model tool
            fit_res = fit_and_validate_model.invoke({
                "component_name": comp_name,
                "version": version,
                "experiments_data": bench_res.get("experiments", []),
                "registry": self.registry,
            })
            model_fit_results.append(fit_res)
            provenance[f"model_{comp_name}"] = "model-predicted"

            if not fit_res.get("is_validated", False):
                errors.append(f"Model validation threshold not met for {comp_name}")

        status = "BENCHMARK_COMPLETED" if not errors else "UNRESOLVED"

        return {
            "benchmark_results": benchmark_results,
            "model_fit_results": model_fit_results,
            "errors": errors,
            "provenance": provenance,
            "workflow_status": status,
        }

    def _simulate_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        candidates = state.get("candidate_architectures", [])
        workload = state.get("workload_spec")
        duration = state.get("simulation_duration_seconds", 5.0)
        seed = state.get("random_seed", 42)

        sim_results: List[SimulationResult] = []
        provenance = dict(state.get("provenance", {}))
        provenance["simulation"] = "simulated"

        # Simulate candidates whose required models are all registered
        for c in candidates:
            all_models_present = all(
                self.registry.get_model(*(m.split(":", 1) if ":" in m else (m, "latest"))) is not None
                for m in c.required_models
            )
            if all_models_present:
                sim_res = simulate_architecture.invoke({
                    "architecture_data": c.model_dump(),
                    "workload_data": workload.model_dump(),
                    "duration_seconds": duration,
                    "random_seed": seed,
                    "registry": self.registry,
                })
                if sim_res.get("success", False):
                    sim_results.append(SimulationResult.model_validate(sim_res["result"]))

        return {
            "simulation_results": sim_results,
            "provenance": provenance,
            "workflow_status": "SIMULATED",
        }

    def _evaluate_and_recommend_node(self, state: AgentWorkflowState) -> Dict[str, Any]:
        workload = state.get("workload_spec")
        sim_results = state.get("simulation_results", [])

        if not sim_results:
            return {
                "workflow_status": "UNRESOLVED",
                "errors": ["No candidates could be simulated due to missing models or validation failures"],
            }

        eval_res = evaluate_candidates.invoke({
            "workload_data": workload.model_dump(),
            "simulation_results_data": [s.model_dump() for s in sim_results],
        })

        if eval_res.get("success", False):
            rec = RecommendationResult.model_validate(eval_res["recommendation"])
            status = "RECOMMENDED"
        else:
            rec = None
            status = "FAILED"

        provenance = dict(state.get("provenance", {}))
        provenance["recommendation"] = "model-predicted"

        return {
            "recommendation": rec,
            "evaluation_results": eval_res,
            "provenance": provenance,
            "workflow_status": status,
        }

    # --- Routing Conditions ---

    def _route_after_parse(self, state: AgentWorkflowState) -> str:
        if state.get("clarification_questions") and state.get("workload_spec") is None:
            return "clarification"
        if state.get("errors"):
            return "failed"
        return "proceed"

    def _route_after_candidates(self, state: AgentWorkflowState) -> str:
        if not state.get("candidate_architectures") or state.get("workflow_status") == "FAILED":
            return "failed"
        return "proceed"

    def _route_after_check_models(self, state: AgentWorkflowState) -> str:
        missing = state.get("missing_models", [])
        if not missing:
            return "simulate"
        if state.get("auto_benchmark_missing", True):
            return "benchmark"
        return "unresolved"

    def _route_after_benchmark(self, state: AgentWorkflowState) -> str:
        if state.get("workflow_status") == "UNRESOLVED" or state.get("errors"):
            return "unresolved"
        return "simulate"

    # --- Top-Level Runner ---

    def run(
        self,
        request_text: str,
        auto_benchmark_missing: bool = True,
        force_synthetic: bool = True,
        simulation_duration_seconds: float = 5.0,
        random_seed: int = 42,
        include_async: bool = True,
        include_unsupported: bool = False,
    ) -> AgentWorkflowState:
        """
        Executes the compiled LangGraph workflow from start to finish.
        """
        initial_state: AgentWorkflowState = {
            "request_text": request_text,
            "auto_benchmark_missing": auto_benchmark_missing,
            "force_synthetic": force_synthetic,
            "simulation_duration_seconds": simulation_duration_seconds,
            "random_seed": random_seed,
            "include_async": include_async,
            "include_unsupported": include_unsupported,
            "workload_spec": None,
            "clarification_questions": [],
            "assumptions": [],
            "candidate_architectures": [],
            "validation_results": {},
            "missing_models": [],
            "benchmark_results": [],
            "model_fit_results": [],
            "simulation_results": [],
            "evaluation_results": None,
            "recommendation": None,
            "provenance": {},
            "errors": [],
            "workflow_status": "INITIALIZED",
            "execution_mode": self.provider_mgr.get_execution_mode().value,
        }

        final_state = self.graph.invoke(initial_state)
        return final_state
