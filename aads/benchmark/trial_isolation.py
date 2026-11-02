"""
Independent Trial Isolation and Baseline State Verification (Phase 4F.3 - Workstream 1).

Guarantees trial-to-trial database isolation by executing each trial inside a freshly
initialized PostgreSQL benchmark container, verifying strict baseline preconditions,
tracking table/index growth and configuration state, and enforcing deterministic cleanup.
"""
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class TrialIsolationError(RuntimeError):
    """Raised when a trial fails its baseline isolation verification."""
    pass


class DatabaseStateSnapshot:
    """
    Exact snapshot of PostgreSQL database state, table row counts, relation sizes,
    and runtime configuration before or after a benchmark trial.
    """

    def __init__(
        self,
        scale_factor: int,
        accounts_count: int,
        branches_count: int,
        tellers_count: int,
        history_count: int,
        accounts_size_bytes: int = 0,
        branches_size_bytes: int = 0,
        tellers_size_bytes: int = 0,
        history_size_bytes: int = 0,
        database_size_bytes: int = 0,
        shared_buffers: str = "128MB",
        work_mem: str = "4MB",
        max_connections: str = "100",
        checkpoint_timeout: str = "5min",
        synchronous_commit: str = "on",
        autovacuum: str = "on",
        cpu_limit: str = "1.0",
        memory_limit: str = "1024m",
        image_digest: Optional[str] = None,
        timestamp_utc: Optional[str] = None,
    ):
        self.scale_factor = scale_factor
        self.accounts_count = accounts_count
        self.branches_count = branches_count
        self.tellers_count = tellers_count
        self.history_count = history_count
        self.accounts_size_bytes = accounts_size_bytes
        self.branches_size_bytes = branches_size_bytes
        self.tellers_size_bytes = tellers_size_bytes
        self.history_size_bytes = history_size_bytes
        self.database_size_bytes = database_size_bytes
        self.shared_buffers = shared_buffers
        self.work_mem = work_mem
        self.max_connections = max_connections
        self.checkpoint_timeout = checkpoint_timeout
        self.synchronous_commit = synchronous_commit
        self.autovacuum = autovacuum
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.image_digest = image_digest
        self.timestamp_utc = timestamp_utc or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scale_factor": self.scale_factor,
            "row_counts": {
                "accounts": self.accounts_count,
                "branches": self.branches_count,
                "tellers": self.tellers_count,
                "history": self.history_count,
            },
            "relation_sizes_bytes": {
                "accounts": self.accounts_size_bytes,
                "branches": self.branches_size_bytes,
                "tellers": self.tellers_size_bytes,
                "history": self.history_size_bytes,
                "total_database": self.database_size_bytes,
            },
            "database_configuration": {
                "shared_buffers": self.shared_buffers,
                "work_mem": self.work_mem,
                "max_connections": self.max_connections,
                "checkpoint_timeout": self.checkpoint_timeout,
                "synchronous_commit": self.synchronous_commit,
                "autovacuum": self.autovacuum,
            },
            "container_configuration": {
                "cpu_limit": self.cpu_limit,
                "memory_limit": self.memory_limit,
                "image_digest": self.image_digest,
            },
            "timestamp_utc": self.timestamp_utc,
        }

    def diff(self, after: "DatabaseStateSnapshot") -> Dict[str, Any]:
        """Calculates exact delta between pre-trial and post-trial database states."""
        return {
            "delta_history_rows": after.history_count - self.history_count,
            "delta_accounts_rows": after.accounts_count - self.accounts_count,
            "delta_branches_rows": after.branches_count - self.branches_count,
            "delta_tellers_rows": after.tellers_count - self.tellers_count,
            "delta_history_size_bytes": after.history_size_bytes - self.history_size_bytes,
            "delta_database_size_bytes": after.database_size_bytes - self.database_size_bytes,
        }


