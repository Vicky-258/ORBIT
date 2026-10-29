"""
Pydantic contracts for Architecture Agent inputs, extractions, and responses.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
)


class AgentExecutionMode(str, Enum):
    LLM = "llm"
    FALLBACK = "fallback"


class ExtractedWorkloadRequirements(BaseModel):
    """Structured extraction of workload requirements from natural language."""
    app_type: str = Field(default="social_media_feed", description="Target application domain or workload type")
    request_rate_rps: Optional[float] = Field(default=None, description="Target steady-state throughput in requests/sec")
    peak_load_factor: Optional[float] = Field(default=None, description="Multiplier for peak traffic burst headroom")
    read_ratio: Optional[float] = Field(default=None, description="Proportion of read operations (0.0 - 1.0)")
    write_ratio: Optional[float] = Field(default=None, description="Proportion of write operations (0.0 - 1.0)")
    dataset_records: Optional[int] = Field(default=None, description="Estimated total dataset size in records/items")
    p95_latency_target_ms: Optional[float] = Field(default=None, description="Target p95 latency threshold in milliseconds")
    min_throughput_rps: Optional[float] = Field(default=None, description="Minimum acceptable throughput in requests/sec")
    max_monthly_budget_usd: Optional[float] = Field(default=None, description="Maximum monthly infrastructure budget in USD")
    cache_assumed_hit_rate: Optional[float] = Field(default=None, description="Assumed cache hit rate (0.0 - 1.0)")
    soft_preferences: Dict[str, float] = Field(
        default_factory=lambda: {"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        description="User preference weights across cost, latency, and simplicity (sum to 1.0)",
    )
    user_provided_facts: List[str] = Field(default_factory=list, description="Requirements explicitly stated by the user")
    agent_assumptions: List[str] = Field(default_factory=list, description="Defaults or assumptions inferred by the agent")
    clarification_needed: bool = Field(default=False, description="True if critical information is missing or contradictory")
    clarification_questions: List[str] = Field(default_factory=list, description="Targeted questions to ask user if clarification is needed")
    ambiguities_identified: List[str] = Field(default_factory=list, description="Ambiguities or conflicts detected in the request")


class InvestigationActionType(str, Enum):
    INSPECT_MODEL_COVERAGE = "inspect_model_coverage"
    SIMULATE_CANDIDATE = "simulate_candidate"
    INSPECT_UNCERTAINTY = "inspect_uncertainty"
    PROPOSE_BENCHMARK = "propose_benchmark"
    STOP_AND_RECOMMEND = "stop_and_recommend"
    STOP_INCONCLUSIVE = "stop_inconclusive"


class BenchmarkProposalDetails(BaseModel):
    """Details for a proposed benchmark campaign."""
    component_name: str = Field(default="postgres_db", description="Target component name to benchmark (postgres_db, redis_cache, mongodb_cluster)")
    version: str = Field(default="16", description="Component version")
    target_concurrency: int = Field(default=50, description="Proposed concurrency level to measure")
    workload_notes: Optional[str] = Field(default=None, description="Specific workload characteristics to test")
    rationale: str = Field(default="", description="Why this benchmark would reduce decision uncertainty")


class InvestigationDecision(BaseModel):
    """Structured decision produced by the agent for the next investigation step."""
    action: InvestigationActionType = Field(
        description="The investigation action chosen by the agent."
    )
    target: Optional[str] = Field(
        default=None,
        description="Target candidate architecture ID (e.g. 'arch_b_cached'), component name, or workload parameter."
    )
    reason: str = Field(
        description="Concise rationale grounded directly in current evidence for choosing this action."
    )
    expected_information_gain: Optional[str] = Field(
        default=None,
        description="Expected qualitative reduction in uncertainty or improvement in decision confidence."
    )
    evidence_reference: List[str] = Field(
        default_factory=list,
        description="References to candidate IDs, metrics, or SLA constraints supporting this decision."
    )
    stop_reason: Optional[str] = Field(
        default=None,
        description="Required when action is stop_and_recommend or stop_inconclusive."
    )
    benchmark_proposal: Optional[BenchmarkProposalDetails] = Field(
        default=None,
        description="Details when action is propose_benchmark."
    )


class InvestigationRecord(BaseModel):
    """Immutable trace record of an executed or evaluated investigation round."""
    round: int = Field(description="Decision round number (1-indexed)")
    action: str = Field(description="Action identifier proposed by agent")
    target: Optional[str] = Field(default=None, description="Target candidate or component")
    reason: str = Field(description="Rationale provided by agent")
    expected_information_gain: Optional[str] = Field(default=None, description="Expected information gain")
    evidence_reference: List[str] = Field(default_factory=list, description="Evidence references supporting action")
    policy_verdict: str = Field(description="Policy decision: APPROVED, REJECTED, MODIFIED, or STOPPED")
    policy_reason: str = Field(description="Explanation for policy verdict")
    tool_invoked: Optional[str] = Field(default=None, description="Tool executed if approved")
    tool_input: Dict[str, Any] = Field(default_factory=dict, description="Bounded tool input parameters")
    tool_output: Dict[str, Any] = Field(default_factory=dict, description="Bounded serializable tool execution output")
    duration_seconds: float = Field(default=0.0, description="Execution time in seconds")
    provenance: str = Field(default="agent_decision", description="Provenance tracking tag")
    stop_reason: Optional[str] = Field(default=None, description="Reason if workflow stopped at this step")


class AgentResponse(BaseModel):
    """Complete structured response from the AADS agentic workflow."""
    workflow_status: str = Field(description="Workflow outcome status: COMPLETED, CLARIFICATION_NEEDED, INSUFFICIENT_EVIDENCE, or FAILED")
    execution_mode: str = Field(description="Mode used: 'llm' (LangChain LLM-powered) or 'fallback' (deterministic labeled fallback)")
    request_text: str = Field(default="", description="Original user prompt")
    workload: Optional[WorkloadSpec] = Field(default=None, description="Validated workload specification")
    clarification_questions: List[str] = Field(default_factory=list, description="Questions for user if clarification is required")
    candidate_architectures: List[ArchitectureGraph] = Field(default_factory=list, description="Generated candidate architecture topologies")
    missing_models: List[str] = Field(default_factory=list, description="Component performance models missing from registry")
    simulation_results: List[SimulationResult] = Field(default_factory=list, description="Discrete-event simulation results per candidate")
    recommendation: Optional[RecommendationResult] = Field(default=None, description="Evidence-backed architectural recommendation")
    evidence_provenance: Dict[str, str] = Field(default_factory=dict, description="Provenance tracking for all metrics and data sources")
    errors: List[str] = Field(default_factory=list, description="Errors or validation failures encountered during workflow")
    executive_summary: str = Field(default="", description="High-level executive explanation of findings")
    investigation_trace: List[InvestigationRecord] = Field(default_factory=list, description="Ordered trace of investigation steps and policy verdicts")
    investigation_rounds: int = Field(default=0, description="Number of investigation rounds executed")
    benchmark_proposals: List[Dict[str, Any]] = Field(default_factory=list, description="Benchmark experiments proposed during investigation")

class RecommendationExplanation(BaseModel):
    """Structured architectural explanation generated by LLM from deterministic evidence."""
    summary: str = Field(
        description="High-level executive summary explaining why the selected architecture was chosen or why results are inconclusive."
    )
    why_this_option: List[str] = Field(
        default_factory=list,
        description="Bullet points explaining why this option was chosen based on SLA feasibility, Pareto dominance, and stated preferences."
    )
    trade_offs: List[str] = Field(
        default_factory=list,
        description="Operational, cost, or complexity trade-offs and disadvantages of the selected architecture."
    )
    constraint_status: str = Field(
        default="",
        description="Status of hard constraints (p95 latency SLA, minimum throughput, monthly budget) with exact numerical values from evidence."
    )
    uncertainties: List[str] = Field(
        default_factory=list,
        description="Identified uncertainties, confidence intervals, or risks in the prediction."
    )
    evidence_limitations: List[str] = Field(
        default_factory=list,
        description="Model limitations, synthetic vs measured provenance distinctions, or missing real-world factors."
    )

class LiveLLMCallRecord(BaseModel):
    """Machine-readable record of an individual live LLM decision call."""
    call_id: str = Field(description="Unique identifier for the invocation")
    timestamp: str = Field(description="ISO-8601 UTC timestamp of call initiation")
    scenario_id: Optional[str] = Field(default=None, description="External scenario identifier for evaluation grouping")
    strategy_name: str = Field(default="strategy_c_llm_live", description="Strategy executing the invocation")
    round_number: int = Field(description="Investigation round number (1-indexed)")
    provider: str = Field(description="LLM provider name (e.g. groq, openai)")
    model_name: str = Field(description="Specific model version invoked")
    request_id: Optional[str] = Field(default=None, description="Provider transaction or request ID")
    latency_ms: float = Field(description="Roundtrip API latency in milliseconds")
    prompt_tokens: int = Field(default=0, description="Input tokens counted")
    completion_tokens: int = Field(default=0, description="Completion tokens generated")
    total_tokens: int = Field(default=0, description="Sum of prompt and completion tokens")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated monetary cost in USD")
    decision: Optional[Dict[str, Any]] = Field(default=None, description="Structured investigation decision returned")
    policy_verdict: Optional[str] = Field(default=None, description="Policy outcome: APPROVED, REJECTED, MODIFIED, STOPPED")
    policy_reason: Optional[str] = Field(default=None, description="Policy evaluation explanation")
    is_live: bool = Field(default=True, description="Whether this call went to a genuine live model endpoint")
    fallback_used: bool = Field(default=False, description="Whether a fallback was triggered")
    error: Optional[str] = Field(default=None, description="Error message if call failed")

