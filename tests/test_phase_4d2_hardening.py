"""
Unit and Integration Tests for Phase 4D.2 Benchmark Integrity, Authorization and Calibration Hardening.
Verifies:
1. Docker benchmark runner fail closed, strict returncode checking, container cleanup, and error handling.
2. Real empirical tail percentiles from pgbench transaction logs (p50/p95/p99) without multiplier formulas.
3. Authorization binding (proposal_id match) and single-use lifecycle (replay prevention).
4. Subprocess timeout and resource envelope enforcement.
5. Calibration split integrity (rejection of < 3 independent groups, zero replication leakage).
6. Mathematically honest R2 metric (None on zero variance; never defaults to 0.90).
7. Strict separation of synthetic fixtures and empirical evidence.
All tests run offline without requiring Docker.
"""
import math
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from orbit.agent.schemas import (
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentProposal,
    ExperimentExecutionResult,
)
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.benchmark.docker_runner import (
    DockerBenchmarkRunner,
    PgbenchOutputParser,
    RedisBenchmarkParser,
)
from orbit.benchmark.runner_interface import BenchmarkRunner
from orbit.core.schemas import ExperimentRecord, ModelRecord
from orbit.modeling.calibration_pipeline import CalibrationPipeline, CalibrationOutcome
from orbit.modeling.lookup_model import LookupInterpolationModel
from orbit.modeling.model_trainer import ModelTrainer, InsufficientIndependentGroupsError
from orbit.modeling.regression_model import RegressionPerformanceModel
from orbit.registry.component_registry import ComponentRegistry


@pytest.fixture
def temp_registry(tmp_path):
    """Provides an isolated SQLite registry seeded with clean baseline models."""
    db_file = tmp_path / "hardening_registry.db"
    reg = ComponentRegistry(db_path=db_file)
    reg.seed_baseline_data(force=True)
    return reg


# ===========================================================================
# 1. Docker Benchmark Runner & Parser Fail Closed Tests
# ===========================================================================

def test_pgbench_parser_clean_summary():
    """Verifies that standard pgbench stdout is parsed accurately."""
    stdout = """
    transaction type: <builtin: select-only>
    scaling factor: 2
    query mode: simple
    number of clients: 16
    number of threads: 4
    maximum number of tries: 1
    duration: 3 s
    number of transactions actually processed: 4892
    number of failed transactions: 0
    latency average = 0.613 ms
    initial connection time = 12.450 ms
    tps = 1630.723412 (without initial connection time)
    """
    summary = PgbenchOutputParser.parse_summary(stdout)
    assert round(summary["tps"], 2) == 1630.72
    assert summary["latency_avg_ms"] == 0.613
    assert summary["failed_transactions"] == 0
    assert summary["total_transactions"] == 4892


def test_pgbench_parser_rejects_empty_or_malformed():
    """Verifies that missing, empty, or non-finite outputs raise ValueError."""
    with pytest.raises(ValueError, match="pgbench stdout is empty"):
        PgbenchOutputParser.parse_summary("")

    malformed = "Error: database connection lost"
    with pytest.raises(ValueError, match="Failed to parse TPS metric"):
        PgbenchOutputParser.parse_summary(malformed)

    zero_tps = "tps = 0.000\nlatency average = 5.0 ms"
    with pytest.raises(ValueError, match="Invalid non-positive or non-finite TPS"):
        PgbenchOutputParser.parse_summary(zero_tps)


def test_pgbench_parser_empirical_transaction_logs():
    """
    Verifies that transaction-level logs produce empirical percentiles (p50/p95/p99)
    using numpy linear quantiles rather than fixed multiplier formulas.
    """
    # 100 transaction log lines with latencies from 1.0ms to 100.0ms (1000us to 100000us)
    lines = []
    for i in range(1, 101):
        time_us = i * 1000  # 1ms to 100ms
        lines.append(f"0 {i} {time_us} 0 1698765432 100000")
    log_text = "\n".join(lines)

    stats = PgbenchOutputParser.parse_transaction_logs(log_text, min_samples=10)
    assert stats["sample_count"] == 100
    assert stats["units"] == "ms"
    assert stats["quantile_method"] == "linear"

    # Empirical percentiles:
    # 50th percentile of [1..100] is 50.5 ms
    # 95th percentile is 95.05 ms
    # 99th percentile is 99.01 ms
    assert abs(stats["p50_ms"] - 50.5) < 0.2
    assert abs(stats["p95_ms"] - 95.05) < 0.2
    assert abs(stats["p99_ms"] - 99.01) < 0.2

    # Verify these values are NOT the old multiplier rule (lat_avg * 1.6 = 50.5 * 1.6 = 80.8 != 95.05)
    mean_lat = stats["mean_ms"]
    assert stats["p95_ms"] != round(mean_lat * 1.60, 2)


