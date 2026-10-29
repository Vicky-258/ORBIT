"""
AADS Phase 4C: Planning Strategies Implementations.
Implements the three comparative strategies:
- Strategy A: Fixed Pipeline (No adaptive investigation)
- Strategy B: Deterministic Adaptive Planner (Heuristic rules)
- Strategy C: LLM Adaptive Planner (Structured LLM planning with policy gatekeeping)
"""
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from aads.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    RecommendationResult,
    FeasibilityStatus,
    ArchitectureGraph,
)
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender
from aads.registry.component_registry import ComponentRegistry
from aads.agent.schemas import (
    LiveLLMCallRecord,
    InvestigationDecision,
    InvestigationActionType,
    InvestigationRecord,
    BenchmarkProposalDetails,
)
from aads.agent.investigation_policy import InvestigationPolicy, PolicyVerdict
from aads.agent.investigation_dispatcher import InvestigationDispatcher
from aads.agent.investigation_planner import InvestigationPlanner
from aads.agent.state import AgentWorkflowState
from aads.evaluation.scenarios import EvaluationScenario, ScenarioClass


class StrategyExecutionResult(BaseModel):
    """Standardized output schema across all three planning strategies."""
    strategy_name: str
    scenario_id: str
    selected_architecture_id: Optional[str] = None
    selected_architecture_name: Optional[str] = None
    status: FeasibilityStatus = FeasibilityStatus.UNCERTAIN
    feasible_candidate_ids: List[str] = Field(default_factory=list)
    candidate_rankings: List[str] = Field(default_factory=list)
    candidate_scores: Dict[str, float] = Field(default_factory=dict)
    predicted_metrics: Dict[str, Any] = Field(default_factory=dict)

    # Investigation metrics
    investigation_rounds: int = 0
    tools_proposed: int = 0
    tools_accepted: int = 0
    tools_rejected: int = 0
    tools_executed: int = 0
    redundant_actions: int = 0
    investigation_trace: List[Dict[str, Any]] = Field(default_factory=list)
    benchmark_proposals: List[Dict[str, Any]] = Field(default_factory=list)
    investigation_budget_spent: float = 0.0

    # Reliability & Resource use
    decision_latency_ms: float = 0.0
    simulation_runs_count: int = 0
    policy_rejection_count: int = 0
    fallback_used: bool = False
    llm_request_count: Optional[int] = None
    llm_token_count: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    errors: List[str] = Field(default_factory=list)
    provenance_map: Dict[str, str] = Field(default_factory=dict)


def _simulate_candidates(
    candidates: List[ArchitectureGraph],
    workload: WorkloadSpec,
    registry: ComponentRegistry,
    duration_seconds: float,
    seed: int,
) -> Tuple[List[SimulationResult], int]:
    """Shared simulation helper ensuring identical deterministic execution."""
    engine = SimPyEngine(registry)
    results: List[SimulationResult] = []
    runs_count = 0
    for cand in candidates:
        all_models_present = all(
            registry.get_model(*(m.split(":", 1) if ":" in m else (m, "latest"))) is not None
            for m in cand.required_models
        )
        if all_models_present:
            res = engine.simulate_architecture(
                architecture=cand,
                workload=workload,
                duration_seconds=duration_seconds,
                random_seed=seed,
            )
            results.append(res)
            runs_count += 1
    return results, runs_count


# ===========================================================================
# Strategy A: Fixed Pipeline (No adaptive investigation)
# ===========================================================================

