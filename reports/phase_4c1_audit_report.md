# AADS Phase 4C.1 Audit & Reproducibility Report
**Date:** October 28, 2026  
**Auditor:** AADS Core Engineering & Verification Agent  
**Branch:** `feat/phase-4c1-audit`  
**Evaluation Suite:** Phase 4C Decision Quality & Comparative Planning Harness  

---

## Executive Summary

Phase 4C.1 was commissioned to conduct an exhaustive, independent audit and reproducibility assessment of the Phase 4C evaluation results prior to advancing empirical calibration work. 

The primary findings of this audit are:
1. **Repository & Baseline Integrity:** The documented baseline commit `1d4b65d` (Phase 4B), interim bugfix commit `07ae687`, and Phase 4C final commit `5eb6763` are verified and present in git history. All 104 existing repository tests pass with zero failures. With the addition of the Phase 4C.1 audit suite, 116 tests pass in project virtual environment.
2. **Deterministic Reproducibility:** Back-to-back offline evaluations of all 24 scenarios across all 3 strategies (72 scenario-strategy executions) confirmed **100% bitwise semantic determinism** for candidate rankings, utility scores, feasibility classifications, and tool dispatch sequences under fixed random seeds. The only variance between runs is minor wall-clock execution timing jitter (1–4 ms).
3. **Top-Choice Agreement vs Zero Regret Resolution:** The reported combination of **70.8% top-choice agreement** and **0.000 mean regret** across all three strategies is mathematically explained by a formula implementation defect in `aads/evaluation/metrics.py`. Because the strategy selects the candidate with maximum utility score ($U(selected) = \max_A U(A)$), the selected score was strictly greater than the reference candidate score in all 7 disagreement scenarios ($U(selected) > U(reference)$). The regret formula clamped negative values to 0.0, masking fixture divergence.
4. **Resolution of the Architecture A Latency Discrepancy (13.58 ms vs 19.8 ms):** The actual, reproducible SimPy simulation of Architecture A under the social-feed workload (500 RPS, seed 42) is **13.58 ms**, yielding overall candidate scores of **Arch B = 0.586, Arch A = 0.550, Arch C = 0.530** (stored in `data/evaluations/phase_4c_results.json`). The **19.8 ms** value cited in Section 6 of `reports/phase_4c_evaluation_report.md` was an uncommitted test dummy value from `tests/test_agent_evaluation.py:316` mistakenly transcribed into the markdown narrative.
5. **Scoring Audit & Complexity Labeling:** Recomputation of the B-vs-C multi-objective scoring confirmed correct cost and latency normalization and hard-constraint precedence. However, the score labeled `complexity_score` is an engineering heuristic proxy based on hardcoded topological substrings (Arch A = 1.0, B = 0.7, C = 0.4), not an empirically calibrated metric.
6. **Latency Uncertainty Bounds Reclassification:** The formula in `aads/simulation/metrics_collector.py` scales the standard error of the sample mean by 1.5 rather than computing quantile standard error under autocorrelated queueing delays. It has been formally reclassified and documented as an **engineering heuristic uncertainty bound**, and misleading "confidence interval" labels have been replaced across the codebase.
7. **Fairness & Provenance:** Strategy C in offline mode was found to branch on `scenario.scenario_class` within `_offline_llm_adaptive_decision`. Provenance tracking has been updated to explicitly distinguish `llm_adaptive_live`, `llm_adaptive_mocked_offline`, and `llm_adaptive_fallback`.

---

## 1. Repository and Baseline Audit

### 1.1 Git Branch Ancestry & Commit Verification
The repository Git graph was audited to verify the commit claims made in the Phase 4C report:
- **Phase 4B Baseline Commit:** `1d4b65d` (`feat(agent): implement agentic planning, tool selection & adaptive investigation (Phase 4B)`) — Verified.
- **Interim Bugfix Commit:** `07ae687` (`fix(api): correct candidate generator arguments in run_end_to_end_workflow`) — Verified.
- **Phase 4C Final Commit:** `5eb6763` (`feat(evaluation): implement agentic evaluation harness, comparative strategies, and decision quality metrics (Phase 4C)`) on branch `feat/phase-4c-evaluation` — Verified.
- **Active Audit Branch:** `feat/phase-4c1-audit` created from `5eb6763`.

