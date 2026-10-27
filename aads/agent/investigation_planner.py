"""
Investigation Planner for AADS Phase 4B.
Evaluates current investigation evidence, builds compact prompts for the LLM,
and obtains structured InvestigationDecision objects with deterministic fallback.
"""
import json
import logging
from typing import Dict, List, Optional, Any

from langchain_core.messages import SystemMessage, HumanMessage

from aads.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    BenchmarkProposalDetails,
)
from aads.agent.provider import LLMProviderManager, ExecutionMode
from aads.core.schemas import WorkloadSpec, SimulationResult, RecommendationResult

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the AADS Architecture Investigation Agent.
Your objective is to inspect the current evidence for a backend workload, evaluate candidate architectures,
and decide the next most valuable investigation step from a finite set of approved actions.

Approved actions:
1. inspect_model_coverage: Check whether component models in registry are available, validated, and cover the workload.
2. simulate_candidate: Re-simulate a specific candidate architecture under deeper conditions (target must be a valid candidate ID).
3. inspect_uncertainty: Audit latency confidence intervals and calculate safety headroom against SLA constraints.
4. propose_benchmark: Recommend a targeted container benchmark to reduce empirical model uncertainty (proposal-only; will not execute without authorization).
5. stop_and_recommend: Conclude that current evidence is sufficient to recommend an architectural winner.
6. stop_inconclusive: Conclude that available evidence is contradictory, insufficient, or hard constraints cannot be resolved.

