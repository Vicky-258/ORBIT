"""
Replication-Aware Model Evaluation Framework (Phase 4F.5).

Implements Leave-One-Replication-Out (LORO) cross-validation preserving experimental independence:
- Evaluates per-condition errors, RMSE, MAE, MAPE (guarded against zero-division), and R² (guarded when undefined).
- Compares Empirical Lookup, Linear Regression, Piecewise, and Mechanistic candidates.
- Generates reproducible comparative benchmark evaluation summaries.
"""
import math
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import numpy as np

from aads.models.empirical_postgres.base import BaseEmpiricalPostgresModel
from aads.models.empirical_postgres.schemas import (
    EmpiricalPostgresQuery,
    EvaluationMetrics,
    TrialObservation,
    WorkloadProfile,
)


def calculate_metrics_safely(
    y_true: List[float],
    y_pred: List[float],
    metric_name: str = "metric",
) -> EvaluationMetrics:
    """
    Computes statistical evaluation metrics with strict guardrails:
    - Guards against division by zero in MAPE (returns None if y_true contains near-zero values).
    - Guards against zero denominator in R² (returns None if total variance is zero or undefined).
    """
    if len(y_true) == 0 or len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be non-empty and of equal length.")

    n = len(y_true)
    arr_true = np.array(y_true, dtype=np.float64)
    arr_pred = np.array(y_pred, dtype=np.float64)

    errors = arr_pred - arr_true
    abs_errors = np.abs(errors)
    sq_errors = errors ** 2

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))

    # MAPE calculation: only meaningful if all y_true are strictly positive and bounded away from zero
    mape_pct: Optional[float] = None
    notes: List[str] = []
    if np.any(np.abs(arr_true) < 1e-5):
        notes.append(f"MAPE is undefined for {metric_name} due to target values near zero.")
    else:
        mape_pct = float(np.mean(abs_errors / arr_true) * 100.0)

    # R² calculation: R² = 1 - SS_res / SS_tot
    # If SS_tot == 0 (e.g. all true values identical in single-condition test), R² is mathematically undefined.
    r2_score: Optional[float] = None
    ss_res = float(np.sum(sq_errors))
    ss_tot = float(np.sum((arr_true - np.mean(arr_true)) ** 2))

    if ss_tot <= 1e-9:
        notes.append(f"R² is undefined for {metric_name} because target variance is zero (SS_tot = 0).")
    else:
        r2_score = float(1.0 - (ss_res / ss_tot))

    return EvaluationMetrics(
        rmse=round(rmse, 4),
        mae=round(mae, 4),
        mape_pct=round(mape_pct, 4) if mape_pct is not None else None,
        r2_score=round(r2_score, 4) if r2_score is not None else None,
        sample_size=n,
        notes=notes,
    )


class ReplicationAwareEvaluator:
    """
    Evaluates candidate models using Leave-One-Replication-Out (LORO) cross-validation.
    """

    def __init__(self, observations: List[TrialObservation]):
        self.observations = observations

    def evaluate_model_family(
        self,
        model_cls: Type[BaseEmpiricalPostgresModel],
        workload_profile: WorkloadProfile,
        target_metric: str = "throughput_tps",
    ) -> Dict[str, Any]:
        """
        Runs Leave-One-Replication-Out (LORO) cross-validation for a model family on a workload.
        Replications: [1, 2, 3].
        Fold 1: train on reps [1, 2], test on rep 3.
        Fold 2: train on reps [2, 3], test on rep 1.
        Fold 3: train on reps [1, 3], test on rep 2.
        """
        profile_str = workload_profile.value if isinstance(workload_profile, WorkloadProfile) else str(workload_profile)
        matching = [o for o in self.observations if o.workload_profile == profile_str]
        if not matching:
            raise ValueError(f"No observations for workload {profile_str}")

        all_replications = sorted(list(set(o.replication for o in matching)))
        if len(all_replications) < 2:
            raise ValueError("Need at least 2 independent replications for replication-aware evaluation.")

        fold_results: List[Dict[str, Any]] = []
        overall_y_true: List[float] = []
        overall_y_pred: List[float] = []
        per_condition_true: Dict[float, List[float]] = {}
        per_condition_pred: Dict[float, List[float]] = {}

        for holdout_rep in all_replications:
            train_obs = [o for o in matching if o.replication != holdout_rep]
            test_obs = [o for o in matching if o.replication == holdout_rep]

            # Fit candidate on train_obs
            model_instance = model_cls(
                model_id=f"candidate_{model_cls.__name__}_{profile_str}_holdout_r{holdout_rep}",
                workload_profile=workload_profile,
            )
            model_instance.fit(train_obs)

            # Evaluate on test_obs
            fold_true = []
            fold_pred = []
            for obs in test_obs:
                q = EmpiricalPostgresQuery(
                    workload_profile=workload_profile,
                    cpu_quota_cores=obs.cpu_quota_cores,
                    concurrency=8,
                    scale_factor=2,
                    memory_mb=1024.0,
                )
                pred_obj = model_instance.predict(q)
                pred_metric_obj = getattr(pred_obj, target_metric)
                pred_val = pred_metric_obj.point_estimate
                true_val = getattr(obs, target_metric)

                fold_true.append(true_val)
                fold_pred.append(pred_val)
                overall_y_true.append(true_val)
                overall_y_pred.append(pred_val)

                c_quota = obs.cpu_quota_cores
                per_condition_true.setdefault(c_quota, []).append(true_val)
                per_condition_pred.setdefault(c_quota, []).append(pred_val)

            fold_eval = calculate_metrics_safely(fold_true, fold_pred, f"{target_metric}_fold_r{holdout_rep}")
            fold_results.append({
                "holdout_replication": holdout_rep,
                "train_sample_count": len(train_obs),
                "test_sample_count": len(test_obs),
                "metrics": fold_eval.model_dump(),
            })

        overall_eval = calculate_metrics_safely(overall_y_true, overall_y_pred, target_metric)

        # Per-condition RMSE
        per_cond_errors = {}
        for c_quota, t_vals in per_condition_true.items():
            p_vals = per_condition_pred[c_quota]
            c_eval = calculate_metrics_safely(t_vals, p_vals, f"{target_metric}_cpu{c_quota}")
            per_cond_errors[f"cpu_{c_quota}vCPU"] = {
                "rmse": c_eval.rmse,
                "mae": c_eval.mae,
                "mape_pct": c_eval.mape_pct,
            }

        # Replication variability (CV) of ground truth
        replication_cv = {}
        for c_quota, t_vals in per_condition_true.items():
            mean_v = float(np.mean(t_vals))
            std_v = float(np.std(t_vals, ddof=1)) if len(t_vals) > 1 else 0.0
            cv = (std_v / mean_v * 100.0) if mean_v > 0 else 0.0
            replication_cv[f"cpu_{c_quota}vCPU"] = round(cv, 2)

        return {
            "model_family": model_cls.__name__,
            "workload_profile": profile_str,
            "target_metric": target_metric,
            "cross_validation_method": "Leave-One-Replication-Out (LORO)",
            "folds_evaluated": len(fold_results),
            "overall_metrics": overall_eval.model_dump(),
            "per_condition_errors": per_cond_errors,
            "ground_truth_replication_cv_pct": replication_cv,
            "fold_details": fold_results,
        }
