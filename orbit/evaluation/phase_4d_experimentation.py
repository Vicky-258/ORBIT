"""
AADS Phase 4D: Evidence-Driven Active Experimentation Evaluation.
Compares four strategies on controlled scenarios where benchmark measurements can
genuinely update component models and alter architecture recommendations:
- Strategy 1: Baseline Architecture Evaluation (No Experiments)
- Strategy 2: Fixed Experiment Matrix (Rigid predetermined benchmarks)
- Strategy 3: Deterministic Active Experimenter (Ranker-driven experiment selection)
- Strategy 4: Agent-Driven Active Experimenter (LLM-proposed, policy-gated active experimentation)
"""
import copy
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from orbit.core.schemas import (
    WorkloadSpec,
    SimulationResult,
    RecommendationResult,
    FeasibilityStatus,
    ArchitectureGraph,
    ExperimentRecord,
    ModelRecord,
)
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.simulation.simpy_engine import SimPyEngine
from orbit.evaluation.recommender import ArchitectureRecommender
from orbit.registry.component_registry import ComponentRegistry
from orbit.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    InvestigationRecord,
    ExperimentProposal,
    AuthorizationRecord,
    AuthorizationStatus,
    AuthorizationLevel,
    ExperimentExecutionResult,
)
from orbit.agent.investigation_policy import InvestigationPolicy, PolicyVerdict
from orbit.agent.investigation_dispatcher import InvestigationDispatcher
from orbit.agent.investigation_planner import InvestigationPlanner
from orbit.benchmark.experiment_ranker import ExperimentRanker
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.modeling.calibration_pipeline import CalibrationPipeline
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner


class Phase4DScenario(BaseModel):
    """Controlled experimentation scenario definition."""
    scenario_id: str
    scenario_name: str
    description: str
    workload: WorkloadSpec
    initial_prior_bias: str = Field(
        default="optimistic",
        description="Bias of initial component model: 'optimistic' (underestimates latency near SLA) or 'calibrated'",
    )
    ground_truth_winner: str = Field(
        description="Architecture that is genuinely optimal under true empirical performance",
    )
    ground_truth_sla_status: Dict[str, bool] = Field(
        default_factory=dict,
        description="Whether candidates genuinely satisfy SLA under true measurements",
    )
    requires_experiment_to_detect_violation: bool = Field(
        default=True,
        description="True if initial uncalibrated model fails to detect SLA violation without real benchmark",
    )


class ExperimentationStrategyResult(BaseModel):
    """Standardized result for Phase 4D comparative strategies."""
    strategy_name: str
    scenario_id: str
    selected_architecture_id: Optional[str] = None
    selected_architecture_name: Optional[str] = None
    status: str = "FEASIBLE"
    pre_experiment_winner: Optional[str] = None
    recommendation_changed: bool = False
    correct_under_ground_truth: bool = False
    sla_violation_prevented: bool = False

    # Experiment metrics
    experiments_executed_count: int = 0
    useful_experiments_count: int = 0
    redundant_experiments_count: int = 0
    model_promoted: bool = False
    calibration_rmse_before: Optional[float] = None
    calibration_rmse_after: Optional[float] = None
    calibration_rmse_improvement: Optional[float] = None

    # Operational metrics
    execution_duration_seconds: float = 0.0
    investigation_rounds: int = 0
    llm_call_count: int = 0
    llm_tokens: int = 0
    llm_cost_usd: float = 0.0
    investigation_trace: List[Dict[str, Any]] = Field(default_factory=list)


