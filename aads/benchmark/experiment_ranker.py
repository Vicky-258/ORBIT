"""
Deterministic Experiment Selection and Ranking Engine (Phase 4D).
Evaluates, validates, and prioritizes experiment proposals against decision-relevance criteria:
- SLA boundary proximity (uncertainty overlapping constraints)
- Hypothesis separation (distinguishing close candidate architectures)
- Model validity & range coverage (operating in uncalibrated or boundary regimes)
- Execution efficiency and risk bounds
"""
import uuid
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field

from aads.agent.schemas import ExperimentProposal, BenchmarkProposalDetails, AuthorizationLevel
from aads.core.schemas import WorkloadSpec, SimulationResult, ArchitectureGraph
from aads.registry.component_registry import ComponentRegistry


ALLOWED_BENCHMARK_COMPONENTS = {"postgres_db", "redis_cache"}


class RankedExperimentProposal(BaseModel):
    """Experiment proposal annotated with deterministic priority score and validation verdict."""
    proposal: ExperimentProposal
    priority_score: float = Field(default=0.0, description="Deterministic priority score between 0.0 and 1.0")
    is_approved: bool = Field(default=True, description="Whether proposal is approved for execution")
    rejection_reason: Optional[str] = Field(default=None, description="Reason if proposal was rejected")
    score_components: Dict[str, float] = Field(default_factory=dict, description="Detailed score breakdown")


