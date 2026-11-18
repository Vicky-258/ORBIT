"""
Phase 4E.0 Pilot Readiness Verification Suite.
Validates the complete execution path, authorization lifecycle, provenance schema,
measurement semantics, and calibration safety before any real Docker benchmark is run.
All tests run strictly offline with unit mocks and fixtures.
"""
import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from orbit.agent.schemas import AuthorizationRecord, AuthorizationStatus, ExperimentProposal
from orbit.benchmark.bounded_executor import BoundedBenchmarkExecutor
from orbit.benchmark.docker_runner import DockerBenchmarkRunner, PgbenchOutputParser
from orbit.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from orbit.core.schemas import ExperimentRecord, ModelRecord
from orbit.modeling.calibration_pipeline import CalibrationPipeline
from orbit.modeling.model_trainer import InsufficientIndependentGroupsError, ModelTrainer
from orbit.registry.component_registry import ComponentRegistry


def _make_sample_exp(
    exp_id: str,
    concurrency: int,
    achieved_rps: float,
    p50_ms: float,
    p95_ms: float,
    read_ratio: float = 0.8,
    error_count: int = 0,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=exp_id,
        component_name="postgresql_db",
        version="16-alpine",
        concurrency=concurrency,
        read_ratio=read_ratio,
        offered_rps=round(achieved_rps * 1.05, 1),
        achieved_rps=achieved_rps,
        p50_ms=p50_ms,
        p90_ms=p95_ms * 0.9,
        p95_ms=p95_ms,
        p99_ms=p95_ms * 1.2,
        cpu_pct=25.0,
        memory_mb=128.0,
        error_count=error_count,
        env_fingerprint="test_host_env",
        is_synthetic_fixture=False,
        notes="readiness_test_fixture",
        timestamp="2026-10-30T10:00:00Z",
    )


# ---------------------------------------------------------------------------
# 1. Authorization Persistence Across Simulated Restarts
# ---------------------------------------------------------------------------

def test_authorization_persistence_across_simulated_restart(tmp_path):
    """
    Verify that an authorization marked EXHAUSTED is persisted to SQLite
    and cannot be replayed after a cold executor restart with an empty in-memory cache.
    """
    db_file = tmp_path / "registry.db"
    reg1 = ComponentRegistry(db_path=db_file)

    auth = AuthorizationRecord(
        authorization_id="auth_restart_test_001",
        proposal_id="prop_restart_test_001",
        authorized_by="human_evaluator",
        status=AuthorizationStatus.AUTHORIZED,
        execution_mode="synthetic",
        max_runtime_seconds=60.0,
        allowed_components=["postgresql_db"],
        timestamp_utc="2026-10-30T10:00:00Z",
    )
    reg1.save_authorization(auth)

    prop = ExperimentProposal(
        proposal_id="prop_restart_test_001",
        target_component="postgresql_db",
        version="16-alpine",
        concurrency_levels=[1, 2],
        read_ratio=0.8,
        replications=1,
        timeout_seconds=30.0,
        hypothesis="Latency scales sublinearly",
        unknown_being_investigated="Latency scaling under concurrency",
        reasoning="Test restart persistence",
    )

    executor1 = BoundedBenchmarkExecutor(
        registry=reg1,
        synthetic_runner=SyntheticBenchmarkRunner(),
    )

    # 1. First execution succeeds and marks authorization EXHAUSTED in registry
    res1 = executor1.execute_experiment(prop, auth)
    assert res1.status == "SUCCESS"
    assert "auth_restart_test_001" in executor1.used_authorization_ids

    persisted_auth = reg1.get_authorization("auth_restart_test_001")
    assert persisted_auth is not None
    assert persisted_auth.status == AuthorizationStatus.EXHAUSTED

    # 2. Simulate complete restart: instantiate a fresh registry and fresh executor
    # with an entirely cold, empty in-memory used_authorization_ids cache.
    reg2 = ComponentRegistry(db_path=db_file)
    executor2 = BoundedBenchmarkExecutor(
        registry=reg2,
        synthetic_runner=SyntheticBenchmarkRunner(),
    )
    assert len(executor2.used_authorization_ids) == 0

    # 3. Simulate replay by presenting the authorization anew (claiming AUTHORIZED status)
    # The new executor has an empty in-memory cache, but will query SQLite and detect that it was exhausted.
    replayed_auth = AuthorizationRecord(
        authorization_id="auth_restart_test_001",
        proposal_id="prop_restart_test_001",
        authorized_by="human_evaluator",
        status=AuthorizationStatus.AUTHORIZED,
        execution_mode="synthetic",
        max_runtime_seconds=60.0,
        allowed_components=["postgresql_db"],
        timestamp_utc="2026-10-30T10:00:00Z",
    )
    res2 = executor2.execute_experiment(prop, replayed_auth)
    assert res2.status == "AUTHORIZATION_EXHAUSTED"
    assert "is recorded as EXHAUSTED in the component registry" in res2.error_message


