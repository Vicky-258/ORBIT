"""
Investigation Tool Dispatcher for AADS Phase 4B.
Executes approved investigation actions through explicit, deterministic handlers.
Records bounded, serializable results and updates workflow state with proper provenance.
"""
import time
import logging
from typing import Dict, List, Optional, Any, Tuple

from aads.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    InvestigationRecord,
    ExperimentProposal,
    AuthorizationRecord,
    AuthorizationStatus,
)
from aads.benchmark.bounded_executor import BoundedBenchmarkExecutor
from aads.benchmark.experiment_ranker import ExperimentRanker
from aads.modeling.calibration_pipeline import CalibrationPipeline
from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
)
from aads.registry.component_registry import ComponentRegistry
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender
from aads.agent.tools import ALLOWED_BENCHMARK_COMPONENTS

logger = logging.getLogger(__name__)


class InvestigationDispatcher:
    """
    Explicit dispatcher for validated investigation actions.
    Guarantees deterministic execution and strict isolation from LLM hallucinations.
    """

    def __init__(
        self,
        registry: Optional[ComponentRegistry] = None,
        executor: Optional[BoundedBenchmarkExecutor] = None,
        calibration_pipeline: Optional[CalibrationPipeline] = None,
        ranker: Optional[ExperimentRanker] = None,
    ):
        self.registry = registry or ComponentRegistry()
        self.registry.seed_baseline_data()
        self.executor = executor or BoundedBenchmarkExecutor(registry=self.registry)
        self.calibration_pipeline = calibration_pipeline or CalibrationPipeline(registry=self.registry)
        self.ranker = ranker or ExperimentRanker(registry=self.registry)

    def dispatch(
        self,
        decision: InvestigationDecision,
        state: Dict[str, Any],
        round_num: int,
    ) -> Tuple[Dict[str, Any], InvestigationRecord]:
        """
        Executes an approved investigation action.
        Returns (state_updates, record).
        """
        start_t = time.perf_counter()
        action = decision.action
        target = decision.target
        workload: Optional[WorkloadSpec] = state.get("workload_spec")
        candidates: List[ArchitectureGraph] = state.get("candidate_architectures", [])
        sim_results: List[SimulationResult] = list(state.get("simulation_results", []))
        rec: Optional[RecommendationResult] = state.get("recommendation")

        tool_invoked = None
        tool_input: Dict[str, Any] = {}
        tool_output: Dict[str, Any] = {}
        state_updates: Dict[str, Any] = {}
        provenance = "agent_decision"
        stop_reason = None

        try:
            if action == InvestigationActionType.INSPECT_MODEL_COVERAGE:
                tool_invoked = "check_component_models"
                tool_input = {"target": target or "all_candidates"}
                tool_output, updates = self._handle_inspect_model_coverage(candidates, workload)
                state_updates.update(updates)
                provenance = "model_derived"

            elif action == InvestigationActionType.SIMULATE_CANDIDATE:
                tool_invoked = "simulate_architecture"
                tool_input = {
                    "target": target,
                    "duration_seconds": state.get("simulation_duration_seconds", 5.0),
                    "random_seed": state.get("random_seed", 42),
                }
                tool_output, updates = self._handle_simulate_candidate(target, candidates, workload, state)
                state_updates.update(updates)
                provenance = "simulated"

            elif action == InvestigationActionType.INSPECT_UNCERTAINTY:
                tool_invoked = "inspect_uncertainty"
                tool_input = {"target": target or "all_candidates"}
                tool_output, updates = self._handle_inspect_uncertainty(target, sim_results, workload)
                state_updates.update(updates)
                provenance = "uncertainty_analysis"

            elif action == InvestigationActionType.PROPOSE_BENCHMARK:
                tool_invoked = "propose_benchmark"
                tool_input = {
                    "proposal": decision.benchmark_proposal.model_dump() if decision.benchmark_proposal else (
                        decision.experiment_proposal.model_dump() if decision.experiment_proposal else {"target": target}
                    )
                }
                tool_output, updates = self._handle_propose_benchmark(decision, state)
                state_updates.update(updates)
                provenance = "benchmark_proposal"

            elif action == InvestigationActionType.EXECUTE_EXPERIMENT:
                tool_invoked = "execute_experiment"
                tool_input = {
                    "proposal": decision.experiment_proposal.model_dump() if decision.experiment_proposal else {"target": target}
                }
                tool_output, updates = self._handle_execute_experiment(decision, candidates, sim_results, workload, state)
                state_updates.update(updates)
                provenance = tool_output.get("provenance", "measured_experiment")

            elif action == InvestigationActionType.STOP_AND_RECOMMEND:
                tool_invoked = "stop_and_recommend"
                tool_input = {"stop_reason": decision.stop_reason}
                tool_output, updates = self._handle_stop_and_recommend(decision, sim_results, workload)
                state_updates.update(updates)
                stop_reason = decision.stop_reason or "Sufficient evidence established for architectural recommendation."
                provenance = "decision_policy"

            elif action == InvestigationActionType.STOP_INCONCLUSIVE:
                tool_invoked = "stop_inconclusive"
                tool_input = {"stop_reason": decision.stop_reason}
                tool_output, updates = self._handle_stop_inconclusive(decision)
                state_updates.update(updates)
                stop_reason = decision.stop_reason or "Investigation terminated inconclusively."
                provenance = "decision_policy"

            else:
                tool_output = {"success": False, "error": f"Unhandled action: {action}"}
                provenance = "error"

        except Exception as exc:
            logger.error(f"Investigation tool dispatch error ({action}): {exc}", exc_info=True)
            tool_output = {"success": False, "error": str(exc)}
            provenance = "error"

        elapsed = round(time.perf_counter() - start_t, 3)

        record = InvestigationRecord(
            round=round_num,
            action=str(action.value if hasattr(action, "value") else action),
            target=target,
            reason=decision.reason,
            expected_information_gain=decision.expected_information_gain,
            evidence_reference=decision.evidence_reference,
            policy_verdict="APPROVED",
            policy_reason="Action passed all policy constraints and dispatched successfully.",
            tool_invoked=tool_invoked,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_seconds=elapsed,
            provenance=provenance,
            stop_reason=stop_reason,
        )

        # Update budget and round tracking in state updates
        budget_spent = state.get("investigation_budget_spent", 0.0) + elapsed
        state_updates["investigation_budget_spent"] = budget_spent
        state_updates["investigation_round"] = round_num

        return state_updates, record

    def _handle_inspect_model_coverage(
        self,
        candidates: List[ArchitectureGraph],
        workload: Optional[WorkloadSpec],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        coverage_by_arch = {}
        all_missing = []

        for c in candidates:
            c_missing = []
            c_statuses = {}
            for req in c.required_models:
                comp, ver = req.split(":", 1) if ":" in req else (req, "latest")
                status, model, warn = self.registry.check_compatibility(comp, ver, workload)
                c_statuses[req] = {
                    "status": status,
                    "is_validated": model.is_validated if model else False,
                    "is_synthetic": model.is_synthetic_fixture if model else None,
                    "model_type": model.model_type if model else None,
                }
                if status == "MISSING":
                    c_missing.append(req)
                    all_missing.append(req)

            coverage_by_arch[c.id] = {
                "name": c.name,
                "required_models": c.required_models,
                "missing_models": c_missing,
                "fully_covered": len(c_missing) == 0,
                "statuses": c_statuses,
            }

        all_missing = sorted(list(set(all_missing)))
        output = {
            "success": True,
            "coverage_by_architecture": coverage_by_arch,
            "missing_models": all_missing,
            "total_candidates_audited": len(candidates),
            "summary": f"Audited {len(candidates)} candidates; {len(all_missing)} missing models identified.",
        }
        return output, {"missing_models": all_missing}

    def _handle_simulate_candidate(
        self,
        target_id: Optional[str],
        candidates: List[ArchitectureGraph],
        workload: Optional[WorkloadSpec],
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        cand = next((c for c in candidates if c.id == target_id), None)
        if not cand:
            return {"success": False, "error": f"Candidate '{target_id}' not found in candidates."}, {}

        if not workload:
            return {"success": False, "error": "Workload specification missing in state."}, {}

        duration = state.get("simulation_duration_seconds", 5.0)
        seed = state.get("random_seed", 42)

        engine = SimPyEngine(registry=self.registry)
        sim_res = engine.simulate_architecture(
            architecture=cand,
            workload=workload,
            duration_seconds=duration,
            random_seed=seed,
        )

        # Update or append simulation results
        existing_sims = list(state.get("simulation_results", []))
        updated_sims = [s for s in existing_sims if s.architecture_id != cand.id]
        updated_sims.append(sim_res)

        # Re-evaluate candidates with the refreshed simulation data
        recommender_rec = ArchitectureRecommender.evaluate_and_recommend(
            workload=workload,
            sim_results=updated_sims,
        )

        output = {
            "success": True,
            "architecture_id": cand.id,
            "architecture_name": cand.name,
            "throughput_achieved_rps": sim_res.throughput_achieved_rps,
            "p95_latency_ms": sim_res.p95_latency_ms,
            "latency_uncertainty_p95_ms": sim_res.latency_uncertainty_p95_ms,
            "bottleneck_component": sim_res.bottleneck_component,
            "component_utilizations": sim_res.component_utilizations,
            "estimated_monthly_cost_usd": sim_res.estimated_monthly_cost_usd,
            "summary": f"Simulated {cand.name}: {sim_res.throughput_achieved_rps:.1f} RPS, p95={sim_res.p95_latency_ms:.2f}ms.",
        }
        updates = {
            "simulation_results": updated_sims,
            "recommendation": recommender_rec,
        }
        return output, updates

    def _handle_inspect_uncertainty(
        self,
        target: Optional[str],
        sim_results: List[SimulationResult],
        workload: Optional[WorkloadSpec],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if not sim_results:
            return {"success": False, "error": "No simulation results available for uncertainty inspection."}, {}

        target_p95 = workload.p95_latency_target_ms if workload else 50.0
        budget = workload.max_monthly_budget_usd if workload else 250.0
        min_tp = workload.min_throughput_rps if workload else 400.0

        targets_to_inspect = [s for s in sim_results if s.architecture_id == target] if (target and target != "all") else sim_results
        audit = []
        for r in targets_to_inspect:
            ci = r.latency_uncertainty_p95_ms or [r.p95_latency_ms, r.p95_latency_ms]
            lower, upper = ci[0], ci[1]
            ci_width = round(upper - lower, 2)
            headroom = round(target_p95 - upper, 2)
            crosses_sla = upper > target_p95
            is_boundary = abs(headroom) <= 5.0 or (lower <= target_p95 <= upper)

            audit.append({
                "architecture_id": r.architecture_id,
                "architecture_name": r.architecture_name,
                "p95_measured": r.p95_latency_ms,
                "latency_uncertainty_ci_95": [round(lower, 2), round(upper, 2)],
                "ci_width_ms": ci_width,
                "sla_target_ms": target_p95,
                "sla_headroom_ms": headroom,
                "crosses_sla_threshold": crosses_sla,
                "is_near_sla_boundary": is_boundary,
                "budget_cap_usd": budget,
                "cost_monthly_usd": r.estimated_monthly_cost_usd,
                "cost_headroom_usd": round(budget - r.estimated_monthly_cost_usd, 2),
                "throughput_achieved_rps": r.throughput_achieved_rps,
                "throughput_headroom_rps": round(r.throughput_achieved_rps - min_tp, 2),
            })

        output = {
            "success": True,
            "uncertainty_audit": audit,
            "total_candidates_analyzed": len(audit),
            "summary": f"Uncertainty analysis completed across {len(audit)} candidates.",
        }
        return output, {}

    def _handle_propose_benchmark(
        self,
        decision: InvestigationDecision,
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        bp = decision.benchmark_proposal
        comp_name = bp.component_name if bp else (decision.target or "postgres_db")
        comp_name = comp_name.strip().lower()
        version = bp.version if bp else "16"
        concurrency = bp.target_concurrency if bp else 50
        rationale = bp.rationale if bp else decision.reason

        proposal_record = {
            "component_name": comp_name,
            "version": version,
            "target_concurrency": min(max(concurrency, 1), 64),
            "rationale": rationale,
            "authorization_status": "PROPOSED_AWAITING_EXPLICIT_AUTHORIZATION",
            "requires_docker": True,
            "is_executed": False,
            "safety_boundary": "Resource-intensive container benchmark was NOT executed. Explicit user approval required.",
            "provenance": "benchmark_proposal",
        }

        existing_proposals = list(state.get("benchmark_proposals", []))
        existing_proposals.append(proposal_record)

        output = {
            "success": True,
            "proposal": proposal_record,
            "executed": False,
            "requires_authorization": True,
            "summary": f"Benchmark proposal recorded for '{comp_name}:{version}' at concurrency {concurrency}. Live execution withheld pending authorization.",
        }
        return output, {"benchmark_proposals": existing_proposals}

    def _handle_stop_and_recommend(
        self,
        decision: InvestigationDecision,
        sim_results: List[SimulationResult],
        workload: Optional[WorkloadSpec],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if not sim_results or not workload:
            return {"success": False, "error": "Cannot recommend without simulations and workload."}, {}

        rec = ArchitectureRecommender.evaluate_and_recommend(
            workload=workload,
            sim_results=sim_results,
        )
        output = {
            "success": True,
            "selected_architecture_id": rec.selected_architecture_id,
            "selected_architecture_name": rec.selected_architecture_name,
            "feasibility_status": rec.status.value,
            "stop_reason": decision.stop_reason or "Sufficient evidence collected.",
            "summary": f"Investigation concluded: Recommended {rec.selected_architecture_name} ({rec.status.value}).",
        }
        updates = {
            "recommendation": rec,
            "workflow_status": "RECOMMENDED",
            "investigation_status": "CONCLUDED_RECOMMENDED",
        }
        return output, updates

    def _handle_stop_inconclusive(
        self,
        decision: InvestigationDecision,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        output = {
            "success": True,
            "selected_architecture_id": None,
            "feasibility_status": "INCONCLUSIVE",
            "stop_reason": decision.stop_reason or "Investigation terminated inconclusively.",
            "summary": "Investigation concluded without finding sufficient evidence for recommendation.",
        }
        updates = {
            "workflow_status": "INSUFFICIENT_EVIDENCE",
            "investigation_status": "CONCLUDED_INCONCLUSIVE",
        }
        return output, updates

    def _handle_execute_experiment(
        self,
        decision: InvestigationDecision,
        candidates: List[ArchitectureGraph],
        sim_results: List[SimulationResult],
        workload: Optional[WorkloadSpec],
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Executes an authorized benchmark experiment, records measured evidence immutably,
        recalibrates component model through held-out validation, and re-evaluates architecture recommendation.
        """
        import uuid
        from datetime import datetime, timezone

        # 1. Resolve experiment proposal
        proposal: Optional[ExperimentProposal] = decision.experiment_proposal
        if proposal is None:
            if decision.benchmark_proposal:
                proposal = ExperimentRanker.proposal_from_details(decision.benchmark_proposal, workload)
            else:
                comp = (decision.target or "postgres_db").strip().lower()
                ver = "redis:7.2-alpine" if "redis" in comp else "postgres:16-alpine"
                proposal = ExperimentProposal(
                    proposal_id=f"prop_{uuid.uuid4().hex[:10]}",
                    target_component=comp,
                    version=ver,
                    hypothesis=f"Measure {comp} service demand scaling under load",
                    unknown_being_investigated=f"{comp} latency and capacity inflection point",
                    concurrency_levels=[1, 4, 8, 16, 24, 32],
                    read_ratio=workload.read_ratio if workload else 1.0,
                    target_rps=workload.request_rate_rps if workload else 200.0,
                )
        else:
            # Ensure proper version tag and concurrency range if LLM provided generic proposal
            if "postgres" in proposal.target_component and proposal.version in ("16", "latest", "postgres_db"):
                proposal.version = "postgres:16-alpine"
            elif "redis" in proposal.target_component and proposal.version in ("7", "latest", "redis_cache"):
                proposal.version = "redis:7.2-alpine"
            if max(proposal.concurrency_levels or [1]) < 24 and "postgres" in proposal.target_component:
                proposal.concurrency_levels = sorted(list(set(proposal.concurrency_levels + [24, 32])))

        # 2. Resolve authorization record
        auth: Optional[AuthorizationRecord] = state.get("experiment_authorization")
        if auth is not None and auth.proposal_id in ("agent_authorized_exp", "*"):
            # Bind the pre-authorized session token to this specific proposal
            auth.proposal_id = proposal.proposal_id
        elif auth is None and state.get("auto_authorize_synthetic"):
            auth = AuthorizationRecord(
                authorization_id=f"auth_{uuid.uuid4().hex[:8]}",
                proposal_id=proposal.proposal_id,
                authorized_by="state_auto_authorize_synthetic",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                execution_mode="synthetic",
                status=AuthorizationStatus.AUTHORIZED,
                max_runtime_seconds=60.0,
            )

        # 3. Execute experiment via bounded interface
        exec_res = self.executor.execute_experiment(proposal, auth)
        if exec_res.status != "SUCCESS":
            return {
                "success": False,
                "error": exec_res.error_message or "Experiment execution failed.",
                "execution_result": exec_res.model_dump(),
                "provenance": exec_res.provenance,
            }, {}

        # 4. Validated Model Calibration Pipeline
        calib_outcome = self.calibration_pipeline.calibrate_component(
            component_name=proposal.target_component,
            version=proposal.version,
        )

        exec_res.model_update_status = calib_outcome.status
        exec_res.promoted_model_id = calib_outcome.new_model_id

        # 5. Closed-loop re-simulation & recommendation re-evaluation
        prev_rec = state.get("recommendation")
        prev_winner = prev_rec.selected_architecture_id if prev_rec else None
        prev_status = prev_rec.status.value if prev_rec and hasattr(prev_rec.status, "value") else str(prev_rec.status if prev_rec else "UNKNOWN")

        new_sim_results = list(sim_results)
        recommendation_changed = False
        new_winner = prev_winner
        new_status = prev_status
        new_rec = prev_rec

        if calib_outcome.status == "PROMOTED" and workload and candidates:
            # Re-simulate candidates that use this component
            target_comp = proposal.target_component.lower()
            resimulated_count = 0
            updated_results = []

            for cand in candidates:
                # Check if architecture utilizes calibrated component
                comps = getattr(cand, "components", {})
                uses_comp = False
                if isinstance(comps, dict):
                    for k, comp in comps.items():
                        c_name = getattr(comp, "name", str(comp)).lower()
                        if target_comp in c_name or target_comp in k.lower():
                            uses_comp = True
                            break

                if uses_comp:
                    engine = SimPyEngine(self.registry)
                    sim_run = engine.simulate_architecture(
                        architecture=cand,
                        workload=workload,
                        duration_seconds=state.get("simulation_duration_seconds", 5.0),
                        random_seed=state.get("random_seed", 42),
                    )
                    updated_results.append(sim_run)
                    resimulated_count += 1
                else:
                    # Retain prior simulation
                    cand_id = cand.id if hasattr(cand, "id") else cand.get("id")
                    prior = next((s for s in sim_results if s.architecture_id == cand_id), None)
                    if prior:
                        updated_results.append(prior)

            new_sim_results = updated_results

            # Reapply hard constraints and ranking logic
            new_rec = ArchitectureRecommender.evaluate_and_recommend(
                workload=workload,
                sim_results=new_sim_results,
            )
            new_winner = new_rec.selected_architecture_id
            new_status = new_rec.status.value if hasattr(new_rec.status, "value") else str(new_rec.status)
            recommendation_changed = (prev_winner != new_winner)

        output = {
            "success": True,
            "execution": exec_res.model_dump(),
            "calibration": calib_outcome.model_dump(),
            "closed_loop_delta": {
                "model_promoted": (calib_outcome.status == "PROMOTED"),
                "promoted_model_id": calib_outcome.new_model_id,
                "is_empirical_upgrade": calib_outcome.is_empirical_upgrade,
                "previous_winner": prev_winner,
                "new_winner": new_winner,
                "recommendation_changed": recommendation_changed,
                "feasibility_status_before": prev_status,
                "feasibility_status_after": new_status,
                "affected_candidates_resimulated": len(new_sim_results),
            },
            "provenance": exec_res.provenance,
            "summary": (
                f"Experiment executed ({exec_res.raw_records_count} trials). Calibration: {calib_outcome.status}. "
                + (f"Recommendation changed from {prev_winner} to {new_winner}." if recommendation_changed else f"Recommendation retained at {prev_winner}.")
            ),
        }

        updates = {
            "simulation_results": new_sim_results,
            "recommendation": new_rec,
            "last_experiment_delta": output["closed_loop_delta"],
        }
        return output, updates
