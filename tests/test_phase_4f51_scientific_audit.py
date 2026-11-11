"""
Phase 4F.5.1 — Candidate Model Scientific Audit & Prediction Contract Hardening Test Suite.

Comprehensive offline test suite covering:
1. Evidence classification (OBSERVED, INTERPOLATED, OUT_OF_RANGE, INSUFFICIENT_EVIDENCE).
2. Explicit uncertainty types (REPLICATION, INTERPOLATION_HEURISTIC, EXTRAPOLATION_HEURISTIC, UNAVAILABLE).
3. Heuristic multipliers strictly separated from statistical confidence intervals.
4. Mechanistic model identifiability audit (S_cpu identifiable, S_wal / W_lock confounded).
5. Evaluation terminology: Replication Holdout vs Configuration/Workload/Environment Holdout.
6. Guardrails for R² (undefined for zero variance) and MAPE (guarded near zero).
7. Mathematical indistinguishability of Lookup, Linear, and Piecewise models at measured support points.
8. SimPy discrete-event simulation integration and queueing double-counting protection.
9. Recommendation engine integration (FeasibilityFilter rejects silent OUT_OF_RANGE and INSUFFICIENT_EVIDENCE).
10. Preservation of 8 candidate models, 24 active registry models, and historical evidence hashes.

All fixtures are offline and synthetic or reconciled; zero Docker or live benchmarks executed.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Dict, List

import numpy as np
import pytest

from aads.core.schemas import FeasibilityStatus, SimulationResult, WorkloadSpec
from aads.evaluation.feasibility_filter import FeasibilityFilter
from aads.evaluation.recommender import ArchitectureRecommender
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


@pytest.fixture(scope="module")
def reconciled_observations() -> List[TrialObservation]:
    loader = ReconciledEvidenceLoader("artifacts/phase_4f46/reconciliation")
    return loader.load_trial_observations()


# ==============================================================================
# 1. Evidence Classification
# ==============================================================================
def test_01_evidence_classification_exact_observed(reconciled_observations):
    """Verifies that exact match to measured support returns OBSERVED."""
    model = EmpiricalLookupModel("test_obs", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    # 1.0 vCPU anchor
    q1 = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=1.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p1 = model.predict(q1)
    assert p1.evidence_status == EvidenceStatus.OBSERVED
    assert p1.is_extrapolated is False

    # 2.0 vCPU anchor
    q2 = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=2.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p2 = model.predict(q2)
    assert p2.evidence_status == EvidenceStatus.OBSERVED
    assert p2.is_extrapolated is False


def test_02_evidence_classification_cpu_1_5_interpolated(reconciled_observations):
    """Verifies that CPU quota 1.5 returns INTERPOLATED, and NEVER OBSERVED or IN_RANGE."""
    model = EmpiricalLookupModel("test_interp", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=1.5,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.INTERPOLATED
    assert p.evidence_status != EvidenceStatus.OBSERVED
    assert p.evidence_status.value != "IN_RANGE"
    assert p.is_extrapolated is False
    assert any("interpolat" in note.lower() for note in p.limitations)


def test_03_evidence_classification_cpu_3_out_of_range(reconciled_observations):
    """Verifies that CPU quota 3.0 returns OUT_OF_RANGE."""
    model = EmpiricalLookupModel("test_oor_cpu", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=3.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.OUT_OF_RANGE
    assert p.is_extrapolated is True
    assert any("outside empirically validated range" in note for note in p.limitations)


def test_04_evidence_classification_concurrency_16_out_of_range(reconciled_observations):
    """Verifies that concurrency 16 returns OUT_OF_RANGE."""
    model = EmpiricalLookupModel("test_oor_conc", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=2.0,
        concurrency=16,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.OUT_OF_RANGE
    assert p.is_extrapolated is True


def test_05_evidence_classification_sf20_out_of_range(reconciled_observations):
    """Verifies that scale factor 20 returns OUT_OF_RANGE."""
    model = EmpiricalLookupModel("test_oor_sf", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=2.0,
        concurrency=8,
        scale_factor=20,
        memory_mb=1024.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.OUT_OF_RANGE
    assert p.is_extrapolated is True


def test_06_evidence_classification_memory_out_of_range(reconciled_observations):
    """Verifies that memory 2048 MB returns OUT_OF_RANGE."""
    model = EmpiricalLookupModel("test_oor_mem", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.READ_ONLY_SELECT,
        cpu_quota_cores=2.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=2048.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.OUT_OF_RANGE
    assert p.is_extrapolated is True


def test_07_evidence_classification_unsupported_workload_insufficient_evidence(reconciled_observations):
    """Verifies that querying with an unsupported workload returns INSUFFICIENT_EVIDENCE."""
    model = EmpiricalLookupModel("test_unsupported_wl", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    q = EmpiricalPostgresQuery(
        workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB,  # mismatched
        cpu_quota_cores=1.0,
        concurrency=8,
        scale_factor=2,
        memory_mb=1024.0,
    )
    p = model.predict(q)
    assert p.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert p.throughput_tps.point_estimate is None
    assert p.throughput_tps.uncertainty_std is None
    assert p.throughput_tps.uncertainty_type == UncertaintyType.UNAVAILABLE


def test_08_evidence_classification_missing_cpu_insufficient_evidence(reconciled_observations):
    """Verifies that missing cpu_quota_cores returns INSUFFICIENT_EVIDENCE."""
    model = EmpiricalLookupModel("test_missing_cpu", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    # Bypass pydantic validation via raw dict construct or check_input_boundaries directly
    status, is_extrap, notes = model.check_input_boundaries(
        EmpiricalPostgresQuery.model_construct(
            workload_profile=WorkloadProfile.READ_ONLY_SELECT,
            cpu_quota_cores=None,
            concurrency=8,
            scale_factor=2,
            memory_mb=1024.0,
        )
    )
    assert status == EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert is_extrap is True
    assert any("missing" in note.lower() for note in notes)


# ==============================================================================
# 2. Uncertainty Types and Heuristic Multipliers
# ==============================================================================
def test_09_uncertainty_replication_vs_interpolation(reconciled_observations):
    """Verifies replication uncertainty is strictly distinguished from interpolation uncertainty."""
    model = EmpiricalLookupModel("test_unc_diff", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    # Observed query at 1.0 vCPU
    q_obs = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)
    p_obs = model.predict(q_obs)
    assert p_obs.throughput_tps.uncertainty_type == UncertaintyType.REPLICATION_SAMPLE_STD
    assert p_obs.throughput_tps.is_heuristic is False
    assert p_obs.throughput_tps.confidence_interval_95 is not None

    # Interpolated query at 1.5 vCPU
    q_interp = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.5)
    p_interp = model.predict(q_interp)
    assert p_interp.throughput_tps.uncertainty_type == UncertaintyType.INTERPOLATION_HEURISTIC
    assert p_interp.throughput_tps.is_heuristic is True
    assert p_interp.throughput_tps.confidence_interval_95 is None
    assert p_interp.throughput_tps.heuristic_interval is not None


def test_10_heuristic_multipliers_never_labelled_statistical_ci(reconciled_observations):
    """Verifies that heuristic multipliers are NEVER labelled as statistical confidence intervals."""
    for model_cls in [EmpiricalLookupModel, EmpiricalLinearRegressionModel, EmpiricalPiecewiseModel]:
        model = model_cls(f"test_ci_guard_{model_cls.__name__}", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

        # Extrapolated query at 3.0 vCPU
        q_oor = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=3.0)
        p_oor = model.predict(q_oor)

        assert p_oor.throughput_tps.is_heuristic is True
        assert p_oor.throughput_tps.confidence_interval_95 is None
        assert p_oor.throughput_tps.heuristic_multiplier is not None
        assert p_oor.throughput_tps.heuristic_multiplier > 1.0
        assert p_oor.throughput_tps.heuristic_interval is not None


def test_11_extrapolation_heuristic_distance_multiplier(reconciled_observations):
    """Verifies the exact heuristic multiplier calculation (2.0 + 1.5 * distance) outside support."""
    model = EmpiricalLookupModel("test_mult", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    # Query at 3.0 vCPU -> distance = 3.0 - 2.0 = 1.0 -> penalty = 2.0 + 1.5 * 1.0 = 3.5
    q3 = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=3.0)
    p3 = model.predict(q3)
    assert p3.throughput_tps.heuristic_multiplier == 3.5
    assert p3.throughput_tps.uncertainty_type == UncertaintyType.EXTRAPOLATION_HEURISTIC

    # Query at 0.5 vCPU -> distance = 1.0 - 0.5 = 0.5 -> penalty = 2.0 + 1.5 * 0.5 = 2.75
    q05 = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=0.5)
    p05 = model.predict(q05)
    assert p05.throughput_tps.heuristic_multiplier == 2.75


def test_12_missing_uncertainty_remains_unavailable_not_zero(reconciled_observations):
    """Verifies that missing uncertainty is UNAVAILABLE (None), never silently reported as 0.0."""
    model = EmpiricalLookupModel("test_unavail", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    # Incompatible query triggers INSUFFICIENT_EVIDENCE
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB, cpu_quota_cores=1.0)
    p = model.predict(q)
    assert p.throughput_tps.uncertainty_std is None
    assert p.throughput_tps.uncertainty_type == UncertaintyType.UNAVAILABLE
    assert p.throughput_tps.uncertainty_std != 0.0


def test_13_interpolation_uncertainty_not_solely_endpoint_variance(reconciled_observations):
    """Verifies that interpolation discloses that endpoint variance alone does not validate intermediate behavior."""
    model = EmpiricalLookupModel("test_interp_disc", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.5)
    p = model.predict(q)

    assert p.evidence_status == EvidenceStatus.INTERPOLATED
    assert any("not a calibrated statistical confidence interval" in note.lower() or "unmeasured" in note.lower() for note in p.limitations)


# ==============================================================================
# 3. Mechanistic Model Identifiability Audit
# ==============================================================================
def test_14_mechanistic_identifiability_parameters_identified(reconciled_observations):
    """Verifies formal parameter identifiability status in the mechanistic model."""
    model = EmpiricalMechanisticModel("test_ident", WorkloadProfile.BALANCED_OLTP_TPCB).fit(reconciled_observations)

    assert model.identifiability["s_cpu"] == "IDENTIFIABLE"
    assert model.identifiability["s_fixed"] == "IDENTIFIABLE"
    assert model.identifiability["s_wal"] == "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE"
    assert model.identifiability["w_lock"] == "ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE"


def test_15_mechanistic_identifiability_sum_constant(reconciled_observations):
    """Verifies that multiple combinations of (S_wal, W_lock) having constant sum yield identical predictions."""
    m1 = EmpiricalMechanisticModel("m1", WorkloadProfile.BALANCED_OLTP_TPCB).fit(reconciled_observations)
    s_fixed = m1.s_fixed_ms

    # Setup alternative model m2 with different S_wal and W_lock split but same S_fixed
    m2 = EmpiricalMechanisticModel("m2", WorkloadProfile.BALANCED_OLTP_TPCB).fit(reconciled_observations)
    m2.s_wal_ms = 1.50
    m2.w_lock_ms = s_fixed - 1.50

    q_1 = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB, cpu_quota_cores=1.0)
    q_2 = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB, cpu_quota_cores=2.0)

    p1_1 = m1.predict(q_1)
    p2_1 = m2.predict(q_1)
    assert abs(p1_1.throughput_tps.point_estimate - p2_1.throughput_tps.point_estimate) < 1e-3
    assert abs(p1_1.latency_mean_ms.point_estimate - p2_1.latency_mean_ms.point_estimate) < 1e-3

    p1_2 = m1.predict(q_2)
    p2_2 = m2.predict(q_2)
    assert abs(p1_2.throughput_tps.point_estimate - p2_2.throughput_tps.point_estimate) < 1e-3
    assert abs(p1_2.latency_mean_ms.point_estimate - p2_2.latency_mean_ms.point_estimate) < 1e-3


def test_16_mechanistic_causal_claims_absent(reconciled_observations):
    """Verifies that unsupported causal claims (e.g. locks proven dominant) are absent from output disclosures."""
    model = EmpiricalMechanisticModel("test_causal_disc", WorkloadProfile.BALANCED_OLTP_TPCB).fit(reconciled_observations)
    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.BALANCED_OLTP_TPCB, cpu_quota_cores=1.0)
    p = model.predict(q)

    notes_str = " ".join(p.identifiability_notes)
    assert "NON-IDENTIFIABLE / CONFOUNDED" in notes_str
    assert "does NOT prove" in notes_str


# ==============================================================================
# 4. Evaluation Terminology and Mathematical Indistinguishability
# ==============================================================================
def test_17_evaluation_loro_labelled_replication_holdout(reconciled_observations):
    """Verifies that LORO cross-validation is formally classified as a REPLICATION HOLDOUT."""
    evaluator = ReplicationAwareEvaluator(reconciled_observations)
    res = evaluator.evaluate_model_family(EmpiricalLookupModel, WorkloadProfile.READ_ONLY_SELECT, "throughput_tps")

    assert res["evaluation_type"] == "REPLICATION_HOLDOUT"
    assert "Replication-to-Replication repeatability" in res["cross_validation_method"] or "Leave-One-Replication-Out" in res["cross_validation_method"]
    assert any("observed configurations only" in lim for lim in res["scope_limitations"])


def test_18_evaluation_no_unseen_configuration_generalization_claim(reconciled_observations):
    """Verifies that evaluator output explicitly disclaims unseen configuration generalization."""
    evaluator = ReplicationAwareEvaluator(reconciled_observations)
    res = evaluator.evaluate_model_family(EmpiricalLookupModel, WorkloadProfile.READ_ONLY_SELECT, "throughput_tps")

    limitations_str = " ".join(res["scope_limitations"])
    assert "Does NOT evaluate configuration holdout" in limitations_str


def test_19_model_mathematical_indistinguishability_at_observed_anchors(reconciled_observations):
    """Verifies that Lookup, Linear, and Piecewise models produce mathematically indistinguishable predictions at observed anchors."""
    m_lookup = EmpiricalLookupModel("lookup", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)
    m_linear = EmpiricalLinearRegressionModel("linear", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)
    m_piecewise = EmpiricalPiecewiseModel("piecewise", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    for c in [1.0, 2.0]:
        q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=c)
        p_look = m_lookup.predict(q).throughput_tps.point_estimate
        p_lin = m_linear.predict(q).throughput_tps.point_estimate
        p_pw = m_piecewise.predict(q).throughput_tps.point_estimate

        # Difference must be negligible (< 0.01 TPS)
        assert abs(p_look - p_lin) < 0.01
        assert abs(p_look - p_pw) < 0.01


def test_20_r2_guard_near_zero_variance():
    """Verifies that R² is safely returned as None when target variance is zero."""
    y_true = [100.0, 100.0, 100.0]
    y_pred = [100.1, 99.9, 100.0]

    met = calculate_metrics_safely(y_true, y_pred, "constant_target")
    assert met.r2_score is None
    assert any("R² is undefined" in note for note in met.notes)


def test_21_mape_guard_near_zero_actuals():
    """Verifies that MAPE is safely returned as None when actuals contain values near zero."""
    y_true = [0.0, 50.0, 100.0]
    y_pred = [0.1, 51.0, 99.0]

    met = calculate_metrics_safely(y_true, y_pred, "near_zero_target")
    assert met.mape_pct is None
    assert any("MAPE is undefined" in note for note in met.notes)


# ==============================================================================
# 5. SimPy and Recommendation Engine Integration
# ==============================================================================
def test_22_simpy_service_time_result_tuple_backward_compatibility(reconciled_observations):
    """Verifies that predict_service_time_ms returns a backward-compatible 3-tuple with evidence_status."""
    model = EmpiricalLookupModel("test_sim_res", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations)

    res = model.predict_service_time_ms("read", concurrency=8, offered_rps=100.0)

    # 1. Unpacking backward compatibility
    service_ms, unc_ms, is_extrap = res
    assert service_ms > 0
    assert unc_ms > 0
    assert is_extrap is False
    assert len(res) == 3

    # 2. Epistemological extension attribute
    assert hasattr(res, "evidence_status")
    assert res.evidence_status == "OBSERVED"


def test_23_simpy_queueing_double_counting_protection(reconciled_observations):
    """Verifies docstring and logic protecting against double-counting queueing delays."""
    model = EmpiricalLookupModel("test_double_count", WorkloadProfile.BALANCED_OLTP_TPCB).fit(reconciled_observations)

    # Docstring must disclose queueing delay boundary
    doc = model.predict_service_time_ms.__doc__
    assert "Double-Counting" in doc
    assert "pure service demand" in doc

    # p50 in service time corresponds to per-request demand, not aggregated queue latency
    res = model.predict_service_time_ms("read", concurrency=8, offered_rps=100.0)
    assert res[0] <= 5.0  # reasonable single-request service demand


def test_24_feasibility_filter_rejects_silent_insufficient_evidence():
    """Verifies that FeasibilityFilter flags UNCERTAIN when simulation has INSUFFICIENT_EVIDENCE."""
    workload = WorkloadSpec(
        workload_id="wl_test",
        workload_name="Test Workload",
        description="Testing evidence integrity filter",
        request_rate_rps=100.0,
        read_ratio=0.8,
        write_ratio=0.2,
        concurrency_target=10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=50.0,
        max_monthly_budget_usd=1000.0,
    )
    sim_res = SimulationResult(
        architecture_id="arch_test",
        architecture_name="Arch Test",
        throughput_achieved_rps=100.0,
        p50_latency_ms=10.0,
        p90_latency_ms=20.0,
        p95_latency_ms=25.0,
        p99_latency_ms=30.0,
        max_latency_ms=40.0,
        error_rate_pct=0.0,
        total_requests=100,
        completed_requests=100,
        error_count=0,
        avg_queue_length=1.0,
        max_queue_length=5,
        component_utilizations={"db": 40.0},
        bottleneck_component="db",
        estimated_monthly_cost_usd=200.0,
        simulation_duration_seconds=10.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(20.0, 30.0),
        warnings=["Component 'db' prediction has evidence status INSUFFICIENT_EVIDENCE."],
    )

    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_res)
    assert status == FeasibilityStatus.UNCERTAIN
    ev_check = [c for c in checks if c.criterion == "evidence_integrity"][0]
    assert ev_check.status == FeasibilityStatus.UNCERTAIN
    assert "Insufficient empirical evidence" in ev_check.explanation


def test_25_feasibility_filter_rejects_silent_out_of_range():
    """Verifies that FeasibilityFilter flags UNCERTAIN when simulation has OUT_OF_RANGE."""
    workload = WorkloadSpec(
        workload_id="wl_test",
        workload_name="Test Workload",
        description="Testing evidence integrity filter",
        request_rate_rps=100.0,
        read_ratio=0.8,
        write_ratio=0.2,
        concurrency_target=10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=50.0,
        max_monthly_budget_usd=1000.0,
    )
    sim_res = SimulationResult(
        architecture_id="arch_test",
        architecture_name="Arch Test",
        throughput_achieved_rps=100.0,
        p50_latency_ms=10.0,
        p90_latency_ms=20.0,
        p95_latency_ms=25.0,
        p99_latency_ms=30.0,
        max_latency_ms=40.0,
        error_rate_pct=0.0,
        total_requests=100,
        completed_requests=100,
        error_count=0,
        avg_queue_length=1.0,
        max_queue_length=5,
        component_utilizations={"db": 40.0},
        bottleneck_component="db",
        estimated_monthly_cost_usd=200.0,
        simulation_duration_seconds=10.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(20.0, 30.0),
        warnings=["Component 'db' prediction has evidence status OUT_OF_RANGE: Concurrency 16 outside [8, 8]."],
    )

    status, checks = FeasibilityFilter.evaluate_candidate(workload, sim_res)
    assert status == FeasibilityStatus.UNCERTAIN
    ev_check = [c for c in checks if c.criterion == "evidence_integrity"][0]
    assert ev_check.status == FeasibilityStatus.UNCERTAIN
    assert "Operating outside empirically validated boundaries" in ev_check.explanation


def test_26_recommender_discloses_evidence_limitations_in_rationale():
    """Verifies that ArchitectureRecommender surfaces evidence gaps in validation_gaps."""
    workload = WorkloadSpec(
        workload_id="wl_test",
        workload_name="Test Workload",
        description="Testing recommendation rationale",
        request_rate_rps=100.0,
        read_ratio=0.8,
        write_ratio=0.2,
        concurrency_target=10,
        p95_latency_target_ms=50.0,
        min_throughput_rps=50.0,
        max_monthly_budget_usd=1000.0,
    )
    sim_res = SimulationResult(
        architecture_id="arch_a_monolith",
        architecture_name="Monolith Architecture",
        throughput_achieved_rps=100.0,
        p50_latency_ms=10.0,
        p90_latency_ms=20.0,
        p95_latency_ms=25.0,
        p99_latency_ms=30.0,
        max_latency_ms=40.0,
        error_rate_pct=0.0,
        total_requests=100,
        completed_requests=100,
        error_count=0,
        avg_queue_length=1.0,
        max_queue_length=5,
        component_utilizations={"db": 40.0},
        bottleneck_component="db",
        estimated_monthly_cost_usd=200.0,
        simulation_duration_seconds=10.0,
        random_seed=42,
        latency_uncertainty_p95_ms=(20.0, 30.0),
        warnings=["Model operating under INTERPOLATED CPU quota assumption (1.5 vCPU)."],
    )

    rec = ArchitectureRecommender.evaluate_and_recommend(workload, [sim_res])
    assert any("INTERPOLATED" in gap for gap in rec.validation_gaps)


# ==============================================================================
# 6. Preservation and Integrity
# ==============================================================================
def test_27_preservation_eight_candidate_models_intact():
    """Verifies that all 8 candidate JSON files exist in artifacts/phase_4f5/candidates/."""
    candidates_dir = Path("artifacts/phase_4f5/candidates")
    expected_files = [
        "pg16_candidate_lookup_read_only_select.json",
        "pg16_candidate_linear_read_only_select.json",
        "pg16_candidate_piecewise_read_only_select.json",
        "pg16_candidate_mechanistic_read_only_select.json",
        "pg16_candidate_lookup_balanced_oltp_tpcb.json",
        "pg16_candidate_linear_balanced_oltp_tpcb.json",
        "pg16_candidate_piecewise_balanced_oltp_tpcb.json",
        "pg16_candidate_mechanistic_balanced_oltp_tpcb.json",
    ]
    for fn in expected_files:
        p = candidates_dir / fn
        assert p.exists(), f"Candidate file {fn} missing!"
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "model_id" in data
            assert "workload_profile" in data


def test_28_preservation_twenty_four_active_models_untouched():
    """Verifies that data/registry.db has exactly 24 models and remains untouched."""
    conn = sqlite3.connect("data/registry.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM models")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 24, f"Expected 24 active registry models, got {count}!"


def test_29_preservation_historical_raw_artifacts_untouched():
    """Verifies that historical manifest hash is unchanged."""
    manifest_path = Path("artifacts/manifests/phase_4f4_execution_manifest.json")
    with open(manifest_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    assert digest == "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"


def test_30_all_four_candidate_families_conform_to_prediction_contract(reconciled_observations):
    """Verifies that all 4 candidate families expose all contract fields upon prediction."""
    models = [
        EmpiricalLookupModel("test_cand_look", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations),
        EmpiricalLinearRegressionModel("test_cand_lin", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations),
        EmpiricalPiecewiseModel("test_cand_pw", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations),
        EmpiricalMechanisticModel("test_cand_mech", WorkloadProfile.READ_ONLY_SELECT).fit(reconciled_observations),
    ]

    q = EmpiricalPostgresQuery(workload_profile=WorkloadProfile.READ_ONLY_SELECT, cpu_quota_cores=1.0)

    for m in models:
        p = m.predict(q)
        assert isinstance(p.evidence_status, EvidenceStatus)
        assert isinstance(p.prediction_method, str)
        assert len(p.prediction_method) > 0
        assert isinstance(p.measured_support, dict)
        assert "cpu_quotas" in p.measured_support
        assert isinstance(p.requested_configuration, dict)
        assert isinstance(p.uncertainty_type, UncertaintyType)
        assert isinstance(p.limitations, list)
        assert isinstance(p.identifiability_notes, list)
        assert isinstance(p.provenance, dict)