def run_strategy_a_fixed_pipeline(
    scenario: EvaluationScenario,
    registry: Optional[ComponentRegistry] = None,
) -> StrategyExecutionResult:
    """
    Executes standard fixed pipeline:
    Candidate generation -> Model check -> SimPy simulation -> Recommendation.
    Zero adaptive follow-up rounds.
    """
    start_t = time.perf_counter()
    reg = registry or ComponentRegistry()
    reg.seed_baseline_data()
    generator = ArchitectureGenerator()

    candidates = generator.generate_candidates(
        include_async=scenario.include_async,
        include_unsupported=scenario.include_unsupported,
    )

    sim_results, sim_runs = _simulate_candidates(
        candidates=candidates,
        workload=scenario.workload_spec,
        registry=reg,
        duration_seconds=scenario.simulation_duration_seconds,
        seed=scenario.random_seed,
    )

    errors = []
    if not sim_results:
        rec = None
        status = FeasibilityStatus.INFEASIBLE
        sel_id = None
        sel_name = None
        rankings = []
        scores = {}
        feasible_ids = []
        metrics = {}
        errors.append("No candidate could be simulated due to missing models or validation failures.")
    else:
        rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload_spec, sim_results)
        sel_id = rec.selected_architecture_id
        sel_name = rec.selected_architecture_name
        status = rec.status
        rankings = [e.architecture_id for e in rec.evaluations]
        scores = {e.architecture_id: e.overall_score for e in rec.evaluations}
        feasible_ids = [e.architecture_id for e in rec.evaluations if e.feasibility_status == FeasibilityStatus.FEASIBLE]
        metrics = rec.predicted_metrics

    latency_ms = (time.perf_counter() - start_t) * 1000.0

    return StrategyExecutionResult(
        strategy_name="strategy_a_fixed",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=sel_id,
        selected_architecture_name=sel_name,
        status=status,
        feasible_candidate_ids=feasible_ids,
        candidate_rankings=rankings,
        candidate_scores=scores,
        predicted_metrics=metrics,
        investigation_rounds=0,
        tools_proposed=0,
        tools_accepted=0,
        tools_rejected=0,
        tools_executed=0,
        redundant_actions=0,
        investigation_trace=[],
        benchmark_proposals=[],
        investigation_budget_spent=0.0,
        decision_latency_ms=round(latency_ms, 2),
        simulation_runs_count=sim_runs,
        policy_rejection_count=0,
        fallback_used=False,
        llm_request_count=0,
        llm_token_count=0,
        llm_cost_usd=0.0,
        errors=errors,
        provenance_map={"pipeline": "deterministic_fixed", "simulation": "simulated"},
    )


# ===========================================================================
# Strategy B: Deterministic Adaptive Planner
# ===========================================================================

