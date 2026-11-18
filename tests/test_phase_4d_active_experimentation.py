"""
Unit and Integration Tests for AADS Phase 4D: Evidence-Driven Active Experimentation.
Verifies:
- ExperimentProposal and AuthorizationRecord schema contracts
- Deterministic experiment ranking, scoring, and rejection of invalid targets
- Bounded benchmark execution security gates (unauthorized blocked fail-closed)
- Validated model calibration pipeline with held-out validation and quality gating
- Immutable evidence recording and registry versioning
- Closed-loop agent investigation: experiment execution -> calibration -> re-simulation -> recommendation change
- 100% credential-free and docker-free offline test execution
"""
import pytest
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from orbit.agent.schemas import (
    InvestigationActionType,
    InvestigationDecision,
    ExperimentProposal,
    AuthorizationRecord,
    AuthorizationStatus,
    AuthorizationLevel,
    ExperimentExecutionResult,
)
from orbit.core.schemas import WorkloadSpec, ModelRecord, FeasibilityStatus
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.simulation.simpy_engine import SimPyEngine
from orbit.registry.component_registry import ComponentRegistry
from orbit.benchmark.experiment_ranker import ExperimentRanker, RankedExperimentProposal
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.modeling.calibration_pipeline import CalibrationPipeline
from orbit.agent.investigation_dispatcher import InvestigationDispatcher
from orbit.evaluation.phase_4d_experimentation import (
    build_controlled_scenarios,
    create_scenario_registry,
    run_strategy_1_baseline_no_experiments,
    run_strategy_2_fixed_experiments,
    run_strategy_3_deterministic_active,
    run_strategy_4_agent_active,
)


@pytest.fixture
def isolated_registry(tmp_path):
    """Provides a fresh, isolated ComponentRegistry backed by a temporary SQLite database."""
    db_file = tmp_path / "test_registry.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data()
    return reg


@pytest.fixture
def sample_workload():
    return WorkloadSpec(
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
    )


# --------------------------------------------------------------------------
# 1. Schema Contracts & Validation
# --------------------------------------------------------------------------

def test_experiment_proposal_and_authorization_schemas():
    """Verifies typed experiment proposal and authorization record instantiation."""
    proposal = ExperimentProposal(
        proposal_id="prop_test_01",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Test p95 latency under concurrency 16",
        unknown_being_investigated="postgres service demand",
        competing_hypotheses=["Linear scaling", "Queue saturation"],
        concurrency_levels=[1, 4, 8, 16],
        read_ratio=0.85,
        target_rps=380.0,
        replications=3,
        benchmark_framework="pgbench:16-select-only",
        expected_information_gain="Resolve true p95 latency",
        decision_change_probability="HIGH",
        expected_runtime_seconds=12.0,
        operational_risk="LOW",
        authorization_level=AuthorizationLevel.OPERATOR_APPROVAL_REQUIRED,
    )
    assert proposal.proposal_id == "prop_test_01"
    assert proposal.target_component == "postgres_db"
    assert proposal.concurrency_levels == [1, 4, 8, 16]

    auth = AuthorizationRecord(
        authorization_id="auth_test_01",
        proposal_id=proposal.proposal_id,
        authorized_by="security_officer",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=45.0,
    )
    assert auth.status == AuthorizationStatus.AUTHORIZED
    assert auth.execution_mode == "synthetic"

    # Verify decision integration
    decision = InvestigationDecision(
        action=InvestigationActionType.EXECUTE_EXPERIMENT,
        target="postgres_db",
        reason="Execute authorized experiment to resolve database saturation.",
        experiment_proposal=proposal,
    )
    assert decision.action == InvestigationActionType.EXECUTE_EXPERIMENT
    assert decision.experiment_proposal is not None


# --------------------------------------------------------------------------
# 2. Deterministic Experiment Selection & Ranking
# --------------------------------------------------------------------------

