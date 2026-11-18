"""
LangGraph Typed State for ORBIT Agentic Workflow.
Maintains typed state across all workflow nodes, routing conditions, and evaluations.
"""
from typing import TypedDict, List, Dict, Any, Optional
from orbit.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
)


class AgentWorkflowState(TypedDict, total=False):
    """Authoritative state schema for LangGraph workflow execution."""
    request_text: str
    execution_mode: str
    auto_benchmark_missing: bool
    force_synthetic: bool
    simulation_duration_seconds: float
    random_seed: int
    include_async: bool
    include_unsupported: bool
    workload_spec: Optional[WorkloadSpec]
    clarification_questions: List[str]
    assumptions: List[str]
    candidate_architectures: List[ArchitectureGraph]
    validation_results: Dict[str, Any]
    missing_models: List[str]
    benchmark_results: List[Dict[str, Any]]
    model_fit_results: List[Dict[str, Any]]
    simulation_results: List[SimulationResult]
    evaluation_results: Optional[Dict[str, Any]]
    recommendation: Optional[RecommendationResult]
    provenance: Dict[str, str]
    errors: List[str]
    workflow_status: str
    executive_summary: str
    structured_explanation: Optional[Dict[str, Any]]
    explanation_source: Optional[str]
    investigation_round: int
    max_investigation_rounds: int
    investigation_trace: List[Dict[str, Any]]
    investigation_budget_seconds: float
    investigation_budget_spent: float
    benchmark_proposals: List[Dict[str, Any]]
    active_decision: Optional[Dict[str, Any]]
    investigation_status: str
    clarification_turn: int
    sdk_workspace_id: Optional[str]
    sdk_experiments: List[str]