def run_strategy_b_deterministic_adaptive(
    scenario: EvaluationScenario,
    registry: Optional[ComponentRegistry] = None,
) -> StrategyExecutionResult:
    """
    Executes deterministic adaptive investigation using explicit heuristic rules
    gated by the authoritative InvestigationPolicy.
    """
    start_t = time.perf_counter()
    reg = registry or ComponentRegistry()
    reg.seed_baseline_data()
    generator = ArchitectureGenerator()

    candidates = generator.generate_candidates(
        include_async=scenario.include_async,
        include_unsupported=scenario.include_unsupported,
    )

    sim_results, sim_runs = _simulate_candidates(
        candidates=candidates,
        workload=scenario.workload_spec,
        registry=reg,
        duration_seconds=scenario.simulation_duration_seconds,
        seed=scenario.random_seed,
    )

    initial_rec = None
    if sim_results:
        initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload_spec, sim_results)

    # Initialize workflow state
    state: Dict[str, Any] = {
        "candidate_architectures": candidates,
        "workload_spec": scenario.workload_spec,
        "simulation_results": sim_results,
        "recommendation": initial_rec,
        "missing_models": list(scenario.missing_model_keys),
        "investigation_round": 0,
        "max_investigation_rounds": scenario.max_investigation_rounds,
        "investigation_budget_seconds": scenario.investigation_budget_seconds,
        "investigation_budget_spent": 0.0,
        "investigation_trace": [],
        "benchmark_proposals": [],
        "errors": [],
    }

    policy = InvestigationPolicy()
    dispatcher = InvestigationDispatcher(registry=reg)
    planner = InvestigationPlanner()

    tools_proposed = 0
    tools_accepted = 0
    tools_rejected = 0
    tools_executed = 0
    redundant_actions = 0
    seen_proposals = set()

    for r_num in range(1, scenario.max_investigation_rounds + 1):
        state["investigation_round"] = r_num - 1

        # Propose action deterministically via heuristic planner
        proposal = planner._heuristic_fallback(state)
        tools_proposed += 1

        prop_key = (proposal.action, proposal.target)
        if prop_key in seen_proposals:
            redundant_actions += 1
        seen_proposals.add(prop_key)

        # Policy validation
        val_res = policy.evaluate_action(proposal, state)


        if val_res.verdict == PolicyVerdict.APPROVED:
            tools_accepted += 1
            # Dispatch
            updates, record = dispatcher.dispatch(val_res.sanitized_decision, state, round_num=r_num)
            tools_executed += 1
            state.update(updates)
            state["investigation_trace"].append(record.model_dump())
            state["investigation_budget_spent"] += record.duration_seconds

            # Stop condition checked
            if val_res.sanitized_decision.action in (InvestigationActionType.STOP_AND_RECOMMEND, InvestigationActionType.STOP_INCONCLUSIVE):
                break
        elif val_res.verdict == PolicyVerdict.STOPPED:
            tools_accepted += 1
            # Direct stop
            rec_entry = InvestigationRecord(
                round=r_num,
                action=str(proposal.action.value if hasattr(proposal.action, "value") else proposal.action),
                target=proposal.target,
                reason=proposal.reason,
                policy_verdict=val_res.verdict.value,
                policy_reason=val_res.reason,
                duration_seconds=0.0,
                provenance="investigation_policy",
                stop_reason=val_res.sanitized_decision.stop_reason or val_res.reason,
            )
            state["investigation_trace"].append(rec_entry.model_dump())
            break
        else:
            tools_rejected += 1
            rec_entry = InvestigationRecord(
                round=r_num,
                action=str(proposal.action.value if hasattr(proposal.action, "value") else proposal.action),
                target=proposal.target,
                reason=proposal.reason,
                policy_verdict=val_res.verdict.value,
                policy_reason=val_res.reason,
                duration_seconds=0.0,
                provenance="investigation_policy",
            )
            state["investigation_trace"].append(rec_entry.model_dump())
            break

    # Final recommendation re-evaluation with updated simulation results
    updated_sim_results = state.get("simulation_results", [])
    if updated_sim_results:
        final_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload_spec, updated_sim_results)
        sel_id = final_rec.selected_architecture_id
        sel_name = final_rec.selected_architecture_name
        status = final_rec.status
        rankings = [e.architecture_id for e in final_rec.evaluations]
        scores = {e.architecture_id: e.overall_score for e in final_rec.evaluations}
        feasible_ids = [e.architecture_id for e in final_rec.evaluations if e.feasibility_status == FeasibilityStatus.FEASIBLE]
        metrics = final_rec.predicted_metrics
    else:
        sel_id = None
        sel_name = None
        status = FeasibilityStatus.INFEASIBLE
        rankings = []
        scores = {}
        feasible_ids = []
        metrics = {}

    latency_ms = (time.perf_counter() - start_t) * 1000.0

    return StrategyExecutionResult(
        strategy_name="strategy_b_deterministic",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=sel_id,
        selected_architecture_name=sel_name,
        status=status,
        feasible_candidate_ids=feasible_ids,
        candidate_rankings=rankings,
        candidate_scores=scores,
        predicted_metrics=metrics,
        investigation_rounds=len(state.get("investigation_trace", [])),
        tools_proposed=tools_proposed,
        tools_accepted=tools_accepted,
        tools_rejected=tools_rejected,
        tools_executed=tools_executed,
        redundant_actions=redundant_actions,
        investigation_trace=state.get("investigation_trace", []),
        benchmark_proposals=state.get("benchmark_proposals", []),
        investigation_budget_spent=round(state.get("investigation_budget_spent", 0.0), 3),
        decision_latency_ms=round(latency_ms, 2),
        simulation_runs_count=sim_runs,
        policy_rejection_count=tools_rejected,
        fallback_used=False,
        llm_request_count=0,
        llm_token_count=0,
        llm_cost_usd=0.0,
        errors=state.get("errors", []),
        provenance_map={"pipeline": "deterministic_adaptive", "simulation": "simulated"},
    )


# ===========================================================================
# Strategy C: LLM Adaptive Planner
# ===========================================================================

