"""
CLI Demonstration Script for AADS.
Executes the end-to-end reproducible architecture evaluation workflow:
1. Workload Specification & Assumptions
2. Candidate Architecture Generation
3. Component Registry Check & Model Discovery
4. Controlled Benchmarking & Model Calibration (Synthetic or Docker)
5. SimPy Discrete-Event Simulation & Tail-Latency Estimation
6. Multi-Objective Feasibility Filtering, Trade-off Analysis & Recommendation

Usage:
  python run_demo.py [OPTIONS]

Examples:
  python run_demo.py --seed 42 --mode synthetic
  python run_demo.py --rps 750 --budget 300
  python run_demo.py --json-output demo_results.json
"""
import argparse
import json
import random
import sys
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List

from aads.core.schemas import WorkloadSpec, FeasibilityStatus
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.registry.component_registry import ComponentRegistry
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.experiment_manager import AdaptiveExperimentManager
from aads.modeling.model_trainer import ModelTrainer
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender


def print_banner(text: str, char: str = "="):
    line = char * 74
    print(f"\n{line}")
    print(f"  {text}")
    print(f"{line}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="AADS: Agentic Architecture Design & Simulation Technical Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--seed", type=int, default=42, help="Fixed random seed for deterministic reproduction")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "docker", "auto"],
        default="synthetic",
        help="Benchmark execution mode (synthetic: fast offline fixtures; docker: live container benchmark; auto: detect Docker)",
    )
    parser.add_argument("--rps", type=float, default=500.0, help="Offered steady-state request rate (req/s)")
    parser.add_argument("--peak-factor", type=float, default=2.0, help="Peak load multiplier for burst headroom")
    parser.add_argument("--budget", type=float, default=250.0, help="Maximum monthly infrastructure budget (USD)")
    parser.add_argument("--p95-target", type=float, default=50.0, help="Maximum allowable p95 latency target (ms)")
    parser.add_argument("--min-throughput", type=float, default=450.0, help="Minimum acceptable throughput target (req/s)")
    parser.add_argument("--duration", type=float, default=5.0, help="SimPy simulation duration per candidate (seconds)")
    parser.add_argument("--json-output", type=str, default=None, help="Optional file path to export structured JSON results")
    parser.add_argument("--prompt", type=str, default=None, help="Natural-language architecture request to run through LangGraph agent")
    parser.add_argument("--verify-llm", action="store_true", help="Run explicit opt-in live LLM provider verification and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if getattr(args, "verify_llm", False):
        from aads.agent.provider import verify_live_llm
        print_banner("🔍 AADS: Opt-In Live LLM Connectivity Verification", "=")
        print("  Notice: Initiating external provider API request. May incur minor token charges.\n")
        res = verify_live_llm()
        print(f"  • Status   : {res.get('status')}")
        print(f"  • Provider : {res.get('provider')} ({res.get('model_name')})")
        print(f"  • Latency  : {res.get('latency_seconds', 0.0):.3f}s")
        if res.get("success"):
            print("\n  ✅ SUCCESS: Live LLM connectivity verified successfully!")
            for k, v in res.get("extracted_fields", {}).items():
                print(f"    - {k:22s}: {v}")
            sys.exit(0)
        else:
            print("\n  ❌ VERIFICATION FAILED:")
            print(f"    • Error Details : {res.get('error_message')}")
            if res.get("instructions"):
                print(f"    • Tip           : {res.get('instructions')}")
            sys.exit(1 if res.get("status") == "MISSING_CREDENTIALS" else 2)

    # 0. Global Seed Initialization
    random.seed(args.seed)
    np.random.seed(args.seed)

    if args.prompt:
        print_banner("🤖 AADS: LangChain & LangGraph Architecture Agent", "=")
        from aads.agent.orchestrator import AADSOrchestrator
        from aads.agent.provider import LLMProviderManager

        prov_mgr = LLMProviderManager()
        summary = prov_mgr.get_status_summary()
        print(f"  • User Prompt      : \"{args.prompt}\"")
        print(f"  • Execution Mode   : {summary['execution_mode']} ({summary['provider']}:{summary['model_name']})")
        if summary["is_fallback"]:
            print(f"  ℹ Mode Note        : {summary['reason']}")
        print(f"  • Random Seed      : {args.seed} (Deterministic Reproducibility Enabled)")
        print(f"  • SimPy Duration   : {args.duration}s per candidate\n")

        orch = AADSOrchestrator(provider_mgr=prov_mgr)
        state = orch.run(
            request_text=args.prompt,
            auto_benchmark_missing=True,
            force_synthetic=(args.mode != "docker"),
            simulation_duration_seconds=args.duration,
            random_seed=args.seed,
            include_async=True,
            include_unsupported=True,
        )

        status = state.get("workflow_status")
        print_banner(f"Workflow Status: {status}", "-")

        if state.get("clarification_questions") and not state.get("workload_spec"):
            print("  ⚠️ Clarifying Questions Required:")
            for q in state["clarification_questions"]:
                print(f"    • {q}")
            return

        if state.get("clarification_questions"):
            print("  ℹ️ Clarification Inquiries (Non-Blocking Assumptions Inferred):")
            for q in state["clarification_questions"]:
                print(f"    • {q}")
            print()

        workload = state.get("workload_spec")
        if workload:
            print("  Extracted Workload Specification:")
            print(f"    • Domain       : {workload.app_type}")
            print(f"    • Offered Load : {workload.request_rate_rps:.1f} req/s (Peak: {workload.request_rate_rps * workload.peak_load_factor:.1f} req/s)")
            print(f"    • Mix          : {workload.read_ratio:.0%} Reads / {workload.write_ratio:.0%} Writes")
            print(f"    • SLA Target   : p95 <= {workload.p95_latency_target_ms:.1f} ms | Min Throughput >= {workload.min_throughput_rps:.1f} req/s")
            print(f"    • Budget Cap   : ${workload.max_monthly_budget_usd:.2f} / month")

        sim_res = state.get("simulation_results", [])
        if sim_res:
            print_banner("SimPy Simulation Results", "-")
            for r in sim_res:
                hit_str = f"Cache Hit: {r.cache_hit_rate:.1%}" if r.cache_hit_rate is not None else "No Cache"
                ci_str = f"[{r.latency_uncertainty_p95_ms[0]:.2f}, {r.latency_uncertainty_p95_ms[1]:.2f}] ms"
                print(f"  📊 {r.architecture_name}")
                print(f"     Throughput : {r.throughput_achieved_rps:.1f} req/s | p95 Latency: {r.p95_latency_ms:.2f} ms (95% CI: {ci_str})")
                print(f"     Bottleneck : {r.bottleneck_component.upper():5s} | Utilizations: {r.component_utilizations} | {hit_str}")
                print(f"     Cost       : ${r.estimated_monthly_cost_usd:.2f} / month\n")

        trace = state.get("investigation_trace", [])
        if trace:
            print_banner("Agentic Investigation Trace & Decision History", "-")
            for t in trace:
                r_num = t.get("round", 1)
                action = t.get("action", "")
                target = t.get("target") or "all"
                verdict = t.get("policy_verdict", "APPROVED")
                tool = t.get("tool_invoked") or "None"
                elapsed = t.get("duration_seconds", 0.0)
                reason = t.get("reason", "")
                summary = t.get("tool_output", {}).get("summary", "")
                stop_reason = t.get("stop_reason")

                print(f"  Round {r_num}: Action={action} (Target: {target})")
                print(f"    • Policy Verdict : {verdict}")
                print(f"    • Agent Rationale: {reason}")
                if tool != "None":
                    print(f"    • Tool Executed  : {tool} ({elapsed:.3f}s)")
                    if summary:
                        print(f"    • Tool Outcome   : {summary}")
                if stop_reason:
                    print(f"    • Stop Reason    : {stop_reason}")
                print()

        rec = state.get("recommendation")
        if rec:
            print_banner(f"🏆 Recommendation: {rec.selected_architecture_name}", "=")
            exp_src = getattr(rec, "explanation_source", "deterministic") or "deterministic"
            print(f"  Status             : {rec.status.value}")
            label = 'LLM-Backed Reasoning' if exp_src == 'llm' else 'Deterministic Baseline'
            print(f"  Explanation Source : {exp_src.upper()} ({label})\n")
            print(f"  Executive Summary:\n    {rec.executive_summary}\n")
            print("  Decision Rationale:")
            for r in rec.rationale:
                print(f"    ✔ {r}")
            print("\n  Trade-offs & Identified Disadvantages:")
            for t in rec.trade_offs_and_risks:
                print(f"    ⚠ {t}")
            if rec.recommended_next_experiment:
                print(f"\n  Recommended Next Experiment:\n    🔬 {rec.recommended_next_experiment}")

        if args.json_output:
            import json
            from datetime import datetime, timezone
            export_data = {
                "metadata": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "seed": args.seed,
                    "mode": state.get("execution_mode"),
                    "prompt": args.prompt,
                },
                "workflow_status": state.get("workflow_status"),
                "workload": workload.model_dump() if workload else None,
                "candidates": [c.model_dump() for c in state.get("candidate_architectures", [])],
                "simulation_results": [s.model_dump() for s in sim_res],
                "recommendation": rec.model_dump() if rec else None,
                "investigation_trace": trace,
                "benchmark_proposals": state.get("benchmark_proposals", []),
            }
            with open(args.json_output, "w") as f:
                json.dump(export_data, f, indent=2)
            print(f"\n  💾 Results exported to: {args.json_output}")
        return

    print_banner("⚡ AADS: Agentic Architecture Design & Simulation POC", "=")
    print(f"  • Execution Mode   : {args.mode.upper()}")
    print(f"  • Random Seed      : {args.seed} (Deterministic Reproducibility Enabled)")
    print(f"  • SimPy Duration   : {args.duration}s per candidate")

    # 1. User Workload Specification
    print_banner("[Step 1] Initializing Workload & Requirements", "-")
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=args.rps,
        peak_load_factor=args.peak_factor,
        read_ratio=0.90,
        write_ratio=0.10,
        dataset_records=1_000_000,
        p95_latency_target_ms=args.p95_target,
        min_throughput_rps=args.min_throughput,
        max_monthly_budget_usd=args.budget,
        cache_assumed_hit_rate=0.85,
        soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
    )
    print(f"  • Domain / Application : {workload.app_type}")
    print(f"  • Steady-State Load    : {workload.request_rate_rps:.1f} req/s")
    print(f"  • Peak Burst Load      : {workload.request_rate_rps * workload.peak_load_factor:.1f} req/s ({workload.peak_load_factor:.1f}x headroom)")
    print(f"  • Workload Mix         : {workload.read_ratio:.0%} Reads / {workload.write_ratio:.0%} Writes")
    print(f"  • Hard SLA Target      : p95 latency <= {workload.p95_latency_target_ms:.1f} ms | Throughput >= {workload.min_throughput_rps:.1f} req/s")
    print(f"  • Budget Limit         : ${workload.max_monthly_budget_usd:.2f} / month")
    print("  • Stated Assumptions   :")
    print(f"      - Cache hit rate expectation: {workload.cache_assumed_hit_rate:.0%} based on social feed temporal locality")
    print(f"      - Standardized cloud pricing baseline: $24/vCPU-month, $4/GB-month, base node costs")
    print(f"      - Database connection pool capacity: 25 slots, 2 vCPUs per database instance")

    # 2. Candidate Architectures
    print_banner("[Step 2] Generating Candidate Architectures", "-")
    gen = ArchitectureGenerator()
    candidates = gen.generate_candidates(include_async=True, include_unsupported=True)
    for c in candidates:
        print(f"  ➔ [{c.id:23s}] {c.name}")
        print(f"     Topology : Read [{' -> '.join(c.read_path)}] | Write [{' -> '.join(c.write_path)}]")
        print(f"     Est Cost : ${c.total_monthly_cost_usd:.2f}/mo | Models: {c.required_models}")

    # 3. Component Registry & Missing Model Discovery
    print_banner("[Step 3] Inspecting Component Registry & Model Provenance", "-")
    registry = ComponentRegistry()
    registry.seed_baseline_data()
    # Reset uncalibrated demonstration component so model discovery triggers reliably
    with registry._get_connection() as conn:
        conn.cursor().execute("DELETE FROM models WHERE component_name = 'mongodb_cluster'")
        conn.commit()

    missing_components = []
    checked_keys = set()
    for c in candidates:
        for model_key in c.required_models:
            if model_key in checked_keys:
                continue
            checked_keys.add(model_key)
            comp_name, version = model_key.split(":", 1) if ":" in model_key else (model_key, "latest")
            status, model, warnings = registry.check_compatibility(comp_name, version, workload)
            if status == "VALIDATED" and model:
                prov_str = "[PROVENANCE: SYNTHETIC FIXTURE]" if model.is_synthetic_fixture else "[PROVENANCE: LIVE DOCKER BENCHMARK]"
                print(f"  • {model_key:35s} -> Status: [VALIDATED] {prov_str}")
                print(f"      Model Type: {model.model_type} (R²={model.r2_score:.3f}, RMSE={model.validation_rmse_ms:.2f}ms) | Limitations: {model.known_limitations[:60]}...")
            elif status == "MISSING":
                print(f"  • {model_key:35s} -> Status: [MISSING] ⚠️ No calibrated performance model found in registry!")
                missing_components.append((comp_name, version))
            else:
                print(f"  • {model_key:35s} -> Status: [{status}] {warnings}")

    # 4. Calibration of Missing Model
    benchmark_info = {}
    if missing_components:
        print_banner("[Step 4] Missing Model Identified — Launching Controlled Benchmark & Calibration", "-")
        for comp_name, version in missing_components:
            # Determine runner based on requested mode and environment capability
            use_synthetic = True
            runner_provenance_badge = "[BENCHMARK PROVENANCE: SYNTHETIC CALIBRATED FIXTURE (Deterministic CI/Demo Mode)]"

            if args.mode == "docker":
                d_runner = DockerBenchmarkRunner()
                check = d_runner.health_check()
                if check.get("docker_available"):
                    use_synthetic = False
                    runner_provenance_badge = "[BENCHMARK PROVENANCE: LIVE DOCKER CONTAINER MEASUREMENT]"
                    print(f"  ⚡ Running empirical benchmark on Docker daemon for {comp_name}:{version}...")
                else:
                    print(f"  ⚠️ Docker requested but unavailable: {check.get('error', 'Daemon down')}")
                    print("     Falling back safely to labeled synthetic calibration fixtures.")
            elif args.mode == "auto":
                d_runner = DockerBenchmarkRunner()
                check = d_runner.health_check()
                if check.get("docker_available"):
                    use_synthetic = False
                    runner_provenance_badge = "[BENCHMARK PROVENANCE: LIVE DOCKER CONTAINER MEASUREMENT]"
                    print(f"  ⚡ Docker detected! Running live empirical benchmark for {comp_name}:{version}...")
                else:
                    print(f"  ℹ Docker not detected. Using labeled synthetic calibration fixtures.")

            print(f"  {runner_provenance_badge}")
            if use_synthetic:
                print(f"  ℹ Note: Generating deterministic calibration curves (seed={args.seed}). No live containers created.")

            syn_runner = SyntheticBenchmarkRunner(seed=args.seed)
            exp_mgr = AdaptiveExperimentManager(registry=registry, synthetic_runner=syn_runner)
            campaign = exp_mgr.run_campaign(
                component_name=comp_name,
                version=version,
                workload=workload,
                budget_runs=6,
                force_synthetic=use_synthetic,
            )
            print(f"     Campaign: Completed {campaign['total_experiments']} trials across {len(campaign['iterations'])} adaptive iterations.")
            
            # Model fitting with group-based zero-leakage cross-validation
            model_rec, metrics = ModelTrainer.train_and_validate(comp_name, version, campaign["experiments"])
            eval_metrics = metrics.get("chosen_eval", {})
            print(f"     Fitted: {model_rec.model_type} on {metrics.get('train_samples')} training trials.")
            print(f"     Held-out Validation (Zero Leakage): R² = {model_rec.r2_score:.3f} | RMSE = {model_rec.validation_rmse_ms:.2f} ms | MAE = {eval_metrics.get('mae', 0.0):.2f} ms")
            if model_rec.is_validated:
                registry.register_model(model_rec)
                print(f"     ✅ Model validated and registered: {model_rec.model_id}")

            benchmark_info = {
                "component": f"{comp_name}:{version}",
                "provenance": runner_provenance_badge,
                "is_synthetic": use_synthetic,
                "model_id": model_rec.model_id,
                "model_type": model_rec.model_type,
                "r2_score": model_rec.r2_score,
                "rmse_ms": model_rec.validation_rmse_ms,
            }

    # 5. Discrete-Event SimPy Simulation
    print_banner("[Step 5] Simulating Candidate Architectures in SimPy Discrete-Event Engine", "-")
    print("  [SIMULATION PROVENANCE: SIMPY DISCRETE-EVENT ENGINE]")
    print(f"  ℹ Queueing & contention modeled: Client requests, API threads, DB CPU cores (2 cores), DB connection pool (25 slots), Redis cache.")
    
    sim_engine = SimPyEngine(registry=registry)
    simulatable = [
        c for c in candidates
        if all(registry.get_model(*(m.split(":", 1) if ":" in m else (m, "latest"))) is not None for m in c.required_models)
    ]
    sim_results = []

    for c in simulatable:
        res = sim_engine.simulate_architecture(c, workload, duration_seconds=args.duration, random_seed=args.seed)
        sim_results.append(res)
        hit_str = f"Cache Hit: {res.cache_hit_rate:.1%}" if res.cache_hit_rate is not None else "No Cache"
        ci_str = f"[{res.latency_uncertainty_p95_ms[0]:.2f}, {res.latency_uncertainty_p95_ms[1]:.2f}] ms"
        print(f"\n  📊 {c.name}")
        print(f"     Throughput : {res.throughput_achieved_rps:.1f} req/s (Target: >= {workload.min_throughput_rps:.1f} req/s)")
        print(f"     Latencies  : p50: {res.p50_latency_ms:5.2f} ms | p90: {res.p90_latency_ms:5.2f} ms | p95: {res.p95_latency_ms:5.2f} ms | p99: {res.p99_latency_ms:5.2f} ms")
        print(f"     Uncertainty: p95 95% Confidence Interval: {ci_str}")
        print(f"     Bottleneck : {res.bottleneck_component.upper():5s} | Utilizations: {res.component_utilizations} | {hit_str}")
        print(f"     Est. Cost  : ${res.estimated_monthly_cost_usd:.2f} / month (Cap: ${workload.max_monthly_budget_usd:.2f})")

    # 6. Evaluation and Recommendation
    print_banner("[Step 6] Running Two-Stage Feasibility Filtering & Multi-Attribute Trade-off Analysis", "-")
    rec = ArchitectureRecommender.evaluate_and_recommend(workload, sim_results)

    # Print Feasibility Table
    print("  Candidate Feasibility & Constraint Breakdown:")
    print("  " + "-" * 92)
    print(f"  {'Candidate':<30s} | {'Overall':<12s} | {'p95 Latency':<16s} | {'Throughput':<16s} | {'Budget':<16s}")
    print("  " + "-" * 92)
    for ev in rec.evaluations:
        status_badge = f"[{ev.feasibility_status.value}]"
        p95_chk = next((c for c in ev.checks if c.criterion == "p95_latency"), None)
        thr_chk = next((c for c in ev.checks if c.criterion == "min_throughput"), None)
        cst_chk = next((c for c in ev.checks if c.criterion == "max_budget"), None)

        p95_str = f"{p95_chk.predicted_value:.1f}ms [{p95_chk.status.value[:4]}]" if p95_chk else "N/A"
        thr_str = f"{thr_chk.predicted_value:.0f} rps [{thr_chk.status.value[:4]}]" if thr_chk else "N/A"
        cst_str = f"${cst_chk.predicted_value:.0f}/mo [{cst_chk.status.value[:4]}]" if cst_chk else "N/A"

        print(f"  {ev.architecture_name[:30]:<30s} | {status_badge:<12s} | {p95_str:<16s} | {thr_str:<16s} | {cst_str:<16s}")
    print("  " + "-" * 92)

    # 7. Final Recommendation
    print_banner(f"🏆 RECOMMENDATION: {rec.selected_architecture_name}", "=")
    print(f"  Status: {rec.status.value}\n")
    print(f"  Executive Summary:\n    {rec.executive_summary}\n")
    
    print("  Decision Rationale:")
    for r in rec.rationale:
        print(f"    ✔ {r}")

    print("\n  Trade-offs & Identified Disadvantages:")
    for t in rec.trade_offs_and_risks:
        print(f"    ⚠ {t}")

    print("\n  Stated Assumptions & Provenance:")
    for a in rec.assumptions_cited:
        print(f"    ℹ {a}")

    print("\n  Identified Validation Gaps & Limitations:")
    for g in rec.validation_gaps:
        print(f"    🔍 {g}")

    print("\n  Alternative Options Evaluated:")
    alts = rec.predicted_metrics.get("alternatives", {})
    for alt_k, alt_v in alts.items():
        print(f"    • {alt_k.replace('_', ' ').title():20s}: {alt_v['name']} (${alt_v['cost']:.2f}/mo, p95: {alt_v['p95_ms']:.2f}ms)")

    if rec.recommended_next_experiment:
        print(f"\n  Recommended Next Experiment:\n    🔬 {rec.recommended_next_experiment}\n")

    # 8. Optional JSON export
    if args.json_output:
        export_data = {
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "seed": args.seed,
                "mode": args.mode,
                "duration_seconds": args.duration,
            },
            "workload": workload.model_dump(),
            "benchmark_campaign": benchmark_info,
            "candidates": [c.model_dump() for c in candidates],
            "simulation_results": [s.model_dump() for s in sim_results],
            "recommendation": rec.model_dump(),
        }
        with open(args.json_output, "w") as f:
            json.dump(export_data, f, indent=2)
        print(f"  💾 Results exported to: {args.json_output}\n")


if __name__ == "__main__":
    main()
