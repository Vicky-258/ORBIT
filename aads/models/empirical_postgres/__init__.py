"""
AADS Empirical PostgreSQL Performance Models Package (Phase 4F.5).

Provides bounded, reproducible performance models developed from Phase 4F.4.5 empirical evidence:
- EmpiricalLookupModel: Non-parametric baseline with sample variance propagation
- EmpiricalLinearRegressionModel: Parametric OLS response model
- EmpiricalPiecewiseModel: Resource saturation threshold model
- EmpiricalMechanisticModel: Queueing-theoretic decomposition model
- ReconciledEvidenceLoader: Verified empirical evidence parser
- ReplicationAwareEvaluator: Leave-One-Replication-Out (LORO) validation framework
"""
from aads.models.empirical_postgres.schemas import (
    EvidenceStatus,
    UncertaintyType,
    ModelState,
    WorkloadProfile,
    EmpiricalPostgresQuery,
    EmpiricalPostgresPrediction,
    MetricPrediction,
    TrialObservation,
    EvaluationMetrics,
)
from aads.models.empirical_postgres.base import BaseEmpiricalPostgresModel
from aads.models.empirical_postgres.evidence_loader import ReconciledEvidenceLoader
from aads.models.empirical_postgres.lookup_candidate import EmpiricalLookupModel
from aads.models.empirical_postgres.linear_candidate import EmpiricalLinearRegressionModel
from aads.models.empirical_postgres.piecewise_candidate import EmpiricalPiecewiseModel
from aads.models.empirical_postgres.mechanistic_candidate import EmpiricalMechanisticModel
from aads.models.empirical_postgres.evaluator import ReplicationAwareEvaluator, calculate_metrics_safely

__all__ = [
    "EvidenceStatus",
    "UncertaintyType",
    "ModelState",
    "WorkloadProfile",
    "EmpiricalPostgresQuery",
    "EmpiricalPostgresPrediction",
    "MetricPrediction",
    "TrialObservation",
    "EvaluationMetrics",
    "BaseEmpiricalPostgresModel",
    "ReconciledEvidenceLoader",
    "EmpiricalLookupModel",
    "EmpiricalLinearRegressionModel",
    "EmpiricalPiecewiseModel",
    "EmpiricalMechanisticModel",
    "ReplicationAwareEvaluator",
    "calculate_metrics_safely",
]
