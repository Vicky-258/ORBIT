"""
AADS Phase 4C: Decision-Quality Metrics Engine.
Computes objective, structured metrics independently of LLM narrative explanations:
- Constraint Correctness
- Recommendation Quality
- Investigation Usefulness
- Efficiency and Reliability
- Stability Analysis
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from orbit.core.schemas import FeasibilityStatus
from orbit.evaluation.scenarios import EvaluationScenario, ScenarioClass
from orbit.evaluation.strategies import StrategyExecutionResult


class DecisionQualityMetrics(BaseModel):
    """Comprehensive evaluation metrics for an individual strategy execution."""
    scenario_id: str
    strategy_name: str

    # 1. Constraint Correctness
    hard_constraints_satisfied: bool
    infeasible_candidate_recommended: bool
    infeasible_workload_detected: bool
    inconclusive_correctly_reported: bool
    constraint_correctness_score: float  # 0.0 to 1.0

    # 2. Recommendation Quality
    top_choice_agreement: bool
    feasible_set_jaccard: float
    ranking_agreement: Optional[float] = None
    regret_vs_reference: float = 0.0
    raw_unrounded_regret: float = 0.0
    score_margin_selected_vs_ref: Optional[float] = None

    # 3. Investigation Usefulness
    investigation_rounds: int
    tools_proposed: int
    tools_accepted: int
    tools_rejected: int
    tools_executed: int
    redundant_actions: int
    investigation_budget_spent: float
    uncertainty_reduced: bool
    coverage_gap_resolved: bool
    recommendation_changed_defensibly: bool
    investigation_usefulness_score: float  # 0.0 to 1.0

    # 4. Efficiency and Reliability
    decision_latency_ms: float
    simulation_runs_count: int
    policy_rejection_rate: float
    fallback_used: bool
    llm_request_count: Optional[int] = None
    llm_token_count: Optional[int] = None
    llm_cost_usd: Optional[float] = None


def compute_metrics(
    scenario: EvaluationScenario,
    result: StrategyExecutionResult,
) -> DecisionQualityMetrics:
    """
    Evaluates strategy outcome against scenario reference and constraints.
    """
    ref = scenario.expected_reference
    workload = scenario.workload_spec

    # 1. Constraint Correctness
    is_infeasible_workload = (ref.expected_status == FeasibilityStatus.INFEASIBLE)

    if is_infeasible_workload:
        infeasible_detected = (result.status == FeasibilityStatus.INFEASIBLE or result.selected_architecture_id is None)
        infeasible_recommended = (result.status == FeasibilityStatus.FEASIBLE and result.selected_architecture_id is not None)
        hard_sat = not infeasible_recommended
    else:
        infeasible_detected = True  # Not applicable, workload is feasible
        infeasible_recommended = (result.status == FeasibilityStatus.INFEASIBLE and result.selected_architecture_id is not None)
        
        # Check if winner actually satisfied numerical constraints
        hard_sat = True
        metrics = result.predicted_metrics
        if metrics and result.selected_architecture_id:
            p95 = metrics.get("p95_latency_ms")
            tp = metrics.get("throughput_achieved_rps")
            cost = metrics.get("estimated_monthly_cost_usd")

            if p95 is not None and "p95_latency" in workload.hard_constraints and p95 > workload.p95_latency_target_ms:
                hard_sat = False
            if tp is not None and "min_throughput" in workload.hard_constraints and tp < workload.min_throughput_rps:
                hard_sat = False
            if cost is not None and "max_budget" in workload.hard_constraints and cost > workload.max_monthly_budget_usd:
                hard_sat = False

    # Inconclusive / abstention
    if ref.is_abstention_expected:
        inconclusive_correct = (result.status == FeasibilityStatus.INFEASIBLE or result.selected_architecture_id is None)
    else:
        inconclusive_correct = (result.status == FeasibilityStatus.FEASIBLE)

    # Constraint correctness score (0.0 to 1.0)
    c_score = 1.0
    if not hard_sat:
        c_score -= 0.5
    if infeasible_recommended:
        c_score -= 0.5
    if not inconclusive_correct:
        c_score -= 0.2
    c_score = max(0.0, c_score)

    # 2. Recommendation Quality
    winner_set = list(ref.expected_winner_set) if ref.expected_winner_set else ([ref.expected_winner_id] if ref.expected_winner_id else [])
    if not winner_set:
        top_agreement = (result.selected_architecture_id is None or result.status == FeasibilityStatus.INFEASIBLE)
    else:
        top_agreement = (result.selected_architecture_id in winner_set and result.status == FeasibilityStatus.FEASIBLE)

    # Feasible set Jaccard similarity
    pred_feas = set(result.feasible_candidate_ids)
    ref_feas = set(ref.expected_feasible_ids)
    if not pred_feas and not ref_feas:
        jaccard = 1.0
    elif not pred_feas or not ref_feas:
        jaccard = 0.0
    else:
        jaccard = round(len(pred_feas & ref_feas) / len(pred_feas | ref_feas), 3)

    # Ranking agreement (Kendall tau or rank overlap)
    ranking_corr = None
    if ref.expected_ranking and result.candidate_rankings:
        # Measure fraction of concordant relative pairs
        shared = [c for c in ref.expected_ranking if c in result.candidate_rankings]
        if len(shared) >= 2:
            concordant = 0
            total_pairs = 0
            for i in range(len(shared)):
                for j in range(i + 1, len(shared)):
                    a, b = shared[i], shared[j]
                    ref_order = ref.expected_ranking.index(a) < ref.expected_ranking.index(b)
                    pred_order = result.candidate_rankings.index(a) < result.candidate_rankings.index(b)
                    if ref_order == pred_order:
                        concordant += 1
                    total_pairs += 1
            ranking_corr = round(concordant / total_pairs, 3) if total_pairs > 0 else 1.0
        else:
            ranking_corr = 1.0

    # Regret vs reference
    regret = 0.0
    raw_regret = 0.0
    score_margin = None
    if ref.expected_winner_id and result.selected_architecture_id:
        ref_score = result.candidate_scores.get(ref.expected_winner_id, 0.0)
        sel_score = result.candidate_scores.get(result.selected_architecture_id, 0.0)
        score_margin = round(sel_score - ref_score, 6)
        if ref.expected_winner_id != result.selected_architecture_id:
            if ref.reference_objective_value is not None:
                diff = ref.reference_objective_value - sel_score
                if diff > 0:
                    raw_regret = diff
                    regret = round(diff, 3)
            else:
                if ref_score > sel_score:
                    raw_regret = ref_score - sel_score
                    regret = round(raw_regret, 3)

    # 3. Investigation Usefulness
    trace = result.investigation_trace
    executed_actions = {t.get("action") for t in trace if t.get("policy_verdict") == "APPROVED"}
    
    uncertainty_reduced = ("inspect_uncertainty" in executed_actions)
    coverage_gap_resolved = ("inspect_model_coverage" in executed_actions or "propose_benchmark" in executed_actions)
    
    # Recommendation changed defensibly: in decision-changing or boundary scenarios, did investigation maintain SLA correctness?
    rec_changed_defensibly = False
    if scenario.scenario_class in (ScenarioClass.DECISION_CHANGING_INVESTIGATION, ScenarioClass.HARD_CONSTRAINT_BOUNDARY):
        rec_changed_defensibly = top_agreement

    # Investigation usefulness score
    # High score if: useful actions executed without rejections, and no unneeded investigation on obvious workloads
    if scenario.scenario_class == ScenarioClass.UNNECESSARY_INVESTIGATION:
        # If strategy stopped in 0 or 1 round, it was efficient; 3 rounds is wasteful
        usefulness_score = 1.0 if result.investigation_rounds == 0 else (0.7 if result.investigation_rounds == 1 else 0.3)
    else:
        base_u = 0.5
        if uncertainty_reduced:
            base_u += 0.25
        if coverage_gap_resolved:
            base_u += 0.25
        if result.policy_rejection_count > 0:
            base_u -= 0.2
        usefulness_score = max(0.0, min(1.0, round(base_u, 2)))

    # 4. Efficiency and Reliability
    rejection_rate = 0.0
    if result.tools_proposed > 0:
        rejection_rate = round(result.tools_rejected / result.tools_proposed, 3)

    return DecisionQualityMetrics(
        scenario_id=scenario.scenario_id,
        strategy_name=result.strategy_name,
        hard_constraints_satisfied=hard_sat,
        infeasible_candidate_recommended=infeasible_recommended,
        infeasible_workload_detected=infeasible_detected,
        inconclusive_correctly_reported=inconclusive_correct,
        constraint_correctness_score=round(c_score, 2),
        top_choice_agreement=top_agreement,
        feasible_set_jaccard=jaccard,
        ranking_agreement=ranking_corr,
        regret_vs_reference=regret,
        raw_unrounded_regret=raw_regret,
        score_margin_selected_vs_ref=score_margin,
        investigation_rounds=result.investigation_rounds,
        tools_proposed=result.tools_proposed,
        tools_accepted=result.tools_accepted,
        tools_rejected=result.tools_rejected,
        tools_executed=result.tools_executed,
        redundant_actions=result.redundant_actions,
        investigation_budget_spent=result.investigation_budget_spent,
        uncertainty_reduced=uncertainty_reduced,
        coverage_gap_resolved=coverage_gap_resolved,
        recommendation_changed_defensibly=rec_changed_defensibly,
        investigation_usefulness_score=usefulness_score,
        decision_latency_ms=result.decision_latency_ms,
        simulation_runs_count=result.simulation_runs_count,
        policy_rejection_rate=rejection_rate,
        fallback_used=result.fallback_used,
        llm_request_count=result.llm_request_count,
        llm_token_count=result.llm_token_count,
        llm_cost_usd=result.llm_cost_usd,
    )
