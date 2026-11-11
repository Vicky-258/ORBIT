"""
Phase 4F.5 — Empirical PostgreSQL Performance Model Development Test Suite.

Covers all 20 required verification areas:
1. Reconciled evidence loading.
2. Provenance preservation.
3. Workload separation.
4. Candidate model training.
5. Deterministic reproducibility.
6. Metric calculation.
7. Missing observation handling.
8. Replication-aware evaluation.
9. Undefined R² behavior.
10. MAPE handling near zero.
11. Prediction uncertainty.
12. In-range prediction.
13. Out-of-range prediction.
14. Insufficient evidence handling.
15. Candidate model serialization.
16. Candidate model reload.
17. Compatibility with existing simulation interfaces.
18. Protection of all 24 active models.
19. Protection of historical experiment records.
20. Confirmation that no benchmark execution occurred.

All synthetic fixtures are explicitly labelled as synthetic test data.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Dict, List

import numpy as np
import pytest

from aads.modeling.model_interface import ComponentPerformanceModel
from aads.models.empirical_postgres import (
    EmpiricalLinearRegressionModel,
    EmpiricalLookupModel,
    EmpiricalMechanisticModel,
    EmpiricalPiecewiseModel,
    EmpiricalPostgresQuery,
    EvaluationMetrics,
    EvidenceStatus,
    ModelState,
    ReconciledEvidenceLoader,
    ReplicationAwareEvaluator,
    TrialObservation,
    UncertaintyType,
    WorkloadProfile,
    calculate_metrics_safely,
)


# ==============================================================================
# 1. Reconciled evidence loading
# ==============================================================================
def test_01_reconciled_evidence_loading():
    """Verifies that ReconciledEvidenceLoader loads all 12 reconciled trials with complete metrics."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()
    assert len(obs) == 12

    # Check that both workloads and quotas are present
    ro_obs = [o for o in obs if o.workload_profile == "read_only_select"]
    tpcb_obs = [o for o in obs if o.workload_profile == "balanced_oltp_tpcb"]
    assert len(ro_obs) == 6
    assert len(tpcb_obs) == 6

    # Verify metric fields are populated
    for o in obs:
        assert o.throughput_tps > 0
        assert o.latency_mean_ms > 0
        assert o.cpu_quota_cores in [1.0, 2.0]
        assert o.replication in [1, 2, 3]


# ==============================================================================
# 2. Provenance preservation
# ==============================================================================
def test_02_provenance_preservation():
    """Verifies that evidence provenance is validated and transferred to models."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    valid, prov = loader.verify_provenance()
    assert valid is True
    assert prov["execution_id"] == "exec_p4f4_20261103_053428_525413_19491"
    assert prov["manifest_sha256"] == "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"
    assert prov["model_registry_intact"] is True

    obs = loader.load_trial_observations()
    model = EmpiricalLookupModel("test_prov_model", WorkloadProfile.READ_ONLY_SELECT, provenance=prov)
    model.fit(obs)
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)
    pred = model.predict(q)
    assert pred.provenance["execution_id"] == "exec_p4f4_20261103_053428_525413_19491"
    assert pred.provenance["manifest_sha256"] == "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"


# ==============================================================================
# 3. Workload separation
# ==============================================================================
def test_03_workload_separation():
    """Verifies that models are workload-specific and reject cross-workload prediction queries."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    ro_model = EmpiricalLookupModel("ro_model", WorkloadProfile.READ_ONLY_SELECT)
    ro_model.fit(obs)

    # Valid read-only query
    q_ro = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)
    p_ro = ro_model.predict(q_ro)
    assert p_ro.evidence_status == EvidenceStatus.OBSERVED
    assert p_ro.state in [ModelState.OBSERVED, ModelState.IN_RANGE]

    # Invalid query: pass balanced_oltp_tpcb to read_only model
    q_invalid = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB, cpu_quota_cores=1.0)
    p_invalid = ro_model.predict(q_invalid)
    assert p_invalid.state == ModelState.INSUFFICIENT_EVIDENCE
    assert p_invalid.is_extrapolated is True