### 1.2 Baseline Test Execution
Before modifying any files, the complete repository test suite was executed using the project virtual environment:
```bash
.venv/bin/pytest -v
```
**Results:**
- **Status:** PASS (Exit code: 0)
- **Tests Collected & Passed:** 104 passed in 203.88s (0:03:23)
- **Failures:** 0
- **Warnings:** 0

---

## 2. Reproducibility Assessment

The offline evaluation suite was executed across repeated runs to establish reproducibility:
```bash
.venv/bin/python3 -m aads.evaluation.run --suite all --mode offline
```
Two isolated audit runs were saved:
- Run 1: `data/evaluations/phase_4c1_audit_run1.json` (Timestamp: `2026-10-28T08:08:42.593817+00:00`)
- Run 2: `data/evaluations/phase_4c1_audit_run2.json` (Timestamp: `2026-10-28T08:12:15.118294+00:00`)

### 2.1 Comparison Summary
Detailed comparison between Run 1 and Run 2 is preserved in `data/evaluations/phase_4c1_reproducibility.json`:

| Metric Dimension | Run 1 | Run 2 | Difference / Match |
| :--- | :--- | :--- | :--- |
| **Scenarios Evaluated** | 24 | 24 | Identical (12 Dev, 12 Held-out) |
| **Total Executions** | 72 | 72 | Identical |
| **Selected Architecture IDs** | 72 / 72 match | 72 / 72 match | 100% Bitwise Match |
| **Candidate Utility Scores** | 72 / 72 match | 72 / 72 match | 100% Bitwise Match |
| **Candidate Rankings** | 72 / 72 match | 72 / 72 match | 100% Bitwise Match |
| **Feasible Candidate Sets** | 72 / 72 match | 72 / 72 match | 100% Bitwise Match |
| **Hard Constraint Satisfaction Rate** | 100.0% | 100.0% | Identical across all strategies |
| **Top-Choice Agreement Rate** | 70.8% | 70.8% | Identical across all strategies |
| **Mean Regret vs Reference** | 0.000 | 0.000 | Identical across all strategies |
| **Investigation Trace Sequences** | 72 / 72 match | 72 / 72 match | Identical actions, targets & verdicts |
| **Strategy A Mean Latency** | 144.4 ms | 147.6 ms | $\\Delta = 3.2$ ms (Wall-clock jitter) |
| **Strategy B Mean Latency** | 165.8 ms | 169.5 ms | $\\Delta = 3.7$ ms (Wall-clock jitter) |
| **Strategy C Mean Latency** | 153.2 ms | 156.6 ms | $\\Delta = 3.4$ ms (Wall-clock jitter) |

**Conclusion on Reproducibility:**
The simulation engine and offline decision rules are **100% semantically deterministic** when executed with fixed scenario seeds. Nondeterminism is strictly confined to physical wall-clock CPU execution time.

---

## 3. Investigation: Top-Choice Agreement vs Zero Regret

The Phase 4C report claimed:
- Top-choice agreement: **70.8%** (17 of 24 scenarios) for all three strategies.
- Mean regret: **0.000** for all three strategies.
- Identical top-choice selections across all three strategies.

### 3.1 Mathematical Implementation Audit
In `aads/evaluation/metrics.py`:
```python
# Regret vs reference
regret = 0.0
if ref.expected_winner_id and result.selected_architecture_id:
    if ref.expected_winner_id != result.selected_architecture_id:
        ref_score = result.candidate_scores.get(ref.expected_winner_id, 0.0)
        sel_score = result.candidate_scores.get(result.selected_architecture_id, 0.0)
        if ref_score > sel_score:
            regret = round(ref_score - sel_score, 3)
```

The mathematical reason for zero regret is straightforward:
1. The architecture recommendation engine ranks candidates by `overall_score` and selects the feasible candidate that maximizes `overall_score`.
2. Therefore, by definition:
   $$\\text{sel\\_score} = \\max_{a \\in \\text{feasible}} \\text{candidate\\_scores}[a]$$
3. In all 7 scenarios where `ref.expected_winner_id != result.selected_architecture_id`, the candidate chosen by the strategy had a **strictly higher score** under the evaluator utility function than the author-designated reference candidate:
   $$\\text{sel\\_score} > \\text{ref\\_score} \\implies \\text{ref\\_score} - \\text{sel\\_score} < 0$$
4. Because `ref_score > sel_score` was never true, `regret` evaluated to `0.0` for all 24 scenarios.

