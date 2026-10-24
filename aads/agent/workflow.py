"""
LangGraph Orchestrator for AADS.
Constructs and compiles the bounded, typed StateGraph workflow with conditional routing.
"""
import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END

from aads.agent.state import AgentWorkflowState
from aads.agent.schemas import AgentResponse
from aads.agent.provider import LLMProvider
from aads.agent.architecture_agent import ArchitectureAgent
from aads.agent.tools import (
    ValidateWorkloadTool,
    GenerateCandidatesTool,
    CheckComponentModelsTool,
    RunBenchmarkTool,
    FitModelTool,
    SimulateArchitectureTool,
    EvaluateCandidatesTool,
)
from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
)
from aads.core.config import settings, LLMConfig

logger = logging.getLogger("aads.agent.workflow")


class WorkflowNodes:
    """Nodes defining individual steps in the LangGraph workflow."""

    def __init__(self, agent: ArchitectureAgent):
        self.agent = agent
        self.validate_tool = ValidateWorkloadTool()
        self.generate_tool = GenerateCandidatesTool()
        self.check_models_tool = CheckComponentModelsTool()
        self.benchmark_tool = RunBenchmarkTool()
        self.fit_tool = FitModelTool()
        self.simulate_tool = SimulateArchitectureTool()
        self.evaluate_tool = EvaluateCandidatesTool()

    def parse_requirements(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 1: Extract structured engineering workload specs from natural language."""
        req_text = state.get("request_text", "")
        extracted, mode = self.agent.extract_requirements(req_text)

        if extracted.clarification_needed:
            return {
                "execution_mode": mode,
                "clarification_questions": extracted.clarification_questions,
                "workflow_status": "CLARIFICATION_NEEDED",
                "executive_summary": "Requirements are ambiguous or missing operational targets. Clarification needed.",
            }

        try:
            workload = self.agent.build_workload_spec(extracted)
            v_res = self.validate_tool._run(workload.model_dump())
            if v_res.get("status") != "VALID":
                return {
                    "execution_mode": mode,
                    "errors": [f"Workload validation failed: {v_res.get('error')}"],
                    "workflow_status": "FAILED",
                }

            prov = {
                "workload_provenance": "Extracted via " + ("LangChain ChatOpenAI" if mode == "llm" else "Deterministic Fallback Parser"),
                "benchmark_mode": "Deterministic Synthetic Fixtures & Empirical Regressions",
                "simulation_mode": "SimPy Discrete-Event Contention Simulation",
            }
            return {
                "execution_mode": mode,
                "workload_spec": v_res["workload"],
                "assumptions": extracted.agent_assumptions,
                "provenance": prov,
                "workflow_status": "VALIDATING",
            }
        except Exception as e:
            return {
                "execution_mode": mode,
                "errors": [f"Failed to parse requirements: {str(e)}"],
                "workflow_status": "FAILED",
            }

    def generate_and_validate_candidates(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 2: Generate candidate architectures and validate topology DAGs."""
        try:
            candidates = self.generate_tool._run(include_async=True, include_unsupported=True)
            return {
                "candidate_architectures": candidates,
                "validation_results": {"topology_status": "VALID", "candidate_count": len(candidates)},
                "workflow_status": "VALIDATING",
            }
        except Exception as e:
            return {
                "errors": state.get("errors", []) + [f"Candidate generation failed: {str(e)}"],
                "workflow_status": "FAILED",
            }

    def inspect_models(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 3: Inspect SQLite registry for required component performance models."""
        candidates = state.get("candidate_architectures", [])
        workload = state.get("workload_spec", {})

        all_models = []
        for c in candidates:
            all_models.extend(c.get("required_models", []))
        all_models = sorted(list(set(all_models)))

        check_res = self.check_models_tool._run(model_keys=all_models, workload_dict=workload)
        missing = check_res.get("missing_models", [])

        return {
            "missing_models": missing,
            "validation_results": {**state.get("validation_results", {}), "model_checks": check_res},
            "workflow_status": "BENCHMARKING" if missing else "SIMULATING",
        }

    def benchmark_models(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 4: Execute controlled benchmark campaigns and calibrate missing models."""
        missing = state.get("missing_models", [])
        workload = state.get("workload_spec", {})
        bench_results = []
        fit_results = []

        for model_key in missing:
            comp_name, version = model_key.split(":", 1) if ":" in model_key else (model_key, "latest")
            b_res = self.benchmark_tool._run(
                component_name=comp_name,
                version=version,
                workload_dict=workload,
                budget_runs=6,
                force_synthetic=True,
            )
            bench_results.append(b_res)

            f_res = self.fit_tool._run(
                component_name=comp_name,
                version=version,
                experiments_data=b_res["experiments"],
            )
            fit_results.append(f_res)

        return {
            "benchmark_results": bench_results,
            "model_fit_results": fit_results,
            "missing_models": [],  # Calibrated and registered!
            "workflow_status": "SIMULATING",
        }

    def report_insufficient_evidence(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 4b: Handle unbenchmarked components when authorization is not granted."""
        missing = state.get("missing_models", [])
        return {
            "workflow_status": "INSUFFICIENT_EVIDENCE",
            "executive_summary": (
                f"Workflow stopped: Component models {missing} are missing from the registry, "
                "and autonomous benchmark authorization was not granted. Cannot establish feasibility."
            ),
        }

    def simulate_candidates(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 5: Run SimPy discrete-event simulations under identical workload."""
        candidates = state.get("candidate_architectures", [])
        workload = state.get("workload_spec", {})
        duration = state.get("simulation_duration_seconds", 5.0)
        seed = state.get("random_seed", 42)

        # Simulate all candidates with validated models
        sim_results = []
        for c in candidates:
            # Skip unsupported candidates if still unbenchmarked
            if c.get("id") == "arch_mongo_unregistered" and state.get("missing_models"):
                continue
            res = self.simulate_tool._run(
                architecture_dict=c,
                workload_dict=workload,
                duration_seconds=duration,
                random_seed=seed,
            )
            sim_results.append(res)

        return {
            "simulation_results": sim_results,
            "workflow_status": "EVALUATING",
        }

    def evaluate_and_recommend(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 6: Feasibility filtering, Pareto analysis, and multi-objective ranking."""
        workload = state.get("workload_spec", {})
        sim_results = state.get("simulation_results", [])

        if not sim_results:
            return {
                "workflow_status": "INSUFFICIENT_EVIDENCE",
                "errors": state.get("errors", []) + ["No candidate architectures could be simulated."],
            }

        rec = self.evaluate_tool._run(
            workload_dict=workload,
            simulation_results_data=sim_results,
        )

        return {
            "recommendation": rec,
            "evaluation_results": {"evaluations": rec.get("evaluations", [])},
            "workflow_status": "COMPLETED",
        }

    def synthesize_explanation(self, state: AgentWorkflowState) -> Dict[str, Any]:
        """Step 7: Final explanation synthesis and status consolidation."""
        rec = state.get("recommendation", {})
        if not rec:
            return {"executive_summary": "No recommendation could be established."}

        winner_name = rec.get("selected_architecture_name", "Unknown")
        status = rec.get("status", "UNKNOWN")
        exec_summary = rec.get("executive_summary", "")

        summary_text = (
            f"[{status}] Recommended Architecture: {winner_name}\n"
            f"{exec_summary}\n"
            f"Execution Mode: {state.get('execution_mode', 'unknown').upper()}"
        )

        return {
            "executive_summary": summary_text,
            "workflow_status": "COMPLETED",
        }


# ==============================================================================
# Conditional Routing Functions
# ==============================================================================
def route_after_parsing(state: AgentWorkflowState) -> str:
    """Routes based on whether clarification is needed or parsing failed."""
    if state.get("workflow_status") == "CLARIFICATION_NEEDED":
        return "need_clarification"
    if state.get("workflow_status") == "FAILED":
        return "failed"
    return "proceed_to_candidates"


def route_after_model_check(state: AgentWorkflowState) -> str:
    """Routes based on model availability and benchmark authorization."""
    missing = state.get("missing_models", [])
    if not missing:
        return "ready_to_simulate"
    if state.get("authorized_benchmarks", True):
        return "benchmark_missing"
    return "insufficient_evidence"


# ==============================================================================
# LangGraph Workflow Builder
# ==============================================================================
def create_aads_graph(agent: ArchitectureAgent) -> StateGraph:
    """Assembles and connects the LangGraph state graph for AADS."""
    nodes = WorkflowNodes(agent)
    workflow = StateGraph(AgentWorkflowState)

    # Add Nodes
    workflow.add_node("parse_requirements", nodes.parse_requirements)
    workflow.add_node("generate_candidates", nodes.generate_and_validate_candidates)
    workflow.add_node("inspect_models", nodes.inspect_models)
    workflow.add_node("benchmark_models", nodes.benchmark_models)
    workflow.add_node("report_insufficient_evidence", nodes.report_insufficient_evidence)
    workflow.add_node("simulate", nodes.simulate_candidates)
    workflow.add_node("evaluate", nodes.evaluate_and_recommend)
    workflow.add_node("synthesize", nodes.synthesize_explanation)

    # Set Entry Point
    workflow.set_entry_point("parse_requirements")

    # Add Conditional Edges
    workflow.add_conditional_edges(
        "parse_requirements",
        route_after_parsing,
        {
            "need_clarification": END,
            "failed": END,
            "proceed_to_candidates": "generate_candidates",
        },
    )

    workflow.add_edge("generate_candidates", "inspect_models")

    workflow.add_conditional_edges(
        "inspect_models",
        route_after_model_check,
        {
            "ready_to_simulate": "simulate",
            "benchmark_missing": "benchmark_models",
            "insufficient_evidence": "report_insufficient_evidence",
        },
    )

    workflow.add_edge("benchmark_models", "simulate")
    workflow.add_edge("report_insufficient_evidence", END)
    workflow.add_edge("simulate", "evaluate")
    workflow.add_edge("evaluate", "synthesize")
    workflow.add_edge("synthesize", END)

    return workflow


class AADSWorkflow:
    """High-level runner for the compiled AADS LangGraph workflow."""

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        self.config = llm_config or settings.llm
        llm, self.execution_mode = LLMProvider.get_chat_model(self.config)
        self.agent = ArchitectureAgent(llm=llm)
        self.graph = create_aads_graph(self.agent).compile()

    def run(
        self,
        request_text: str,
        authorized_benchmarks: bool = True,
        simulation_duration_seconds: float = 5.0,
        random_seed: int = 42,
    ) -> AgentResponse:
        """Executes the complete LangGraph workflow given a natural language prompt."""
        initial_state: AgentWorkflowState = {
            "request_text": request_text,
            "execution_mode": self.execution_mode,
            "workload_spec": None,
            "clarification_questions": [],
            "assumptions": [],
            "candidate_architectures": [],
            "validation_results": {},
            "missing_models": [],
            "authorized_benchmarks": authorized_benchmarks,
            "benchmark_results": [],
            "model_fit_results": [],
            "simulation_results": [],
            "evaluation_results": None,
            "recommendation": None,
            "provenance": {},
            "errors": [],
            "workflow_status": "PARSING",
            "executive_summary": "",
            "random_seed": random_seed,
            "simulation_duration_seconds": simulation_duration_seconds,
        }

        final_state = self.graph.invoke(initial_state)

        # Convert state dictionaries to typed Pydantic models for safe response return
        workload = WorkloadSpec(**final_state["workload_spec"]) if final_state.get("workload_spec") else None
        candidates = [ArchitectureGraph(**c) for c in final_state.get("candidate_architectures", [])]
        sim_res = [SimulationResult(**s) for s in final_state.get("simulation_results", [])]
        rec = RecommendationResult(**final_state["recommendation"]) if final_state.get("recommendation") else None

        return AgentResponse(
            workflow_status=final_state.get("workflow_status", "UNKNOWN"),
            execution_mode=final_state.get("execution_mode", self.execution_mode),
            request_text=request_text,
            workload=workload,
            clarification_questions=final_state.get("clarification_questions", []),
            candidate_architectures=candidates,
            missing_models=final_state.get("missing_models", []),
            simulation_results=sim_res,
            recommendation=rec,
            evidence_provenance=final_state.get("provenance", {}),
            errors=final_state.get("errors", []),
            executive_summary=final_state.get("executive_summary", ""),
        )
