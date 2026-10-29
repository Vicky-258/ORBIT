"""
Script to execute complete Phase 4D Active Experimentation evaluation and output structured artifacts.
"""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aads.evaluation.phase_4d_experimentation import (
    build_controlled_scenarios,
    run_strategy_1_baseline_no_experiments,
    run_strategy_2_fixed_experiments,
    run_strategy_3_deterministic_active,
    run_strategy_4_agent_active,
)


def main():
    scenarios = build_controlled_scenarios()
    results = {
        "evaluation_phase": "Phase 4D",
        "description": "Evidence-Driven Active Experimentation Comparative Evaluation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scenarios": [],
        "aggregate_summary": {},
    }

    strategy_stats = {
        "strategy_1_baseline_no_exp": {"correct": 0, "total": 0, "changes": 0, "exps": 0, "useful": 0, "redundant": 0, "duration": 0.0},
        "strategy_2_fixed_experiments": {"correct": 0, "total": 0, "changes": 0, "exps": 0, "useful": 0, "redundant": 0, "duration": 0.0},
        "strategy_3_deterministic_active": {"correct": 0, "total": 0, "changes": 0, "exps": 0, "useful": 0, "redundant": 0, "duration": 0.0},
        "strategy_4_agent_active": {"correct": 0, "total": 0, "changes": 0, "exps": 0, "useful": 0, "redundant": 0, "duration": 0.0, "llm_calls": 0, "tokens": 0, "cost": 0.0},
    }

    for s in scenarios:
        s_data = {
            "scenario_id": s.scenario_id,
            "scenario_name": s.scenario_name,
            "sla_p95_target_ms": s.workload.p95_latency_target_ms,
            "ground_truth_winner": s.ground_truth_winner,
            "requires_experiment": s.requires_experiment_to_detect_violation,
            "strategy_results": {},
        }

        # Run all 4 strategies
        r1 = run_strategy_1_baseline_no_experiments(s)
        r2 = run_strategy_2_fixed_experiments(s)
        r3 = run_strategy_3_deterministic_active(s)
        r4 = run_strategy_4_agent_active(s, mode="offline")

        for r, strat_key in [
            (r1, "strategy_1_baseline_no_exp"),
            (r2, "strategy_2_fixed_experiments"),
            (r3, "strategy_3_deterministic_active"),
            (r4, "strategy_4_agent_active"),
        ]:
            s_data["strategy_results"][strat_key] = r.model_dump()
            st = strategy_stats[strat_key]
            st["total"] += 1
            if r.correct_under_ground_truth:
                st["correct"] += 1
            if r.recommendation_changed:
                st["changes"] += 1
            st["exps"] += r.experiments_executed_count
            st["useful"] += r.useful_experiments_count
            st["redundant"] += r.redundant_experiments_count
            st["duration"] += r.execution_duration_seconds
            if strat_key == "strategy_4_agent_active":
                st["llm_calls"] += r.llm_call_count
                st["tokens"] += r.llm_tokens
                st["cost"] += r.llm_cost_usd

        results["scenarios"].append(s_data)

    # Compute summary rates
    for k, v in strategy_stats.items():
        v["accuracy_rate"] = round(v["correct"] / max(1, v["total"]), 3)
        v["mean_duration_seconds"] = round(v["duration"] / max(1, v["total"]), 3)
        v["total_experiments"] = v["exps"]
        v["useful_experiments"] = v["useful"]
        v["redundant_experiments"] = v["redundant"]

    results["aggregate_summary"] = strategy_stats

    # Write results JSON
    out_path = Path("data/evaluations/phase_4d_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved evaluation results to {out_path}")

    # Write reproducibility manifest
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True).stdout.strip()

    manifest = {
        "metadata": {
            "evaluation_phase": "Phase 4D",
            "description": "Evidence-Driven Active Experimentation Reproducibility Manifest",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "git_branch": branch,
            "python_version": "3.12.12",
        },
        "scenarios_evaluated": [s.scenario_id for s in scenarios],
        "strategies_evaluated": list(strategy_stats.keys()),
        "aggregate_accuracy": {k: v["accuracy_rate"] for k, v in strategy_stats.items()},
        "total_experiments_by_strategy": {k: v["total_experiments"] for k, v in strategy_stats.items()},
        "redundant_experiments_by_strategy": {k: v["redundant_experiments"] for k, v in strategy_stats.items()},
        "reproduction_commands": [
            ".venv/bin/python3 scripts/run_phase_4d_evaluation.py",
            ".venv/bin/pytest -v tests/test_phase_4d_active_experimentation.py",
        ],
    }

    manifest_path = Path("data/evaluations/phase_4d_reproducibility_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved reproducibility manifest to {manifest_path}")


if __name__ == "__main__":
    main()
