"""
Stage 1: Feasibility Filtering.
Evaluates candidate architectures against hard constraints (p95 latency, throughput, budget)
and flags uncertainty boundary overlaps.
"""
from typing import List, Tuple, Dict, Any
from aads.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    FeasibilityStatus,
    FeasibilityCheck,
)


class FeasibilityFilter:
    """Filters architectures by mandatory SLA and cost constraints."""

    @staticmethod
    def evaluate_candidate(
        workload: WorkloadSpec,
        sim_result: SimulationResult,
    ) -> Tuple[FeasibilityStatus, List[FeasibilityCheck]]:
        checks: List[FeasibilityCheck] = []
        overall_status = FeasibilityStatus.FEASIBLE

        # 1. Check p95 Latency Constraint
        target_p95 = workload.p95_latency_target_ms
        pred_p95 = sim_result.p95_latency_ms
        uncertainty = sim_result.latency_uncertainty_p95_ms
        lower_bound, upper_bound = uncertainty

        if pred_p95 > target_p95:
            p95_status = FeasibilityStatus.INFEASIBLE
            exp = f"p95 latency ({pred_p95:.1f}ms) exceeds hard SLA limit ({target_p95:.1f}ms)."
        elif upper_bound > target_p95:
            p95_status = FeasibilityStatus.UNCERTAIN
            exp = f"Predicted p95 ({pred_p95:.1f}ms) is within SLA, but upper uncertainty bound ({upper_bound:.1f}ms) crosses threshold ({target_p95:.1f}ms)."
        else:
            p95_status = FeasibilityStatus.FEASIBLE
            exp = f"p95 latency ({pred_p95:.1f}ms) satisfies target SLA ({target_p95:.1f}ms)."

        checks.append(
            FeasibilityCheck(
                criterion="p95_latency",
                target_value=target_p95,
                predicted_value=pred_p95,
                uncertainty_range=uncertainty,
                status=p95_status,
                explanation=exp,
            )
        )

        # 2. Check Minimum Throughput Constraint
        min_tp = workload.min_throughput_rps
        pred_tp = sim_result.throughput_achieved_rps

        if pred_tp < min_tp * 0.95:  # more than 5% deficit
            tp_status = FeasibilityStatus.INFEASIBLE
            exp = f"Throughput ({pred_tp:.1f} rps) is below minimum threshold ({min_tp:.1f} rps)."
        elif pred_tp < min_tp:
            tp_status = FeasibilityStatus.UNCERTAIN
            exp = f"Throughput ({pred_tp:.1f} rps) borderline near threshold ({min_tp:.1f} rps)."
        else:
            tp_status = FeasibilityStatus.FEASIBLE
            exp = f"Achieved throughput ({pred_tp:.1f} rps) satisfies requirement ({min_tp:.1f} rps)."

        checks.append(
            FeasibilityCheck(
                criterion="min_throughput",
                target_value=min_tp,
                predicted_value=pred_tp,
                status=tp_status,
                explanation=exp,
            )
        )

        # 3. Check Monthly Budget Constraint
        max_budget = workload.max_monthly_budget_usd
        cost = sim_result.estimated_monthly_cost_usd

        if cost > max_budget:
            cost_status = FeasibilityStatus.INFEASIBLE
            exp = f"Monthly infrastructure cost () exceeds budget cap ()."
        elif cost > max_budget * 0.92:
            cost_status = FeasibilityStatus.UNCERTAIN
            exp = f"Cost () is within 8% of budget cap (), leaving limited headroom."
        else:
            cost_status = FeasibilityStatus.FEASIBLE
            exp = f"Cost () is within budget cap ()."

        checks.append(
            FeasibilityCheck(
                criterion="max_budget",
                target_value=max_budget,
                predicted_value=cost,
                status=cost_status,
                explanation=exp,
            )
        )

        # Determine overall candidate feasibility
        statuses = [c.status for c in checks]
        if FeasibilityStatus.INFEASIBLE in statuses:
            overall_status = FeasibilityStatus.INFEASIBLE
        elif FeasibilityStatus.UNCERTAIN in statuses:
            overall_status = FeasibilityStatus.UNCERTAIN
        else:
            overall_status = FeasibilityStatus.FEASIBLE

        return overall_status, checks