def build_controlled_scenarios() -> List[Phase4DScenario]:
    """
    Constructs controlled evaluation scenarios specifically testing whether active experimentation
    improves decision quality by detecting SLA boundaries that initial models miss.
    """
    scenarios = []

    # Scenario 1: Boundary Latency Shift (Active experiment prevents catastrophic SLA violation)
    # Workload: 380 RPS, p95 <= 20 ms SLA, Budget <= $250.
    # Initial prior model on postgres underestimates concurrency penalty (predicts p95=10.9ms for arch_a).
    # Since arch_a ($133) is cheaper than arch_b ($176), baseline mistakenly recommends arch_a.
    # Real measurements show postgres saturates at 350 RPS (p95=48ms, violating SLA).
    # Cache in arch_b keeps postgres load at 57 RPS (p95=12ms, well within SLA).
    # Ground truth winner: arch_b_cached.
    scenarios.append(Phase4DScenario(
        scenario_id="exp_01_boundary_shift",
        scenario_name="SLA Boundary Latency Shift (PostgreSQL Saturation)",
        description="Initial optimistic prior predicts arch_a satisfies SLA. Active benchmark reveals saturation, forcing correct pivot to arch_b_cached.",
        workload=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=380.0,
            peak_load_factor=1.2,
            read_ratio=0.85,
            write_ratio=0.15,
            dataset_records=500000,
            p95_latency_target_ms=20.0,
            min_throughput_rps=350.0,
            max_monthly_budget_usd=250.0,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.40, "latency": 0.40, "simplicity": 0.20},
        ),
        initial_prior_bias="optimistic",
        ground_truth_winner="arch_b_cached",
        ground_truth_sla_status={"arch_a_simple": False, "arch_b_cached": True, "arch_c_async": True},
        requires_experiment_to_detect_violation=True,
    ))

    # Scenario 2: Definite Margin (Experiment confirms sufficiency without unjustified change)
    # Workload: 120 RPS, p95 <= 60 ms SLA, Budget <= $200.
    # Low load. arch_a is well within SLA (p95=9ms).
    # Experiment on postgres confirms low latency and tight variance.
    # Ground truth winner: arch_a_simple.
    scenarios.append(Phase4DScenario(
        scenario_id="exp_02_confirmed_margin",
        scenario_name="SLA Headroom Confirmation (Low Load)",
        description="Workload is well within capacity. Active benchmark confirms stability without causing unnecessary recommendation churn.",
        workload=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=120.0,
            peak_load_factor=1.1,
            read_ratio=0.90,
            write_ratio=0.10,
            dataset_records=100000,
            p95_latency_target_ms=60.0,
            min_throughput_rps=100.0,
            max_monthly_budget_usd=200.0,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.50, "latency": 0.30, "simplicity": 0.20},
        ),
        initial_prior_bias="calibrated",
        ground_truth_winner="arch_a_simple",
        ground_truth_sla_status={"arch_a_simple": True, "arch_b_cached": True, "arch_c_async": True},
        requires_experiment_to_detect_violation=False,
    ))

    # Scenario 3: Near-Tie Discrimination
    # Workload: 450 RPS, p95 <= 40 ms SLA, Budget <= $260.
    # Ground truth winner: arch_b_cached.
    scenarios.append(Phase4DScenario(
        scenario_id="exp_03_near_tie_discrimination",
        scenario_name="Near-Tie Architecture Discrimination",
        description="Close scores between arch_a and arch_b. Active benchmarking isolates service demand and resolves the tie conclusively.",
        workload=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=450.0,
            peak_load_factor=1.15,
            read_ratio=0.85,
            write_ratio=0.15,
            dataset_records=1000000,
            p95_latency_target_ms=40.0,
            min_throughput_rps=400.0,
            max_monthly_budget_usd=260.0,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        initial_prior_bias="optimistic",
        ground_truth_winner="arch_b_cached",
        ground_truth_sla_status={"arch_a_simple": False, "arch_b_cached": True, "arch_c_async": True},
        requires_experiment_to_detect_violation=True,
    ))

    # Scenario 4: Extreme Infeasible Workload (Triage to Inconclusive)
    # Workload: 3500 RPS, p95 <= 8 ms, Budget <= $120.
    # No candidate can satisfy SLA. Benchmark confirms all candidates fail.
    # Ground truth: None (Inconclusive).
    scenarios.append(Phase4DScenario(
        scenario_id="exp_04_infeasible_triage",
        scenario_name="Extreme Infeasible Workload Triage",
        description="All architectures violate constraints. Experiment confirms saturation; system safely halts with stop_inconclusive.",
        workload=WorkloadSpec(
            app_type="social_media_feed",
            request_rate_rps=3500.0,
            peak_load_factor=1.2,
            read_ratio=0.80,
            write_ratio=0.20,
            dataset_records=5000000,
            p95_latency_target_ms=8.0,
            min_throughput_rps=3000.0,
            max_monthly_budget_usd=120.0,
            hard_constraints=["p95_latency", "min_throughput", "max_budget"],
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
        ),
        initial_prior_bias="optimistic",
        ground_truth_winner="inconclusive",
        ground_truth_sla_status={"arch_a_simple": False, "arch_b_cached": False, "arch_c_async": False},
        requires_experiment_to_detect_violation=False,
    ))

    return scenarios