def _offline_llm_adaptive_decision(state: Dict[str, Any], round_num: int, scenario: EvaluationScenario) -> InvestigationDecision:
    """
    Offline intelligent structured decision planner that mimics an expert LLM
    inspecting evidence, prioritizing high-risk SLA boundaries or missing models.
    """
    trace = state.get("investigation_trace", [])
    executed = {t.get("action") for t in trace if t.get("policy_verdict") == "APPROVED"}
    sim_results = state.get("simulation_results", [])
    rec = state.get("recommendation")
    workload = state.get("workload_spec")

    # If mock decisions provided explicitly in scenario, use them
    if scenario.mock_llm_decisions and round_num <= len(scenario.mock_llm_decisions):
        raw = scenario.mock_llm_decisions[round_num - 1]
        return InvestigationDecision.model_validate(raw)

    # 1. Incomplete coverage scenario: check model coverage first
    if scenario.scenario_class == ScenarioClass.INCOMPLETE_MODEL_COVERAGE and "inspect_model_coverage" not in executed:
        return InvestigationDecision(
            action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
            target="all_candidates",
            reason="Detected potential unvalidated candidates; audit model registry coverage.",
            expected_information_gain="Identify uncalibrated models for candidate components.",
            evidence_reference=["candidate_architectures"],
        )

    # 2. Hard constraint boundary or high uncertainty scenario: audit uncertainty
    if scenario.scenario_class in (ScenarioClass.HARD_CONSTRAINT_BOUNDARY, ScenarioClass.HIGH_UNCERTAINTY, ScenarioClass.DECISION_CHANGING_INVESTIGATION) and "inspect_uncertainty" not in executed:
        return InvestigationDecision(
            action=InvestigationActionType.INSPECT_UNCERTAINTY,
            target="all",
            reason="SLA boundary risk detected; audit p95 latency heuristic uncertainty bounds.",
            expected_information_gain="Verify whether p95 uncertainty breaches SLA limits.",
            evidence_reference=["simulation_results"],
        )

    # 3. Model coverage check if not done
    if "inspect_model_coverage" not in executed:
        return InvestigationDecision(
            action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
            target="all_candidates",
            reason="Audit model calibration status across candidate architectures.",
            expected_information_gain="Confirm component model provenance.",
            evidence_reference=["candidate_architectures"],
        )

    # 4. Uncertainty check if not done
    if "inspect_uncertainty" not in executed and sim_results:
        return InvestigationDecision(
            action=InvestigationActionType.INSPECT_UNCERTAINTY,
            target="all",
            reason="Inspect latency heuristic uncertainty bounds against hard constraints.",
            expected_information_gain="Quantify SLA confidence margins.",
            evidence_reference=["simulation_results"],
        )

    # 5. Stop and recommend if evidence is complete
    if sim_results:
        winner = rec.selected_architecture_id if rec else "arch_b_cached"
        return InvestigationDecision(
            action=InvestigationActionType.STOP_AND_RECOMMEND,
            target=winner,
            reason="Sufficient empirical evidence obtained; stopping investigation.",
            expected_information_gain="Final recommendation verified.",
            evidence_reference=["simulation_results", "evaluator"],
            stop_reason="Evidence sufficient to support recommendation.",
        )

    return InvestigationDecision(
        action=InvestigationActionType.STOP_INCONCLUSIVE,
        reason="Insufficient simulation evidence to recommend an architecture.",
        stop_reason="Evidence absent.",
    )