class ExperimentRanker:
    """
    Evaluates and ranks proposed benchmark experiments deterministically.
    Ensures proposals address decision-relevant unknowns rather than arbitrary exploration.
    """

    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry

    def rank_proposals(
        self,
        proposals: List[ExperimentProposal],
        workload: WorkloadSpec,
        candidates: List[ArchitectureGraph],
        simulation_results: List[SimulationResult],
        remaining_budget_seconds: float = 60.0,
        executed_experiment_keys: Optional[Set[str]] = None,
    ) -> List[RankedExperimentProposal]:
        """
        Validates, filters, and ranks a list of experiment proposals.
        Returns list of RankedExperimentProposal sorted descending by priority_score.
        """
        executed_keys = executed_experiment_keys or set()
        ranked: List[RankedExperimentProposal] = []

        # Identify components actually used by the candidate architectures
        used_components = set()
        for c in candidates:
            comps = getattr(c, "components", {})
            if isinstance(comps, dict):
                for k, comp in comps.items():
                    c_name = getattr(comp, "name", str(comp)).lower()
                    used_components.add(c_name)
                    used_components.add(k.lower())

        for p in proposals:
            ranked_item = self.evaluate_proposal(
                proposal=p,
                workload=workload,
                candidates=candidates,
                simulation_results=simulation_results,
                used_components=used_components,
                remaining_budget_seconds=remaining_budget_seconds,
                executed_experiment_keys=executed_keys,
            )
            ranked.append(ranked_item)

        # Sort descending by priority score; rejected proposals go to the bottom
        ranked.sort(key=lambda r: (r.is_approved, r.priority_score), reverse=True)
        return ranked

    def evaluate_proposal(
        self,
        proposal: ExperimentProposal,
        workload: WorkloadSpec,
        candidates: List[ArchitectureGraph],
        simulation_results: List[SimulationResult],
        used_components: Set[str],
        remaining_budget_seconds: float = 60.0,
        executed_experiment_keys: Optional[Set[str]] = None,
    ) -> RankedExperimentProposal:
        """Evaluates an individual experiment proposal against deterministic criteria."""
        comp = proposal.target_component.strip().lower()

        # 1. Component allowlist check
        if comp not in ALLOWED_BENCHMARK_COMPONENTS:
            return RankedExperimentProposal(
                proposal=proposal,
                priority_score=0.0,
                is_approved=False,
                rejection_reason=f"Target component '{comp}' is not in approved benchmark catalog ({sorted(list(ALLOWED_BENCHMARK_COMPONENTS))}).",
            )

        # 2. Relevance to candidate architectures check
        # Match component names (e.g. postgres_db matches postgres_db node type)
        is_relevant = any(comp in u for u in used_components)
        if not is_relevant:
            return RankedExperimentProposal(
                proposal=proposal,
                priority_score=0.0,
                is_approved=False,
                rejection_reason=f"Target component '{comp}' is not utilized by any candidate architecture in this workload.",
            )

        # 3. Budget & timeout check
        if proposal.expected_runtime_seconds > remaining_budget_seconds:
            return RankedExperimentProposal(
                proposal=proposal,
                priority_score=0.0,
                is_approved=False,
                rejection_reason=f"Estimated runtime ({proposal.expected_runtime_seconds:.1f}s) exceeds remaining budget ({remaining_budget_seconds:.1f}s).",
            )

        # 4. Duplicate proposal check
        exp_key = f"{comp}_{proposal.version}_{sorted(proposal.concurrency_levels)}_{round(proposal.read_ratio, 2)}"
        if executed_experiment_keys and exp_key in executed_experiment_keys:
            return RankedExperimentProposal(
                proposal=proposal,
                priority_score=0.0,
                is_approved=False,
                rejection_reason="Duplicate experiment: identical component, version, and load matrix already executed.",
            )

        # 5. Compute deterministic score components
        # A. SLA Boundary Proximity Score (0.0 to 1.0, weight 0.35)
        sla_target = workload.p95_latency_target_ms
        boundary_score = 0.2
        if simulation_results and sla_target:
            for s in simulation_results:
                # Check candidates that use this component
                p95 = s.p95_latency_ms
                if p95:
                    ratio = p95 / sla_target
                    # If p95 is between 75% and 125% of SLA target, highly decision-relevant
                    if 0.75 <= ratio <= 1.25:
                        boundary_score = max(boundary_score, 1.0 - abs(ratio - 1.0) * 2.0)
                    elif 0.5 <= ratio <= 2.0:
                        boundary_score = max(boundary_score, 0.5)

        # B. Hypothesis Separation / Near-Tie Score (0.0 to 1.0, weight 0.30)
        separation_score = 0.3
        if len(simulation_results) >= 2:
            latencies = [s.p95_latency_ms for s in simulation_results if s.p95_latency_ms]
            if len(latencies) >= 2:
                latencies.sort()
                margin = (latencies[1] - latencies[0]) / max(1.0, latencies[0])
                if margin < 0.20:
                    # Candidates are closely clustered; resolving model error directly affects ranking
                    separation_score = 1.0 - (margin / 0.20) * 0.5
                elif margin < 0.50:
                    separation_score = 0.5

        # C. Model Range & Calibration Status Score (0.0 to 1.0, weight 0.20)
        coverage_score = 0.4
        if self.registry:
            status, model, _ = self.registry.check_compatibility(comp, proposal.version, workload)
            if status == "OUT_OF_RANGE":
                coverage_score = 1.0
            elif status == "UNVALIDATED":
                coverage_score = 0.9
            elif status == "VALIDATED":
                if model:
                    if getattr(model, "validation_rmse_ms", 0.0) > 1.0:
                        coverage_score = 0.95  # High uncalibrated model uncertainty
                    elif getattr(model, "is_synthetic_fixture", False):
                        coverage_score = 0.50  # Synthetic baseline with acceptable calibration
                    else:
                        coverage_score = 0.20  # Real empirical measurement
                else:
                    coverage_score = 0.40

        # D. Execution Efficiency & Risk Score (0.0 to 1.0, weight 0.15)
        efficiency_score = 1.0
        if proposal.operational_risk == "HIGH":
            efficiency_score -= 0.5
        elif proposal.operational_risk == "MEDIUM":
            efficiency_score -= 0.2
        if proposal.expected_runtime_seconds > 30:
            efficiency_score -= 0.3
        efficiency_score = max(0.1, efficiency_score)

        # Total weighted score
        total_score = (
            0.35 * boundary_score +
            0.30 * separation_score +
            0.20 * coverage_score +
            0.15 * efficiency_score
        )
        total_score = round(max(0.0, min(1.0, total_score)), 3)

        return RankedExperimentProposal(
            proposal=proposal,
            priority_score=total_score,
            is_approved=True,
            score_components={
                "boundary_proximity": round(boundary_score, 3),
                "hypothesis_separation": round(separation_score, 3),
                "model_coverage": round(coverage_score, 3),
                "efficiency_risk": round(efficiency_score, 3),
            },
        )

    @classmethod
    def proposal_from_details(
        cls,
        details: BenchmarkProposalDetails,
        workload: Optional[WorkloadSpec] = None,
    ) -> ExperimentProposal:
        """Adapts legacy BenchmarkProposalDetails into typed ExperimentProposal."""
        comp = details.component_name.strip().lower()
        concurrency = details.target_concurrency or 16
        concurrencies = sorted(list({max(1, concurrency // 4), max(1, concurrency // 2), concurrency, concurrency * 2}))

        read_ratio = workload.read_ratio if workload else 1.0
        target_rps = workload.request_rate_rps if workload else 200.0

        return ExperimentProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:10]}",
            target_component=comp,
            version=details.version or "16-alpine",
            hypothesis=f"Measure {comp} service demand scaling under target concurrency {concurrency}",
            unknown_being_investigated=f"{comp} concurrency bottleneck and p95 latency under offered load",
            competing_hypotheses=[
                f"{comp} scales linearly up to {concurrency} concurrency",
                f"{comp} saturates before {concurrency} concurrency causing queue delay",
            ],
            concurrency_levels=concurrencies,
            read_ratio=read_ratio,
            target_rps=target_rps,
            replications=3,
            benchmark_framework="pgbench:16-select-only" if "postgres" in comp else "redis-benchmark:7-get",
            expected_information_gain="Resolve empirical p95 service demand and saturation inflection point.",
            decision_change_probability="MEDIUM",
            expected_runtime_seconds=12.0,
            estimated_cost_usd=0.0,
            operational_risk="LOW",
            authorization_level=AuthorizationLevel.OPERATOR_APPROVAL_REQUIRED,
            success_criteria="Container execution completed with parseable TPS and latency metrics",
            timeout_seconds=45,
        )
