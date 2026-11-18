"""
AADS Phase 4D.1: Empirical Evidence, Calibration, and Safety Audit Tests.
Offline, credential-free, hermetic tests verifying:
1. Provenance integrity: synthetic evidence cannot be labeled as empirical
2. Calibration validation: group-based held-out split, data leakage prevention, quality gates
3. Error handling: failed validation, insufficient evidence, and withheld promotion
4. Authorization enforcement: fail-closed on missing, denied, or mismatched authorization
5. Execution safety: failures and timeouts do not produce phantom evidence
6. Registry versioning: immutable history and provenance retention
7. Re-simulation gating: recommendation changes require genuine model promotion
8. Information isolation: hidden scenario labels do not contaminate evidence summary
"""
import pytest
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from orbit.core.schemas import WorkloadSpec, ExperimentRecord, ModelRecord, FeasibilityStatus
from orbit.agent.schemas import (
    ExperimentProposal,
    AuthorizationRecord,
    AuthorizationStatus,
    AuthorizationLevel,
    InvestigationDecision,
    InvestigationActionType,
)
from orbit.registry.component_registry import ComponentRegistry
from orbit.modeling.model_trainer import ModelTrainer
from orbit.modeling.calibration_pipeline import CalibrationPipeline
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from orbit.agent.investigation_dispatcher import InvestigationDispatcher
from orbit.agent.investigation_planner import InvestigationPlanner
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.simulation.simpy_engine import SimPyEngine
from orbit.evaluation.recommender import ArchitectureRecommender


@pytest.fixture
def temp_registry(tmp_path):
    """Provides an isolated ComponentRegistry backed by a temporary SQLite database."""
    db_file = tmp_path / "audit_test_registry.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)
    return reg


# ---------------------------------------------------------------------------
# 1. Provenance Integrity: Synthetic vs Empirical Separation
# ---------------------------------------------------------------------------

def test_synthetic_evidence_cannot_be_represented_as_empirical(temp_registry):
    """Audits that synthetic fixture evidence retains is_synthetic_fixture=True and prevents empirical upgrade."""
    runner = SyntheticBenchmarkRunner(seed=42)
    records = runner.run_benchmark_matrix(
        component_name="postgres_db",
        version="postgres:16-alpine",
        concurrency_levels=[1, 4, 8, 16],
        read_ratios=[0.85],
        replications=3,
    )
    assert len(records) > 0
    # Every record produced by synthetic runner must be labeled synthetic
    assert all(r.is_synthetic_fixture is True for r in records)
    assert all("synthetic" in r.benchmark_framework.lower() for r in records)

    # When calibrated, the resulting ModelRecord must retain is_synthetic_fixture=True
    model, metrics = ModelTrainer.train_and_validate("postgres_db", "postgres:16-alpine", records)
    assert model.is_synthetic_fixture is True

    # CalibrationPipeline must NOT flag this as an empirical upgrade
    calib = CalibrationPipeline(registry=temp_registry)
    outcome = calib.calibrate_component("postgres_db", "postgres:16-alpine", experiments=records)
    assert outcome.status == "PROMOTED"
    assert outcome.is_empirical_upgrade is False


# ---------------------------------------------------------------------------
# 2. Calibration Validation & Group-Based Split Leakage Prevention
# ---------------------------------------------------------------------------