def test_pgbench_parser_rejects_insufficient_or_corrupt_logs():
    """Verifies that empty or insufficient transaction logs fail closed."""
    with pytest.raises(ValueError, match="Transaction log is empty"):
        PgbenchOutputParser.parse_transaction_logs("")

    # Only 3 samples when 10 are required
    short_log = "0 1 1500 0\n0 2 2000 0\n0 3 2500 0\n"
    with pytest.raises(ValueError, match="Insufficient transaction samples"):
        PgbenchOutputParser.parse_transaction_logs(short_log, min_samples=10)


def test_redis_parser_clean_and_percentiles():
    """Verifies that redis-benchmark throughput and percentiles are parsed accurately."""
    stdout = """
    ====== GET ======
      20000 requests completed in 0.22 seconds
      50 parallel clients
      3 bytes payload
      keep alive: 1

    91234.50 requests per second
    p50=0.312 msec
    p95=0.589 msec
    p99=0.941 msec
    """
    res = RedisBenchmarkParser.parse_summary_and_percentiles(stdout)
    assert res["achieved_rps"] == 91234.5
    assert res["p50_ms"] == 0.312
    assert res["p95_ms"] == 0.589
    assert res["p99_ms"] == 0.941


def test_redis_parser_rejects_missing_percentiles():
    """Verifies that redis-benchmark output without tail percentiles fails closed."""
    stdout = "GET: 80000.00 requests per second"
    with pytest.raises(ValueError, match="missing required empirical p50/p95/p99"):
        RedisBenchmarkParser.parse_summary_and_percentiles(stdout)


def test_docker_runner_rejects_nonzero_exit_code():
    """
    Verifies that non-zero returncodes raise RuntimeError and never produce
    default 100 TPS or 5 ms records.
    """
    runner = DockerBenchmarkRunner()

    def mock_subp(cmd, **kwargs):
        if cmd[0] == "uname":
            return MagicMock(returncode=0, stdout="x86_64")
        if cmd[:2] == ["docker", "info"]:
            return MagicMock(returncode=0, stdout="24.0.5")
        if cmd[:2] == ["docker", "run"]:
            return MagicMock(returncode=1, stderr="Error response from daemon: conflict")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=mock_subp) as mock_run:
        with pytest.raises(RuntimeError, match="Failed to start PostgreSQL container"):
            runner.run_benchmark_matrix("postgres_db", "16-alpine", [1])


def test_docker_runner_enforces_cleanup_on_timeout():
    """
    Verifies that if a benchmark execution times out, container cleanup is guaranteed.
    """
    runner = DockerBenchmarkRunner()
    cleanup_called = False

    def mock_subp(cmd, **kwargs):
        nonlocal cleanup_called
        if cmd[0] == "uname":
            return MagicMock(returncode=0, stdout="x86_64")
        if cmd[:2] == ["docker", "info"]:
            return MagicMock(returncode=0, stdout="24.0.5")
        if cmd[:2] == ["docker", "run"]:
            return MagicMock(returncode=0)
        if cmd[:2] == ["docker", "exec"] and "pg_isready" in cmd:
            return MagicMock(returncode=0)
        if cmd[:2] == ["docker", "exec"] and "pgbench" in cmd and "-i" in cmd:
            return MagicMock(returncode=0)
        if cmd[:2] == ["docker", "exec"] and "pgbench" in cmd and "-T" in cmd and "-c" in cmd and "2" in cmd:
            return MagicMock(returncode=0)
        if cmd[:2] == ["docker", "exec"] and "pgbench" in cmd and "-S" in cmd:
            raise subprocess.TimeoutExpired(cmd="pgbench", timeout=15)
        if cmd[:3] == ["docker", "rm", "-f"]:
            cleanup_called = True
            return MagicMock(returncode=0)
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=mock_subp):
        with pytest.raises(subprocess.TimeoutExpired):
            runner.run_benchmark_matrix("postgres_db", "16-alpine", [4])

    assert cleanup_called is True, "docker rm -f cleanup must be called upon timeout"


# ===========================================================================
# 2. Authorization Binding & Single-Use Lifecycle Tests
# ===========================================================================

