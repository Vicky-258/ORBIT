"""
ORBIT Phase 4C: CLI Evaluation Harness.
Usage:
    python -m orbit.evaluation.run --suite default --mode offline
    python -m orbit.evaluation.run --suite heldout --mode offline
"""
import argparse
import sys
from pathlib import Path

from orbit.evaluation.scenarios import (
    PILOT_SCENARIOS,
    DEV_SCENARIOS,
    HELDOUT_SCENARIOS,
    get_scenarios,
)
from orbit.evaluation.runner import run_evaluation_suite


def print_comparison_table(suite_res) -> None:
    print("\n=========================================================================================")
    print(f"  ORBIT Phase 4C Evaluation Suite: {suite_res.suite_name.upper()} (Mode: {suite_res.mode.upper()})")
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
    parser.add_argument("--suite", choices=["default", "pilot", "dev", "heldout", "all"], default="default", help="Scenario suite to evaluate")
    parser.add_argument("--mode", choices=["offline", "live"], default="offline", help="Evaluation execution mode")
    parser.add_argument("--live-llm", action="store_true", help="Explicit opt-in to execute genuine live LLM calls")
    parser.add_argument("--max-calls", type=int, default=50, help="Maximum live LLM calls budget")
    parser.add_argument("--max-cost", type=float, default=5.0, help="Maximum estimated cost in USD")
    parser.add_argument("--calls-output", type=str, default="data/evaluations/phase_4c2_live_calls.jsonl", help="JSONL path for per-call live telemetry")
    parser.add_argument("--output", type=str, default=None, help="Output report path")

    args = parser.parse_args()

    mode = "live" if (args.live_llm or args.mode == "live") else "offline"

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path("data/evaluations/phase_4c2_results.json") if mode == "live" else Path("data/evaluations/phase_4c_results.json")

    calls_path = Path(args.calls_output) if mode == "live" else None

    if args.suite == "pilot":
        scenarios = PILOT_SCENARIOS
        suite_label = "pilot"
    elif args.suite in ("default", "dev"):
        scenarios = DEV_SCENARIOS
        suite_label = "development"
    elif args.suite == "heldout":
        scenarios = HELDOUT_SCENARIOS
        suite_label = "held_out"
    else:
        scenarios = DEV_SCENARIOS + HELDOUT_SCENARIOS
        suite_label = "full_suite"

    print(f"Running Phase 4C/4C.2 evaluation on '{suite_label}' ({len(scenarios)} scenarios) in '{mode}' mode...")
    suite_res = run_evaluation_suite(
        scenarios=scenarios,
        suite_name=suite_label,
        mode=mode,
        output_path=out_path,
        live_calls_path=calls_path,
        max_llm_calls=args.max_calls,
        max_cost_usd=args.max_cost,
        fail_closed=(mode == "live"),
    )

    print_comparison_table(suite_res)
    if suite_res.live_llm_calls_count > 0:
        print(f"  Live LLM Telemetry:")
        print(f"    - Total Verified Live Calls: {suite_res.live_llm_calls_count}")
        print(f"    - Total Tokens Consumed:     {suite_res.total_llm_tokens}")
        print(f"    - Total Estimated Cost:      ${suite_res.total_llm_cost_usd:.5f}")
        if calls_path:
            print(f"    - Call Telemetry Streamed to: {calls_path.resolve()}")
    print(f"Structured evaluation results saved to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