def test_experiment_ranker_scoring_and_filtering(isolated_registry, sample_workload):
    """Verifies that ExperimentRanker filters invalid components and prioritizes high-uncertainty targets."""
    candidates = ArchitectureGenerator().generate_candidates(include_async=True)
    ranker = ExperimentRanker(registry=isolated_registry)

    valid_prop = ExperimentProposal(
        proposal_id="prop_valid_pg",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Benchmark postgres",
        unknown_being_investigated="postgres scaling",
        concurrency_levels=[1, 4, 8, 16],
    )

    invalid_comp_prop = ExperimentProposal(
        proposal_id="prop_invalid_cassandra",
        target_component="cassandra_db",
        version="4.1",
        hypothesis="Benchmark unsupported cassandra",
        unknown_being_investigated="cassandra",
        concurrency_levels=[1, 4],
    )

    unrelated_prop = ExperimentProposal(
        proposal_id="prop_unrelated_kafka",
        target_component="redis_cache",
        version="redis:7.2-alpine",
        hypothesis="Benchmark redis",
        unknown_being_investigated="redis",
        concurrency_levels=[1, 4],
    )

    ranked = ranker.rank_proposals(
        proposals=[valid_prop, invalid_comp_prop],
        workload=sample_workload,
        candidates=candidates,
        simulation_results=[],
    )

    # Valid postgres proposal should be approved with positive score
    assert ranked[0].proposal.proposal_id == "prop_valid_pg"
    assert ranked[0].is_approved is True
    assert ranked[0].priority_score > 0.0

    # Cassandra proposal must be rejected
    assert ranked[1].proposal.proposal_id == "prop_invalid_cassandra"
    assert ranked[1].is_approved is False
    assert "not in approved benchmark catalog" in ranked[1].rejection_reason


def test_experiment_ranker_rejects_duplicates(isolated_registry, sample_workload):
    """Verifies that identical previously executed experiments are rejected as duplicates."""
    candidates = ArchitectureGenerator().generate_candidates(include_async=True)
    ranker = ExperimentRanker(registry=isolated_registry)

    prop = ExperimentProposal(
        proposal_id="prop_dup",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Test dup",
        unknown_being_investigated="dup",
        concurrency_levels=[1, 4, 8, 16],
        read_ratio=0.85,
    )

    executed_key = f"postgres_db_postgres:16-alpine_[1, 4, 8, 16]_0.85"
    ranked = ranker.rank_proposals(
        proposals=[prop],
        workload=sample_workload,
        candidates=candidates,
        simulation_results=[],
        executed_experiment_keys={executed_key},
    )

    assert ranked[0].is_approved is False
    assert "Duplicate experiment" in ranked[0].rejection_reason


# --------------------------------------------------------------------------
# 3. Bounded Benchmark Execution Interface
# --------------------------------------------------------------------------

def test_bounded_executor_blocks_unauthorized_execution(isolated_registry):
    """Verifies that BoundedBenchmarkExecutor blocks execution when authorization is absent or denied."""
    executor = BoundedBenchmarkExecutor(registry=isolated_registry)
    prop = ExperimentProposal(
        proposal_id="prop_no_auth",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Test without auth",
        unknown_being_investigated="test",
        concurrency_levels=[1, 4],
    )

    # 1. Missing authorization
    res_no_auth = executor.execute_experiment(prop, authorization=None)
    assert res_no_auth.status == "UNAUTHORIZED"
    assert res_no_auth.raw_records_count == 0
    assert "Execution blocked" in res_no_auth.error_message

    # 2. Denied authorization
    denied_auth = AuthorizationRecord(
        authorization_id="auth_denied",
        proposal_id=prop.proposal_id,
        authorized_by="security_gate",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.DENIED,
        max_runtime_seconds=60.0,
    )
    res_denied = executor.execute_experiment(prop, authorization=denied_auth)
    assert res_denied.status == "UNAUTHORIZED"