# ---------------------------------------------------------------------------
# 2. Atomic Authorization Consumption (Single-Use Lifecycle)
# ---------------------------------------------------------------------------

def test_atomic_authorization_consumption_single_use(tmp_path):
    """
    Verify single-use authorization lifecycle: execution succeeds exactly once,
    and a second attempt within the same process is blocked immediately.
    """
    db_file = tmp_path / "registry.db"
    reg = ComponentRegistry(db_path=db_file)

    auth = AuthorizationRecord(
        authorization_id="auth_single_use_002",
        proposal_id="prop_single_use_002",
        authorized_by="security_admin",
        status=AuthorizationStatus.AUTHORIZED,
        execution_mode="synthetic",
        max_runtime_seconds=45.0,
        allowed_components=["postgresql_db"],
        timestamp_utc="2026-10-30T10:00:00Z",
    )
    reg.save_authorization(auth)

    prop = ExperimentProposal(
        proposal_id="prop_single_use_002",
        target_component="postgresql_db",
        version="16-alpine",
        concurrency_levels=[4],
        read_ratio=0.5,
        replications=1,
        timeout_seconds=20.0,
        hypothesis="Latency scales sublinearly",
        unknown_being_investigated="Latency scaling under concurrency",
        reasoning="Test atomic single-use authorization",
    )

    executor = BoundedBenchmarkExecutor(registry=reg, synthetic_runner=SyntheticBenchmarkRunner())

    # Attempt 1 -> SUCCESS
    res1 = executor.execute_experiment(prop, auth)
    assert res1.status == "SUCCESS"

    # Attempt 2 -> AUTHORIZATION_EXHAUSTED
    res2 = executor.execute_experiment(prop, auth)
    assert res2.status == "AUTHORIZATION_EXHAUSTED"
    assert "has already been consumed" in res2.error_message


# ---------------------------------------------------------------------------
# 3. Docker Readiness Failure and Guaranteed Cleanup
# ---------------------------------------------------------------------------

def test_docker_readiness_failure_triggers_cleanup():
    """
    Verify that if PostgreSQL fails readiness checks after container startup,
    the runner fails closed and executes 'docker rm -f <container_id>' without dangling containers.
    """
    runner = DockerBenchmarkRunner()
    executed_cmds = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cid_readiness_fail\n", stderr="")
        if "pg_isready" in cmd:
            # Simulate readiness check failing repeatedly
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="pg_isready: connection failed")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cid_readiness_fail", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        with pytest.raises(RuntimeError) as exc_info:
            runner._benchmark_postgres(
                component_name="postgresql_db",
                version="16-alpine",
                concurrency_list=[1],
                replications=1,
            )

        assert "PostgreSQL container failed to become ready" in str(exc_info.value)

    # Verify that container cleanup was executed
    rm_calls = [cmd for cmd in executed_cmds if cmd[0:3] == ["docker", "rm", "-f"]]
    assert len(rm_calls) >= 1, "Guaranteed container cleanup 'docker rm -f' was not called upon readiness failure!"


