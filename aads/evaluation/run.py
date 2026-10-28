"""
AADS Phase 4C: CLI Evaluation Harness.
Usage:
    python -m aads.evaluation.run --suite default --mode offline
    python -m aads.evaluation.run --suite heldout --mode offline
"""
import argparse
import sys
from pathlib import Path

from aads.evaluation.scenarios import (
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
    get_scenarios,
)
from aads.evaluation.runner import run_evaluation_suite


def print_comparison_table(suite_res) -> None:
    print("\n=========================================================================================")
    print(f"  AADS Phase 4C Evaluation Suite: {suite_res.suite_name.upper()} (Mode: {suite_res.mode.upper()})")
    print(f"  Evaluated Scenarios: {suite_res.scenarios_evaluated_count} | Git Commit: {suite_res.git_commit}")
    print("=========================================================================================")
    
    headers = [
        "Strategy",
        "Constraint Correct",
        "Hard Sat %",
        "Infeas Det %",
        "Top Agreement",
        "Feas Jaccard",
        "Mean Regret",
        "Mean Rounds",
        "Rejection %",
        "Mean Lat (ms)",
    ]
    
    row_fmt = "| {:<24} | {:<18} | {:<10} | {:<12} | {:<13} | {:<12} | {:<11} | {:<11} | {:<11} | {:<13} |"
    sep = "+" + "+".join(["-" * (len(h) + 2) for h in [
        "Strategy                ",
        "Constraint Correct",
        "Hard Sat %",
        "Infeas Det %",
        "Top Agreement",
        "Feas Jaccard",
        "Mean Regret",
        "Mean Rounds",
        "Rejection %",
        "Mean Lat (ms)",
    ]]) + "+"
    
    print(row_fmt.format(*headers))
    print("|--------------------------|--------------------|------------|--------------|---------------|--------------|-------------|-------------|-------------|---------------|")

    for sname, agg in suite_res.aggregate_summaries.items():
        name_display = {
            "strategy_a_fixed": "Strategy A (Fixed)",
            "strategy_b_deterministic": "Strategy B (Det Adapt)",
            "strategy_c_llm": "Strategy C (LLM Adapt)",
        }.get(sname, sname)

        print(row_fmt.format(
            name_display,
            f"{agg.mean_constraint_correctness:.1%}",
            f"{agg.hard_constraint_satisfaction_rate:.1%}",
            f"{agg.infeasible_detection_rate:.1%}",
            f"{agg.top_choice_agreement_rate:.1%}",
            f"{agg.mean_feasible_jaccard:.2f}",
            f"{agg.mean_regret:.3f}",
            f"{agg.mean_investigation_rounds:.1f}",
            f"{agg.policy_rejection_rate:.1%}",
            f"{agg.mean_decision_latency_ms:.1f}",
        ))
    print("=========================================================================================\n")


def main():
    parser = argparse.ArgumentParser(description="AADS Phase 4C Comparative Evaluation Runner")
    parser.add_argument("--suite", choices=["default", "dev", "heldout", "all"], default="default", help="Scenario suite to evaluate")
    parser.add_argument("--mode", choices=["offline", "live"], default="offline", help="Evaluation execution mode")
    parser.add_argument("--output", type=str, default="data/evaluations/phase_4c_results.json", help="Output report path")

    args = parser.parse_args()

    if args.suite in ("default", "dev"):
        scenarios = DEV_SCENARIOS
        suite_label = "development"
    elif args.suite == "heldout":
        scenarios = HELDOUT_SCENARIOS
        suite_label = "held_out"
    else:
        scenarios = DEV_SCENARIOS + HELDOUT_SCENARIOS
        suite_label = "full_suite"

    print(f"Running Phase 4C evaluation on '{suite_label}' ({len(scenarios)} scenarios) in '{args.mode}' mode...")
    out_path = Path(args.output)
    suite_res = run_evaluation_suite(
        scenarios=scenarios,
        suite_name=suite_label,
        mode=args.mode,
        output_path=out_path,
    )

    print_comparison_table(suite_res)
    print(f"Structured evaluation results saved to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