def test_bounded_executor_authorized_synthetic_execution(isolated_registry):
    """Verifies that an authorized synthetic experiment executes and immutably records measurements."""
    executor = BoundedBenchmarkExecutor(registry=isolated_registry)
    prop = ExperimentProposal(
        proposal_id="prop_authorized_syn",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Authorized synthetic run",
        unknown_being_investigated="test",
        concurrency_levels=[1, 4, 8, 16],
        read_ratio=0.85,
    )
    auth = AuthorizationRecord(
        authorization_id="auth_valid_syn",
        proposal_id=prop.proposal_id,
        authorized_by="test_harness",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    res = executor.execute_experiment(prop, auth)
    assert res.status == "SUCCESS"
    assert res.raw_records_count == 4
    assert res.provenance == "synthetic_fixture"
    assert len(res.experiment_ids) == 4

    # Verify records persisted in registry
    saved_exps = isolated_registry.get_experiments("postgres_db", "postgres:16-alpine")
    assert len(saved_exps) >= 4
    # Check authorization lineage stamped on records
    assert any("auth_valid_syn" in (e.notes or "") for e in saved_exps)


# --------------------------------------------------------------------------
# 4. Validated Model Calibration Pipeline
# --------------------------------------------------------------------------

def test_calibration_pipeline_held_out_validation_and_promotion(isolated_registry):
    """Verifies that CalibrationPipeline executes group-based validation and promotes valid models."""
    executor = BoundedBenchmarkExecutor(registry=isolated_registry)
    prop = ExperimentProposal(
        proposal_id="prop_calib_test",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Calibrate postgres model",
        unknown_being_investigated="scaling",
        concurrency_levels=[1, 4, 8, 16, 24],
        read_ratio=0.85,
    )
    auth = AuthorizationRecord(
        authorization_id="auth_calib_test",
        proposal_id=prop.proposal_id,
        authorized_by="test",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )
    executor.execute_experiment(prop, auth)

    calib = CalibrationPipeline(registry=isolated_registry)
    outcome = calib.calibrate_component("postgres_db", "postgres:16-alpine")

    assert outcome.status == "PROMOTED"
    assert outcome.new_model_id is not None
    assert outcome.validation_rmse_ms is not None
    assert outcome.r2_score is not None
    assert outcome.r2_score >= 0.65 or outcome.validation_mae_ms <= 1.5

    # Verify model is active in registry
    active_model = isolated_registry.get_model("postgres_db", "postgres:16-alpine")
    assert active_model.model_id == outcome.new_model_id


def test_calibration_pipeline_withholds_insufficient_evidence(isolated_registry):
    """Verifies that CalibrationPipeline withholds recalibration when fewer than 3 observations exist."""
    calib = CalibrationPipeline(registry=isolated_registry)
    # Query with empty observations
    outcome = calib.calibrate_component("unseen_comp", "1.0", experiments=[])
    assert outcome.status == "INSUFFICIENT_EVIDENCE"
    assert outcome.new_model_id is None
    assert "minimum 3 required" in outcome.summary


# --------------------------------------------------------------------------
# 5. Closed-Loop Agent Investigation & Decision Shift
# --------------------------------------------------------------------------

def test_closed_loop_resimulation_and_recommendation_change(tmp_path, sample_workload):
    """
    Verifies that executing an authorized experiment updates the component model,
    re-simulates affected architectures, and detects an evidence-backed recommendation change.
    """
    db_file = tmp_path / "closed_loop.db"
    scenario = build_controlled_scenarios()[0]  # exp_01_boundary_shift
    reg = create_scenario_registry(scenario, db_path=db_file)
    candidates = ArchitectureGenerator().generate_candidates(include_async=True)

    # Initial pre-experiment baseline simulation
    engine = SimPyEngine(reg)
    sims = [engine.simulate_architecture(c, scenario.workload, duration_seconds=3.0) for c in candidates]
    from orbit.evaluation.recommender import ArchitectureRecommender
    initial_rec = ArchitectureRecommender.evaluate_and_recommend(scenario.workload, sims)
    assert initial_rec.selected_architecture_id == "arch_a_simple"  # Optimistic prior picks cheap arch_a

    # Prepare closed-loop investigation state
    auth = AuthorizationRecord(
        authorization_id="auth_closed_loop",
        proposal_id="prop_closed_loop",
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    state = {
        "workload_spec": scenario.workload,
        "candidate_architectures": candidates,
        "simulation_results": sims,
        "recommendation": initial_rec,
        "investigation_trace": [],
        "investigation_round": 0,
        "enable_active_experimentation": True,
        "experiment_authorization": auth,
        "component_registry": reg,
    }

    dispatcher = InvestigationDispatcher(registry=reg)
    decision = InvestigationDecision(
        action=InvestigationActionType.EXECUTE_EXPERIMENT,
        target="postgres_db",
        reason="Execute authorized experiment to resolve database saturation boundary.",
        experiment_proposal=ExperimentProposal(
            proposal_id="prop_closed_loop",
            target_component="postgres_db",
            version="postgres:16-alpine",
            hypothesis="Benchmark postgres under offered load",
            unknown_being_investigated="postgres service demand",
            concurrency_levels=[1, 4, 8, 16, 24],
            read_ratio=scenario.workload.read_ratio,
        ),
    )

    updates, record = dispatcher.dispatch(decision, state, round_num=1)
    tool_out = record.tool_output
    assert tool_out.get("success") is True
    delta = tool_out.get("closed_loop_delta", {})

    # Recommendation must have changed from arch_a_simple to arch_b_cached!
    assert delta.get("recommendation_changed") is True
    assert delta.get("previous_winner") == "arch_a_simple"
    assert delta.get("new_winner") == "arch_b_cached"
    assert delta.get("model_promoted") is True


# --------------------------------------------------------------------------
# 6. Comparative Strategy Evaluation (Offline & Credential-Free)
# --------------------------------------------------------------------------

def test_comparative_strategies_on_controlled_scenarios():
    """
    Executes all 4 comparative strategies across controlled scenarios and validates:
    - Baseline (Strategy 1) fails on boundary shift scenario (misses SLA violation)
    - Active experimentation (Strategies 2, 3, 4) prevents SLA violation by pivoting to arch_b_cached
    - Strategy 3 avoids redundant experiments when SLA margin is high
    """
    scenarios = build_controlled_scenarios()
    s1 = scenarios[0]  # exp_01_boundary_shift
    s2 = scenarios[1]  # exp_02_confirmed_margin

    # Scenario 1: Boundary shift
    r1 = run_strategy_1_baseline_no_experiments(s1)
    r2 = run_strategy_2_fixed_experiments(s1)
    r3 = run_strategy_3_deterministic_active(s1)
    r4 = run_strategy_4_agent_active(s1, mode="offline")

    assert r1.correct_under_ground_truth is False
    assert r1.selected_architecture_id == "arch_a_simple"

    assert r2.correct_under_ground_truth is True
    assert r2.selected_architecture_id == "arch_b_cached"
    assert r2.recommendation_changed is True

    assert r3.correct_under_ground_truth is True
    assert r3.selected_architecture_id == "arch_b_cached"
    assert r3.recommendation_changed is True

    assert r4.correct_under_ground_truth is True
    assert r4.selected_architecture_id == "arch_b_cached"
    assert r4.recommendation_changed is True

    # Scenario 2: Confirmed margin (low load)
    r3_s2 = run_strategy_3_deterministic_active(s2)
    # Strategy 3 should recognize high headroom and avoid redundant experiment
    assert r3_s2.experiments_executed_count == 0
    assert r3_s2.correct_under_ground_truth is True
    assert r3_s2.selected_architecture_id == "arch_a_simple"