# ---------------------------------------------------------------------------
# 4. Timeout During Benchmark Execution and Container Cleanup
# ---------------------------------------------------------------------------

def test_docker_benchmark_timeout_and_container_cleanup(tmp_path):
    """
    Verify that a subprocess timeout during benchmark execution is caught,
    triggers container cleanup, and BoundedBenchmarkExecutor reports TIMED_OUT status cleanly.
    """
    db_file = tmp_path / "registry.db"
    reg = ComponentRegistry(db_path=db_file)

    runner = DockerBenchmarkRunner()
    executed_cmds = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        executed_cmds.append(cmd)
        if cmd[0:2] == ["docker", "info"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="24.0.5\n", stderr="")
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_timeout_123\n", stderr="")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="accepting connections\n", stderr="")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="done\n", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            # Simulate execution timing out
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=3.0)
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_timeout_123", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    auth = AuthorizationRecord(
        authorization_id="auth_timeout_003",
        proposal_id="prop_timeout_003",
        authorized_by="evaluator",
        status=AuthorizationStatus.AUTHORIZED,
        execution_mode="docker",
        max_runtime_seconds=60.0,
        allowed_components=["postgresql_db"],
        timestamp_utc="2026-10-30T10:00:00Z",
    )
    reg.save_authorization(auth)

    prop = ExperimentProposal(
        proposal_id="prop_timeout_003",
        target_component="postgresql_db",
        version="16-alpine",
        concurrency_levels=[4],
        read_ratio=1.0,
        replications=1,
        timeout_seconds=30.0,
        hypothesis="Latency scales sublinearly",
        unknown_being_investigated="Latency scaling under concurrency",
        reasoning="Test timeout handling and container cleanup",
    )

    executor = BoundedBenchmarkExecutor(
        registry=reg,
        docker_runner=runner,
        synthetic_runner=SyntheticBenchmarkRunner(),
    )

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        result = executor.execute_experiment(prop, auth)

    assert result.status == "TIMED_OUT"
    assert "Benchmark execution timed out" in result.error_message
    assert result.raw_records_count == 0

    # Verify container removal occurred in finally block
    rm_calls = [cmd for cmd in executed_cmds if cmd[0:3] == ["docker", "rm", "-f"]]
    assert len(rm_calls) >= 1, "Container cleanup was not performed after benchmark timeout!"


# ---------------------------------------------------------------------------
# 5. Missing, Corrupt, and Insufficient Transaction Log Validation
# ---------------------------------------------------------------------------

def test_pgbench_output_parser_transaction_log_validation():
    """
    Verify that PgbenchOutputParser strictly validates transaction logs:
    - Empty log text raises ValueError.
    - Log with < 10 samples raises ValueError.
    - Corrupt non-numeric lines are skipped or rejected.
    - Valid log calculates p50, p95, p99 in milliseconds.
    """
    # Case A: Empty text
    with pytest.raises(ValueError) as exc_a:
        PgbenchOutputParser.parse_transaction_logs("")
    assert "Transaction log is empty" in str(exc_a.value)

    # Case B: Insufficient samples (< 10)
    sparse_text = "\n".join([f"0 {i} {i * 1000} 0" for i in range(5)])
    with pytest.raises(ValueError) as exc_b:
        PgbenchOutputParser.parse_transaction_logs(sparse_text, min_samples=10)
    assert "Insufficient transaction samples" in str(exc_b.value)

    # Case C: Corrupt / malformed lines mixed with 5 valid samples (< 10)
    corrupt_text = "0 1 not_a_number 0\n" * 10 + "\n".join([f"0 {i} 2000 0" for i in range(5)])
    with pytest.raises(ValueError) as exc_c:
        PgbenchOutputParser.parse_transaction_logs(corrupt_text, min_samples=10)
    assert "Insufficient transaction samples" in str(exc_c.value)

    # Case D: Valid log (20 samples with microsecond latencies from 1000us to 20000us)
    lines = [f"0 {i} {i * 1000} 0" for i in range(1, 21)]  # 1ms to 20ms
    valid_text = "\n".join(lines)

    metrics = PgbenchOutputParser.parse_transaction_logs(valid_text, min_samples=10)
    assert metrics["sample_count"] == 20
    assert 10.0 <= metrics["p50_ms"] <= 11.0
    assert 18.0 <= metrics["p95_ms"] <= 20.0
    assert metrics["p99_ms"] >= metrics["p95_ms"]


