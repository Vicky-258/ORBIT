#!/usr/bin/env python3
"""
Reproducible Demo Scenarios Runner for AADS Phase 5.0.
Executes the three canonical demonstration scenarios:
1. Scenario 1: Read-Heavy E-Commerce (Caching Architecture)
2. Scenario 2: Write-Heavy Transactional (Database Trade-offs)
3. Scenario 3: Background Worker Processing (Asynchronous Queue Architecture)
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

# Ensure workspace root is in sys.path
workspace_root = Path(__file__).resolve().parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from aads.agent.orchestrator import AADSOrchestrator
from aads.core.demo_response_builder import build_demo_workflow_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aads.demo_scenarios")

SCENARIOS = [
    {
        "id": "scenario_1_ecommerce",
        "title": "Scenario 1: Read-Heavy E-Commerce API",
        "prompt": (
            "Design a backend for an e-commerce API expecting approximately 500 requests per second. "
            "The p95 latency must remain below 100 ms, the monthly infrastructure budget is $250, "
            "and the system should support read-heavy traffic with occasional writes."
        ),
        "expected_winner_id": "arch_b_cached",
        "expected_winner_name": "Architecture B — Cached Reads (API → Redis → PostgreSQL)",
        "expected_workload_app_type": "ecommerce",
        "purpose": "Demonstrates caching architecture investigation under high read ratios.",
    },
    {
        "id": "scenario_2_transactional",
        "title": "Scenario 2: Write-Heavy Transactional Workload",
        "prompt": (
            "Write-heavy transactional workload with 150 RPS, 40% reads and 60% writes, "
            "p95 latency under 150 ms, monthly budget $300"
        ),
        "expected_winner_id": "arch_a_simple",
        "expected_winner_name": "Architecture A — Simple (API → PostgreSQL)",
        "expected_workload_app_type": "transactional",
        "purpose": "Demonstrates database direct transactional trade-offs where cache overhead is unjustified.",
    },
    {
        "id": "scenario_3_background_worker",
        "title": "Scenario 3: Background Worker Processing",
        "prompt": (
            "Background processing workload: 300 RPS incoming, background tasks can be processed asynchronously, "
            "p95 API response target 100 ms, budget $350/month"
        ),
        "expected_winner_id": "arch_c_async",
        "expected_winner_name": "Architecture C — Async Processing (API → Queue → Worker → PostgreSQL)",
        "expected_workload_app_type": "background_processing",
        "purpose": "Demonstrates asynchronous message queue & worker architecture for lowest client response latency.",
    },
]


def run_scenario(scenario: Dict[str, Any], orchestrator: AADSOrchestrator) -> Dict[str, Any]:
    logger.info("=" * 70)
    logger.info("RUNNING %s", scenario["title"])
    logger.info("Prompt: %s", scenario["prompt"])
    logger.info("Purpose: %s", scenario["purpose"])

    state = orchestrator.run(
        request_text=scenario["prompt"],
        simulation_duration_seconds=5.0,
        max_investigation_rounds=3,
        include_unsupported=False,
    )
    demo_resp = build_demo_workflow_response(state)

    winner_id = demo_resp.recommendation.winner_architecture_id
    winner_name = demo_resp.recommendation.winner_architecture_name
    is_conclusive = demo_resp.recommendation.is_conclusive

    logger.info("--- RESULTS ---")
    logger.info("Workflow Status: %s", demo_resp.workflow_status)
    logger.info("Execution Mode: %s", demo_resp.execution_mode)
    logger.info("App Type: %s", demo_resp.request_summary.app_type)
    logger.info("Offered Load: %.1f RPS", demo_resp.request_summary.request_rate_rps)
    logger.info("Traffic Mix: %.0f%% Read / %.0f%% Write", demo_resp.request_summary.read_ratio * 100, demo_resp.request_summary.write_ratio * 100)
    logger.info("Investigation Rounds: %d", demo_resp.investigation_summary.investigation_rounds)
    logger.info("Winning Architecture: %s (ID: %s)", winner_name, winner_id)
    logger.info("Executive Summary: %s", demo_resp.recommendation.executive_summary)

    logger.info("Candidate Architecture Comparison:")
    for comp in demo_resp.architecture_comparison:
        logger.info(
            "  [%s] p95=%.2f ms (Bounds: [%.1f, %.1f] ms) | Cost=$%.2f/mo | SLA: %s | Evidence: %s",
            comp.architecture_id,
            comp.p95_latency_ms,
            comp.uncertainty_bounds_p95_ms[0],
            comp.uncertainty_bounds_p95_ms[1],
            comp.estimated_monthly_cost_usd,
            comp.sla_result,
            comp.evidence_status,
        )

    # Verification assertions
    assert is_conclusive, f"Scenario {scenario['id']} did not reach a conclusive recommendation"
    assert winner_id == scenario["expected_winner_id"], (
        f"Scenario {scenario['id']}: expected winner {scenario['expected_winner_id']}, got {winner_id}"
    )

    logger.info("✔ %s PASSED (Winner: %s)", scenario["title"], winner_id)
    return demo_resp.model_dump()


def main():
    orchestrator = AADSOrchestrator()
    all_results = {}
    passed = 0

    for sc in SCENARIOS:
        try:
            res = run_scenario(sc, orchestrator)
            all_results[sc["id"]] = res
            passed += 1
        except Exception as exc:
            logger.error("FAILED %s: %s", sc["title"], exc, exc_info=True)

    logger.info("=" * 70)
    logger.info("SCENARIO VERIFICATION COMPLETE: %d / %d PASSED", passed, len(SCENARIOS))

    if passed == len(SCENARIOS):
        print("\nALL 3 DEMO SCENARIOS VERIFIED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print(f"\nFAILURE: {len(SCENARIOS) - passed} scenarios failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