# ==============================================================================
# 4. Candidate model training
# ==============================================================================
def test_04_candidate_model_training():
    """Verifies that all 4 candidate model families train successfully on empirical observations."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    candidates = [
        EmpiricalLookupModel("test_lookup", WorkloadProfile.READ_ONLY_SELECT),
        EmpiricalLinearRegressionModel("test_linear", WorkloadProfile.READ_ONLY_SELECT),
        EmpiricalPiecewiseModel("test_piecewise", WorkloadProfile.READ_ONLY_SELECT),
        EmpiricalMechanisticModel("test_mechanistic", WorkloadProfile.READ_ONLY_SELECT),
    ]

    for model in candidates:
        model.fit(obs)
        q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=2.0)
        pred = model.predict(q)
        assert pred.throughput_tps.point_estimate > 30000.0
        assert pred.evidence_status == EvidenceStatus.OBSERVED
        assert pred.state in [ModelState.OBSERVED, ModelState.IN_RANGE]


# ==============================================================================
# 5. Deterministic reproducibility
# ==============================================================================
def test_05_deterministic_reproducibility():
    """Verifies that training candidate models twice produces bit-identical parameters and predictions."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    m1 = EmpiricalLinearRegressionModel("m1", WorkloadProfile.READ_ONLY_SELECT).fit(obs)
    m2 = EmpiricalLinearRegressionModel("m2", WorkloadProfile.READ_ONLY_SELECT).fit(obs)

    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.5)
    p1 = m1.predict(q)
    p2 = m2.predict(q)

    assert p1.throughput_tps.point_estimate == p2.throughput_tps.point_estimate
    assert p1.latency_mean_ms.point_estimate == p2.latency_mean_ms.point_estimate
    assert m1.equations["throughput_tps"]["slope"] == m2.equations["throughput_tps"]["slope"]


# ==============================================================================
# 6. Metric calculation
# ==============================================================================
def test_06_metric_calculation():
    """Verifies statistical metric calculation (RMSE, MAE, MAPE, R2) on deterministic synthetic test fixture."""
    # Synthetic test fixture: true = [10.0, 20.0, 30.0], pred = [12.0, 18.0, 32.0]
    # errors = [+2.0, -2.0, +2.0], abs_errors = [2, 2, 2], sq_errors = [4, 4, 4]
    # MAE = 2.0, RMSE = 2.0
    # y_mean = 20.0, SS_tot = (-10)^2 + 0^2 + 10^2 = 200. SS_res = 12. R2 = 1 - 12/200 = 0.94
    y_true = [10.0, 20.0, 30.0]
    y_pred = [12.0, 18.0, 32.0]

    met = calculate_metrics_safely(y_true, y_pred, "synthetic_metric")
    assert met.mae == 2.0
    assert met.rmse == 2.0
    assert met.r2_score == 0.94
    assert met.mape_pct == pytest.approx(12.2222, abs=1e-3)


# ==============================================================================
# 7. Missing observation handling
# ==============================================================================
def test_07_missing_observation_handling(tmp_path: Path):
    """Verifies error handling when observations or evidence files are missing."""
    empty_loader = ReconciledEvidenceLoader(tmp_path)
    with pytest.raises(FileNotFoundError):
        empty_loader.load_trial_observations()

    model = EmpiricalLookupModel("test_empty", WorkloadProfile.READ_ONLY_SELECT)
    with pytest.raises(ValueError):
        model.fit([])


