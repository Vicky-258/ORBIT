"""
Model Trainer and Held-Out Evaluator (Hardened for Phase 4D.2).
Performs strict group-based train/validation split (holding out entire independent configurations
to prevent replication data leakage), computes mathematically honest RMSE, MAE, MAPE, Max Error,
and R2 on held-out observations, and constructs validated ModelRecord for registry insertion.
"""
import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from orbit.core.schemas import ExperimentRecord, ModelRecord
from orbit.modeling.lookup_model import LookupInterpolationModel
from orbit.modeling.regression_model import RegressionPerformanceModel


class InsufficientIndependentGroupsError(ValueError):
    """Raised when an experiment dataset lacks sufficient independent configurations for held-out validation."""
    pass


class ModelTrainer:
    """Trains and validates empirical component models with strict group-based held-out evaluation."""

    @staticmethod
    def _group_train_test_split(
        experiments: List[ExperimentRecord],
        test_ratio: float = 0.30,
    ) -> Tuple[List[ExperimentRecord], List[ExperimentRecord]]:
        """
        Splits experiment records into training and testing sets strictly by independent experimental configuration
        unit (concurrency, read_ratio). All replications of a configuration are assigned to the same split.
        Fails closed with InsufficientIndependentGroupsError if fewer than 3 independent configurations exist.
        """
        # Group by independent experimental unit: (concurrency, round(read_ratio, 2))
        configs = sorted(list(set((e.concurrency, round(e.read_ratio, 2)) for e in experiments)))

        if len(configs) < 3:
            raise InsufficientIndependentGroupsError(
                f"Need at least 3 independent experimental configurations to perform group-based held-out validation "
                f"without data leakage. Found {len(configs)} configuration(s): {configs}."
            )

        n_configs = len(configs)
        n_test_configs = max(1, int(round(n_configs * test_ratio)))

        # Boundary-point policy:
        # Boundary configurations (configs[0] and configs[-1]) are intentionally retained in the training set
        # so that the parametric regression and lookup models fit across the entire supported operating range
        # [c_min, c_max], preventing extrapolation errors during simulation.
        # Held-out validation is performed strictly on intermediate configurations configs[1:-1]
        # to assess true interpolation quality within the operational envelope.
        intermediate = configs[1:-1]
        if not intermediate:
            raise InsufficientIndependentGroupsError(
                f"Need at least 3 distinct configurations to have intermediate test configurations. Found {configs}."
            )

        step = max(1, len(intermediate) // n_test_configs)
        test_config_set = set(intermediate[::step][:n_test_configs])

        train_exps = [e for e in experiments if (e.concurrency, round(e.read_ratio, 2)) not in test_config_set]
        test_exps = [e for e in experiments if (e.concurrency, round(e.read_ratio, 2)) in test_config_set]

        # Verify zero configuration leakage between train and test
        train_configs = set((e.concurrency, round(e.read_ratio, 2)) for e in train_exps)
        test_configs = set((e.concurrency, round(e.read_ratio, 2)) for e in test_exps)
        overlap = train_configs.intersection(test_configs)
        if overlap:
            raise RuntimeError(f"Configuration leakage detected between train and test sets: {overlap}")

        if not train_exps or not test_exps:
            raise InsufficientIndependentGroupsError(
                "Train or test split is empty after grouping. Provide more diverse experiment configurations."
            )

        return train_exps, test_exps

    @staticmethod
    def train_and_validate(
        component_name: str,
        version: str,
        experiments: List[ExperimentRecord],
        test_ratio: float = 0.30,
    ) -> Tuple[ModelRecord, Dict[str, Any]]:
        if len(experiments) < 3:
            raise ValueError(
                f"Need at least 3 experiment observations to perform held-out validation for {component_name}:{version}"
            )

        # 1. Group-based split: enforces minimum 3 independent configurations with zero replication leakage
        train_exps, test_exps = ModelTrainer._group_train_test_split(experiments, test_ratio=test_ratio)

        # 2. Fit baseline Lookup Model on train split
        baseline_lookup = LookupInterpolationModel(train_exps)

        # 3. Fit Ridge Regression Model on train split
        regression_model = RegressionPerformanceModel.fit_from_experiments(train_exps)

        # 4. Multi-metric evaluation on held-out test split
        def evaluate_on_held_out(model):
            actuals = []
            predictions = []
            for e in test_exps:
                base_service = (e.concurrency / max(1.0, e.achieved_rps)) * 1000.0
                actual_service = min(e.p50_ms, max(0.2, base_service))
                pred_service, _, _ = model.predict_service_time_ms("read", e.concurrency, e.achieved_rps)
                actuals.append(actual_service)
                predictions.append(pred_service)

            actuals = np.array(actuals, dtype=float)
            predictions = np.array(predictions, dtype=float)

            # Numerical safety checks
            if not np.all(np.isfinite(actuals)) or not np.all(np.isfinite(predictions)):
                return {
                    "rmse": float("inf"),
                    "mae": float("inf"),
                    "mape": float("inf"),
                    "max_error": float("inf"),
                    "r2": None,
                    "is_valid": False,
                }

            residuals = actuals - predictions
            rmse = float(np.sqrt(np.mean(residuals**2)))
            mae = float(np.mean(np.abs(residuals)))
            mape = float(np.mean(np.abs(residuals / np.maximum(actuals, 0.05))) * 100.0)
            max_err = float(np.max(np.abs(residuals)))

            ss_tot = float(np.sum((actuals - np.mean(actuals))**2))
            ss_res = float(np.sum(residuals**2))

            # Mathematically honest R2:
            # If ss_tot <= 1e-6 (constant or near-constant target), variance is zero and R2 is undefined.
            # We explicitly represent undefined R2 as None rather than fabricating an arbitrary 0.90.
            if ss_tot > 1e-6:
                r2 = round(float(1.0 - (ss_res / ss_tot)), 3)
            else:
                r2 = None

            return {
                "rmse": round(rmse, 3),
                "mae": round(mae, 3),
                "mape": round(mape, 2),
                "max_error": round(max_err, 3),
                "r2": r2,
                "is_valid": True,
            }

        lookup_metrics = evaluate_on_held_out(baseline_lookup)
        reg_metrics = evaluate_on_held_out(regression_model)

        # Model selection: prefer parametric regression if its RMSE is competitive with baseline lookup
        if reg_metrics["rmse"] <= lookup_metrics["rmse"] * 1.15:
            chosen_type = "piecewise_ridge"
            chosen_model = regression_model
            chosen_metrics = reg_metrics
            params = regression_model.to_dict()
        else:
            chosen_type = "lookup_interpolation"
            chosen_model = baseline_lookup
            chosen_metrics = lookup_metrics
            params = {"baseline": "knn_inverse_distance", "num_knots": len(train_exps)}

        # Decision-relevant multi-metric quality gating:
        # 1. Honest R2 >= 0.65 (or strict MAE <= 1.5ms on tight scale)
        # 2. MAE <= 2.5ms OR MAPE <= 35%
        # Undefined R2 (None or NaN) cannot claim an R2 threshold pass.
        r2_val = chosen_metrics.get("r2")
        has_strong_r2 = (r2_val is not None and math.isfinite(r2_val) and r2_val >= 0.65)
        tight_scale_pass = (chosen_metrics["mae"] <= 1.5 and chosen_metrics["rmse"] <= 2.0)
        error_bounds_pass = (chosen_metrics["mae"] <= 2.5 or chosen_metrics["mape"] <= 35.0)

        is_validated = (
            chosen_metrics.get("is_valid", False)
            and math.isfinite(chosen_metrics["rmse"])
            and math.isfinite(chosen_metrics["mae"])
            and (has_strong_r2 or tight_scale_pass)
            and error_bounds_pass
        )

        # Operating ranges
        ranges = chosen_model.get_supported_ranges()
        is_synthetic = any(e.is_synthetic_fixture for e in experiments)
        env_fp = experiments[0].env_fingerprint if experiments else "unknown"
        now = datetime.now(timezone.utc).isoformat()

        held_out_concs = sorted(list(set(e.concurrency for e in test_exps)))
        exp_ids = [e.experiment_id for e in experiments]
        train_exp_ids = [e.experiment_id for e in train_exps]
        test_exp_ids = [e.experiment_id for e in test_exps]

        r2_display = f"{chosen_metrics['r2']:.3f}" if chosen_metrics['r2'] is not None else "UNDEFINED_ZERO_VARIANCE"

        model_record = ModelRecord(
            model_id=f"model_{component_name}_{hashlib.sha256(f'{component_name}_{version}_{chosen_type}_{round(chosen_metrics['rmse'], 3)}'.encode()).hexdigest()[:8]}",
            component_name=component_name,
            version=version,
            env_fingerprint=env_fp,
            model_type=chosen_type,
            fitted_parameters=params,
            min_supported_rps=round(ranges["rps"][0], 1),
            max_supported_rps=round(ranges["rps"][1], 1),
            min_supported_concurrency=int(ranges["concurrency"][0]),
            max_supported_concurrency=int(ranges["concurrency"][1]),
            validation_rmse_ms=chosen_metrics["rmse"],
            validation_mape_pct=chosen_metrics["mape"],
            r2_score=chosen_metrics["r2"],
            is_validated=is_validated,
            is_synthetic_fixture=is_synthetic,
            provenance=(
                f"Trained from {len(experiments)} experiments ({len(train_exps)} train, {len(test_exps)} held-out test). "
                f"Source IDs: {exp_ids}. "
                f"Group-based held-out validation on {len(test_exps)} trials across load levels {held_out_concs} "
                f"(zero data leakage; strict interpolation within [{int(ranges['concurrency'][0])}, {int(ranges['concurrency'][1])}]). "
                f"MAE={chosen_metrics['mae']}ms, RMSE={chosen_metrics['rmse']}ms, MAPE={chosen_metrics['mape']}%, R2={r2_display}."
            ),
            known_limitations=(
                f"Interpolation only within concurrency [{int(ranges['concurrency'][0])}, {int(ranges['concurrency'][1])}] "
                f"and throughput [{ranges['rps'][0]:.0f}, {ranges['rps'][1]:.0f}] RPS. Extrapolation beyond these bounds is unvalidated."
            ),
            created_at=now,
        )

        metrics = {
            "chosen_model_type": chosen_type,
            "source_experiment_ids": exp_ids,
            "train_experiment_ids": train_exp_ids,
            "test_experiment_ids": test_exp_ids,
            "train_samples": len(train_exps),
            "test_samples": len(test_exps),
            "held_out_concurrencies": held_out_concs,
            "regression_eval": reg_metrics,
            "lookup_eval": lookup_metrics,
            "chosen_eval": chosen_metrics,
            "is_validated": is_validated,
            "group_based_leakage_free": True,
            "evaluation_nature": "interpolation_only",
        }
        return model_record, metrics