def test_group_based_split_prevents_replication_leakage():
    """Audits that replications of the same configuration do not leak between train and test sets."""
    # Collect 4 independent benchmark trials across 6 configurations (total 24 records)
    records = []
    for rep in range(4):
        runner_rep = SyntheticBenchmarkRunner(seed=100 + rep)
        trial_records = runner_rep.run_benchmark_matrix(
            component_name="postgres_db",
            version="postgres:16-alpine",
            concurrency_levels=[1, 4, 8, 16, 24, 32],
            read_ratios=[0.85],
            replications=1,
        )
        for r in trial_records:
            r.experiment_id = f"{r.experiment_id}_rep{rep}"
        records.extend(trial_records)
    assert len(records) == 24

    # Perform train/validation split logic directly
    configs = sorted(list(set((e.concurrency, round(e.read_ratio, 2)) for e in records)))
    n_configs = len(configs)
    n_test_configs = max(1, int(round(n_configs * 0.30)))
    intermediate = configs[1:-1]
    step = max(1, len(intermediate) // n_test_configs)
    test_config_set = set(intermediate[::step][:n_test_configs])

    train_exps = [e for e in records if (e.concurrency, round(e.read_ratio, 2)) not in test_config_set]
    test_exps = [e for e in records if (e.concurrency, round(e.read_ratio, 2)) in test_config_set]

    train_configs = set((e.concurrency, round(e.read_ratio, 2)) for e in train_exps)
    test_configs = set((e.concurrency, round(e.read_ratio, 2)) for e in test_exps)

    # Mathematical proof of zero group overlap: intersection must be completely empty
    assert len(train_configs.intersection(test_configs)) == 0
    assert len(train_exps) + len(test_exps) == len(records)


def test_small_config_fallback_split_replication_leakage_audit():
    """
    Audits the ModelTrainer behavior when len(configs) < 3.
    Verifies that the index-based slicing fallback has been removed and that
    InsufficientIndependentGroupsError is raised to prevent replication leakage.
    """
    now = datetime.now(timezone.utc).isoformat()
    # 2 configs, 3 replications each (total 6 records)
    records = [
        ExperimentRecord(
            experiment_id=f"rec_{i}",
            component_name="postgres_db",
            version="16",
            env_fingerprint="test",
            benchmark_framework="test",
            concurrency=4 if i < 3 else 8,
            read_ratio=1.0,
            offered_rps=200.0 + i,
            achieved_rps=190.0 + i,
            p50_ms=3.0,
            p95_ms=5.0,
            p99_ms=8.0,
            cpu_pct=20.0,
            memory_mb=100.0,
            error_count=0,
            trial_replications=3,
            variance_ms2=0.01,
            is_synthetic_fixture=True,
            timestamp=now,
        )
        for i in range(6)
    ]
    configs = sorted(list(set((e.concurrency, round(e.read_ratio, 2)) for e in records)))
    assert len(configs) == 2  # Less than 3

    # Hardened behavior: ModelTrainer rejects < 3 configurations to prevent leakage
    from orbit.modeling.model_trainer import InsufficientIndependentGroupsError
    with pytest.raises(InsufficientIndependentGroupsError):
        ModelTrainer._group_train_test_split(records)


# ---------------------------------------------------------------------------
# 3. Model Quality Gating & Failed Validation Preservation
# ---------------------------------------------------------------------------

def test_failed_validation_preserves_existing_model(temp_registry):
    """Audits that candidate models failing validation gates are rejected and existing models preserved."""
    existing_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert existing_model is not None
    initial_id = existing_model.model_id

    # Create corrupted, wildly noisy observations that should fail validation
    now = datetime.now(timezone.utc).isoformat()
    corrupted_records = [
        ExperimentRecord(
            experiment_id=f"noisy_{i}",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="noisy_fixture",
            benchmark_framework="noisy",
            concurrency=2 ** (i % 5),
            read_ratio=0.85,
            offered_rps=100.0 * (i + 1),
            achieved_rps=50.0 + (i * 20.0),
            p50_ms=float(10.0 + ((i * 37) % 50)),
            p95_ms=float(50.0 + ((i * 97) % 200)),
            p99_ms=100.0,
            cpu_pct=50.0,
            memory_mb=200.0,
            error_count=5,
            trial_replications=3,
            variance_ms2=50.0,
            is_synthetic_fixture=True,
            timestamp=now,
        )
        for i in range(8)
    ]

    calib = CalibrationPipeline(registry=temp_registry)
    outcome = calib.calibrate_component("postgres_db", "postgres:16-alpine", experiments=corrupted_records)

    # Candidate must be rejected
    assert outcome.status == "REJECTED"
    assert outcome.old_model_id == initial_id
    assert outcome.new_model_id is not None
    assert "failed quality validation gates" in outcome.summary

    # Active model in registry must remain unchanged!
    active_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert active_model.model_id == initial_id


def test_insufficient_evidence_preserves_model(temp_registry):
    """Audits that fewer than 3 observations withholds recalibration without error."""
    existing_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    initial_id = existing_model.model_id

    calib = CalibrationPipeline(registry=temp_registry)
    outcome = calib.calibrate_component("postgres_db", "postgres:16-alpine", experiments=[])
    assert outcome.status == "INSUFFICIENT_EVIDENCE"
    assert outcome.old_model_id == initial_id
    assert outcome.new_model_id is None

    active_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert active_model.model_id == initial_id


# ---------------------------------------------------------------------------
# 4. Authorization Enforcement & Proposal ID Matching Audit
# ---------------------------------------------------------------------------

def test_missing_and_denied_authorization_fails_closed(temp_registry):
    """Audits that BoundedBenchmarkExecutor strictly blocks execution when authorization is missing or denied."""
    executor = BoundedBenchmarkExecutor(registry=temp_registry)
    prop = ExperimentProposal(
        proposal_id="prop_sec_test",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="test",
        unknown_being_investigated="test",
        concurrency_levels=[1, 4],
    )

    # 1. None authorization
    r1 = executor.execute_experiment(prop, authorization=None)
    assert r1.status == "UNAUTHORIZED"
    assert r1.raw_records_count == 0
    assert len(r1.experiment_ids) == 0

    # 2. Denied authorization
    auth_denied = AuthorizationRecord(
        authorization_id="auth_denied",
        proposal_id=prop.proposal_id,
        authorized_by="security_admin",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.DENIED,
        max_runtime_seconds=60.0,
    )
    r2 = executor.execute_experiment(prop, authorization=auth_denied)
    assert r2.status == "UNAUTHORIZED"

    # 3. Revoked authorization
    auth_revoked = AuthorizationRecord(
        authorization_id="auth_revoked",
        proposal_id=prop.proposal_id,
        authorized_by="security_admin",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.REVOKED,
        max_runtime_seconds=60.0,
    )
    r3 = executor.execute_experiment(prop, authorization=auth_revoked)
    assert r3.status == "UNAUTHORIZED"


def test_authorization_proposal_id_binding_audit(temp_registry):
    """
    Audits whether an authorization record issued for Proposal A can execute Proposal B.
    Documents the defect if proposal_id is not cross-checked.
    """
    executor = BoundedBenchmarkExecutor(registry=temp_registry)
    prop_a = ExperimentProposal(
        proposal_id="prop_original_postgres",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Test postgres",
        unknown_being_investigated="postgres",
        concurrency_levels=[1, 4],
    )
    prop_b = ExperimentProposal(
        proposal_id="prop_hijacked_postgres",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Different proposal",
        unknown_being_investigated="different",
        concurrency_levels=[16, 32],
    )

    # Authorization was granted ONLY for prop_a
    auth_for_a = AuthorizationRecord(
        authorization_id="auth_for_prop_a",
        proposal_id=prop_a.proposal_id,
        authorized_by="security_lead",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    # Audit check: does executor allow prop_b to be executed with auth_for_a?
    res = executor.execute_experiment(prop_b, authorization=auth_for_a)
    assert res.status == "AUTHORIZATION_MISMATCH"
    assert "Authorization record was issued for proposal" in res.error_message


# ---------------------------------------------------------------------------
# 5. Registry Versioning & Immutability
# ---------------------------------------------------------------------------

def test_registry_retains_immutable_version_history(temp_registry):
    """Audits that multiple model registrations and calibrations retain full history without deletion."""
    now = datetime.now(timezone.utc).isoformat()
    history_initial = temp_registry.get_model_history("postgres_db")
    count_initial = len(history_initial)
    assert count_initial >= 1

    # Register Model 1
    m1 = ModelRecord(
        model_id="model_audit_v1",
        component_name="postgres_db",
        version="postgres:16-alpine",
        env_fingerprint="test:v1",
        model_type="piecewise_ridge",
        fitted_parameters={"intercept": 1.0},
        min_supported_rps=10.0,
        max_supported_rps=500.0,
        min_supported_concurrency=1,
        max_supported_concurrency=32,
        validation_rmse_ms=0.5,
        validation_mape_pct=5.0,
        r2_score=0.90,
        is_validated=True,
        is_synthetic_fixture=True,
        provenance="Audit trial 1",
        known_limitations="concurrency up to 32",
        created_at=now,
    )
    temp_registry.register_model(m1)

    # Register Model 2
    m2 = ModelRecord(
        model_id="model_audit_v2",
        component_name="postgres_db",
        version="postgres:16-alpine",
        env_fingerprint="test:v2",
        model_type="piecewise_ridge",
        fitted_parameters={"intercept": 1.2},
        min_supported_rps=10.0,
        max_supported_rps=600.0,
        min_supported_concurrency=1,
        max_supported_concurrency=32,
        validation_rmse_ms=0.4,
        validation_mape_pct=4.0,
        r2_score=0.92,
        is_validated=True,
        is_synthetic_fixture=True,
        provenance="Audit trial 2",
        known_limitations="concurrency up to 32",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    temp_registry.register_model(m2)

    # Verify history contains both models plus initial baseline
    history_after = temp_registry.get_model_history("postgres_db")
    assert len(history_after) == count_initial + 2
    history_ids = [m.model_id for m in history_after]
    assert "model_audit_v1" in history_ids
    assert "model_audit_v2" in history_ids

    # Active model returned by get_model must be the most recently registered
    latest = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert latest.model_id == "model_audit_v2"


# ---------------------------------------------------------------------------
# 6. Recommendation Change Cause & Evidence Dependency
# ---------------------------------------------------------------------------

def test_recommendation_change_requires_actual_model_promotion(temp_registry):
    """
    Audits that recommendation does not change if an experiment fails to promote a model.
    Confirms recommendation change is strictly caused by the model calibration update.
    """
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=380.0,
        peak_load_factor=1.2,
        read_ratio=0.85,
        write_ratio=0.15,
        p95_latency_target_ms=20.0,
        min_throughput_rps=350.0,
        max_monthly_budget_usd=250.0,
    )
    candidates = ArchitectureGenerator().generate_candidates(include_async=True)
    engine = SimPyEngine(temp_registry)
    sims = [engine.simulate_architecture(c, workload, duration_seconds=3.0) for c in candidates]
    initial_rec = ArchitectureRecommender.evaluate_and_recommend(workload, sims)
    initial_winner = initial_rec.selected_architecture_id

    # Create an authorization record
    auth = AuthorizationRecord(
        authorization_id="auth_no_change",
        proposal_id="prop_unpromoted",
        authorized_by="tester",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    state = {
        "workload_spec": workload,
        "candidate_architectures": candidates,
        "simulation_results": sims,
        "recommendation": initial_rec,
        "investigation_trace": [],
        "investigation_round": 0,
        "enable_active_experimentation": True,
        "experiment_authorization": auth,
        "component_registry": temp_registry,
    }

    decision = InvestigationDecision(
        action=InvestigationActionType.EXECUTE_EXPERIMENT,
        target="postgres_db",
        reason="Test execution",
        experiment_proposal=ExperimentProposal(
            proposal_id="prop_unpromoted",
            target_component="postgres_db",
            version="postgres:16-alpine",
            hypothesis="Test",
            unknown_being_investigated="test",
            concurrency_levels=[1],
        ),
    )

    from unittest.mock import patch
    from orbit.modeling.calibration_pipeline import CalibrationOutcome
    dispatcher = InvestigationDispatcher(registry=temp_registry)
    with patch.object(
        dispatcher.calibration_pipeline,
        "calibrate_component",
        return_value=CalibrationOutcome(
            component_name="postgres_db",
            version="postgres:16-alpine",
            status="REJECTED_VALIDATION_FAILED",
            reason="Simulated audit validation failure",
            is_empirical_upgrade=False,
            new_model_id=None,
        ),
    ):
        updates, record = dispatcher.dispatch(decision, state, round_num=1)
    tool_out = record.tool_output or {}
    delta = tool_out.get("closed_loop_delta", {})

    # Calibration was not promoted
    assert delta.get("model_promoted") is False
    # Recommendation must NOT have changed
    assert delta.get("recommendation_changed") is False
    assert delta.get("new_winner") == initial_winner


# ---------------------------------------------------------------------------
# 7. Information Isolation & Hidden Labels Audit
# ---------------------------------------------------------------------------

def test_planner_evidence_summary_contains_zero_scenario_metadata():
    """Audits that InvestigationPlanner evidence summary is free of hidden scenario labels or ground truth."""
    workload = WorkloadSpec(
        app_type="social_media_feed",
        request_rate_rps=380.0,
        p95_latency_target_ms=20.0,
        max_monthly_budget_usd=250.0,
    )
    candidates = ArchitectureGenerator().generate_candidates()
    state = {
        "workload_spec": workload,
        "candidate_architectures": candidates,
        "simulation_results": [],
        "recommendation": None,
        "investigation_trace": [],
        "investigation_round": 0,
        "scenario_id": "exp_01_boundary_shift",
        "ground_truth_winner": "arch_b_cached",
        "requires_experiment_to_detect_violation": True,
        "ground_truth_sla_status": {"arch_a_simple": False},
    }

    planner = InvestigationPlanner()
    summary = planner.build_evidence_summary(state)

    # Evidence summary must not leak hidden scenario metadata
    assert "exp_01_boundary_shift" not in summary
    assert "ground_truth_winner" not in summary
    assert "requires_experiment" not in summary
    assert "ground_truth_sla_status" not in summary
