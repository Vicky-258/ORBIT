"""
Unit tests for Performance Modeling and Held-out Validation.
"""
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.modeling.lookup_model import LookupInterpolationModel
from aads.modeling.regression_model import RegressionPerformanceModel
from aads.modeling.model_trainer import ModelTrainer


def test_lookup_model(synthetic_runner):
    exps = synthetic_runner.run_benchmark_matrix("postgres_db", "postgres:16-alpine", concurrency_levels=[1, 4, 16], replications=2)
    model = LookupInterpolationModel(exps)
    service_ms, uncertainty, is_extrapolated = model.predict_service_time_ms("read", concurrency=4, offered_rps=200.0)
    assert service_ms > 0
    assert uncertainty > 0
    assert not is_extrapolated


def test_regression_model_fit(synthetic_runner):
    exps = synthetic_runner.run_benchmark_matrix("postgres_db", "postgres:16-alpine", concurrency_levels=[1, 4, 8, 16], replications=2)
    reg = RegressionPerformanceModel.fit_from_experiments(exps)
    s_read, _, _ = reg.predict_service_time_ms("read", concurrency=4)
    s_write, _, _ = reg.predict_service_time_ms("write", concurrency=4)
    # Writes should take longer than reads
    assert s_write > s_read


def test_held_out_validation(synthetic_runner):
    exps = synthetic_runner.run_benchmark_matrix("postgres_db", "postgres:16-alpine", concurrency_levels=[1, 2, 4, 8, 16, 24, 32], replications=3)
    model_record, metrics = ModelTrainer.train_and_validate("postgres_db", "postgres:16-alpine", exps, test_ratio=0.30)

    assert metrics["train_samples"] > 0
    assert metrics["test_samples"] > 0
    assert "regression_eval" in metrics
    assert "lookup_eval" in metrics
    assert model_record.validation_rmse_ms < 2.5
    assert metrics["chosen_eval"]["mae"] < 2.5
    assert metrics["group_based_leakage_free"] is True
    assert model_record.is_validated is True