class TrialIsolationManager:
    """
    Manages isolated PostgreSQL container lifecycles and enforces baseline integrity checks.
    """

    def __init__(
        self,
        default_image: str = "postgres:16-alpine",
        pinned_image_digest: Optional[str] = None,
        cpu_limit: str = "1.0",
        memory_limit: str = "1024m",
    ):
        self.default_image = default_image
        self.pinned_image_digest = pinned_image_digest
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit

    @staticmethod
    def verify_baseline_state(
        snapshot: DatabaseStateSnapshot,
        expected_sf: int,
    ) -> Tuple[bool, List[str]]:
        """
        Verifies that a database snapshot represents an uncorrupted, fresh baseline state.
        Fails if previous write activity or incorrect scale factor is detected.
        """
        violations: List[str] = []

        # 1. Scale factor consistency
        if snapshot.scale_factor != expected_sf:
            violations.append(
                f"Scale factor mismatch: expected SF={expected_sf}, but snapshot recorded SF={snapshot.scale_factor}."
            )

        # 2. Strict initial row counts based on TPC-B scale factor specifications
        expected_accounts = 100_000 * expected_sf
        if snapshot.accounts_count != expected_accounts:
            violations.append(
                f"Accounts row count mismatch: expected {expected_accounts} (100,000 * SF), but found {snapshot.accounts_count}."
            )

        expected_branches = expected_sf
        if snapshot.branches_count != expected_branches:
            violations.append(
                f"Branches row count mismatch: expected {expected_branches} (1 * SF), but found {snapshot.branches_count}."
            )

        expected_tellers = 10 * expected_sf
        if snapshot.tellers_count != expected_tellers:
            violations.append(
                f"Tellers row count mismatch: expected {expected_tellers} (10 * SF), but found {snapshot.tellers_count}."
            )

        # 3. Isolation Precondition: History table MUST be completely empty at start
        if snapshot.history_count != 0:
            violations.append(
                f"Trial isolation violated: pgbench_history table contains {snapshot.history_count} rows from prior executions. "
                f"A baseline starting state must have exactly 0 history rows."
            )

        is_valid = len(violations) == 0
        return is_valid, violations

    def capture_database_state(
        self,
        container_name: str,
        scale_factor: int,
    ) -> DatabaseStateSnapshot:
        """
        Queries PostgreSQL inside the target container to capture current row counts,
        relation sizes, and configuration settings.
        """
        sql_query = (
            "SELECT "
            "(SELECT count(*) FROM pgbench_accounts), "
            "(SELECT count(*) FROM pgbench_branches), "
            "(SELECT count(*) FROM pgbench_tellers), "
            "(SELECT count(*) FROM pgbench_history), "
            "pg_total_relation_size('pgbench_accounts'), "
            "pg_total_relation_size('pgbench_branches'), "
            "pg_total_relation_size('pgbench_tellers'), "
            "pg_total_relation_size('pgbench_history'), "
            "pg_database_size('aadsbench'), "
            "current_setting('shared_buffers'), "
            "current_setting('work_mem'), "
            "current_setting('max_connections'), "
            "current_setting('checkpoint_timeout'), "
            "current_setting('synchronous_commit'), "
            "current_setting('autovacuum');"
        )

        cmd = [
            "docker", "exec", container_name,
            "psql", "-U", "postgres", "-d", "aadsbench", "-t", "-A", "-F", "|", "-c", sql_query,
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to query database state from container {container_name}: {res.stderr.strip()}")

            parts = res.stdout.strip().split("|")
            if len(parts) < 15:
                raise ValueError(f"Unexpected database state output format: '{res.stdout.strip()}'")

            return DatabaseStateSnapshot(
                scale_factor=scale_factor,
                accounts_count=int(parts[0]),
                branches_count=int(parts[1]),
                tellers_count=int(parts[2]),
                history_count=int(parts[3]),
                accounts_size_bytes=int(parts[4]),
                branches_size_bytes=int(parts[5]),
                tellers_size_bytes=int(parts[6]),
                history_size_bytes=int(parts[7]),
                database_size_bytes=int(parts[8]),
                shared_buffers=parts[9],
                work_mem=parts[10],
                max_connections=parts[11],
                checkpoint_timeout=parts[12],
                synchronous_commit=parts[13],
                autovacuum=parts[14],
                cpu_limit=self.cpu_limit,
                memory_limit=self.memory_limit,
                image_digest=self.pinned_image_digest,
            )
        except Exception as e:
            logger.error(f"Error querying database state: {e}")
            raise

    def initialize_fresh_container(
        self,
        container_name: str,
        scale_factor: int,
        timeout_seconds: int = 120,
    ) -> Tuple[float, DatabaseStateSnapshot]:
        """
        Starts a fresh PostgreSQL container, initializes pgbench dataset for scale_factor,
        and verifies the initial baseline state.
        Returns:
            Tuple of (initialization_duration_seconds, initial_baseline_snapshot)
        """
        # 1. Start fresh container
        start_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--cpus", str(self.cpu_limit),
            "--memory", str(self.memory_limit),
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e", "POSTGRES_DB=aadsbench",
            self.default_image,
        ]

        res_start = subprocess.run(start_cmd, capture_output=True, text=True, timeout=20)
        if res_start.returncode != 0:
            raise RuntimeError(f"Failed to start container {container_name}: {res_start.stderr.strip()}")

        # 2. Wait for readiness
        ready = False
        for _ in range(30):
            check = subprocess.run(
                ["docker", "exec", container_name, "pg_isready", "-U", "postgres"],
                capture_output=True, timeout=5,
            )
            if check.returncode == 0:
                ready = True
                break
            time.sleep(0.5)

        if not ready:
            self.cleanup_container(container_name)
            raise RuntimeError(f"Container {container_name} failed pg_isready readiness check.")

        # 3. Timed pgbench initialization
        t_init_start = time.monotonic()
        init_cmd = [
            "docker", "exec", container_name,
            "pgbench", "-i", "-s", str(scale_factor), "-U", "postgres", "aadsbench",
        ]
        res_init = subprocess.run(init_cmd, capture_output=True, text=True, timeout=timeout_seconds)
        init_duration = time.monotonic() - t_init_start

        if res_init.returncode != 0:
            self.cleanup_container(container_name)
            raise RuntimeError(f"pgbench initialization failed for SF={scale_factor}: {res_init.stderr.strip()}")

        # 4. Capture and verify baseline snapshot
        try:
            snapshot = self.capture_database_state(container_name, scale_factor)
            is_valid, violations = self.verify_baseline_state(snapshot, scale_factor)
            if not is_valid:
                self.cleanup_container(container_name)
                raise TrialIsolationError(f"Baseline validation failed: {'; '.join(violations)}")
            return init_duration, snapshot
        except Exception:
            self.cleanup_container(container_name)
            raise

    @staticmethod
    def cleanup_container(container_name: str) -> None:
        """Guaranteed forceful removal of benchmark container."""
        try:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=15)
        except Exception as e:
            logger.warning(f"Failed to remove container {container_name}: {e}")
