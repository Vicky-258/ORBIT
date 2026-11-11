# Phase 4F.5.1 — Validation & Test Execution Report

**Phase:** 4F.5.1 — Candidate Model Scientific Audit & Prediction Contract Hardening  
**Date:** November 11, 2026  
**Execution Mode:** Strictly offline test execution  
**Verdict:** COMPLETE_WITH_LIMITATIONS  

---

## 1. Test Suite Execution Summary

All verification and regression tests were executed within the offline Python 3.12 virtual environment using pytest. Zero live benchmarks, zero Docker containers, zero pgbench processes, and zero model promotions were executed.

| Test Suite File | Tests Executed | Passed | Failed | Duration | Scope |
|---|---|---|---|---|---|
| `tests/test_phase_4f51_scientific_audit.py` | 30 | 30 | 0 | 0.09s | Focused Phase 4F.5.1 scientific audit & prediction contract |
| `tests/test_phase_4f5_model_development.py` | 20 | 20 | 0 | 0.09s | Phase 4F.5 candidate model regression suite |
| **Total PostgreSQL Empirical Tests** | **50** | **50** | **0** | **0.18s** | **100% Pass Rate** |
| Full Offline Repository Test Suite | 322 | 322 | 0 | 18.53s | Complete repository offline regression suite (8 live LLM tests deselected) |

---

## 2. Granular Breakdown by Audit Area

### Area 1: Evidence Classification (Tests 1–8)
- `test_01_evidence_classification_exact_observed`: Exact query matching measured support (1.0 or 2.0 vCPU, SF2, 8 clients, 1024 MB RAM) returns `EvidenceStatus.OBSERVED` with `is_extrapolated=False`.
- `test_02_evidence_classification_cpu_1_5_interpolated`: Intermediate query (1.5 vCPU) returns `EvidenceStatus.INTERPOLATED`. Verified strictly that `pred.evidence_status != EvidenceStatus.OBSERVED` and `pred.state != ModelState.IN_RANGE`.
- `test_03_evidence_classification_cpu_3_out_of_range`: Out-of-bounds CPU quota (3.0 vCPU) returns `EvidenceStatus.OUT_OF_RANGE` with `is_extrapolated=True`.
- `test_04_evidence_classification_concurrency_16_out_of_range`: Deviating concurrency (16 clients) returns `EvidenceStatus.OUT_OF_RANGE`.
- `test_05_evidence_classification_sf20_out_of_range`: Deviating database scale (SF20) returns `EvidenceStatus.OUT_OF_RANGE`.
- `test_06_evidence_classification_memory_out_of_range`: Deviating memory quota (2048 MB) returns `EvidenceStatus.OUT_OF_RANGE`.
- `test_07_evidence_classification_unsupported_workload_insufficient_evidence`: Cross-workload query returns `EvidenceStatus.INSUFFICIENT_EVIDENCE` with `point_estimate=None` and `uncertainty_type=UNAVAILABLE`.
- `test_08_evidence_classification_missing_cpu_insufficient_evidence`: Missing required query parameter (`cpu_quota_cores=None`) returns `EvidenceStatus.INSUFFICIENT_EVIDENCE`.

### Area 2: Uncertainty Types and Heuristic Multipliers (Tests 9–13)
- `test_09_uncertainty_replication_vs_interpolation`: Proves empirical sample variance at anchors (`REPLICATION_SAMPLE_STD`, `is_heuristic=False`) is distinguished from interpolation variance (`INTERPOLATION_HEURISTIC`, `is_heuristic=True`).
- `test_10_heuristic_multipliers_never_labelled_statistical_ci`: Confirms that across Lookup, Linear, and Piecewise models, heuristic multipliers set `confidence_interval_95=None` and expose bounds strictly via `heuristic_interval`.
- `test_11_extrapolation_heuristic_distance_multiplier`: Validates exact penalty multiplier formula ($2.0 + 1.5 \times distance$): at 3.0 vCPU, multiplier is 3.5x; at 0.5 vCPU, multiplier is 2.75x.
- `test_12_missing_uncertainty_remains_unavailable_not_zero`: Proves that missing uncertainty under `INSUFFICIENT_EVIDENCE` is `None` with `uncertainty_type=UNAVAILABLE`, never silently set to 0.0.
- `test_13_interpolation_uncertainty_not_solely_endpoint_variance`: Verifies that interpolation estimates disclose that endpoint variance does not prove intermediate behavior.