# ---------------------------------------------------------------------------
# 6. Failed Transaction Accounting
# ---------------------------------------------------------------------------

def test_experiment_record_failed_transaction_accounting(tmp_path):
    """
    Verify that failed transactions reported by pgbench summary
    are parsed and populated into ExperimentRecord.error_count.
    """
    runner = DockerBenchmarkRunner()

    # Create dummy log with 15 valid samples
    dummy_log_dir = tmp_path / "pglogs"
    dummy_log_dir.mkdir()
    log_file = dummy_log_dir / "pglog_4_0.log"
    log_file.write_text("\n".join([f"0 {i} 5000 0" for i in range(15)]))

    pgbench_summary = (
        "transaction type: <builtin: select only>\n"
        "scaling factor: 1\n"
        "query mode: simple\n"
        "number of clients: 4\n"
        "number of threads: 2\n"
        "duration: 3 s\n"
        "number of transactions actually processed: 250\n"
        "number of failed transactions: 17 (6.800%)\n"
        "latency average = 5.210 ms\n"
        "tps = 83.333333 (including connections establishing)\n"
    )

    def mock_subprocess_run(cmd, *args, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_err_44\n", stderr="")
        if "pg_isready" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="accepting connections\n", stderr="")
        if "pgbench" in cmd and "-i" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="done\n", stderr="")
        if "pgbench" in cmd and "-l" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=pgbench_summary, stderr="")
        if any("cat" in str(arg) for arg in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=log_file.read_text(), stderr="")
        if cmd[0:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="mock_cont_err_44", stderr="")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=mock_subprocess_run), patch("time.sleep", return_value=None):
        records = runner._benchmark_postgres(
            component_name="postgresql_db",
            version="16-alpine",
            concurrency_list=[4],
            replications=1,
        )

    assert len(records) == 1
    rec = records[0]
    assert rec.error_count == 17, f"Expected error_count=17, got {rec.error_count}"
    assert rec.execution_mode == "docker"
    assert rec.duration_seconds is not None and rec.duration_seconds > 0


# ---------------------------------------------------------------------------
# 7. Model Provenance Tracking and Extrapolation Warnings
# ---------------------------------------------------------------------------

def test_model_provenance_and_extrapolation_warnings():
    """
    Verify that trained models track source experiment IDs in metrics and provenance,
    and explicitly warn against extrapolation outside the verified operating range.
    """
    # 4 distinct configurations across concurrency [1, 4, 8, 16]
    exps = [
        _make_sample_exp("exp_c1_r1", 1, 150.0, 4.0, 6.0),
        _make_sample_exp("exp_c1_r2", 1, 152.0, 4.1, 6.2),
        _make_sample_exp("exp_c4_r1", 4, 380.0, 8.5, 12.0),
        _make_sample_exp("exp_c4_r2", 4, 375.0, 8.7, 12.5),
        _make_sample_exp("exp_c8_r1", 8, 450.0, 15.0, 22.0),
        _make_sample_exp("exp_c8_r2", 8, 445.0, 15.2, 22.5),
        _make_sample_exp("exp_c16_r1", 16, 480.0, 28.0, 39.0),
        _make_sample_exp("exp_c16_r2", 16, 475.0, 28.5, 39.5),
    ]

    model_record, metrics = ModelTrainer.train_and_validate(
        component_name="postgresql_db",
        version="16-alpine",
        experiments=exps,
        test_ratio=0.25,
    )

    # 1. Check metrics contains source experiment IDs
    all_input_ids = [e.experiment_id for e in exps]
    assert metrics["source_experiment_ids"] == all_input_ids
    assert metrics["evaluation_nature"] == "interpolation_only"

    # 2. Check model_record provenance
    assert "exp_c1_r1" in model_record.provenance
    assert "strict interpolation" in model_record.provenance

    # 3. Check known limitations warns against extrapolation
    assert "Extrapolation beyond these bounds is unvalidated" in model_record.known_limitations
    assert "concurrency [1, 16]" in model_record.known_limitations


