"""
AADS Agent Layer.
LangChain & LangGraph-based Architecture Design & Simulation Agent.
"""
from aads.agent.provider import LLMProviderManager, ExecutionMode, LLMProvider, verify_live_llm
from aads.agent.architecture_agent import ArchitectureAgent, WorkloadExtractionResult
from aads.agent.schemas import (
    RecommendationExplanation,
    InvestigationActionType,
    InvestigationDecision,
    InvestigationRecord,
    BenchmarkProposalDetails,
)
from aads.agent.investigation_policy import (
    InvestigationPolicy,
    PolicyVerdict,
    PolicyEvaluationResult,
)
from aads.agent.investigation_dispatcher import InvestigationDispatcher
from aads.agent.investigation_planner import InvestigationPlanner
from aads.agent.recommendation_synthesizer import RecommendationSynthesizer
from aads.agent.orchestrator import AADSOrchestrator
from aads.agent.state import AgentWorkflowState
from aads.agent.tools import (
    validate_workload,
    generate_architecture_candidates,
    check_component_models,
    run_benchmark,
    fit_and_validate_model,
    simulate_architecture,
    evaluate_candidates,
)

__all__ = [
    "AADSOrchestrator",
    "ArchitectureAgent",
    "WorkloadExtractionResult",
    "RecommendationSynthesizer",
    "RecommendationExplanation",
    "LLMProviderManager",
    "verify_live_llm",
    "ExecutionMode",
    "LLMProvider",
    "AgentWorkflowState",
    "validate_workload",
    "generate_architecture_candidates",
    "check_component_models",
    "run_benchmark",
    "fit_and_validate_model",
    "simulate_architecture",
    "evaluate_candidates",
    "InvestigationActionType",
    "InvestigationDecision",
    "InvestigationRecord",
    "BenchmarkProposalDetails",
    "InvestigationPolicy",
    "PolicyVerdict",
    "PolicyEvaluationResult",
    "InvestigationDispatcher",
    "InvestigationPlanner",
]