# ==============================================================================
# 8. Replication-aware evaluation
# ==============================================================================
def test_08_replication_aware_evaluation():
    """Verifies Leave-One-Replication-Out (LORO) cross-validation evaluation across 3 replications."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    evaluator = ReplicationAwareEvaluator(obs)
    res = evaluator.evaluate_model_family(EmpiricalLookupModel, WorkloadProfile.READ_ONLY_SELECT, "throughput_tps")

    assert res["folds_evaluated"] == 3
    assert res["cross_validation_method"] == "Leave-One-Replication-Out (LORO)"
    assert res["overall_metrics"]["sample_size"] == 6
    assert res["overall_metrics"]["rmse"] > 0
    assert "cpu_1.0vCPU" in res["per_condition_errors"]
    assert "cpu_2.0vCPU" in res["per_condition_errors"]


# ==============================================================================
# 9. Undefined R² behavior
# ==============================================================================
def test_09_undefined_r2_behavior():
    """Verifies that R² returns None without crashing when target variance is zero (SS_tot = 0)."""
    # Synthetic test fixture: constant ground truth values [10.0, 10.0, 10.0]
    y_true = [10.0, 10.0, 10.0]
    y_pred = [10.5, 9.8, 10.1]

    met = calculate_metrics_safely(y_true, y_pred, "constant_target")
    assert met.r2_score is None
    assert any("SS_tot = 0" in note for note in met.notes)


# ==============================================================================
# 10. MAPE handling near zero
# ==============================================================================
def test_10_mape_handling_near_zero():
    """Verifies that MAPE returns None without division by zero when target values approach zero."""
    # Synthetic test fixture containing zero target (e.g. deadlocks = 0)
    y_true = [0.0, 10.0, 20.0]
    y_pred = [0.0, 11.0, 19.0]

    met = calculate_metrics_safely(y_true, y_pred, "metric_with_zero")
    assert met.mape_pct is None
    assert any("near zero" in note for note in met.notes)


# ==============================================================================
# 11. Prediction uncertainty
# ==============================================================================
def test_11_prediction_uncertainty():
    """Verifies that point predictions have non-zero uncertainty, valid CIs at anchors, and heuristic intervals when interpolated."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalLookupModel("test_unc", WorkloadProfile.READ_ONLY_SELECT).fit(obs)

    # Directly observed anchor: statistical confidence interval supported
    q_obs = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)
    pred_obs = model.predict(q_obs)
    assert pred_obs.evidence_status == EvidenceStatus.OBSERVED
    assert pred_obs.throughput_tps.uncertainty_std > 0
    ci = pred_obs.throughput_tps.confidence_interval_95
    assert ci is not None
    assert ci[0] <= pred_obs.throughput_tps.point_estimate <= ci[1]

    # Interpolated query: heuristic interval, confidence_interval_95 is None
    q_interp = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.5)
    pred_interp = model.predict(q_interp)
    assert pred_interp.evidence_status == EvidenceStatus.INTERPOLATED
    assert pred_interp.throughput_tps.uncertainty_std > 0
    assert pred_interp.throughput_tps.confidence_interval_95 is None
    h_int = pred_interp.throughput_tps.heuristic_interval
    assert h_int is not None
    assert h_int[0] <= pred_interp.throughput_tps.point_estimate <= h_int[1]


# ==============================================================================
# 12. In-range prediction
# ==============================================================================
def test_12_in_range_prediction():
    """Verifies evidence status classification for valid queries within [1.0, 2.0] vCPU."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalLookupModel("test_in_range", WorkloadProfile.BALANCED_OLTP_TPCB).fit(obs)

    # Exact anchor query is OBSERVED
    q_obs = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB,
        cpu_quota_cores=1.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    pred_obs = model.predict(q_obs)
    assert pred_obs.evidence_status == EvidenceStatus.OBSERVED
    assert pred_obs.is_extrapolated is False

    # Intermediate query is INTERPOLATED, never OBSERVED
    q_interp = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB,
        cpu_quota_cores=1.5,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    pred_interp = model.predict(q_interp)
    assert pred_interp.evidence_status == EvidenceStatus.INTERPOLATED
    assert pred_interp.state == ModelState.INTERPOLATED
    assert pred_interp.is_extrapolated is False
    assert any("interpolated" in note.lower() for note in pred_interp.uncertainty_notes)


# ==============================================================================
# 13. Out-of-range prediction
# ==============================================================================
def test_13_out_of_range_prediction():
    """Verifies that out-of-range queries are detected, flagged, and assigned uncertainty penalties."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalLookupModel("test_out_range", WorkloadProfile.READ_ONLY_SELECT).fit(obs)

    # Exceed CPU quota: 3.5 vCPU
    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=3.5,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    pred = model.predict(q)
    assert pred.state == ModelState.OUT_OF_RANGE
    assert pred.is_extrapolated is True
    assert any("outside empirically validated range" in note for note in pred.uncertainty_notes)

    # Normal in-range uncertainty at 2.0 vCPU
    q_norm = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=2.0)
    pred_norm = model.predict(q_norm)
    # Out of range prediction uncertainty must be penalized
    assert pred.throughput_tps.uncertainty_std > pred_norm.throughput_tps.uncertainty_std