def create_scenario_registry(scenario: Phase4DScenario, db_path=None) -> ComponentRegistry:
    """Creates an isolated registry with appropriately biased initial prior models."""
    registry = ComponentRegistry(db_path=db_path)
    now = datetime.now(timezone.utc).isoformat()

    if scenario.initial_prior_bias == "optimistic":
        # Optimistic prior: base read service 1.8ms, low slope, saturation 800 RPS
        # This causes SimPy to predict lower latency than real hardware produces under high load
        pg_model = ModelRecord(
            model_id="model_pg16_optimistic_prior",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="synthetic:optimistic_prior",
            model_type="piecewise_ridge",
            fitted_parameters={
                "base_read_service_ms": 1.8,
                "base_write_service_ms": 4.5,
                "concurrency_penalty_slope": 0.04,
                "saturation_rps": 800.0,
            },
            min_supported_rps=10.0,
            max_supported_rps=850.0,
            min_supported_concurrency=1,
            max_supported_concurrency=32,
            validation_rmse_ms=1.45,
            validation_mape_pct=18.5,
            r2_score=0.72,
            is_validated=True,
            is_synthetic_fixture=True,
            provenance="Optimistic uncalibrated prior (synthetic fixture)",
            known_limitations="Underestimates queuing delays above 300 RPS.",
            created_at=now,
        )
    else:
        # Calibrated baseline
        pg_model = ModelRecord(
            model_id="model_pg16_calibrated_baseline",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="synthetic:calibrated_baseline",
            model_type="piecewise_ridge",
            fitted_parameters={
                "base_read_service_ms": 3.2,
                "base_write_service_ms": 7.0,
                "concurrency_penalty_slope": 0.10,
                "saturation_rps": 450.0,
            },
            min_supported_rps=10.0,
            max_supported_rps=500.0,
            min_supported_concurrency=1,
            max_supported_concurrency=32,
            validation_rmse_ms=0.62,
            validation_mape_pct=8.4,
            r2_score=0.94,
            is_validated=True,
            is_synthetic_fixture=True,
            provenance="Calibrated baseline fixture",
            known_limitations="Accurate up to 450 RPS.",
            created_at=now,
        )

    registry.register_model(pg_model)

    # Redis baseline
    redis_model = ModelRecord(
        model_id="model_redis72_baseline",
        component_name="redis_cache",
        version="redis:7.2-alpine",
        env_fingerprint="docker:redis:7.2-alpine",
        model_type="lookup_table",
        fitted_parameters={
            "base_hit_latency_ms": 0.65,
            "base_miss_overhead_ms": 0.35,
            "saturation_rps": 8000.0,
        },
        min_supported_rps=10.0,
        max_supported_rps=5000.0,
        min_supported_concurrency=1,
        max_supported_concurrency=128,
        validation_rmse_ms=0.08,
        validation_mape_pct=5.1,
        r2_score=0.98,
        is_validated=True,
        is_synthetic_fixture=True,
        provenance="In-memory microbenchmark with 10k key working set",
        known_limitations="Assumes working set fits in RAM.",
        created_at=now,
    )
    registry.register_model(redis_model)
    return registry


# --------------------------------------------------------------------------
# Comparative Strategy Implementations
# --------------------------------------------------------------------------

def run_strategy_1_baseline_no_experiments(
    scenario: Phase4DScenario,
    registry: Optional[ComponentRegistry] = None,
) -> ExperimentationStrategyResult:
    """Strategy 1: Evaluates candidates using uncalibrated baseline without additional experiments."""
    start_t = time.perf_counter()
    if registry is None:
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        reg = create_scenario_registry(scenario, db_path=Path(tmp.name))
    else:
        reg = registry
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates(include_async=True)

    engine = SimPyEngine(reg)
    sim_results = []
    for c in candidates:
        sim_run = engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42)
        sim_results.append(sim_run)

    rec = ArchitectureRecommender.evaluate_and_recommend(
        workload=scenario.workload,
        sim_results=sim_results,
    )

    elapsed = round(time.perf_counter() - start_t, 3)
    winner = rec.selected_architecture_id if rec.selected_architecture_id else ("inconclusive" if rec.status == FeasibilityStatus.INFEASIBLE else None)
    is_correct = (winner == scenario.ground_truth_winner)

    return ExperimentationStrategyResult(
        strategy_name="strategy_1_baseline_no_exp",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=rec.selected_architecture_id,
        selected_architecture_name=rec.selected_architecture_name,
        status=rec.status.value,
        pre_experiment_winner=winner,
        recommendation_changed=False,
        correct_under_ground_truth=is_correct,
        sla_violation_prevented=False,  # Baseline never runs experiments, so it cannot prevent violations
        experiments_executed_count=0,
        useful_experiments_count=0,
        redundant_experiments_count=0,
        model_promoted=False,
        execution_duration_seconds=elapsed,
        investigation_rounds=0,
    )


