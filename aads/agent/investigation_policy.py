"""
Deterministic Investigation Policy for AADS Phase 4B.
Enforces safety boundaries, round budgets, target validity, duplicate prevention,
and authorization gates over LLM-selected actions before dispatch.
"""
import os
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field

from aads.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    InvestigationRecord,
)
from aads.agent.tools import ALLOWED_BENCHMARK_COMPONENTS

logger = logging.getLogger(__name__)


class PolicyVerdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    STOPPED = "STOPPED"


class PolicyEvaluationResult(BaseModel):
    """Result of policy validation over an agent investigation proposal."""
    verdict: PolicyVerdict
    allowed: bool
    sanitized_decision: InvestigationDecision
    reason: str
    details: Dict[str, Any] = Field(default_factory=dict)


class InvestigationPolicy:
    """
    Authoritative policy layer ensuring LLM-selected investigation steps
    remain bounded, safe, non-redundant, and verifiable.
    """

    def __init__(
        self,
        default_max_rounds: int = 3,
        hard_max_rounds: int = 5,
        default_budget_seconds: float = 60.0,
    ):
        env_rounds = os.getenv("AADS_MAX_INVESTIGATION_ROUNDS")
        self.default_max_rounds = int(env_rounds) if env_rounds and env_rounds.isdigit() else default_max_rounds
        self.hard_max_rounds = hard_max_rounds
        self.default_budget_seconds = default_budget_seconds

    def evaluate_action(
        self,
        decision: InvestigationDecision,
        state: Dict[str, Any],
    ) -> PolicyEvaluationResult:
        """
        Validates proposed investigation action against policy rules.
        Returns PolicyEvaluationResult with verdict, whether allowed to dispatch,
        sanitized action, and policy rationale.
        """
        current_round = state.get("investigation_round", 0)
        configured_max = state.get("max_investigation_rounds", self.default_max_rounds)
        max_rounds = min(configured_max, self.hard_max_rounds)
        budget_spent = state.get("investigation_budget_spent", 0.0)
        max_budget = state.get("investigation_budget_seconds", self.default_budget_seconds)
        trace: List[Dict[str, Any]] = state.get("investigation_trace", [])
        candidates = state.get("candidate_architectures", [])
        valid_candidate_ids: Set[str] = {c.id if hasattr(c, "id") else c.get("id") for c in candidates if c}
        sim_results = state.get("simulation_results", [])

        # 1. Enforce round budget
        if current_round >= max_rounds:
            has_viable_winner = bool(sim_results)
            fallback_action = InvestigationActionType.STOP_AND_RECOMMEND if has_viable_winner else InvestigationActionType.STOP_INCONCLUSIVE
            sanitized = InvestigationDecision(
                action=fallback_action,
                target=decision.target,
                reason=f"Maximum investigation rounds ({max_rounds}) reached. Terminating investigation.",
                stop_reason=f"Round budget exhausted ({current_round}/{max_rounds}). Proceeding to final synthesis.",
                evidence_reference=decision.evidence_reference,
            )
            return PolicyEvaluationResult(
                verdict=PolicyVerdict.STOPPED,
                allowed=True,  # Allowed to execute the stop handler
                sanitized_decision=sanitized,
                reason=f"Investigation round limit ({max_rounds}) reached.",
                details={"current_round": current_round, "max_rounds": max_rounds},
            )

        # 2. Enforce execution time budget
        if budget_spent >= max_budget:
            has_viable_winner = bool(sim_results)
            fallback_action = InvestigationActionType.STOP_AND_RECOMMEND if has_viable_winner else InvestigationActionType.STOP_INCONCLUSIVE
            sanitized = InvestigationDecision(
                action=fallback_action,
                target=decision.target,
                reason=f"Execution budget ({max_budget:.1f}s) exhausted. Terminating investigation.",
                stop_reason=f"Execution budget reached ({budget_spent:.1f}s >= {max_budget:.1f}s). Proceeding to synthesis.",
                evidence_reference=decision.evidence_reference,
            )
            return PolicyEvaluationResult(
                verdict=PolicyVerdict.STOPPED,
                allowed=True,
                sanitized_decision=sanitized,
                reason=f"Execution budget ({max_budget:.1f}s) exhausted.",
                details={"budget_spent": budget_spent, "max_budget": max_budget},
            )

        # 3. Check for repeated failures or cycles (last 2 rounds failed/rejected)
        if len(trace) >= 2:
            last_two = trace[-2:]
            if all(t.get("policy_verdict") in ("REJECTED", "MODIFIED") or not t.get("tool_output", {}).get("success", True) for t in last_two):
                has_viable_winner = bool(sim_results)
                fallback_action = InvestigationActionType.STOP_AND_RECOMMEND if has_viable_winner else InvestigationActionType.STOP_INCONCLUSIVE
                sanitized = InvestigationDecision(
                    action=fallback_action,
                    target=None,
                    reason="Multiple consecutive actions rejected or failed. Stopping to prevent cycle.",
                    stop_reason="Repeated tool failures detected. Falling back to current evidence.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.STOPPED,
                    allowed=True,
                    sanitized_decision=sanitized,
                    reason="Repeated investigation failures detected; cycle prevention active.",
                    details={"consecutive_failures": len(last_two)},
                )

        # 4. Action allowlist check
        try:
            action_type = InvestigationActionType(decision.action)
        except Exception:
            sanitized = InvestigationDecision(
                action=InvestigationActionType.STOP_AND_RECOMMEND if sim_results else InvestigationActionType.STOP_INCONCLUSIVE,
                reason=f"Proposed action '{decision.action}' is not in approved allowlist.",
                stop_reason="Disallowed action proposed. Stopping safely.",
                evidence_reference=decision.evidence_reference,
            )
            return PolicyEvaluationResult(
                verdict=PolicyVerdict.REJECTED,
                allowed=False,
                sanitized_decision=sanitized,
                reason=f"Action '{decision.action}' not in approved InvestigationActionType allowlist.",
                details={"unapproved_action": str(decision.action)},
            )

        # 5. Target validation
        if action_type == InvestigationActionType.SIMULATE_CANDIDATE:
            if not decision.target:
                sanitized = InvestigationDecision(
                    action=InvestigationActionType.STOP_AND_RECOMMEND if sim_results else InvestigationActionType.STOP_INCONCLUSIVE,
                    reason="Action simulate_candidate requires a valid target candidate ID.",
                    stop_reason="Missing candidate target ID for simulation.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.REJECTED,
                    allowed=False,
                    sanitized_decision=sanitized,
                    reason="Action 'simulate_candidate' proposed without target candidate ID.",
                )
            if decision.target not in valid_candidate_ids:
                if "," in str(decision.target):
                    first_target = str(decision.target).split(",")[0].strip()
                    if first_target in valid_candidate_ids:
                        sanitized = decision.model_copy(update={"target": first_target})
                        return PolicyEvaluationResult(
                            verdict=PolicyVerdict.MODIFIED,
                            allowed=True,
                            sanitized_decision=sanitized,
                            reason=f"Multiple candidates specified in target '{decision.target}'; sanitized to single candidate '{first_target}'.",
                            details={"original_target": decision.target, "sanitized_target": first_target},
                        )
                sanitized = InvestigationDecision(
                    action=InvestigationActionType.STOP_AND_RECOMMEND if sim_results else InvestigationActionType.STOP_INCONCLUSIVE,
                    reason=f"Target '{decision.target}' is not in valid candidates: {sorted(list(valid_candidate_ids))}.",
                    stop_reason="Invalid candidate target ID.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.REJECTED,
                    allowed=False,
                    sanitized_decision=sanitized,
                    reason=f"Target candidate '{decision.target}' does not exist in generated candidates.",
                    details={"invalid_target": decision.target, "valid_candidates": list(valid_candidate_ids)},
                )

        if action_type == InvestigationActionType.INSPECT_UNCERTAINTY:
            if decision.target and decision.target not in ("all", "") and decision.target not in valid_candidate_ids:
                sanitized = InvestigationDecision(
                    action=InvestigationActionType.INSPECT_UNCERTAINTY,
                    target="all",
                    reason=f"Target '{decision.target}' invalid; falling back to auditing all candidates.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.MODIFIED,
                    allowed=True,
                    sanitized_decision=sanitized,
                    reason=f"Target candidate '{decision.target}' invalid for uncertainty inspection; modified target to 'all'.",
                    details={"original_target": decision.target},
                )

        if action_type == InvestigationActionType.PROPOSE_BENCHMARK:
            comp_name = (
                decision.benchmark_proposal.component_name.strip().lower()
                if decision.benchmark_proposal and decision.benchmark_proposal.component_name
                else (decision.target or "").strip().lower()
            )
            if comp_name not in ALLOWED_BENCHMARK_COMPONENTS:
                sanitized = InvestigationDecision(
                    action=InvestigationActionType.STOP_AND_RECOMMEND if sim_results else InvestigationActionType.STOP_INCONCLUSIVE,
                    reason=f"Component '{comp_name}' not in allowed benchmark catalog ({list(ALLOWED_BENCHMARK_COMPONENTS)}).",
                    stop_reason="Benchmark proposed for unapproved component.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.REJECTED,
                    allowed=False,
                    sanitized_decision=sanitized,
                    reason=f"Benchmark proposal rejected: component '{comp_name}' not in allowed catalog {list(ALLOWED_BENCHMARK_COMPONENTS)}.",
                    details={"disallowed_component": comp_name},
                )

        # 6. Duplicate action prevention
        action_str = action_type.value
        target_str = str(decision.target or "")
        for prev in trace:
            prev_act = prev.get("action", "")
            prev_tgt = str(prev.get("target", "") or "")
            if prev_act == action_str and prev_tgt == target_str and prev.get("policy_verdict") == "APPROVED":
                has_viable_winner = bool(sim_results)
                fallback_action = InvestigationActionType.STOP_AND_RECOMMEND if has_viable_winner else InvestigationActionType.STOP_INCONCLUSIVE
                sanitized = InvestigationDecision(
                    action=fallback_action,
                    reason=f"Action '{action_str}' on target '{target_str}' was already performed in round {prev.get('round')}.",
                    stop_reason="Duplicate action blocked. Sufficient evidence exists.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.REJECTED,
                    allowed=False,
                    sanitized_decision=sanitized,
                    reason=f"Duplicate action '{action_str}:{target_str}' already executed in round {prev.get('round')}.",
                    details={"duplicate_action": action_str, "duplicate_target": target_str},
                )

        # 7. Safe stopping condition checks
        if action_type == InvestigationActionType.STOP_AND_RECOMMEND:
            if not sim_results:
                sanitized = InvestigationDecision(
                    action=InvestigationActionType.STOP_INCONCLUSIVE,
                    reason="Cannot recommend architecture: zero simulation results exist.",
                    stop_reason="No simulation evidence available for recommendation.",
                    evidence_reference=decision.evidence_reference,
                )
                return PolicyEvaluationResult(
                    verdict=PolicyVerdict.MODIFIED,
                    allowed=True,
                    sanitized_decision=sanitized,
                    reason="Modified stop_and_recommend to stop_inconclusive because no simulation results exist.",
                )

        # All policy checks passed!
        return PolicyEvaluationResult(
            verdict=PolicyVerdict.APPROVED,
            allowed=True,
            sanitized_decision=decision,
            reason="Action proposal complies with all safety, budget, target, and deduplication rules.",
            details={"round": current_round + 1, "action": action_type.value},
        )
