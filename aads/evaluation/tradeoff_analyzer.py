"""
Stage 2: Trade-off Comparison and Multi-Objective Scoring.
Computes normalized dimension scores, detects Pareto dominance, and ranks candidates.
"""
from typing import List, Dict, Any, Optional, Tuple
from aads.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    CandidateEvaluation,
    FeasibilityStatus,
    FeasibilityCheck,
)


class TradeoffAnalyzer:
    """Multi-objective trade-off comparison and Pareto analysis."""

    @staticmethod
    def analyze_candidates(
        workload: WorkloadSpec,
        sim_results: List[SimulationResult],
        feasibility_map: Dict[str, Tuple[FeasibilityStatus, List[FeasibilityCheck]]],
    ) -> List[CandidateEvaluation]:
        if not sim_results:
            return []

        # Find min/max ranges for normalization
        costs = [r.estimated_monthly_cost_usd for r in sim_results]
        latencies = [r.p95_latency_ms for r in sim_results]
        throughputs = [r.throughput_achieved_rps for r in sim_results]

        min_cost, max_cost = min(costs), max(costs)
        min_lat, max_lat = min(latencies), max(latencies)
        min_tp, max_tp = min(throughputs), max(throughputs)

        weights = workload.soft_preferences
        cost_w = weights.get("cost", 0.35)
        lat_w = weights.get("latency", 0.45)
        simplicity_w = weights.get("simplicity", 0.20)

        # Normalize weights to sum to 1.0
        tot_w = cost_w + lat_w + simplicity_w
        if tot_w > 0:
            cost_w /= tot_w
            lat_w /= tot_w
            simplicity_w /= tot_w

        evaluations: List[CandidateEvaluation] = []

        for res in sim_results:
            f_status, checks = feasibility_map[res.architecture_id]

            # 1. Normalized Cost Score (cheaper = higher score)
            cost_range = max(1.0, max_cost - min_cost)
            cost_score = 1.0 - ((res.estimated_monthly_cost_usd - min_cost) / cost_range)

            # 2. Normalized Latency Score (lower p95 = higher score)
            lat_range = max(0.5, max_lat - min_lat)
            lat_score = 1.0 - ((res.p95_latency_ms - min_lat) / lat_range)

            # 3. Normalized Throughput Score (higher throughput = higher score)
            tp_range = max(10.0, max_tp - min_tp)
            tp_score = ((res.throughput_achieved_rps - min_tp) / tp_range) if max_tp > min_tp else 1.0

            # 4. Complexity Score based on architecture topology
            if "arch_a" in res.architecture_id:
                comp_score = 1.0  # simple
            elif "arch_b" in res.architecture_id:
                comp_score = 0.7  # moderate
            else:
                comp_score = 0.4  # higher complexity (queue + worker)

            # Weighted overall score
            overall_score = (cost_w * cost_score) + (lat_w * lat_score) + (simplicity_w * comp_score)

            # Penalize infeasible options heavily so they cannot win
            if f_status == FeasibilityStatus.INFEASIBLE:
                overall_score *= 0.1
            elif f_status == FeasibilityStatus.UNCERTAIN:
                overall_score *= 0.85

            evaluations.append(
                CandidateEvaluation(
                    architecture_id=res.architecture_id,
                    architecture_name=res.architecture_name,
                    feasibility_status=f_status,
                    checks=checks,
                    cost_score=round(cost_score, 3),
                    latency_score=round(lat_score, 3),
                    throughput_score=round(tp_score, 3),
                    complexity_score=round(comp_score, 3),
                    overall_score=round(overall_score, 3),
                    is_pareto_dominated=False,
                )
            )

        # 5. Detect Pareto Dominance
        for i, a in enumerate(evaluations):
            for j, b in enumerate(evaluations):
                if i == j:
                    continue
                better_or_equal = (
                    b.cost_score >= a.cost_score
                    and b.latency_score >= a.latency_score
                    and b.complexity_score >= a.complexity_score
                )
                strictly_better = (
                    b.cost_score > a.cost_score
                    or b.latency_score > a.latency_score
                    or b.complexity_score > a.complexity_score
                )
                if better_or_equal and strictly_better and (b.feasibility_status != FeasibilityStatus.INFEASIBLE):
                    a.is_pareto_dominated = True
                    a.dominated_by = b.architecture_name

        evaluations.sort(key=lambda e: e.overall_score, reverse=True)
        return evaluations
