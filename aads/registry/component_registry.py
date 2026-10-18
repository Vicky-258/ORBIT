"""
Component and Model Registry.
Manages performance models, benchmark experiment records, and compatibility checks.
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone

from aads.core.config import REGISTRY_DB_PATH, BASE_DIR
from aads.core.schemas import (
    ModelRecord,
    ExperimentRecord,
    WorkloadSpec,
)


class ComponentRegistry:
    """Persistent SQLite-backed registry for models and benchmark experiments."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or REGISTRY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    model_id TEXT PRIMARY KEY,
                    component_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    env_fingerprint TEXT NOT NULL,
                    model_type TEXT NOT NULL,
                    fitted_parameters TEXT NOT NULL,
                    min_supported_rps REAL NOT NULL,
                    max_supported_rps REAL NOT NULL,
                    min_supported_concurrency INTEGER NOT NULL,
                    max_supported_concurrency INTEGER NOT NULL,
                    validation_rmse_ms REAL NOT NULL,
                    validation_mape_pct REAL NOT NULL,
                    r2_score REAL NOT NULL,
                    is_validated INTEGER NOT NULL,
                    is_synthetic_fixture INTEGER NOT NULL,
                    provenance TEXT NOT NULL,
                    known_limitations TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    component_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    env_fingerprint TEXT NOT NULL,
                    benchmark_framework TEXT NOT NULL,
                    concurrency INTEGER NOT NULL,
                    read_ratio REAL NOT NULL,
                    offered_rps REAL NOT NULL,
                    achieved_rps REAL NOT NULL,
                    p50_ms REAL NOT NULL,
                    p95_ms REAL NOT NULL,
                    p99_ms REAL NOT NULL,
                    cpu_pct REAL NOT NULL,
                    memory_mb REAL NOT NULL,
                    error_count INTEGER NOT NULL,
                    trial_replications INTEGER NOT NULL,
                    variance_ms2 REAL NOT NULL,
                    is_synthetic_fixture INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    notes TEXT,
                    raw_json TEXT
                )
            """)
            conn.commit()

    def register_model(self, model: ModelRecord) -> None:
        """Save or update a model record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO models (
                    model_id, component_name, version, env_fingerprint, model_type,
                    fitted_parameters, min_supported_rps, max_supported_rps,
                    min_supported_concurrency, max_supported_concurrency,
                    validation_rmse_ms, validation_mape_pct, r2_score,
                    is_validated, is_synthetic_fixture, provenance, known_limitations, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model.model_id,
                model.component_name,
                model.version,
                model.env_fingerprint,
                model.model_type,
                json.dumps(model.fitted_parameters),
                model.min_supported_rps,
                model.max_supported_rps,
                model.min_supported_concurrency,
                model.max_supported_concurrency,
                model.validation_rmse_ms,
                model.validation_mape_pct,
                model.r2_score,
                1 if model.is_validated else 0,
                1 if model.is_synthetic_fixture else 0,
                model.provenance,
                model.known_limitations,
                model.created_at,
            ))
            conn.commit()

    def get_model(self, component_name: str, version: str) -> Optional[ModelRecord]:
        """Retrieve model for a specific component and version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM models 
                WHERE component_name = ? AND version = ?
                ORDER BY created_at DESC LIMIT 1
            """, (component_name, version))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_model(row)

    def list_models(self) -> List[ModelRecord]:
        """List all registered performance models."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models ORDER BY component_name, version, created_at DESC")
            return [self._row_to_model(row) for row in cursor.fetchall()]

    def check_compatibility(
        self,
        component_name: str,
        version: str,
        workload: WorkloadSpec
    ) -> Tuple[str, Optional[ModelRecord], List[str]]:
        """
        Verify whether a valid, calibrated model is available and covers the requested workload.
        Returns: (status: 'VALIDATED' | 'MISSING' | 'OUT_OF_RANGE' | 'UNVALIDATED', model, warnings)
        """
        model = self.get_model(component_name, version)
        if not model:
            return ("MISSING", None, [f"No performance model registered for {component_name} ({version}). Benchmarking required."])

        warnings = []
        if not model.is_validated:
            warnings.append(f"Model for {component_name}:{version} failed quality validation checks.")
            return ("UNVALIDATED", model, warnings)

        # Check operating range
        required_rps = workload.request_rate_rps
        if required_rps < model.min_supported_rps or required_rps > model.max_supported_rps:
            warnings.append(
                f"Workload RPS ({required_rps:.1f}) is outside model supported range [{model.min_supported_rps:.1f}, {model.max_supported_rps:.1f}] for {component_name}:{version}. Extrapolation would degrade confidence."
            )
            return ("OUT_OF_RANGE", model, warnings)

        return ("VALIDATED", model, warnings)

    def save_experiment(self, exp: ExperimentRecord) -> None:
        """Persist a benchmark experiment record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO experiments (
                    experiment_id, component_name, version, env_fingerprint,
                    benchmark_framework, concurrency, read_ratio, offered_rps, achieved_rps,
                    p50_ms, p95_ms, p99_ms, cpu_pct, memory_mb, error_count,
                    trial_replications, variance_ms2, is_synthetic_fixture, timestamp, notes, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exp.experiment_id,
                exp.component_name,
                exp.version,
                exp.env_fingerprint,
                exp.benchmark_framework,
                exp.concurrency,
                exp.read_ratio,
                exp.offered_rps,
                exp.achieved_rps,
                exp.p50_ms,
                exp.p95_ms,
                exp.p99_ms,
                exp.cpu_pct,
                exp.memory_mb,
                exp.error_count,
                exp.trial_replications,
                exp.variance_ms2,
                1 if exp.is_synthetic_fixture else 0,
                exp.timestamp,
                exp.notes,
                json.dumps(exp.model_dump()),
            ))
            conn.commit()

    def get_experiments(self, component_name: str, version: str) -> List[ExperimentRecord]:
        """Get all benchmark observations for a component and version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM experiments
                WHERE component_name = ? AND version = ?
                ORDER BY concurrency, offered_rps
            """, (component_name, version))
            rows = cursor.fetchall()
            return [self._row_to_experiment(row) for row in rows]

    def list_all_experiments(self) -> List[ExperimentRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM experiments ORDER BY timestamp DESC")
            return [self._row_to_experiment(row) for row in cursor.fetchall()]

    def _row_to_model(self, row: sqlite3.Row) -> ModelRecord:
        return ModelRecord(
            model_id=row["model_id"],
            component_name=row["component_name"],
            version=row["version"],
            env_fingerprint=row["env_fingerprint"],
            model_type=row["model_type"],
            fitted_parameters=json.loads(row["fitted_parameters"]),
            min_supported_rps=row["min_supported_rps"],
            max_supported_rps=row["max_supported_rps"],
            min_supported_concurrency=row["min_supported_concurrency"],
            max_supported_concurrency=row["max_supported_concurrency"],
            validation_rmse_ms=row["validation_rmse_ms"],
            validation_mape_pct=row["validation_mape_pct"],
            r2_score=row["r2_score"],
            is_validated=bool(row["is_validated"]),
            is_synthetic_fixture=bool(row["is_synthetic_fixture"]),
            provenance=row["provenance"],
            known_limitations=row["known_limitations"],
            created_at=row["created_at"],
        )

    def _row_to_experiment(self, row: sqlite3.Row) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id=row["experiment_id"],
            component_name=row["component_name"],
            version=row["version"],
            env_fingerprint=row["env_fingerprint"],
            benchmark_framework=row["benchmark_framework"],
            concurrency=row["concurrency"],
            read_ratio=row["read_ratio"],
            offered_rps=row["offered_rps"],
            achieved_rps=row["achieved_rps"],
            p50_ms=row["p50_ms"],
            p95_ms=row["p95_ms"],
            p99_ms=row["p99_ms"],
            cpu_pct=row["cpu_pct"],
            memory_mb=row["memory_mb"],
            error_count=row["error_count"],
            trial_replications=row["trial_replications"],
            variance_ms2=row["variance_ms2"],
            is_synthetic_fixture=bool(row["is_synthetic_fixture"]),
            timestamp=row["timestamp"],
            notes=row["notes"],
        )

    def seed_baseline_data(self, force: bool = False) -> None:
        """
        Seed default baseline models for PostgreSQL and Redis to allow immediate simulation,
        leaving MongoDB intentionally unseeded/missing to demonstrate model discovery.
        """
        if not force and len(self.list_models()) > 0:
            return

        now = datetime.now(timezone.utc).isoformat()
        
        # Seed PostgreSQL baseline model
        pg_model = ModelRecord(
            model_id="model_pg16_baseline_empirical",
            component_name="postgres_db",
            version="postgres:16-alpine",
            env_fingerprint="docker:linux-x86_64:2cpu-2048mb",
            model_type="piecewise_ridge",
            fitted_parameters={
                "base_read_service_ms": 2.8,
                "base_write_service_ms": 6.5,
                "concurrency_penalty_slope": 0.08,
                "saturation_rps": 650.0,
            },
            min_supported_rps=10.0,
            max_supported_rps=800.0,
            min_supported_concurrency=1,
            max_supported_concurrency=32,
            validation_rmse_ms=0.62,
            validation_mape_pct=8.4,
            r2_score=0.94,
            is_validated=True,
            is_synthetic_fixture=True,
            provenance="Baseline controlled calibration trial (3 replications per point)",
            known_limitations="Accurate for read/write mixes between 80/20 and 95/5; does not model complex subqueries.",
            created_at=now,
        )
        self.register_model(pg_model)

        # Seed Redis baseline model
        redis_model = ModelRecord(
            model_id="model_redis72_baseline_lookup",
            component_name="redis_cache",
            version="redis:7.2-alpine",
            env_fingerprint="docker:linux-x86_64:1cpu-1024mb",
            model_type="lookup_table",
            fitted_parameters={
                "base_hit_latency_ms": 0.65,
                "base_miss_overhead_ms": 0.35,
                "saturation_rps": 8000.0,
            },
            min_supported_rps=10.0,
            max_supported_rps=5000.0,
            min_supported_concurrency=1,
            max_supported_concurrency=128,
            validation_rmse_ms=0.08,
            validation_mape_pct=5.1,
            r2_score=0.98,
            is_validated=True,
            is_synthetic_fixture=True,
            provenance="In-memory microbenchmark with 10k key working set",
            known_limitations="Assumes working set fits in RAM (LRU policy active).",
            created_at=now,
        )
        self.register_model(redis_model)