Decision Rules:
- If all candidates are simulated, feasibility is verified, and a clear winner exists without threshold boundary risks, choose 'stop_and_recommend'.
- If target is specified, it MUST be one of the known candidate architecture IDs or approved components.
- Do NOT repeat an action/target combination that was already executed in a previous round.
- Ground your rationale directly in numerical metrics from the evidence summary.
- You must produce a structured InvestigationDecision.
"""


class InvestigationPlanner:
    """
    Plans and selects investigation actions using either live LLM structured outputs
    or deterministic heuristic fallback.
    """

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()

    def build_evidence_summary(self, state: Dict[str, Any]) -> str:
        """Constructs a compact, readable evidence summary for the decision planner."""
        workload: Optional[WorkloadSpec] = state.get("workload_spec")
        candidates = state.get("candidate_architectures", [])
        sim_results: List[SimulationResult] = state.get("simulation_results", [])
        rec: Optional[RecommendationResult] = state.get("recommendation")
        trace: List[Dict[str, Any]] = state.get("investigation_trace", [])
        round_num = state.get("investigation_round", 0) + 1
        max_rounds = state.get("max_investigation_rounds", 3)

        lines = []
        lines.append(f"=== INVESTIGATION STATUS (Round {round_num} of {max_rounds}) ===")

        # 1. Workload Requirements
        if workload:
            lines.append("Workload Requirements:")
            lines.append(f"  - Domain: {workload.app_type}")
            lines.append(f"  - Offered Load: {workload.request_rate_rps} RPS (Peak: {workload.request_rate_rps * workload.peak_load_factor} RPS)")
            lines.append(f"  - Mix: {workload.read_ratio:.0%} reads / {workload.write_ratio:.0%} writes")
            lines.append(f"  - SLA Targets: p95 <= {workload.p95_latency_target_ms} ms | Min Throughput >= {workload.min_throughput_rps} RPS")
            lines.append(f"  - Monthly Budget: <= ${workload.max_monthly_budget_usd:.2f}")
        else:
            lines.append("Workload: Not yet extracted")

        # 2. Known Candidate Architectures
        lines.append(f"Generated Candidates ({len(candidates)} total):")
        for c in candidates:
            cid = c.id if hasattr(c, "id") else c.get("id")
            cname = c.name if hasattr(c, "name") else c.get("name")
            lines.append(f"  - [{cid}] {cname}")

        # 3. Simulation Results
        lines.append(f"Simulated Results ({len(sim_results)} candidates evaluated):")
        for r in sim_results:
            ci_str = f"[{r.latency_uncertainty_p95_ms[0]:.2f}, {r.latency_uncertainty_p95_ms[1]:.2f}] ms" if r.latency_uncertainty_p95_ms else "N/A"
            lines.append(
                f"  - {r.architecture_id}: {r.throughput_achieved_rps:.1f} RPS | "
                f"p95: {r.p95_latency_ms:.2f} ms (95% CI: {ci_str}) | "
                f"Cost: ${r.estimated_monthly_cost_usd:.2f}/mo | "
                f"Bottleneck: {r.bottleneck_component}"
            )

        # 4. Current Evaluator Winner
        if rec:
            lines.append(f"Authoritative Evaluator Recommendation:")
            lines.append(f"  - Selected: {rec.selected_architecture_name} ({rec.selected_architecture_id})")
            lines.append(f"  - Status: {rec.status.value}")
            lines.append(f"  - Feasible Candidates: {[e.architecture_id for e in rec.evaluations if e.feasibility_status.value == 'FEASIBLE']}")

        # 5. Prior Investigation Trace
        if trace:
            lines.append("Prior Investigation Steps:")
            for t in trace:
                r_num = t.get("round", 1)
                act = t.get("action", "")
                tgt = t.get("target", "")
                verdict = t.get("policy_verdict", "")
                summary = t.get("tool_output", {}).get("summary", "")
                lines.append(f"  - Round {r_num}: action={act} (target={tgt}) -> Verdict={verdict} | Result: {summary}")
        else:
            lines.append("Prior Investigation Steps: None (First round)")

        return chr(10).join(lines)

    def plan_next_action(self, state: Dict[str, Any]) -> InvestigationDecision:
        """
        Proposes the next investigation action. Uses LLM when available,
        otherwise safely falls back to deterministic heuristic planner.
        """
        evidence_summary = self.build_evidence_summary(state)

        def fallback_fn() -> InvestigationDecision:
            return self._heuristic_fallback(state)

        if not self.provider_mgr.is_llm_available():
            logger.info("LLM unavailable; using deterministic investigation planner.")
            return fallback_fn()

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content="Review the current investigation evidence and select the next action:" + chr(10) + chr(10) + evidence_summary),
        ]

        try:
            model = self.provider_mgr.get_chat_model()
            structured = model.with_structured_output(InvestigationDecision)
            decision = structured.invoke(messages)

            if isinstance(decision, InvestigationDecision):
                return decision
            else:
                logger.warning(f"LLM returned non-decision type ({type(decision)}); using heuristic fallback.")
                return fallback_fn()

        except Exception as e:
            logger.warning(f"LLM investigation planning failed ({e}); using heuristic fallback.")
            return fallback_fn()

    def _heuristic_fallback(self, state: Dict[str, Any]) -> InvestigationDecision:
        """
        Deterministic rule-based planning when LLM is unavailable or unconfigured.
        Follows a rigorous empirical sequence: model coverage -> uncertainty audit -> stop/recommend.
        """
        trace: List[Dict[str, Any]] = state.get("investigation_trace", [])
        executed_actions = {t.get("action") for t in trace if t.get("policy_verdict") == "APPROVED"}
        sim_results: List[SimulationResult] = state.get("simulation_results", [])
        workload: Optional[WorkloadSpec] = state.get("workload_spec")
        rec: Optional[RecommendationResult] = state.get("recommendation")

        # Step 1: If model coverage has not been audited yet, inspect model coverage
        if "inspect_model_coverage" not in executed_actions:
            return InvestigationDecision(
                action=InvestigationActionType.INSPECT_MODEL_COVERAGE,
                target="all_candidates",
                reason="Audit registry model coverage and calibration status for all candidate architectures.",
                expected_information_gain="Identify uncalibrated or missing component performance models.",
                evidence_reference=["candidate_architectures"],
            )

        # Step 2: If uncertainty has not been checked yet, audit latency uncertainty
        if "inspect_uncertainty" not in executed_actions and sim_results:
            return InvestigationDecision(
                action=InvestigationActionType.INSPECT_UNCERTAINTY,
                target="all",
                reason="Audit 95% latency confidence intervals against hard SLA targets across all candidates.",
                expected_information_gain="Detect candidate SLA boundary risks and confidence margins.",
                evidence_reference=["simulation_results"],
            )

        # Step 3: If an uncalibrated component or missing model exists, propose a benchmark
        missing = state.get("missing_models", [])
        if missing and "propose_benchmark" not in executed_actions:
            first_missing = missing[0]
            comp, ver = first_missing.split(":", 1) if ":" in first_missing else (first_missing, "16")
            return InvestigationDecision(
                action=InvestigationActionType.PROPOSE_BENCHMARK,
                target=comp,
                benchmark_proposal=BenchmarkProposalDetails(
                    component_name=comp,
                    version=ver,
                    target_concurrency=32,
                    rationale=f"Component model '{first_missing}' is uncalibrated. A benchmark is recommended.",
                ),
                reason=f"Missing empirical calibration for '{first_missing}'. Propose targeted benchmark.",
                expected_information_gain="Reduce empirical model variance for uncalibrated component.",
                evidence_reference=[first_missing],
            )

        # Step 4: Evidence is sufficient, stop and recommend!
        if sim_results:
            winner_name = rec.selected_architecture_name if rec else "winning architecture"
            return InvestigationDecision(
                action=InvestigationActionType.STOP_AND_RECOMMEND,
                target=rec.selected_architecture_id if rec else None,
                reason=f"Sufficient simulation and uncertainty evidence established. {winner_name} identified.",
                expected_information_gain="Final architectural recommendation backed by evidence.",
                evidence_reference=["simulation_results", "evaluator"],
                stop_reason="All candidate evaluations, model coverage checks, and uncertainty audits complete.",
            )

        return InvestigationDecision(
            action=InvestigationActionType.STOP_INCONCLUSIVE,
            reason="No simulation results available to form an architectural recommendation.",
            stop_reason="Simulation evidence absent.",
        )