def test_executor_rejects_mismatched_proposal_id(temp_registry):
    """
    Verifies that BoundedBenchmarkExecutor rejects authorization issued for Proposal A
    when executing Proposal B, without ever invoking the benchmark runner.
    """
    spy_runner = MagicMock(spec=BenchmarkRunner)
    executor = BoundedBenchmarkExecutor(
        registry=temp_registry,
        synthetic_runner=spy_runner,
    )

    prop_target = ExperimentProposal(
        proposal_id="prop_real_workload",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Target proposal",
        unknown_being_investigated="capacity",
        concurrency_levels=[1, 4],
    )

    auth_mismatched = AuthorizationRecord(
        authorization_id="auth_other_task",
        proposal_id="prop_different_workload",  # Mismatch!
        authorized_by="operator",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    result = executor.execute_experiment(prop_target, authorization=auth_mismatched)

    assert result.status == "AUTHORIZATION_MISMATCH"
    assert "Authorization record was issued for proposal" in result.error_message
    assert result.raw_records_count == 0

    # Critical security assertion: benchmark runner was NEVER called
    spy_runner.run_benchmark_matrix.assert_not_called()


def test_executor_rejects_replay_of_used_authorization(temp_registry):
    """
    Verifies that an authorization record cannot be replayed or reused.
    """
    executor = BoundedBenchmarkExecutor(registry=temp_registry)

    prop = ExperimentProposal(
        proposal_id="prop_single_use_test",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Test replay",
        unknown_being_investigated="test",
        concurrency_levels=[1, 4],
    )

    auth = AuthorizationRecord(
        authorization_id="auth_single_use_001",
        proposal_id=prop.proposal_id,
        authorized_by="security_auditor",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    # First run succeeds
    res1 = executor.execute_experiment(prop, authorization=auth)
    assert res1.status == "SUCCESS"
    assert auth.status == AuthorizationStatus.EXHAUSTED

    # Replay attempt with same authorization must be rejected
    res2 = executor.execute_experiment(prop, authorization=auth)
    assert res2.status == "AUTHORIZATION_EXHAUSTED"
    assert "has already been consumed" in res2.error_message


def test_executor_rejects_unauthorized_component(temp_registry):
    """Verifies that components outside the authorized allowlist are rejected."""
    executor = BoundedBenchmarkExecutor(registry=temp_registry)

    prop = ExperimentProposal(
        proposal_id="prop_unauthorized_comp",
        target_component="arbitrary_untrusted_service",
        version="latest",
        hypothesis="Test",
        unknown_being_investigated="test",
        concurrency_levels=[1],
    )

    auth = AuthorizationRecord(
        authorization_id="auth_untrusted",
        proposal_id=prop.proposal_id,
        authorized_by="tester",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,
    )

    res = executor.execute_experiment(prop, authorization=auth)
    assert res.status == "UNAUTHORIZED_COMPONENT"
    assert "not in approved benchmark allowlist" in res.error_message


def test_executor_rejects_excessive_runtime(temp_registry):
    """Verifies that requested timeouts exceeding authorized limit fail closed."""
    executor = BoundedBenchmarkExecutor(registry=temp_registry)

    prop = ExperimentProposal(
        proposal_id="prop_too_long",
        target_component="postgres_db",
        version="postgres:16-alpine",
        hypothesis="Long benchmark",
        unknown_being_investigated="test",
        concurrency_levels=[1],
        timeout_seconds=300,  # 300s requested
    )

    auth = AuthorizationRecord(
        authorization_id="auth_capped",
        proposal_id=prop.proposal_id,
        authorized_by="security",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        execution_mode="synthetic",
        status=AuthorizationStatus.AUTHORIZED,
        max_runtime_seconds=60.0,  # Only 60s authorized
    )

    res = executor.execute_experiment(prop, authorization=auth)
    assert res.status == "RESOURCE_LIMIT_EXCEEDED"
    assert "exceeds authorized max runtime" in res.error_message


# ===========================================================================
# 3. Calibration Split Integrity & Independent Groups Tests
# ===========================================================================

def test_trainer_rejects_single_configuration_multiple_replications():
    """
    Verifies that a dataset with 1 configuration across many replications
    fails closed with InsufficientIndependentGroupsError.
    """
    now = datetime.now(timezone.utc).isoformat()
    # 10 replications of a single concurrency=4 config
    single_config_exps = [
        ExperimentRecord(
            experiment_id=f"exp_rep_{i}",
            component_name="postgres_db",
            version="16-alpine",
            env_fingerprint="test",
            benchmark_framework="test",
            concurrency=4,
            read_ratio=1.0,
            offered_rps=200.0,
            achieved_rps=195.0 + i * 0.1,
            p50_ms=2.5,
            p95_ms=4.8,
            p99_ms=6.0,
            cpu_pct=30.0,
            memory_mb=120.0,
            error_count=0,
            trial_replications=1,
            variance_ms2=0.01,
            is_synthetic_fixture=True,
            timestamp=now,
        )
        for i in range(10)
    ]

    with pytest.raises(InsufficientIndependentGroupsError, match="Need at least 3 independent experimental configurations"):
        ModelTrainer._group_train_test_split(single_config_exps)


def test_trainer_rejects_two_configurations_with_replications():
    """
    Verifies that a dataset with only 2 configurations across multiple replications
    is rejected rather than using naive index slicing.
    """
    now = datetime.now(timezone.utc).isoformat()
    two_config_exps = []
    for c in [4, 8]:
        for rep in range(4):
            two_config_exps.append(
                ExperimentRecord(
                    experiment_id=f"exp_{c}_{rep}",
                    component_name="postgres_db",
                    version="16-alpine",
                    env_fingerprint="test",
                    benchmark_framework="test",
                    concurrency=c,
                    read_ratio=1.0,
                    offered_rps=c * 50.0,
                    achieved_rps=c * 48.0,
                    p50_ms=2.0 + rep * 0.1,
                    p95_ms=4.0 + rep * 0.2,
                    p99_ms=6.0,
                    cpu_pct=30.0,
                    memory_mb=120.0,
                    error_count=0,
                    trial_replications=1,
                    variance_ms2=0.01,
                    is_synthetic_fixture=True,
                    timestamp=now,
                )
            )

    with pytest.raises(InsufficientIndependentGroupsError, match="Need at least 3 independent experimental configurations"):
        ModelTrainer._group_train_test_split(two_config_exps)


def test_trainer_accepts_sufficient_configurations_zero_leakage():
    """
    Verifies that when >= 3 configurations exist, group split assigns all replications
    strictly to either train or test, with mathematically zero overlap.
    """
    now = datetime.now(timezone.utc).isoformat()
    multi_exps = []
    for c in [1, 4, 8, 16, 24, 32]:
        for rep in range(3):
            multi_exps.append(
                ExperimentRecord(
                    experiment_id=f"exp_{c}_{rep}",
                    component_name="postgres_db",
                    version="16-alpine",
                    env_fingerprint="test",
                    benchmark_framework="test",
                    concurrency=c,
                    read_ratio=0.85,
                    offered_rps=c * 40.0,
                    achieved_rps=c * 38.0,
                    p50_ms=2.0 + c * 0.1,
                    p95_ms=4.0 + c * 0.3,
                    p99_ms=6.0 + c * 0.5,
                    cpu_pct=min(90.0, c * 3.0),
                    memory_mb=150.0,
                    error_count=0,
                    trial_replications=1,
                    variance_ms2=0.01,
                    is_synthetic_fixture=True,
                    timestamp=now,
                )
            )

    train_exps, test_exps = ModelTrainer._group_train_test_split(multi_exps, test_ratio=0.30)
    train_concs = set(e.concurrency for e in train_exps)
    test_concs = set(e.concurrency for e in test_exps)

    # Prove zero leakage
    assert len(train_concs.intersection(test_concs)) == 0
    # Prove boundary points policy: min and max concurrency are in train set
    assert 1 in train_concs
    assert 32 in train_concs
    # Test set contains intermediate configurations
    assert len(test_concs) > 0
    assert not test_concs.issubset({1, 32})


# ===========================================================================
# 4. Honest Model-Quality Metrics Tests
# ===========================================================================

def test_honest_r2_on_constant_target_is_none():
    """
    Audits that when actual target has zero variance (SS_tot <= 1e-6),
    R2 is represented honestly as None, and does NOT claim validation pass.
    """
    now = datetime.now(timezone.utc).isoformat()
    # 6 configs where actual service time is completely constant at 2.0 ms
    constant_exps = []
    for c in [1, 4, 8, 16, 24, 32]:
        constant_exps.append(
            ExperimentRecord(
                experiment_id=f"exp_const_{c}",
                component_name="postgres_db",
                version="16-alpine",
                env_fingerprint="test",
                benchmark_framework="test",
                concurrency=c,
                read_ratio=1.0,
                offered_rps=c * 50.0,
                achieved_rps=c * 50.0,
                p50_ms=2.00,  # Exactly 2.00ms across all points
                p95_ms=3.00,
                p99_ms=4.00,
                cpu_pct=20.0,
                memory_mb=100.0,
                error_count=0,
                trial_replications=1,
                variance_ms2=0.0,
                is_synthetic_fixture=True,
                timestamp=now,
            )
        )

    model_rec, metrics = ModelTrainer.train_and_validate("postgres_db", "16-alpine", constant_exps)
    chosen = metrics["chosen_eval"]

    # R2 must be None (not 0.90!)
    assert chosen["r2"] is None
    assert model_rec.r2_score is None
    assert "UNDEFINED_ZERO_VARIANCE" in model_rec.provenance


def test_honest_metrics_handle_nonfinite_predictions_safely():
    """Verifies that non-finite predictions fail validation safely."""
    now = datetime.now(timezone.utc).isoformat()
    exps = [
        ExperimentRecord(
            experiment_id=f"exp_{c}",
            component_name="postgres_db",
            version="16-alpine",
            env_fingerprint="test",
            benchmark_framework="test",
            concurrency=c,
            read_ratio=1.0,
            offered_rps=c * 30.0,
            achieved_rps=c * 28.0,
            p50_ms=3.0,
            p95_ms=5.0,
            p99_ms=8.0,
            cpu_pct=25.0,
            memory_mb=100.0,
            error_count=0,
            trial_replications=1,
            variance_ms2=0.01,
            is_synthetic_fixture=True,
            timestamp=now,
        )
        for c in [1, 4, 8, 16, 24, 32]
    ]

    # Mock models to produce NaN
    with patch.object(RegressionPerformanceModel, "predict_service_time_ms", return_value=(float("nan"), 0.0, 0.0)), \
         patch.object(LookupInterpolationModel, "predict_service_time_ms", return_value=(float("nan"), 0.0, 0.0)):
        model_rec, metrics = ModelTrainer.train_and_validate("postgres_db", "16-alpine", exps)
        assert model_rec.is_validated is False
        assert metrics["is_validated"] is False


# ===========================================================================
# 5. Calibration Pipeline & Model Preservation Tests
# ===========================================================================

def test_calibration_pipeline_insufficient_groups_preserves_model(temp_registry):
    """
    Verifies that CalibrationPipeline returns INSUFFICIENT_INDEPENDENT_GROUPS
    when independent configurations are < 3, and preserves the active model in registry.
    """
    initial_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert initial_model is not None

    now = datetime.now(timezone.utc).isoformat()
    # 4 experiments but only 2 independent concurrency levels (4 and 8)
    underpowered_exps = [
        ExperimentRecord(
            experiment_id=f"under_{i}",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="test",
            benchmark_framework="test",
            concurrency=4 if i < 2 else 8,
            read_ratio=1.0,
            offered_rps=100.0,
            achieved_rps=95.0,
            p50_ms=3.0,
            p95_ms=5.0,
            p99_ms=7.0,
            cpu_pct=20.0,
            memory_mb=100.0,
            error_count=0,
            trial_replications=1,
            variance_ms2=0.01,
            is_synthetic_fixture=True,
            timestamp=now,
        )
        for i in range(4)
    ]

    pipeline = CalibrationPipeline(registry=temp_registry)
    outcome = pipeline.calibrate_component("postgres_db", "postgres:16-alpine", experiments=underpowered_exps)

    assert outcome.status == "INSUFFICIENT_INDEPENDENT_GROUPS"
    assert outcome.new_model_id is None
    assert "Insufficient independent experimental groups" in outcome.summary

    # Active model in registry must remain initial_model
    current = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert current.model_id == initial_model.model_id


def test_calibration_pipeline_synthetic_fixture_cannot_be_empirical_upgrade(temp_registry):
    """
    Verifies that a model calibrated on synthetic fixtures is never labeled as an empirical upgrade.
    """
    now = datetime.now(timezone.utc).isoformat()
    synth_exps = [
        ExperimentRecord(
            experiment_id=f"synth_{c}",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="test",
            benchmark_framework="test",
            concurrency=c,
            read_ratio=0.85,
            offered_rps=c * 30.0,
            achieved_rps=c * 28.0,
            p50_ms=2.0 + c * 0.1,
            p95_ms=4.0 + c * 0.3,
            p99_ms=6.0 + c * 0.5,
            cpu_pct=25.0,
            memory_mb=100.0,
            error_count=0,
            trial_replications=1,
            variance_ms2=0.01,
            is_synthetic_fixture=True,  # Synthetic!
            timestamp=now,
        )
        for c in [1, 4, 8, 16, 24, 32]
    ]

    pipeline = CalibrationPipeline(registry=temp_registry)
    outcome = pipeline.calibrate_component("postgres_db", "postgres:16-alpine", experiments=synth_exps)

    assert outcome.status == "PROMOTED"
    assert outcome.is_empirical_upgrade is False

    promoted_model = temp_registry.get_model("postgres_db", "postgres:16-alpine")
    assert promoted_model.is_synthetic_fixture is True