### 3.2 Audit of the 7 Disagreement Scenarios
The full per-scenario audit record is saved in `data/evaluations/phase_4c1_scenario_audit.json`. The 7 disagreement scenarios fall into three categories:

#### Category 1: Point Estimate vs Uncertainty Bound Feasibility (`dev_03_boundary`)
- **Workload:** 550 RPS, p95 SLA $\\le$ 8.0 ms.
- **Reference Winner:** `arch_c_async` (Author expected Arch B to be disqualified because its heuristic uncertainty bound reached 9.33 ms).
- **Strategy Selected:** `arch_b_cached` (Simulated point estimate was 7.76 ms $\\le$ 8.0 ms).
- **Utility Scores:** Arch B = **0.743**, Arch C = **0.680** (Score margin = $+0.063$ favoring B).
- **Root Cause:** The feasibility filter evaluates hard constraints against the point estimate `p95 <= target_ms`, not the upper uncertainty bound. Arch B met the hard constraint and won on cost ($176 vs $216) and simplicity (0.7 vs 0.4).

#### Category 2: Throughput Variance / Hard SLA Breach (`dev_08_unnecessary_investigation`)
- **Workload:** 80 RPS, hard constraint `min_throughput_rps = 75.0`.
- **Reference Winner:** `arch_a_simple` (Author intuitively assumed Arch A would easily handle 80 RPS).
- **Strategy Selected:** `arch_b_cached`.
- **Simulation Reality:** Arch A achieved **73.6 RPS** in the 5.0s SimPy simulation (seed 42), falling 1.4 RPS short of the 75.0 RPS threshold due to arrival variance and in-flight requests at termination.
- **Feasibility:** Arch A was classified as `INFEASIBLE`. Arch B achieved 79.0 RPS (`FEASIBLE`). Arch C exceeded budget ($216 > $200). Arch B was the sole feasible option.

#### Category 3: Multi-Objective Utility vs Intuitive Author Expectation (`dev_05`, `heldout_02`, `heldout_05`, `heldout_06`, `heldout_10`)
- In these 5 scenarios, the fixture author expected Arch B as the "standard" balanced choice.
- However, when evaluated against the mathematical utility function:
  $$\\text{Overall Score} = w_{\\text{cost}} S_{\\text{cost}} + w_{\\text{lat}} S_{\\text{lat}} + w_{\\text{simp}} S_{\\text{simp}}$$
  Arch A easily met all latency SLAs ($p95 < 10$ ms vs targets of 40–50 ms). Arch A costs $133/mo (vs $176 for B) and has simplicity 1.0 (vs 0.7 for B). Arch A mathematically outscored Arch B in `dev_05`, `heldout_02`, `heldout_05`, and `heldout_10`.
- In `heldout_06_high_uncertainty`, soft preferences allocated 50% weight to latency. Arch C (p95 = 3.28 ms) outscored Arch B (p95 = 7.75 ms) with scores **0.580 vs 0.563**.

### 3.3 Metric Corrections Implemented
To eliminate this artifact without breaking backward compatibility:
1. `ExpectedReferenceOutcome` in `aads/evaluation/scenarios.py` now supports:
   - `expected_winner_set: List[str]` for scenarios with multiple tied or valid optimal architectures.
   - `reference_objective_value: Optional[float]` for an independently defined reference score.
2. `compute_metrics` in `aads/evaluation/metrics.py` now:
   - Checks `selected_architecture_id in (ref.expected_winner_set or [ref.expected_winner_id])`.
   - Records `raw_unrounded_regret` and `score_margin_selected_vs_ref` to expose underlying unrounded margins.

---

## 4. Investigation: Architecture A Latency Discrepancy

### 4.1 Provenance of 13.58 ms vs 19.8 ms
- **Phase 4B Demo / Phase 4C Raw Data:** Reports Architecture A p95 latency = **13.58 ms**.
- **Phase 4C Report Section 6:** Reports Architecture A p95 latency = **19.8 ms** in handwritten LaTeX calculations.

