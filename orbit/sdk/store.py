"""
Workspace and Experiment Persistence Store for AADS Simulation SDK (Phase 5.3B).
Provides in-memory caching with persistent SQLite backing, thread safety,
branching lineage tracking, and strict immutability enforcement on completed experiments.
"""
import copy
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from orbit.core.config import REGISTRY_DB_PATH
from orbit.core.schemas import WorkloadSpec, SimulationResult
from orbit.sdk.models import (
    Workspace,
    Experiment,
    ExperimentStatus,
    TopologyGraph,
)

logger = logging.getLogger(__name__)


class ExperimentStore:
    """
    Thread-safe workspace and experiment store.
    Guarantees immutability of completed experiments and tracks branching lineage.
    """

    def __init__(self, db_path: Optional[Union[Path, str]] = None):
        self.db_path = Path(db_path) if db_path is not None else REGISTRY_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        
        # In-memory fast cache
        self._workspaces: Dict[str, Workspace] = {}
        self._experiments: Dict[str, Experiment] = {}
        
        self._init_db()
        self._load_from_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sdk_workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    intent_summary TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sdk_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    parent_experiment_id TEXT,
                    branch_label TEXT,
                    topology_json TEXT,
                    workload_json TEXT,
                    simulation_duration_seconds REAL NOT NULL,
                    random_seed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT,
                    execution_duration_ms REAL NOT NULL,
                    model_manifest_json TEXT,
                    governance_verdict_json TEXT,
                    results_json TEXT,
                    warnings_json TEXT,
                    limitations_json TEXT,
                    FOREIGN KEY (workspace_id) REFERENCES sdk_workspaces(workspace_id)
                )
            """)
            conn.commit()

    def _load_from_db(self) -> None:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sdk_workspaces")
            for row in cursor.fetchall():
                ws = Workspace(
                    workspace_id=row["workspace_id"],
                    name=row["name"],
                    intent_summary=row["intent_summary"],
                    created_at_utc=row["created_at_utc"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                )
                self._workspaces[ws.workspace_id] = ws

            cursor.execute("SELECT * FROM sdk_experiments")
            for row in cursor.fetchall():
                topo = TopologyGraph.model_validate_json(row["topology_json"]) if row["topology_json"] else None
                wl = WorkloadSpec.model_validate_json(row["workload_json"]) if row["workload_json"] else None
                res = SimulationResult.model_validate_json(row["results_json"]) if row["results_json"] else None
                
                exp = Experiment(
                    experiment_id=row["experiment_id"],
                    workspace_id=row["workspace_id"],
                    parent_experiment_id=row["parent_experiment_id"],
                    branch_label=row["branch_label"],
                    topology=topo,
                    workload=wl,
                    simulation_duration_seconds=row["simulation_duration_seconds"],
                    random_seed=row["random_seed"],
                    status=ExperimentStatus(row["status"]),
                    error_message=row["error_message"],
                    created_at_utc=row["created_at_utc"],
                    completed_at_utc=row["completed_at_utc"],
                    execution_duration_ms=row["execution_duration_ms"],
                    model_manifest=json.loads(row["model_manifest_json"] or "{}"),
                    governance_verdict=json.loads(row["governance_verdict_json"] or "{}"),
                    results=res,
                    warnings=json.loads(row["warnings_json"] or "[]"),
                    limitations=json.loads(row["limitations_json"] or "[]"),
                )
                self._experiments[exp.experiment_id] = exp
                if exp.workspace_id in self._workspaces:
                    if exp.experiment_id not in self._workspaces[exp.workspace_id].experiment_ids:
                        self._workspaces[exp.workspace_id].experiment_ids.append(exp.experiment_id)

    # --- Workspace Operations ---

    def create_workspace(self, name: str, intent_summary: str = "", metadata: Optional[Dict[str, Any]] = None) -> Workspace:
        with self._lock:
            ws = Workspace(name=name, intent_summary=intent_summary, metadata=metadata or {})
            self._workspaces[ws.workspace_id] = ws
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sdk_workspaces (workspace_id, name, intent_summary, created_at_utc, metadata_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (ws.workspace_id, ws.name, ws.intent_summary, ws.created_at_utc, json.dumps(ws.metadata)))
                conn.commit()
            return ws

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        with self._lock:
            return self._workspaces.get(workspace_id)

    def list_workspaces(self) -> List[Workspace]:
        with self._lock:
            return list(self._workspaces.values())

    # --- Experiment Operations ---

    def create_experiment(
        self,
        workspace_id: str,
        label: Optional[str] = None,
        parent_experiment_id: Optional[str] = None,
    ) -> Experiment:
        with self._lock:
            if workspace_id not in self._workspaces:
                raise ValueError(f"Workspace '{workspace_id}' does not exist.")

            exp = Experiment(
                workspace_id=workspace_id,
                branch_label=label,
                parent_experiment_id=parent_experiment_id,
                status=ExperimentStatus.DRAFT,
            )
            self._experiments[exp.experiment_id] = exp
            self._workspaces[workspace_id].experiment_ids.append(exp.experiment_id)
            self.save_experiment(exp)
            return exp

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        with self._lock:
            return self._experiments.get(experiment_id)

    def list_experiments(self, workspace_id: str) -> List[Experiment]:
        with self._lock:
            return [e for e in self._experiments.values() if e.workspace_id == workspace_id]

    def save_experiment(self, experiment: Experiment) -> None:
        """Persists or updates an experiment in cache and SQLite."""
        with self._lock:
            # Enforce Immutability Check
            existing = self._experiments.get(experiment.experiment_id)
            if existing and existing.status == ExperimentStatus.COMPLETED and experiment.status != ExperimentStatus.COMPLETED:
                raise ValueError(
                    f"Experiment '{experiment.experiment_id}' is COMPLETED and immutable. "
                    "To modify configurations, clone/branch the experiment using clone_experiment."
                )

            self._experiments[experiment.experiment_id] = experiment
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO sdk_experiments (
                        experiment_id, workspace_id, parent_experiment_id, branch_label,
                        topology_json, workload_json, simulation_duration_seconds, random_seed,
                        status, error_message, created_at_utc, completed_at_utc,
                        execution_duration_ms, model_manifest_json, governance_verdict_json,
                        results_json, warnings_json, limitations_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    experiment.experiment_id,
                    experiment.workspace_id,
                    experiment.parent_experiment_id,
                    experiment.branch_label,
                    experiment.topology.model_dump_json() if experiment.topology else None,
                    experiment.workload.model_dump_json() if experiment.workload else None,
                    experiment.simulation_duration_seconds,
                    experiment.random_seed,
                    experiment.status.value,
                    experiment.error_message,
                    experiment.created_at_utc,
                    experiment.completed_at_utc,
                    experiment.execution_duration_ms,
                    json.dumps(experiment.model_manifest),
                    json.dumps(experiment.governance_verdict),
                    experiment.results.model_dump_json() if experiment.results else None,
                    json.dumps(experiment.warnings),
                    json.dumps(experiment.limitations),
                ))
                conn.commit()

    def clone_experiment(self, source_experiment_id: str, new_label: str) -> Experiment:
        """
        Branches an experiment while strictly preserving the immutability of the parent.
        Copies topology, workload, and parameters into a fresh DRAFT experiment with parent lineage.
        """
        with self._lock:
            parent = self.get_experiment(source_experiment_id)
            if not parent:
                raise ValueError(f"Source experiment '{source_experiment_id}' not found.")

            cloned_topo = copy.deepcopy(parent.topology) if parent.topology else None
            if cloned_topo:
                # Give child topology a fresh unique ID
                cloned_topo.topology_id = f"topo_{cloned_topo.topology_id.split('_')[-1]}_branch"
                cloned_topo.name = f"{parent.topology.name} ({new_label})"

            child = Experiment(
                workspace_id=parent.workspace_id,
                parent_experiment_id=source_experiment_id,
                branch_label=new_label,
                topology=cloned_topo,
                workload=copy.deepcopy(parent.workload) if parent.workload else None,
                simulation_duration_seconds=parent.simulation_duration_seconds,
                random_seed=parent.random_seed,
                status=ExperimentStatus.DRAFT,
            )

            self._experiments[child.experiment_id] = child
            if child.workspace_id in self._workspaces:
                self._workspaces[child.workspace_id].experiment_ids.append(child.experiment_id)
            self.save_experiment(child)
            return child