def run_strategy_2_fixed_experiments(
    scenario: Phase4DScenario,
    registry: Optional[ComponentRegistry] = None,
) -> ExperimentationStrategyResult:
    """Strategy 2: Runs a fixed, rigid benchmark matrix regardless of workload need."""
    start_t = time.perf_counter()
    if registry is None:
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        reg = create_scenario_registry(scenario, db_path=Path(tmp.name))
    else:
        reg = registry
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates(include_async=True)

    # Initial simulation
    engine = SimPyEngine(reg)
    sim_results = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42) for c in candidates]
    initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, sim_results)
    initial_winner = initial_rec.selected_architecture_id if initial_rec.selected_architecture_id else "inconclusive"

    # Fixed experiment: always benchmark postgres at fixed concurrency [1, 4, 8, 16]
    executor = BoundedBenchmarkExecutor(registry=reg)
    auth = AuthorizationRecord(
        authorization_id=f"auth_{uuid.uuid4().hex[:8]}",
        proposal_id="fixed_postgres_exp",
        authorized_by="fixed_strategy_policy",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )
    fixed_prop = ExperimentProposal(
        proposal_id="fixed_postgres_exp",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Fixed routine calibration of postgres",
        unknown_being_investigated="general scaling",
        concurrency_levels=[1, 4, 8, 16],
        read_ratio=scenario.workload.read_ratio,
    )
    exec_res = executor.execute_experiment(fixed_prop, auth)

    # Calibration
    calib = CalibrationPipeline(registry=reg)
    outcome = calib.calibrate_component("postgres_db", "postgres:16-alpine")

    # Re-simulate
    new_sim_results = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42) for c in candidates]
    final_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, new_sim_results)
    final_winner = final_rec.selected_architecture_id if final_rec.selected_architecture_id else ("inconclusive" if final_rec.status == FeasibilityStatus.INFEASIBLE else None)

    rec_changed = (initial_winner != final_winner)
    is_correct = (final_winner == scenario.ground_truth_winner)
    sla_prevented = rec_changed and is_correct and scenario.requires_experiment_to_detect_violation

    # Useful vs redundant: if scenario did not require an experiment, this fixed run was redundant
    useful = 1 if scenario.requires_experiment_to_detect_violation else 0
    redundant = 1 if not scenario.requires_experiment_to_detect_violation else 0

    elapsed = round(time.perf_counter() - start_t, 3)
    return ExperimentationStrategyResult(
        strategy_name="strategy_2_fixed_experiments",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=final_rec.selected_architecture_id,
        selected_architecture_name=final_rec.selected_architecture_name,
        status=final_rec.status.value,
        pre_experiment_winner=initial_winner,
        recommendation_changed=rec_changed,
        correct_under_ground_truth=is_correct,
        sla_violation_prevented=sla_prevented,
        experiments_executed_count=1,
        useful_experiments_count=useful,
        redundant_experiments_count=redundant,
        model_promoted=(outcome.status == "PROMOTED"),
        calibration_rmse_after=outcome.validation_rmse_ms,
        execution_duration_seconds=elapsed,
        investigation_rounds=1,
    )