### 4.2 Investigation Findings
1. **Raw Simulation Output (13.58 ms):**
   - Workload: 500 RPS, read ratio 0.90, write ratio 0.10, peak load factor 1.5, simulation duration 5.0s, random seed 42.
   - Running `engine.simulate_architecture(arch_a, workload, duration_seconds=5.0, random_seed=42)` produces exactly **13.58 ms**.
   - Under $p95 = 13.58$ ms, the recommender calculates:
     - Cost Scores: A = 1.000 ($35%), B = 0.482 ($35%), C = 0.000 ($35%)
     - Latency Scores: A = 0.000 ($45%), B = 0.616 ($45%), C = 1.000 ($45%)
     - Simplicity Scores: A = 1.000 ($20%), B = 0.700 ($20%), C = 0.400 ($20%)
     - Total Scores: **Arch B = 0.586, Arch A = 0.550, Arch C = 0.530**.
   - These exact scores are stored in `data/evaluations/phase_4c_results.json:2951`.
2. **Report Section 6 Mock Value (19.8 ms):**
   - In `tests/test_agent_evaluation.py:316`:
     ```python
     sim_a = make_dummy_sim_result("arch_a_simple", "Architecture A", p95=19.8, cost=133.0)
     ```
   - When drafting Section 6 of `reports/phase_4c_evaluation_report.md`, the author manually transcribed `19.80` from this unit test mock fixture into the LaTeX formula:
     $$\\text{Latency Score}(B) = 1.0 - \\frac{7.25 - 3.30}{19.80 - 3.30} = 0.761 \\implies 0.45 \\times 0.761 = +0.3423$$
     yielding Total Score B = **0.651** and C = **0.530**.
3. **Conclusion:**
   The difference is **not** caused by model drift or simulation nondeterminism. **13.58 ms** is the true, verified, and reproducible simulation result. **19.8 ms** was a synthetic test fixture number inadvertently copied into the report narrative. In both cases, Arch B beats Arch C under the stated user preferences.

---

## 5. Audit of B-versus-C Recommendation Scoring

The Phase 4B social-feed recommendation was audited against `TradeoffAnalyzer` and `ArchitectureRecommender`:

| Requirement / Dimension | Implementation Rule | Audit Finding |
| :--- | :--- | :--- |
| **1. Hard Constraints** | Checked before multi-objective ranking. | Feasible candidates must satisfy all hard constraints. Infeasible options receive a $0.1\\times$ multiplier. |
| **2. Cost Normalization** | $1.0 - \\frac{\\text{cost} - \\min}{\\max - \\min}$ | Correctly maps lowest cost ($133) to 1.0 and highest cost ($216) to 0.0. |
| **3. Latency Normalization** | $1.0 - \\frac{\\text{p95} - \\min}{\\max - \\min}$ | Correctly maps lowest p95 (3.30 ms) to 1.0 and highest p95 (13.58 ms) to 0.0. |
| **4. Simplicity Score** | Hardcoded by architecture ID. | Arch A = 1.0, Arch B = 0.7, Arch C = 0.4. **Heuristic only; no empirical calibration.** |
| **5. Weight Normalization** | Normalized to sum to 1.0. | $\\sum w_i = 0.35 + 0.45 + 0.20 = 1.00$. Applied linearly. |
| **6. Pareto Dominance** | Pairwise comparison on normalized dimensions. | Neither B nor C dominates the other (B is cheaper and simpler; C is faster). |
| **7. Final Scores** | Weighted linear combination. | **Arch B = 0.586, Arch A = 0.550, Arch C = 0.530.** Arch B wins. |
| **8. Rationale Accuracy** | Matches calculated metrics. | Accurately identifies Redis caching benefits and cost-performance trade-offs. |

---

## 6. Audit of Latency Uncertainty Bounds

### 6.1 Formula Analysis
In `aads/simulation/metrics_collector.py`:
```python
se_margin = 1.96 * (std_lat / math.sqrt(max(1, len(latencies)))) * 1.5 if latencies else 0.5
p95_bounds = (round(max(0.1, p95 - se_margin), 2), round(p95 + se_margin, 2))
```

### 6.2 Statistical Defects
1. **Quantity Mismatch:** The formula computes the standard error of the **mean** ($\\sigma / \\sqrt{n}$) multiplied by an ad-hoc factor of 1.5, rather than the standard error of a quantile:
   $$\\text{SE}(x_p) \\approx \\frac{\\sqrt{p(1-p)}}{f(x_p)\\sqrt{n}}$$
2. **Autocorrelation (Serial Correlation):** Queued request latencies in SimPy are non-independent. The IID assumption severely underestimates variance during congestion periods.
3. **Transient Initialization Bias:** Simulation starts from an empty queue; no warm-up period is discarded.
4. **Single Replication:** Point estimates are derived from a single 5-second trajectory with a fixed seed.

