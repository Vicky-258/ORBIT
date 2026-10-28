"""
AADS Phase 4C: Unified Evaluation Runner.
Executes scenarios across Strategy A (Fixed), Strategy B (Deterministic Adaptive),
and Strategy C (LLM Adaptive), computing comparative metrics with complete provenance.
"""
import os
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from aads.registry.component_registry import ComponentRegistry
from aads.evaluation.scenarios import (
    EvaluationScenario,
    get_scenarios,
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
)
from aads.evaluation.strategies import (
    run_strategy_a_fixed_pipeline,
    run_strategy_b_deterministic_adaptive,
    run_strategy_c_llm_adaptive,
    StrategyExecutionResult,
)
from aads.evaluation.metrics import (
    compute_metrics,
    DecisionQualityMetrics,
)


class StrategyAggregateSummary(BaseModel):
    """Aggregate performance metrics for a strategy across a scenario suite."""
    strategy_name: str
    sample_size: int
    mean_constraint_correctness: float
    hard_constraint_satisfaction_rate: float
    infeasible_detection_rate: float
    top_choice_agreement_rate: float
    mean_feasible_jaccard: float
    mean_regret: float
    total_investigation_rounds: int
    mean_investigation_rounds: float
    total_tools_proposed: int
    total_tools_executed: int
    policy_rejection_rate: float
    mean_decision_latency_ms: float
    fallback_rate: float
    uncertainty_audit_rate: float
    coverage_audit_rate: float


class EvaluationSuiteResult(BaseModel):
    """Complete serialized report of an evaluation run."""
    suite_name: str
    mode: str
    timestamp: str
    git_commit: str
    scenarios_evaluated_count: int
    aggregate_summaries: Dict[str, StrategyAggregateSummary]
    detailed_metrics: List[Dict[str, Any]]
    execution_results: List[Dict[str, Any]]


def _get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "unknown"


def run_evaluation_suite(
    scenarios: List[EvaluationScenario],
    suite_name: str = "default",
    mode: str = "offline",
    output_path: Optional[Path] = None,
) -> EvaluationSuiteResult:
    """
    Executes the comparative evaluation across Strategy A, B, and C.
    """
    reg = ComponentRegistry()
    reg.seed_baseline_data()

    all_metrics: List[DecisionQualityMetrics] = []
    all_executions: List[StrategyExecutionResult] = []

    for scenario in scenarios:
        # Run Strategy A
        res_a = run_strategy_a_fixed_pipeline(scenario, registry=reg)
        m_a = compute_metrics(scenario, res_a)
        all_executions.append(res_a)
        all_metrics.append(m_a)

        # Run Strategy B
        res_b = run_strategy_b_deterministic_adaptive(scenario, registry=reg)
        m_b = compute_metrics(scenario, res_b)
        all_executions.append(res_b)
        all_metrics.append(m_b)

        # Run Strategy C
        res_c = run_strategy_c_llm_adaptive(scenario, registry=reg, mode=mode)
        m_c = compute_metrics(scenario, res_c)
        all_executions.append(res_c)
        all_metrics.append(m_c)

    # Compute aggregates
    aggregates: Dict[str, StrategyAggregateSummary] = {}
    strategy_names = ["strategy_a_fixed", "strategy_b_deterministic", "strategy_c_llm"]

    for sname in strategy_names:
        s_metrics = [m for m in all_metrics if m.strategy_name == sname]
        n = len(s_metrics)
        if n == 0:
            continue

        c_corr = round(sum(m.constraint_correctness_score for m in s_metrics) / n, 3)
        hard_sat = round(sum(1 for m in s_metrics if m.hard_constraints_satisfied) / n, 3)
        inf_det = round(sum(1 for m in s_metrics if m.infeasible_workload_detected) / n, 3)
        top_agree = round(sum(1 for m in s_metrics if m.top_choice_agreement) / n, 3)
        jaccard = round(sum(m.feasible_set_jaccard for m in s_metrics) / n, 3)
        regret = round(sum(m.regret_vs_reference for m in s_metrics) / n, 3)
        tot_rounds = sum(m.investigation_rounds for m in s_metrics)
        mean_rounds = round(tot_rounds / n, 2)
        tot_prop = sum(m.tools_proposed for m in s_metrics)
        tot_exec = sum(m.tools_executed for m in s_metrics)
        tot_rej = sum(m.tools_rejected for m in s_metrics)
        rej_rate = round(tot_rej / tot_prop, 3) if tot_prop > 0 else 0.0
        mean_lat = round(sum(m.decision_latency_ms for m in s_metrics) / n, 1)
        fallback_rate = round(sum(1 for m in s_metrics if m.fallback_used) / n, 3)
        unc_rate = round(sum(1 for m in s_metrics if m.uncertainty_reduced) / n, 3)
        cov_rate = round(sum(1 for m in s_metrics if m.coverage_gap_resolved) / n, 3)

        aggregates[sname] = StrategyAggregateSummary(
            strategy_name=sname,
            sample_size=n,
            mean_constraint_correctness=c_corr,
            hard_constraint_satisfaction_rate=hard_sat,
            infeasible_detection_rate=inf_det,
            top_choice_agreement_rate=top_agree,
            mean_feasible_jaccard=jaccard,
            mean_regret=regret,
            total_investigation_rounds=tot_rounds,
            mean_investigation_rounds=mean_rounds,
            total_tools_proposed=tot_prop,
            total_tools_executed=tot_exec,
            policy_rejection_rate=rej_rate,
            mean_decision_latency_ms=mean_lat,
            fallback_rate=fallback_rate,
            uncertainty_audit_rate=unc_rate,
            coverage_audit_rate=cov_rate,
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    suite_result = EvaluationSuiteResult(
        suite_name=suite_name,
        mode=mode,
        timestamp=now_iso,
        git_commit=_get_git_commit(),
        scenarios_evaluated_count=len(scenarios),
        aggregate_summaries=aggregates,
        detailed_metrics=[m.model_dump() for m in all_metrics],
        execution_results=[e.model_dump() for e in all_executions],
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(suite_result.model_dump_json(indent=2))

    return suite_result
