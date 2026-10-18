"""
CLI Demonstration Script for AADS.
Executes the end-to-end workflow:
1. Workload Specification
2. Candidate Architecture Generation
3. Registry Check & Model Discovery
4. Controlled Benchmarking & Model Calibration
5. SimPy Discrete-Event Simulation
6. Multi-Objective Evaluation & Explainable Recommendation
"""
import sys
from datetime import datetime
from aads.core.schemas import WorkloadSpec, FeasibilityStatus
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.registry.component_registry import ComponentRegistry
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.experiment_manager import AdaptiveExperimentManager
from aads.modeling.model_trainer import ModelTrainer
from aads.simulation.simpy_engine import SimPyEngine
from aads.evaluation.recommender import ArchitectureRecommender


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def main():
    print_banner("⚡ AADS: Agentic Architecture Design & Simulation POC")

    # 1. User Workload Specification
    print("\n[Step 1] Initializing Workload & Requirements...")
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=500.0,
        peak_load_factor=2.0,
        read_ratio=0.90,
        write_ratio=0.10,
        dataset_records=1_000_000,
        p95_latency_target_ms=50.0,
        min_throughput_rps=450.0,
        max_monthly_budget_usd=250.0,
        cache_assumed_hit_rate=0.85,
        soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
    )
    print(f"  • Domain: {workload.app_type}")
    print(f"  • Offered Load: {workload.request_rate_rps} RPS (Peak: {workload.request_rate_rps * workload.peak_load_factor} RPS)")
    print(f"  • Workload Mix: {workload.read_ratio:.0%} Reads / {workload.write_ratio:.0%} Writes")
    print(f"  • SLA Target: p95 <= {workload.p95_latency_target_ms} ms | Throughput >= {workload.min_throughput_rps} RPS")
    print(f"  • Budget Cap: ${workload.max_monthly_budget_usd:.2f} / month")
    print(f"  • Labeled Assumptions: Cache Hit Rate = {workload.cache_assumed_hit_rate:.0%}, 2x Peak Headroom")

    # 2. Candidate Architectures
    print("\n[Step 2] Generating Candidate Architectures...")
    gen = ArchitectureGenerator()
    candidates = gen.generate_candidates(include_async=True, include_unsupported=True)
    for c in candidates:
        print(f"  ➔ [{c.id}] {c.name}")
        print(f"     Est. Cost: ${c.total_monthly_cost_usd:.2f}/mo | Models: {c.required_models}")

    # 3. Component Registry & Missing Model Discovery
    print("\n[Step 3] Checking Component Registry & Discovering Missing Models...")
    registry = ComponentRegistry()
    registry.seed_baseline_data()

    missing_components = []
    for c in candidates:
        for model_key in c.required_models:
            comp_name, version = model_key.split(":", 1) if ":" in model_key else (model_key, "latest")
            status, model, warnings = registry.check_compatibility(comp_name, version, workload)
            print(f"  • Model {model_key:30s} -> Status: {status}")
            if status == "MISSING":
                missing_components.append((comp_name, version))

    # 4. Calibration of Missing Model
    if missing_components:
        print("\n[Step 4] Missing Model Identified! Launching Controlled Benchmark & Calibration...")
        for comp_name, version in missing_components:
            print(f"  ⚡ Running adaptive benchmark campaign for {comp_name}:{version}...")
            exp_mgr = AdaptiveExperimentManager(registry=registry)
            campaign = exp_mgr.run_campaign(
                component_name=comp_name,
                version=version,
                workload=workload,
                budget_runs=6,
                force_synthetic=True,
            )
            print(f"     Completed {campaign['total_experiments']} trials across {len(campaign['iterations'])} iterations.")
            model_rec, metrics = ModelTrainer.train_and_validate(comp_name, version, campaign["experiments"])
            print(f"     Model Fit: {model_rec.model_type} | R² = {model_rec.r2_score} | RMSE = {model_rec.validation_rmse_ms} ms")
            if model_rec.is_validated:
                registry.register_model(model_rec)
                print(f"     ✅ Model validated on held-out observations and registered: {model_rec.model_id}")

    # 5. Discrete-Event SimPy Simulation
    print("\n[Step 5] Simulating Candidate Architectures under Identical Workload in SimPy...")
    sim_engine = SimPyEngine(registry=registry)
    simulatable = [c for c in candidates if c.id != "arch_mongo_unregistered"]
    sim_results = []

    for c in simulatable:
        res = sim_engine.simulate_architecture(c, workload, duration_seconds=5.0, random_seed=42)
        sim_results.append(res)
        hit_str = f"Cache Hit: {res.cache_hit_rate:.1%}" if res.cache_hit_rate is not None else "No Cache"
        print(f"  📊 {c.name}")
        print(f"     Throughput: {res.throughput_achieved_rps:.1f} RPS | p50: {res.p50_latency_ms:.2f} ms | p95: {res.p95_latency_ms:.2f} ms | p99: {res.p99_latency_ms:.2f} ms")
        print(f"     Bottleneck: {res.bottleneck_component.upper()} | Utilizations: {res.component_utilizations} | {hit_str}")

    # 6. Evaluation and Recommendation
    print("\n[Step 6] Running Two-Stage Feasibility Filtering and Trade-off Analysis...")
    rec = ArchitectureRecommender.evaluate_and_recommend(workload, sim_results)

    print_banner(f"🏆 RECOMMENDATION: {rec.selected_architecture_name}")
    print(f"Status: {rec.status.value}")
    print(f"\nExecutive Summary:\n  {rec.executive_summary}\n")
    print("Decision Rationale:")
    for r in rec.rationale:
        print(f"  ✔ {r}")

    print("\nTrade-offs & Disadvantages:")
    for t in rec.trade_offs_and_risks:
        print(f"  ⚠ {t}")

    print("\nCited Assumptions:")
    for a in rec.assumptions_cited:
        print(f"  ℹ {a}")

    print("\nAlternative Options:")
    alts = rec.predicted_metrics.get("alternatives", {})
    for alt_k, alt_v in alts.items():
        print(f"  • {alt_k.replace('_', ' ').title():20s}: {alt_v['name']} (${alt_v['cost']:.2f}/mo, p95: {alt_v['p95_ms']:.2f}ms)")

    print(f"\nRecommended Next Experiment:\n  🔬 {rec.recommended_next_experiment}\n")


if __name__ == "__main__":
    main()