### 6.3 Remediation Actions
1. Reclassified all references from "confidence interval" to **heuristic uncertainty bounds** in `aads/core/schemas.py`, `aads/simulation/metrics_collector.py`, `aads/evaluation/recommender.py`, and `aads/agent/investigation_planner.py`.
2. Preserved the schema field `latency_uncertainty_p95_ms` for backward compatibility, with updated docstrings explicitly noting its heuristic proxy status.
3. Requirements for a rigorous statistical interval in a future phase:
   - Multiple independent replications (e.g., $R \\ge 10$ with different seeds).
   - Batch-means estimator or bootstrap quantile estimation on steady-state intervals.
   - Discarding initial warm-up period ($t < 1.0$s).

---

## 7. Evaluation Fairness & Provenance Findings

| Fairness Dimension | Audit Status | Details |
| :--- | :--- | :--- |
| **Input Equivalence** | EQUIVALENT | Strategies A, B, and C receive identical `workload_spec`, candidate sets, simulation configurations, and registry snapshots. |
| **Investigation Budgets** | EQUIVALENT | Fixed maximum rounds (3) and execution timeout budgets (60s) enforced uniformly. |
| **Offline Mode Integrity** | DEFECT IDENTIFIED | In offline mode, Strategy C executed `_offline_llm_adaptive_decision`, which branched on `scenario.scenario_class` (metadata unavailable to a live agent). |
| **Provenance Tracking** | CORRECTED | Updated `provenance_map` to explicitly distinguish `llm_adaptive_live`, `llm_adaptive_mocked_offline`, and `llm_adaptive_fallback`. |
| **Synthetic vs Empirical Models** | VERIFIED | Component models in registry cleanly track `is_synthetic_fixture`, `is_validated`, and `provenance`. |

---

## 8. Summary of Files Changed

1. `aads/core/schemas.py`: Documented `latency_uncertainty_p95_ms` as heuristic uncertainty bounds.
2. `aads/simulation/metrics_collector.py`: Updated uncertainty comments to clarify heuristic nature.
3. `aads/evaluation/recommender.py`: Updated executive summary label from "confidence interval" to "heuristic uncertainty bounds".
4. `aads/agent/investigation_planner.py`: Updated planning reasons to reference heuristic uncertainty bounds.
5. `aads/evaluation/strategies.py`: Updated uncertainty strings and set explicit pipeline provenance (`llm_adaptive_live` vs `llm_adaptive_mocked_offline` vs `llm_adaptive_fallback`).
6. `aads/evaluation/scenarios.py`: Added `expected_winner_set` and `reference_objective_value` to `ExpectedReferenceOutcome`.
7. `aads/evaluation/metrics.py`: Supported `expected_winner_set`, exposed `raw_unrounded_regret` and `score_margin_selected_vs_ref`.
8. `run_demo.py`: Updated CLI output label to "p95 Heuristic Uncertainty Bounds".
9. `tests/test_phase_4c1_audit.py`: Added 12 comprehensive regression tests.
10. `data/evaluations/phase_4c1_reproducibility.json`: Generated reproducibility verification artifact.
11. `data/evaluations/phase_4c1_scenario_audit.json`: Generated per-scenario audit records across all 72 executions.

---

## 9. Regression Testing & Verification Commands

All 116 tests (104 baseline + 12 audit tests) pass cleanly:
```bash
# Run Phase 4C.1 audit suite
.venv/bin/pytest tests/test_phase_4c1_audit.py -v

# Run complete repository test suite
.venv/bin/pytest -v
```

---

## 10. Remaining Limitations & Open Questions

1. **Synthetic Scenario Authoring:** The 7 divergence cases in evaluation were caused by human author intuition differing from the mathematical multi-objective scoring formula. Future scenario authoring should calibrate reference expectations against independently evaluated utility values.
2. **Online LLM Benchmarking:** Strategy C in offline mode currently simulates decisions via a deterministic heuristic. Comprehensive empirical calibration with live LLM calls requires an isolated, non-rate-limited environment.
3. **Statistical Quantile Estimation:** The current simulator uses heuristic uncertainty bounds. A dedicated replication harness is needed before claiming statistically valid 95% confidence intervals.