def run_strategy_3_deterministic_active(
    scenario: Phase4DScenario,
    registry: Optional[ComponentRegistry] = None,
) -> ExperimentationStrategyResult:
    """Strategy 3: Deterministic Active Experimenter (Ranks proposals by decision-relevance)."""
    start_t = time.perf_counter()
    if registry is None:
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        reg = create_scenario_registry(scenario, db_path=Path(tmp.name))
    else:
        reg = registry
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates(include_async=True)

    # 1. Initial simulation & recommendation
    engine = SimPyEngine(reg)
    sim_results = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42) for c in candidates]
    initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, sim_results)
    initial_winner = initial_rec.selected_architecture_id if initial_rec.selected_architecture_id else "inconclusive"

    # 2. Formulate candidate experiment proposals
    ranker = ExperimentRanker(registry=reg)
    candidate_proposals = [
        ExperimentProposal(
            proposal_id="prop_pg_target",
            target_component="postgres_db",
            version="postgres:16-alpine",
            hypothesis="Evaluate postgres p95 scaling near workload load boundary",
            unknown_being_investigated="postgres service demand inflection",
            concurrency_levels=[1, 4, 8, 16, 24],
            read_ratio=scenario.workload.read_ratio,
            target_rps=scenario.workload.request_rate_rps,
        ),
        ExperimentProposal(
            proposal_id="prop_redis_target",
            target_component="redis_cache",
            version="redis:7.2-alpine",
            hypothesis="Evaluate redis cache throughput headroom",
            unknown_being_investigated="redis cache latency under load",
            concurrency_levels=[8, 16, 32],
            read_ratio=1.0,
        ),
    ]

    ranked = ranker.rank_proposals(
        proposals=candidate_proposals,
        workload=scenario.workload,
        candidates=candidates,
        simulation_results=sim_results,
    )

    # 3. Decision rule: execute top proposal if priority score >= 0.50 and approved
    top = ranked[0] if ranked else None
    exp_count = 0
    model_promoted = False
    rmse_after = None

    if top and top.is_approved and top.priority_score >= 0.45:
        exp_count += 1
        executor = BoundedBenchmarkExecutor(registry=reg)
        auth = AuthorizationRecord(
            authorization_id=f"auth_{uuid.uuid4().hex[:8]}",
            proposal_id=top.proposal.proposal_id,
            authorized_by="deterministic_active_ranker",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            execution_mode="synthetic",
            status=AuthorizationStatus.AUTHORIZED,
            max_runtime_seconds=60.0,
        )
        executor.execute_experiment(top.proposal, auth)
        calib = CalibrationPipeline(registry=reg)
        outcome = calib.calibrate_component(top.proposal.target_component, top.proposal.version)
        model_promoted = (outcome.status == "PROMOTED")
        rmse_after = outcome.validation_rmse_ms

        # Re-simulation
        sim_results = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42) for c in candidates]

    final_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, sim_results)
    final_winner = final_rec.selected_architecture_id if final_rec.selected_architecture_id else ("inconclusive" if final_rec.status == FeasibilityStatus.INFEASIBLE else None)

    rec_changed = (initial_winner != final_winner)
    is_correct = (final_winner == scenario.ground_truth_winner)
    sla_prevented = rec_changed and is_correct and scenario.requires_experiment_to_detect_violation

    # Useful vs redundant
    useful = 1 if (exp_count > 0 and scenario.requires_experiment_to_detect_violation) else 0
    redundant = 1 if (exp_count > 0 and not scenario.requires_experiment_to_detect_violation) else 0

    elapsed = round(time.perf_counter() - start_t, 3)
    return ExperimentationStrategyResult(
        strategy_name="strategy_3_deterministic_active",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=final_rec.selected_architecture_id,
        selected_architecture_name=final_rec.selected_architecture_name,
        status=final_rec.status.value,
        pre_experiment_winner=initial_winner,
        recommendation_changed=rec_changed,
        correct_under_ground_truth=is_correct,
        sla_violation_prevented=sla_prevented,
        experiments_executed_count=exp_count,
        useful_experiments_count=useful,
        redundant_experiments_count=redundant,
        model_promoted=model_promoted,
        calibration_rmse_after=rmse_after,
        execution_duration_seconds=elapsed,
        investigation_rounds=1 if exp_count > 0 else 0,
    )