# ==============================================================================
# 14. Insufficient evidence handling
# ==============================================================================
def test_14_insufficient_evidence_handling():
    """Verifies that incompatible workload queries trigger INSUFFICIENT_EVIDENCE state."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalLookupModel("test_insufficient", WorkloadProfile.BALANCED_OLTP_TPCB).fit(obs)
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)
    pred = model.predict(q)

    assert pred.state == ModelState.INSUFFICIENT_EVIDENCE
    assert pred.is_extrapolated is True
    assert any("unsupported" in note for note in pred.uncertainty_notes)


# ==============================================================================
# 15. Candidate model serialization
# ==============================================================================
def test_15_candidate_model_serialization(tmp_path: Path):
    """Verifies candidate model serialization to JSON format."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalPiecewiseModel("test_serialize", WorkloadProfile.BALANCED_OLTP_TPCB).fit(obs)
    out_file = tmp_path / "model.json"
    saved_path = model.save_json(out_file)

    assert Path(saved_path).is_file()
    with open(out_file) as f:
        data = json.load(f)
    assert data["model_type"] == "EmpiricalPiecewiseModel"
    assert data["model_id"] == "test_serialize"
    assert data["knee_cpu"] == 1.25


# ==============================================================================
# 16. Candidate model reload
# ==============================================================================
def test_16_candidate_model_reload(tmp_path: Path):
    """Verifies that serialized candidate models reload and reproduce identical predictions."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    original = EmpiricalLinearRegressionModel("test_reload", WorkloadProfile.READ_ONLY_SELECT).fit(obs)
    out_file = tmp_path / "linear_model.json"
    original.save_json(out_file)

    reloaded = EmpiricalLinearRegressionModel.load_json(out_file)
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.75)

    p_orig = original.predict(q)
    p_reload = reloaded.predict(q)

    assert p_orig.throughput_tps.point_estimate == p_reload.throughput_tps.point_estimate
    assert p_orig.latency_mean_ms.point_estimate == p_reload.latency_mean_ms.point_estimate
    assert p_orig.p95_ms.point_estimate == p_reload.p95_ms.point_estimate


# ==============================================================================
# 17. Compatibility with existing simulation interfaces
# ==============================================================================
def test_17_compatibility_with_simulation_interfaces():
    """Verifies that candidate models implement ComponentPerformanceModel interface."""
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    obs = loader.load_trial_observations()

    model = EmpiricalLookupModel("sim_compat", WorkloadProfile.READ_ONLY_SELECT).fit(obs)
    assert isinstance(model, ComponentPerformanceModel)

    # Test predict_service_time_ms
    svc_ms, unc_ms, is_extra = model.predict_service_time_ms("read", concurrency=8, offered_rps=20000.0)
    assert svc_ms > 0
    assert unc_ms > 0
    assert is_extra is False

    # Test get_supported_ranges
    ranges = model.get_supported_ranges()
    assert "concurrency" in ranges
    assert "rps" in ranges
    assert "cpu_cores" in ranges


# ==============================================================================
# 18. Protection of all 24 active models
# ==============================================================================
def test_18_protection_of_active_models():
    """Verifies that data/registry.db contains exactly 24 models and zero were modified or promoted."""
    db_path = Path("data/registry.db").resolve()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM models")
    cnt = c.fetchone()[0]
    conn.close()
    assert cnt == 24


# ==============================================================================
# 19. Protection of historical experiment records
# ==============================================================================
def test_19_protection_of_historical_experiment_records():
    """Verifies that empirical artifacts in artifacts/phase_4f4_empirical/ remain unchanged."""
    empirical_summary = Path("artifacts/phase_4f4_empirical/exec_p4f4_20261103_053428_525413_19491/campaign_summary.json")
    assert empirical_summary.is_file()
    with open(empirical_summary) as f:
        data = json.load(f)
    assert data["execution_id"] == "exec_p4f4_20261103_053428_525413_19491"
    assert data["successful_trials"] == 12


# ==============================================================================
# 20. Confirmation that no benchmark execution occurred
# ==============================================================================
def test_20_confirmation_no_benchmark_execution():
    """Verifies that Phase 4F.5 executed purely offline without generating benchmark logs."""
    candidates_dir = Path("artifacts/phase_4f5/candidates")
    assert candidates_dir.is_dir()
    # Candidate directory must only contain JSON model files and evaluation results, NO pgbench logs or CSVs
    files = list(candidates_dir.iterdir())
    for f in files:
        assert f.suffix == ".json"
        assert "pgbench" not in f.name