# ---------------------------------------------------------------------------
# 8. Calibration Failure Preserves Active Model Intact
# ---------------------------------------------------------------------------

def test_calibration_failure_preserves_active_model(tmp_path):
    """
    Verify that if candidate calibration fails (e.g. insufficient independent groups,
    or quality validation gates fail), the prior active model in the registry is untouched.
    """
    db_file = tmp_path / "registry.db"
    reg = ComponentRegistry(db_path=db_file)

    # Register initial baseline model
    base_model = ModelRecord(
        model_id="model_baseline_active_001",
        component_name="postgresql_db",
        version="16-alpine",
        env_fingerprint="test_host",
        model_type="synthetic_baseline",
        fitted_parameters={"p50_base": 5.0},
        min_supported_rps=10.0,
        max_supported_rps=300.0,
        min_supported_concurrency=1,
        max_supported_concurrency=16,
        validation_rmse_ms=2.0,
        validation_mape_pct=15.0,
        r2_score=0.85,
        is_validated=True,
        is_synthetic_fixture=True,
        provenance="Initial synthetic baseline",
        known_limitations="Initial baseline",
        created_at="2026-10-30T00:00:00Z",
    )
    reg.register_model(base_model)
    assert reg.get_model("postgresql_db", "16-alpine").model_id == "model_baseline_active_001"

    cal_pipe = CalibrationPipeline(registry=reg)

    # Case A: Insufficient observations (< 3)
    sparse_exps = [_make_sample_exp("exp_single_1", 2, 200.0, 5.0, 8.0)]
    outcome_sparse = cal_pipe.calibrate_component(
        component_name="postgresql_db",
        version="16-alpine",
        experiments=sparse_exps,
    )
    assert outcome_sparse.status == "INSUFFICIENT_EVIDENCE"
    assert reg.get_model("postgresql_db", "16-alpine").model_id == "model_baseline_active_001"

    # Case B: Insufficient independent groups (all 4 exps have the same concurrency=4)
    same_group_exps = [
        _make_sample_exp(f"exp_grp_{i}", 4, 300.0, 10.0, 15.0) for i in range(4)
    ]
    outcome_grp = cal_pipe.calibrate_component(
        component_name="postgresql_db",
        version="16-alpine",
        experiments=same_group_exps,
    )
    assert outcome_grp.status == "INSUFFICIENT_INDEPENDENT_GROUPS"
    assert reg.get_model("postgresql_db", "16-alpine").model_id == "model_baseline_active_001"

    # Case C: Quality gates rejection (huge errors causing rejection)
    bad_exps = [
        _make_sample_exp("exp_bad_1", 1, 100.0, 5.0, 7.0),
        _make_sample_exp("exp_bad_2", 4, 400.0, 50.0, 80.0),  # extreme jump
        _make_sample_exp("exp_bad_3", 8, 20.0, 150.0, 250.0), # extreme inconsistency
        _make_sample_exp("exp_bad_4", 16, 500.0, 5.0, 8.0),   # erratic drop
    ]
    outcome_rejected = cal_pipe.calibrate_component(
        component_name="postgresql_db",
        version="16-alpine",
        experiments=bad_exps,
    )
    # Status should be REJECTED and baseline model preserved
    assert outcome_rejected.status == "REJECTED"
    assert reg.get_model("postgresql_db", "16-alpine").model_id == "model_baseline_active_001"
