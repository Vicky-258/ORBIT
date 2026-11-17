"""
Investigation Planner for AADS Phase 4B.
Evaluates current investigation evidence, builds compact prompts for the LLM,
and obtains structured InvestigationDecision objects with deterministic fallback.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from aads.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    BenchmarkProposalDetails,
)
from aads.agent.provider import LLMProviderManager, ExecutionMode
from aads.core.schemas import WorkloadSpec, SimulationResult, RecommendationResult

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the ORBIT (Orchestrated Reasoning and Benchmarking for Infrastructure Testing) Architecture Investigation Agent.
Your objective is to inspect the current evidence for a backend workload, evaluate candidate architectures,
and decide the next most valuable investigation step from a finite set of approved actions.

Approved actions:
1. inspect_model_coverage: Check whether component models in registry are available, validated, and cover the workload.
2. simulate_candidate: Re-simulate a specific candidate architecture under deeper conditions (target MUST be exactly ONE candidate architecture ID, e.g. 'arch_a_simple', NOT comma-separated).
3. inspect_uncertainty: Audit latency heuristic uncertainty bounds and calculate safety headroom against SLA constraints (target should be 'all' or a single candidate ID).
4. propose_benchmark: Recommend a targeted container benchmark to reduce empirical model uncertainty (proposal-only; will not execute without authorization).
5. execute_experiment: Run an authorized benchmark trial to calibrate a component model, re-simulate affected candidates, and update recommendations.
6. stop_and_recommend: Conclude that current evidence is sufficient to recommend an architectural winner.
7. stop_inconclusive: Conclude that available evidence is contradictory, insufficient, or hard constraints cannot be resolved.

Decision Rules:
- If component model status indicates an uncalibrated synthetic prior or high uncertainty, and Experiment Authorization is GRANTED, prioritize "execute_experiment" to measure real performance and recalibrate the model.
- If all candidates are simulated, feasibility is verified, and component models are calibrated without threshold boundary risks, choose "stop_and_recommend".
- If target is specified, it MUST be exactly one single candidate ID (e.g. "arch_a_simple") or component name (e.g. "postgres_db").
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
                f"p95: {r.p95_latency_ms:.2f} ms (Uncertainty bounds: {ci_str}) | "
                f"Cost: ${r.estimated_monthly_cost_usd:.2f}/mo | "
                f"Bottleneck: {r.bottleneck_component}"
            )

        # 4. Current Evaluator Winner
        if rec:
            lines.append(f"Authoritative Evaluator Recommendation:")
            lines.append(f"  - Selected: {rec.selected_architecture_name} ({rec.selected_architecture_id})")
            lines.append(f"  - Status: {rec.status.value}")
            lines.append(f"  - Feasible Candidates: {[e.architecture_id for e in rec.evaluations if e.feasibility_status.value == 'FEASIBLE']}")

        # 4b. Component Model Status & Authorization
        reg = state.get("component_registry")
        active_exp = state.get("enable_active_experimentation", False)
        auth = state.get("experiment_authorization")
        if reg and workload:
            lines.append("Component Model Status:")
            for comp_name in ["postgres_db", "redis_cache"]:
                ver = "postgres:16-alpine" if "postgres" in comp_name else "redis:7.2-alpine"
                status, model, warns = reg.check_compatibility(comp_name, ver, workload)
                calib_tag = "synthetic prior (uncalibrated)" if (model and model.is_synthetic_fixture) else ("empirically calibrated" if model else "missing")
                rmse_str = f"RMSE={model.validation_rmse_ms:.2f}ms" if (model and model.validation_rmse_ms) else "unvalidated"
                lines.append(f"  - {comp_name}: status={status} | type={calib_tag} | {rmse_str}")
        if active_exp and auth:
            lines.append(f"Experiment Authorization: GRANTED (Mode: {auth.execution_mode}, AuthID: {auth.authorization_id}). Authorized benchmark action: execute_experiment.")

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

    def plan_next_action_with_telemetry(
        self,
        state: Dict[str, Any],
        fail_closed: bool = False,
    ) -> Tuple[InvestigationDecision, Dict[str, Any]]:
        """
        Proposes the next action and returns comprehensive telemetry metadata.
        If fail_closed is True, failures will NOT invoke fallback; instead they raise RuntimeError
        or return error telemetry to ensure live evaluations are strictly verified.
        """
        evidence_summary = self.build_evidence_summary(state)
        call_id = f"call_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        telemetry: Dict[str, Any] = {
            "call_id": call_id,
            "timestamp": timestamp,
            "provider": "unknown",
            "model_name": "unknown",
            "request_id": None,
            "latency_ms": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "is_live": False,
            "fallback_used": False,
            "error": None,
        }

        if not self.provider_mgr.is_llm_available():
            msg = "LLM provider credentials unavailable."
            telemetry["error"] = msg
            if fail_closed:
                raise RuntimeError(f"Fail-closed: {msg}")
            telemetry["fallback_used"] = True
            return self._heuristic_fallback(state), telemetry

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content="Review the current investigation evidence and select the next action:\n\n" + evidence_summary),
        ]

        t0 = time.perf_counter()
        try:
            model = self.provider_mgr.get_chat_model()
            structured = model.with_structured_output(InvestigationDecision, include_raw=True)
            res = structured.invoke(messages)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            telemetry["latency_ms"] = round(elapsed_ms, 2)
            telemetry["is_live"] = True

            # Extract raw metadata if available
            raw = res.get("raw")
            if raw and hasattr(raw, "response_metadata"):
                meta = raw.response_metadata or {}
                telemetry["request_id"] = meta.get("id")
                telemetry["model_name"] = meta.get("model_name", "unknown")
                telemetry["provider"] = meta.get("model_provider", "groq" if "groq" in str(meta).lower() else "openai")

            if raw and hasattr(raw, "usage_metadata") and raw.usage_metadata:
                usage = raw.usage_metadata
                telemetry["prompt_tokens"] = usage.get("input_tokens", 0)
                telemetry["completion_tokens"] = usage.get("output_tokens", 0)
                telemetry["total_tokens"] = usage.get("total_tokens", 0)
            elif raw and hasattr(raw, "response_metadata") and "token_usage" in raw.response_metadata:
                tu = raw.response_metadata["token_usage"]
                telemetry["prompt_tokens"] = tu.get("prompt_tokens", 0)
                telemetry["completion_tokens"] = tu.get("completion_tokens", 0)
                telemetry["total_tokens"] = tu.get("total_tokens", 0)

            # Estimate cost ($0.15/1M input, $0.75/1M output standard rate)
            cost = (telemetry["prompt_tokens"] * 0.00000015) + (telemetry["completion_tokens"] * 0.00000075)
            telemetry["estimated_cost_usd"] = round(cost, 6)

            parsed = res.get("parsed")
            parsing_err = res.get("parsing_error")

            if isinstance(parsed, InvestigationDecision):
                return parsed, telemetry
            elif parsing_err:
                err_msg = f"LLM output parsing error: {parsing_err}"
                telemetry["error"] = err_msg
                if fail_closed:
                    raise RuntimeError(f"Fail-closed: {err_msg}")
                telemetry["fallback_used"] = True
                return self._heuristic_fallback(state), telemetry
            else:
                err_msg = f"Unexpected decision output type: {type(parsed)}"
                telemetry["error"] = err_msg
                if fail_closed:
                    raise RuntimeError(f"Fail-closed: {err_msg}")
                telemetry["fallback_used"] = True
                return self._heuristic_fallback(state), telemetry

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            telemetry["latency_ms"] = round(elapsed_ms, 2)
            telemetry["error"] = str(e)
            if fail_closed:
                raise RuntimeError(f"Fail-closed LLM call failed: {e}") from e
            telemetry["fallback_used"] = True
            return self._heuristic_fallback(state), telemetry

    def plan_next_action(self, state: Dict[str, Any]) -> InvestigationDecision:
        """
        Proposes the next investigation action. Uses LLM when available,
        otherwise safely falls back to deterministic heuristic planner.
        """
        decision, _ = self.plan_next_action_with_telemetry(state, fail_closed=False)
        return decision

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
                reason="Audit latency heuristic uncertainty bounds against hard SLA targets across all candidates.",
                expected_information_gain="Detect candidate SLA boundary risks and confidence margins.",
                evidence_reference=["simulation_results"],
            )

        # Step 3: Active Experimentation if enabled and authorized
        has_auth = bool(state.get("experiment_authorization") or state.get("auto_authorize_synthetic"))
        active_exp_enabled = state.get("enable_active_experimentation", False)

        if (active_exp_enabled or has_auth) and "execute_experiment" not in executed_actions:
            target_comp = "postgres_db"
            return InvestigationDecision(
                action=InvestigationActionType.EXECUTE_EXPERIMENT,
                target=target_comp,
                reason=f"Execute authorized benchmark on {target_comp} to acquire empirical measurements and resolve model uncertainty.",
                expected_information_gain="Calibrate empirical service demand model with group-based held-out validation.",
                evidence_reference=["simulation_results", target_comp],
            )

        # Step 3b: If an uncalibrated component or missing model exists, propose a benchmark
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
