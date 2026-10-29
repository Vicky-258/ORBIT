"""
Validated Model Calibration Pipeline (Phase 4D).
Safely ingests newly measured benchmark evidence, performs group-based held-out validation,
compares predictions against baseline models, and enforces quality gates before promoting models.
"""
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from aads.core.schemas import ModelRecord, ExperimentRecord
from aads.modeling.model_trainer import ModelTrainer
from aads.registry.component_registry import ComponentRegistry


class CalibrationOutcome(BaseModel):
    """Structured report of component model calibration and validation outcome."""
    component_name: str
    version: str
    status: str = Field(description="PROMOTED, INSUFFICIENT_EVIDENCE, or REJECTED")
    old_model_id: Optional[str] = None
    new_model_id: Optional[str] = None
    validation_rmse_ms: Optional[float] = None
    validation_mae_ms: Optional[float] = None
    validation_mape_pct: Optional[float] = None
    r2_score: Optional[float] = None
    is_empirical_upgrade: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class CalibrationPipeline:
    """
    Manages the controlled path from benchmark measurements to active component models.
    """

    def __init__(self, registry: Optional[ComponentRegistry] = None):
        self.registry = registry or ComponentRegistry()

    def calibrate_component(
        self,
        component_name: str,
        version: str,
        experiments: Optional[List[ExperimentRecord]] = None,
        test_ratio: float = 0.30,
        force_promote: bool = False,
    ) -> CalibrationOutcome:
        """
        Calibrates and validates a component model from benchmark evidence.
        Promotes the model in the registry only if validation quality checks pass.
        """
        # 1. Fetch all experiments for this component if not provided
        all_exps = experiments if experiments is not None else self.registry.get_experiments(component_name, version)
        
        # Fetch current active model for comparison
        existing_model = self.registry.get_model(component_name, version)
        old_id = existing_model.model_id if existing_model else None

        # 2. Check for sufficient observations
        if len(all_exps) < 3:
            return CalibrationOutcome(
                component_name=component_name,
                version=version,
                status="INSUFFICIENT_EVIDENCE",
                old_model_id=old_id,
                new_model_id=None,
                summary=(
                    f"Insufficient evidence for {component_name}:{version} (found {len(all_exps)} observations, minimum 3 required). "
                    "Prior model preserved; recalibration withheld."
                ),
                details={"observations_count": len(all_exps), "min_required": 3},
            )

        # 3. Train and validate candidate model with group-based held-out split
        try:
            candidate_model, eval_metrics = ModelTrainer.train_and_validate(
                component_name=component_name,
                version=version,
                experiments=all_exps,
                test_ratio=test_ratio,
            )
        except Exception as exc:
            return CalibrationOutcome(
                component_name=component_name,
                version=version,
                status="REJECTED",
                old_model_id=old_id,
                new_model_id=None,
                summary=f"Model training and validation failed: {str(exc)}",
                details={"error": str(exc)},
            )

        chosen_eval = eval_metrics.get("chosen_eval", {})
        rmse = chosen_eval.get("rmse")
        mae = chosen_eval.get("mae")
        mape = chosen_eval.get("mape")
        r2 = chosen_eval.get("r2")
        is_validated = eval_metrics.get("is_validated", False)

        # Check empirical upgrade: candidate is real empirical while previous was synthetic fixture
        is_empirical_upgrade = (
            not candidate_model.is_synthetic_fixture and
            (existing_model is None or existing_model.is_synthetic_fixture)
        )

        # 4. Enforce quality gates
        if not is_validated and not force_promote:
            return CalibrationOutcome(
                component_name=component_name,
                version=version,
                status="REJECTED",
                old_model_id=old_id,
                new_model_id=candidate_model.model_id,
                validation_rmse_ms=rmse,
                validation_mae_ms=mae,
                validation_mape_pct=mape,
                r2_score=r2,
                is_empirical_upgrade=is_empirical_upgrade,
                details=eval_metrics,
                summary=(
                    f"Candidate model failed quality validation gates: RMSE={rmse}ms, MAE={mae}ms, "
                    f"MAPE={mape}%, R2={r2}. Prior model preserved; candidate not promoted."
                ),
            )

        # 5. Model promotion
        self.registry.register_model(candidate_model)

        summary_msg = (
            f"Successfully calibrated and promoted model '{candidate_model.model_id}' for {component_name}:{version}. "
            f"Held-out validation: RMSE={rmse}ms, MAE={mae}ms, MAPE={mape}%, R2={r2}."
        )
        if is_empirical_upgrade:
            summary_msg += " (Empirical upgrade: replaced synthetic fixture with real benchmark measurements)."

        return CalibrationOutcome(
            component_name=component_name,
            version=version,
            status="PROMOTED",
            old_model_id=old_id,
            new_model_id=candidate_model.model_id,
            validation_rmse_ms=rmse,
            validation_mae_ms=mae,
            validation_mape_pct=mape,
            r2_score=r2,
            is_empirical_upgrade=is_empirical_upgrade,
            details=eval_metrics,
            summary=summary_msg,
        )