def run_strategy_4_agent_active(
    scenario: Phase4DScenario,
    registry: Optional[ComponentRegistry] = None,
    mode: str = "offline",
    fail_closed: bool = False,
) -> ExperimentationStrategyResult:
    """Strategy 4: Agent-Driven Active Experimenter (LLM proposes, policy gates, bounded execution)."""
    start_t = time.perf_counter()
    if registry is None:
        import tempfile
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        reg = create_scenario_registry(scenario, db_path=Path(tmp.name))
    else:
        reg = registry
    generator = ArchitectureGenerator()
    candidates = generator.generate_candidates(include_async=True)

    # Initial simulation
    engine = SimPyEngine(reg)
    sim_results = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0, random_seed=42) for c in candidates]
    initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, sim_results)
    initial_winner = initial_rec.selected_architecture_id if initial_rec.selected_architecture_id else "inconclusive"

    # Prepare investigation state
    auth = AuthorizationRecord(
        authorization_id=f"auth_{uuid.uuid4().hex[:8]}",
        proposal_id="agent_authorized_exp",
        authorized_by="operator_session",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    state = {
        "workload_spec": scenario.workload,
        "candidate_architectures": candidates,
        "simulation_results": sim_results,
        "recommendation": initial_rec,
        "investigation_trace": [],
        "investigation_round": 0,
        "max_investigation_rounds": 3,
        "enable_active_experimentation": True,
        "experiment_authorization": auth,
        "auto_authorize_synthetic": True,
        "missing_models": [],
        "benchmark_proposals": [],
        "component_registry": reg,
    }

    planner = InvestigationPlanner()
    policy = InvestigationPolicy()
    dispatcher = InvestigationDispatcher(registry=reg)

    exp_count = 0
    useful = 0
    redundant = 0
    model_promoted = False
    rmse_after = None
    llm_calls = 0
    llm_tokens = 0
    llm_cost = 0.0

    # Multi-round agent loop (up to 3 rounds)
    for r_num in range(1, 4):
        state["investigation_round"] = r_num - 1

        if mode == "live" and planner.provider_mgr.is_llm_available():
            try:
                proposal, telemetry = planner.plan_next_action_with_telemetry(state, fail_closed=fail_closed)
                llm_calls += 1
                llm_tokens += telemetry.get("total_tokens", 0)
                llm_cost += telemetry.get("estimated_cost_usd", 0.0)
            except Exception as e:
                if fail_closed:
                    raise RuntimeError(f"Fail-closed LLM call failed in active experimentation: {e}") from e
                proposal = planner._heuristic_fallback(state)
        else:
            # Deterministic heuristic fallback
            proposal = planner._heuristic_fallback(state)

        # Policy validation
        val_res = policy.evaluate_action(proposal, state)
        if val_res.verdict == PolicyVerdict.APPROVED:
            updates, record = dispatcher.dispatch(val_res.sanitized_decision, state, round_num=r_num)
            state["investigation_trace"].append(record.model_dump())
            state.update(updates)

            if record.action == "execute_experiment":
                exp_count += 1
                tool_out = record.tool_output or {}
                delta = tool_out.get("closed_loop_delta", {})
                if delta.get("model_promoted"):
                    model_promoted = True
                    calib_dict = tool_out.get("calibration", {})
                    rmse_after = calib_dict.get("validation_rmse_ms")

            if record.action in ("stop_and_recommend", "stop_inconclusive"):
                break
        elif val_res.verdict == PolicyVerdict.STOPPED:
            break

    final_rec = state.get("recommendation", initial_rec)
    final_winner = final_rec.selected_architecture_id if final_rec.selected_architecture_id else ("inconclusive" if final_rec.status == FeasibilityStatus.INFEASIBLE else None)

    rec_changed = (initial_winner != final_winner)
    is_correct = (final_winner == scenario.ground_truth_winner)
    sla_prevented = rec_changed and is_correct and scenario.requires_experiment_to_detect_violation

    if exp_count > 0:
        if scenario.requires_experiment_to_detect_violation:
            useful = exp_count
        else:
            redundant = exp_count

    elapsed = round(time.perf_counter() - start_t, 3)
    return ExperimentationStrategyResult(
        strategy_name="strategy_4_agent_active",
        scenario_id=scenario.scenario_id,
        selected_architecture_id=final_rec.selected_architecture_id,
        selected_architecture_name=final_rec.selected_architecture_name,
        status=final_rec.status.value if hasattr(final_rec.status, "value") else str(final_rec.status),
        pre_experiment_winner=initial_winner,
        recommendation_changed=rec_changed,
        correct_under_ground_truth=is_correct,
        sla_violation_prevented=sla_prevented,
        experiments_executed_count=exp_count,
        useful_experiments_count=useful,
        redundant_experiments_count=redundant,
        model_promoted=model_promoted,
        calibration_rmse_after=rmse_after,
        execution_duration_seconds=elapsed,
        investigation_rounds=len(state["investigation_trace"]),
        llm_call_count=llm_calls,
        llm_tokens=llm_tokens,
        llm_cost_usd=round(llm_cost, 6),
        investigation_trace=state["investigation_trace"],
    )