### Area 3: Mechanistic Model Identifiability (Tests 14–16)
- `test_14_mechanistic_identifiability_parameters_identified`: Verifies `s_cpu` and `s_fixed` are recorded as `IDENTIFIABLE`, while `s_wal` and `w_lock` are recorded as `ASSUMPTION_DEPENDENT_NON_IDENTIFIABLE`.
- `test_15_mechanistic_identifiability_sum_constant`: Empirically demonstrates that multiple distinct $(S_{\text{wal}}, W_{\text{lock}})$ pairs having constant sum yield identical predictions across all CPU quotas.
- `test_16_mechanistic_causal_claims_absent`: Verifies absence of unproven claims (e.g. row locks proven dominant) from generated output disclosures.

### Area 4: Evaluation Terminology and Indistinguishability (Tests 17–21)
- `test_17_evaluation_loro_labelled_replication_holdout`: Confirms LORO cross-validation is formally classified as `REPLICATION_HOLDOUT` with explicit scope limitations.
- `test_18_evaluation_no_unseen_configuration_generalization_claim`: Confirms evaluation disclaims unseen configuration, workload, and environment holdouts.
- `test_19_model_mathematical_indistinguishability_at_observed_anchors`: Proves that Lookup, Linear, and Piecewise models predict identical point estimates (within 0.01 TPS) at 1.0 and 2.0 vCPU.
- `test_20_r2_guard_near_zero_variance`: Confirms $R^2$ is safely returned as `None` when target variance is near zero.
- `test_21_mape_guard_near_zero_actuals`: Confirms MAPE is safely returned as `None` when actual values approach zero.

### Area 5: SimPy and Recommendation Engine Integration (Tests 22–26)
- `test_22_simpy_service_time_result_tuple_backward_compatibility`: Verifies `predict_service_time_ms` returns a 3-tuple that unpacks cleanly while carrying `.evidence_status`.
- `test_23_simpy_queueing_double_counting_protection`: Confirms documentation and behavior guarding against simulating queueing on top of already-queued latency.
- `test_24_feasibility_filter_rejects_silent_insufficient_evidence`: Proves `FeasibilityFilter` marks candidate feasibility `UNCERTAIN` when simulation warnings contain `INSUFFICIENT_EVIDENCE`.
- `test_25_feasibility_filter_rejects_silent_out_of_range`: Proves `FeasibilityFilter` marks candidate feasibility `UNCERTAIN` when simulation warnings contain `OUT_OF_RANGE`.
- `test_26_recommender_discloses_evidence_limitations_in_rationale`: Confirms `ArchitectureRecommender` discloses simulation warnings in `validation_gaps`.

### Area 6: Preservation and Artifact Integrity (Tests 27–30)
- `test_27_preservation_eight_candidate_models_intact`: Confirms all 8 candidate JSON files exist in `artifacts/phase_4f5/candidates/` and load valid models.
- `test_28_preservation_twenty_four_active_models_untouched`: Confirms `data/registry.db` contains exactly 24 active models, with zero promotions or mutations.
- `test_29_preservation_historical_raw_artifacts_untouched`: Confirms historical execution manifest SHA-256 matches `69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6`.
- `test_30_all_four_candidate_families_conform_to_prediction_contract`: Confirms that Lookup, Linear, Piecewise, and Mechanistic models all populate all required contract fields.

---

## 3. Candidate Model Inventory & Artifact Verification

All 8 candidate models were re-serialized with the hardened contract fields:

| Candidate Model ID | Model Family | Workload Profile | Serialized File | Identifiability Status |
|---|---|---|---|---|
| `pg16_candidate_lookup_read_only_select` | EmpiricalLookupModel | `read_only_select` | `artifacts/phase_4f5/candidates/pg16_candidate_lookup_read_only_select.json` | Non-parametric |
| `pg16_candidate_linear_read_only_select` | EmpiricalLinearRegressionModel | `read_only_select` | `artifacts/phase_4f5/candidates/pg16_candidate_linear_read_only_select.json` | OLS Parametric |
| `pg16_candidate_piecewise_read_only_select` | EmpiricalPiecewiseModel | `read_only_select` | `artifacts/phase_4f5/candidates/pg16_candidate_piecewise_read_only_select.json` | Saturation Knee (Hypothesis) |
| `pg16_candidate_mechanistic_read_only_select` | EmpiricalMechanisticModel | `read_only_select` | `artifacts/phase_4f5/candidates/pg16_candidate_mechanistic_read_only_select.json` | $S_{\text{cpu}}$ Identifiable |
| `pg16_candidate_lookup_balanced_oltp_tpcb` | EmpiricalLookupModel | `balanced_oltp_tpcb` | `artifacts/phase_4f5/candidates/pg16_candidate_lookup_balanced_oltp_tpcb.json` | Non-parametric |
| `pg16_candidate_linear_balanced_oltp_tpcb` | EmpiricalLinearRegressionModel | `balanced_oltp_tpcb` | `artifacts/phase_4f5/candidates/pg16_candidate_linear_balanced_oltp_tpcb.json` | OLS Parametric |
| `pg16_candidate_piecewise_balanced_oltp_tpcb` | EmpiricalPiecewiseModel | `balanced_oltp_tpcb` | `artifacts/phase_4f5/candidates/pg16_candidate_piecewise_balanced_oltp_tpcb.json` | Saturation Knee at 1.25 (Hypothesis) |
| `pg16_candidate_mechanistic_balanced_oltp_tpcb` | EmpiricalMechanisticModel | `balanced_oltp_tpcb` | `artifacts/phase_4f5/candidates/pg16_candidate_mechanistic_balanced_oltp_tpcb.json` | $S_{\text{wal}}, W_{\text{lock}}$ Confounded |

Comparison report: `artifacts/phase_4f5/candidates/model_comparison_results.json` updated with replication holdout terminology and identifiability disclosures.

---

## 4. Active Model Registry Preservation

Inspection of `data/registry.db`:
```sql
SELECT COUNT(*) FROM models; -- Output: 24
```
- Active model count: **24 models** (unchanged).
- Model promotions: **0** (strictly prohibited).
- Registry file modifications: **None**.

---

## 5. Compliance with Strict Execution Restrictions

1. **Docker Execution:** Zero Docker commands executed (`docker run`, `docker start`, etc. = 0).
2. **PostgreSQL Benchmarks:** Zero `pgbench` or live queries executed.
3. **Model Promotion:** Zero models promoted into `data/registry.db`.
4. **Historical Evidence:** All raw artifacts in `artifacts/phase_4f4_empirical/` and reconciliation outputs in `artifacts/phase_4f46/reconciliation/` remain byte-for-byte identical.
5. **Manifest Hash:** Verified match with `69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6`.

---

## 6. Final Readiness Verdict

**Verdict:** `COMPLETE_WITH_LIMITATIONS`

**Rationale:**
- All scientific audit criteria, schema definitions, uncertainty types, identifiability declarations, and evaluation terminology corrections are fully implemented.
- 50 PostgreSQL empirical tests and 322 total repository tests pass cleanly.
- The `WITH_LIMITATIONS` qualification is mandated because the underlying empirical evidence remains narrow (2-point CPU support), leaving intermediate curvature and OLTP lock vs. WAL causal decomposition unidentifiable until multi-point counterfactual benchmark campaigns are conducted in Phase 4F.6.