def run_strategy_c_llm_adaptive(
    scenario: EvaluationScenario,
    registry: Optional[ComponentRegistry] = None,
    mode: str = "offline",
    call_records: Optional[List[LiveLLMCallRecord]] = None,
    fail_closed: bool = False,
) -> StrategyExecutionResult:
    """
    Executes Strategy C (LLM Adaptive Planner):
    - Uses structured output LLM when in live mode or simulated intelligent offline planner in offline mode.
    - Simulates provider failures if requested by scenario.
    - All actions strictly validated by InvestigationPolicy.
    """
    start_t = time.perf_counter()
    reg = registry or ComponentRegistry()
    reg.seed_baseline_data()
    generator = ArchitectureGenerator()

    candidates = generator.generate_candidates(
        include_async=scenario.include_async,
        include_unsupported=scenario.include_unsupported,
    )

    sim_results, sim_runs = _simulate_candidates(
        candidates=candidates,
        workload=scenario.workload_spec,
        registry=reg,
        duration_seconds=scenario.simulation_duration_seconds,
        seed=scenario.random_seed,
    )

    initial_rec = None
    if sim_results:
        initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload_spec, sim_results)

    state: Dict[str, Any] = {
        "candidate_architectures": candidates,
        "workload_spec": scenario.workload_spec,
        "simulation_results": sim_results,
        "recommendation": initial_rec,
        "missing_models": list(scenario.missing_model_keys),
        "investigation_round": 0,
        "max_investigation_rounds": scenario.max_investigation_rounds,
        "investigation_budget_seconds": scenario.investigation_budget_seconds,
        "investigation_budget_spent": 0.0,
        "investigation_trace": [],
        "benchmark_proposals": [],
        "errors": [],
    }

    policy = InvestigationPolicy()
    dispatcher = InvestigationDispatcher(registry=reg)
    planner = InvestigationPlanner()

    tools_proposed = 0
    tools_accepted = 0
    tools_rejected = 0
    tools_executed = 0
    redundant_actions = 0
    fallback_used = False
    seen_proposals = set()
    llm_requests = 0
    llm_tokens = 0
    llm_cost = 0.0

    if mode == "live" and not planner.provider_mgr.is_llm_available():
        if fail_closed:
            raise RuntimeError("Live LLM evaluation aborted: Provider credentials unavailable.")
        fallback_used = True

    for r_num in range(1, scenario.max_investigation_rounds + 1):
        state["investigation_round"] = r_num - 1
        call_telemetry = {}

        # Check provider failure injection
        if scenario.simulate_provider_failure:
            fallback_used = True
            proposal = planner._heuristic_fallback(state)
            call_telemetry = {
                "is_live": False,
                "fallback_used": True,
                "error": "Simulated provider failure injected by scenario.",
                "provider": "groq",
                "model_name": "openai/gpt-oss-120b",
                "latency_ms": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            }
        elif mode == "live":
            try:
                proposal, call_telemetry = planner.plan_next_action_with_telemetry(state, fail_closed=fail_closed)
                llm_requests += 1
                llm_tokens += call_telemetry.get("total_tokens", 0)
                llm_cost += call_telemetry.get("estimated_cost_usd", 0.0)
                if call_telemetry.get("fallback_used"):
                    fallback_used = True
            except Exception as e:
                if fail_closed:
                    raise RuntimeError(f"Live LLM call failed in scenario {scenario.scenario_id} round {r_num}: {e}") from e
                fallback_used = True
                proposal = planner._heuristic_fallback(state)
                call_telemetry = {
                    "is_live": False,
                    "fallback_used": True,
                    "error": str(e),
                    "provider": "groq",
                    "model_name": "openai/gpt-oss-120b",
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost_usd": 0.0,
                }
        else:
            # Offline intelligent decision
            proposal = _offline_llm_adaptive_decision(state, r_num, scenario)

        tools_proposed += 1
        prop_key = (proposal.action, proposal.target)
        if prop_key in seen_proposals:
            redundant_actions += 1
        seen_proposals.add(prop_key)

        # Policy validation
        val_res = policy.evaluate_action(proposal, state)

        # Record structured call telemetry for live strategy
        if call_records is not None and mode == "live":
            rec_call = LiveLLMCallRecord(
                call_id=call_telemetry.get("call_id", f"call_{uuid.uuid4().hex[:12]}"),
                timestamp=call_telemetry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                scenario_id=scenario.scenario_id,
                strategy_name="strategy_c_llm_live",
                round_number=r_num,
                provider=call_telemetry.get("provider", "groq"),
                model_name=call_telemetry.get("model_name", "openai/gpt-oss-120b"),
                request_id=call_telemetry.get("request_id"),
                latency_ms=call_telemetry.get("latency_ms", 0.0),
                prompt_tokens=call_telemetry.get("prompt_tokens", 0),
                completion_tokens=call_telemetry.get("completion_tokens", 0),
                total_tokens=call_telemetry.get("total_tokens", 0),
                estimated_cost_usd=call_telemetry.get("estimated_cost_usd", 0.0),
                decision=proposal.model_dump(),
                policy_verdict=val_res.verdict.value,
                policy_reason=val_res.reason,
                is_live=call_telemetry.get("is_live", False),
                fallback_used=fallback_used or call_telemetry.get("fallback_used", False),
                error=call_telemetry.get("error"),
            )
            call_records.append(rec_call)

        if val_res.verdict == PolicyVerdict.APPROVED:
            tools_accepted += 1
            updates, record = dispatcher.dispatch(val_res.sanitized_decision, state, round_num=r_num)
            tools_executed += 1
            state.update(updates)
            state["investigation_trace"].append(record.model_dump())
            state["investigation_budget_spent"] += record.duration_seconds

            if val_res.sanitized_decision.action in (InvestigationActionType.STOP_AND_RECOMMEND, InvestigationActionType.STOP_INCONCLUSIVE):
                break
        elif val_res.verdict == PolicyVerdict.STOPPED:
            tools_accepted += 1
            rec_entry = InvestigationRecord(
                round=r_num,
                action=str(proposal.action.value if hasattr(proposal.action, "value") else proposal.action),
                target=proposal.target,
                reason=proposal.reason,
                policy_verdict=val_res.verdict.value,
                policy_reason=val_res.reason,
                duration_seconds=0.0,
                provenance="investigation_policy",
                stop_reason=val_res.sanitized_decision.stop_reason or val_res.reason,
            )
            state["investigation_trace"].append(rec_entry.model_dump())
            break
        else:
            tools_rejected += 1
            rec_entry = InvestigationRecord(
                round=r_num,
                action=str(proposal.action.value if hasattr(proposal.action, "value") else proposal.action),
                target=proposal.target,
                reason=proposal.reason,
                policy_verdict=val_res.verdict.value,
                policy_reason=val_res.reason,
                duration_seconds=0.0,
                provenance="investigation_policy",
            )
            state["investigation_trace"].append(rec_entry.model_dump())
            break

    updated_sim_results = state.get("simulation_results", [])
    if updated_sim_results:
        final_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload_spec, updated_sim_results)
        sel_id = final_rec.selected_architecture_id
        sel_name = final_rec.selected_architecture_name
        status = final_rec.status
        rankings = [e.architecture_id for e in final_rec.evaluations]
        scores = {e.architecture_id: e.overall_score for e in final_rec.evaluations}
        feasible_ids = [e.architecture_id for e in final_rec.evaluations if e.feasibility_status == FeasibilityStatus.FEASIBLE]
        metrics = final_rec.predicted_metrics
    else:
        sel_id = None
        sel_name = None
        status = FeasibilityStatus.INFEASIBLE
        rankings = []
        scores = {}
        feasible_ids = []
        metrics = {}

    latency_ms = (time.perf_counter() - start_t) * 1000.0

    return StrategyExecutionResult(
        strategy_name="strategy_c_llm",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=sel_id,
        selected_architecture_name=sel_name,
        status=status,
        feasible_candidate_ids=feasible_ids,
        candidate_rankings=rankings,
        candidate_scores=scores,
        predicted_metrics=metrics,
        investigation_rounds=len(state.get("investigation_trace", [])),
        tools_proposed=tools_proposed,
        tools_accepted=tools_accepted,
        tools_rejected=tools_rejected,
        tools_executed=tools_executed,
        redundant_actions=redundant_actions,
        investigation_trace=state.get("investigation_trace", []),
        benchmark_proposals=state.get("benchmark_proposals", []),
        investigation_budget_spent=round(state.get("investigation_budget_spent", 0.0), 3),
        decision_latency_ms=round(latency_ms, 2),
        simulation_runs_count=sim_runs,
        policy_rejection_count=tools_rejected,
        fallback_used=fallback_used,
        llm_request_count=llm_requests if mode == "live" else None,
        llm_token_count=llm_tokens if mode == "live" else None,
        llm_cost_usd=round(llm_cost, 6) if mode == "live" else None,
        errors=state.get("errors", []),
        provenance_map={
            "pipeline": "llm_adaptive_live" if (mode == "live" and not fallback_used) else ("llm_adaptive_fallback" if fallback_used else "llm_adaptive_mocked_offline"),
            "simulation": "simulated",
        },
    )
