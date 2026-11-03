"""
Independent Trial Isolation and Baseline State Verification (Phase 4F.3 - Workstream 1).

Guarantees trial-to-trial database isolation by executing each trial inside a freshly
initialized PostgreSQL benchmark container, verifying strict baseline preconditions,
tracking table/index growth and configuration state, and enforcing deterministic cleanup.
Updated in Phase 4F.3.2 with stronger deterministic content fingerprints (FIX 03) and
mandatory I/O timing instrumentation (FIX 02).
"""
import hashlib
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


def compute_content_fingerprint(
    scale_factor: int,
    accounts_count: int,
    min_aid: int,
    max_aid: int,
    min_abalance: int,
    max_abalance: int,
    sum_abalance: int,
    accounts_hash: int,
    branches_count: int,
    min_bid: int,
    max_bid: int,
    min_bbalance: int,
    max_bbalance: int,
    sum_bbalance: int,
    branches_hash: int,
    tellers_count: int,
    min_tid: int,
    max_tid: int,
    min_tbalance: int,
    max_tbalance: int,
    sum_tbalance: int,
    tellers_hash: int,
    history_count: int,
) -> str:
    """Computes a deterministic SHA256 content fingerprint over exact database state invariants."""
    canonical = (
        f"v1:sf={scale_factor}:"
        f"a_cnt={accounts_count}:a_min={min_aid}:a_max={max_aid}:a_bmin={min_abalance}:a_bmax={max_abalance}:a_bsum={sum_abalance}:a_h={accounts_hash}:"
        f"b_cnt={branches_count}:b_min={min_bid}:b_max={max_bid}:b_bmin={min_bbalance}:b_bmax={max_bbalance}:b_bsum={sum_bbalance}:b_h={branches_hash}:"
        f"t_cnt={tellers_count}:t_min={min_tid}:t_max={max_tid}:t_bmin={min_tbalance}:t_bmax={max_tbalance}:t_bsum={sum_tbalance}:t_h={tellers_hash}:"
        f"h_cnt={history_count}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DatabaseStateSnapshot:
    """
    Exact snapshot of PostgreSQL database state, table row counts, relation sizes,
    deterministic content fingerprints, and runtime configuration before or after a benchmark trial.
    """

    def __init__(
        self,
        scale_factor: int,
        accounts_count: int,
        branches_count: int,
        tellers_count: int,
        history_count: int,
        min_aid: Optional[int] = None,
        max_aid: Optional[int] = None,
        min_abalance: int = 0,
        max_abalance: int = 0,
        sum_abalance: int = 0,
        accounts_hash: int = 0,
        min_bid: Optional[int] = None,
        max_bid: Optional[int] = None,
        min_bbalance: int = 0,
        max_bbalance: int = 0,
        sum_bbalance: int = 0,
        branches_hash: int = 0,
        min_tid: Optional[int] = None,
        max_tid: Optional[int] = None,
        min_tbalance: int = 0,
        max_tbalance: int = 0,
        sum_tbalance: int = 0,
        tellers_hash: int = 0,
        content_fingerprint: Optional[str] = None,
        fingerprint_algorithm: str = "aads_composite_aggregate_sha256_v1",
        accounts_size_bytes: int = 0,
        branches_size_bytes: int = 0,
        tellers_size_bytes: int = 0,
        history_size_bytes: int = 0,
        database_size_bytes: int = 0,
        indexes_size_bytes: int = 0,
        dead_tuples_estimate: int = 0,
        shared_buffers: str = "128MB",
        work_mem: str = "4MB",
        max_connections: str = "100",
        checkpoint_timeout: str = "5min",
        synchronous_commit: str = "on",
        autovacuum: str = "on",
        track_io_timing: str = "on",
        track_wal_io_timing: str = "on",
        cpu_limit: str = "1.0",
        memory_limit: str = "1024m",
        image_digest: Optional[str] = None,
        host_port: Optional[int] = None,
        timestamp_utc: Optional[str] = None,
    ):
        self.scale_factor = scale_factor
        self.accounts_count = accounts_count
        self.branches_count = branches_count
        self.tellers_count = tellers_count
        self.history_count = history_count
        self.host_port = host_port

        # Default bounds for backward compatibility if omitted
        self.min_aid = 1 if min_aid is None and accounts_count > 0 else (min_aid or 0)
        self.max_aid = accounts_count if max_aid is None and accounts_count > 0 else (max_aid or 0)
        self.min_abalance = min_abalance
        self.max_abalance = max_abalance
        self.sum_abalance = sum_abalance
        self.accounts_hash = accounts_hash

        self.min_bid = 1 if min_bid is None and branches_count > 0 else (min_bid or 0)
        self.max_bid = branches_count if max_bid is None and branches_count > 0 else (max_bid or 0)
        self.min_bbalance = min_bbalance
        self.max_bbalance = max_bbalance
        self.sum_bbalance = sum_bbalance
        self.branches_hash = branches_hash

        self.min_tid = 1 if min_tid is None and tellers_count > 0 else (min_tid or 0)
        self.max_tid = tellers_count if max_tid is None and tellers_count > 0 else (max_tid or 0)
        self.min_tbalance = min_tbalance
        self.max_tbalance = max_tbalance
        self.sum_tbalance = sum_tbalance
        self.tellers_hash = tellers_hash

        self.fingerprint_algorithm = fingerprint_algorithm
        self.content_fingerprint = content_fingerprint or compute_content_fingerprint(
            scale_factor=self.scale_factor,
            accounts_count=self.accounts_count,
            min_aid=self.min_aid,
            max_aid=self.max_aid,
            min_abalance=self.min_abalance,
            max_abalance=self.max_abalance,
            sum_abalance=self.sum_abalance,
            accounts_hash=self.accounts_hash,
            branches_count=self.branches_count,
            min_bid=self.min_bid,
            max_bid=self.max_bid,
            min_bbalance=self.min_bbalance,
            max_bbalance=self.max_bbalance,
            sum_bbalance=self.sum_bbalance,
            branches_hash=self.branches_hash,
            tellers_count=self.tellers_count,
            min_tid=self.min_tid,
            max_tid=self.max_tid,
            min_tbalance=self.min_tbalance,
            max_tbalance=self.max_tbalance,
            sum_tbalance=self.sum_tbalance,
            tellers_hash=self.tellers_hash,
            history_count=self.history_count,
        )

        self.accounts_size_bytes = accounts_size_bytes
        self.branches_size_bytes = branches_size_bytes
        self.tellers_size_bytes = tellers_size_bytes
        self.history_size_bytes = history_size_bytes
        self.database_size_bytes = database_size_bytes
        self.indexes_size_bytes = indexes_size_bytes
        self.dead_tuples_estimate = dead_tuples_estimate

        self.shared_buffers = shared_buffers
        self.work_mem = work_mem
        self.max_connections = max_connections
        self.checkpoint_timeout = checkpoint_timeout
        self.synchronous_commit = synchronous_commit
        self.autovacuum = autovacuum
        self.track_io_timing = track_io_timing
        self.track_wal_io_timing = track_wal_io_timing

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
            "exact_invariants": {
                "accounts": {
                    "count": self.accounts_count,
                    "min_aid": self.min_aid,
                    "max_aid": self.max_aid,
                    "min_balance": self.min_abalance,
                    "max_balance": self.max_abalance,
                    "sum_balance": self.sum_abalance,
                    "hash_sum": self.accounts_hash,
                },
                "branches": {
                    "count": self.branches_count,
                    "min_bid": self.min_bid,
                    "max_bid": self.max_bid,
                    "min_balance": self.min_bbalance,
                    "max_balance": self.max_bbalance,
                    "sum_balance": self.sum_bbalance,
                    "hash_sum": self.branches_hash,
                },
                "tellers": {
                    "count": self.tellers_count,
                    "min_tid": self.min_tid,
                    "max_tid": self.max_tid,
                    "min_balance": self.min_tbalance,
                    "max_balance": self.max_tbalance,
                    "sum_balance": self.sum_tbalance,
                    "hash_sum": self.tellers_hash,
                },
                "history": {
                    "count": self.history_count,
                },
            },
            "fingerprint": {
                "content_fingerprint": self.content_fingerprint,
                "algorithm": self.fingerprint_algorithm,
            },
            "relation_sizes_bytes": {
                "accounts": self.accounts_size_bytes,
                "branches": self.branches_size_bytes,
                "tellers": self.tellers_size_bytes,
                "history": self.history_size_bytes,
                "total_database": self.database_size_bytes,
                "indexes_total": self.indexes_size_bytes,
            },
            "diagnostic_metadata": {
                "dead_tuples_estimate": self.dead_tuples_estimate,
            },
            "database_configuration": {
                "shared_buffers": self.shared_buffers,
                "work_mem": self.work_mem,
                "max_connections": self.max_connections,
                "checkpoint_timeout": self.checkpoint_timeout,
                "synchronous_commit": self.synchronous_commit,
                "autovacuum": self.autovacuum,
                "track_io_timing": self.track_io_timing,
                "track_wal_io_timing": self.track_wal_io_timing,
            },
            "container_configuration": {
                "cpu_limit": self.cpu_limit,
                "memory_limit": self.memory_limit,
                "image_digest": self.image_digest,
                "host_port": self.host_port,
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
            "delta_dead_tuples_estimate": after.dead_tuples_estimate - self.dead_tuples_estimate,
            "initial_fingerprint": self.content_fingerprint,
            "final_fingerprint": after.content_fingerprint,
            "fingerprint_matches": self.content_fingerprint == after.content_fingerprint,
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
        Enforces exact invariants, bounds, zero balances, and deterministic content fingerprints.
        Diagnostic metrics (like dead_tuples_estimate) are recorded without failing validation.
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

        # 3. Account ID bounds and zero balances
        if snapshot.min_aid != 1 or snapshot.max_aid != expected_accounts:
            violations.append(
                f"Accounts ID bounds mismatch: expected min=1, max={expected_accounts}, but found min={snapshot.min_aid}, max={snapshot.max_aid}."
            )

        if snapshot.min_abalance != 0 or snapshot.max_abalance != 0 or snapshot.sum_abalance != 0:
            violations.append(
                f"Accounts balance invariant violated: expected all balances 0 (min=0, max=0, sum=0), "
                f"but found min={snapshot.min_abalance}, max={snapshot.max_abalance}, sum={snapshot.sum_abalance}."
            )

        # 4. Branch invariants
        expected_branches = expected_sf
        if snapshot.branches_count != expected_branches:
            violations.append(
                f"Branches row count mismatch: expected {expected_branches} (1 * SF), but found {snapshot.branches_count}."
            )
        if snapshot.min_bid != 1 or snapshot.max_bid != expected_branches:
            violations.append(
                f"Branches ID bounds mismatch: expected min=1, max={expected_branches}, but found min={snapshot.min_bid}, max={snapshot.max_bid}."
            )
        if snapshot.min_bbalance != 0 or snapshot.max_bbalance != 0 or snapshot.sum_bbalance != 0:
            violations.append(
                f"Branches balance invariant violated: expected all balances 0, "
                f"but found min={snapshot.min_bbalance}, max={snapshot.max_bbalance}, sum={snapshot.sum_bbalance}."
            )

        # 5. Teller invariants
        expected_tellers = 10 * expected_sf
        if snapshot.tellers_count != expected_tellers:
            violations.append(
                f"Tellers row count mismatch: expected {expected_tellers} (10 * SF), but found {snapshot.tellers_count}."
            )
        if snapshot.min_tid != 1 or snapshot.max_tid != expected_tellers:
            violations.append(
                f"Tellers ID bounds mismatch: expected min=1, max={expected_tellers}, but found min={snapshot.min_tid}, max={snapshot.max_tid}."
            )
        if snapshot.min_tbalance != 0 or snapshot.max_tbalance != 0 or snapshot.sum_tbalance != 0:
            violations.append(
                f"Tellers balance invariant violated: expected all balances 0, "
                f"but found min={snapshot.min_tbalance}, max={snapshot.max_tbalance}, sum={snapshot.sum_tbalance}."
            )

        # 6. Isolation Precondition: History table MUST be completely empty at start
        if snapshot.history_count != 0:
            violations.append(
                f"Trial isolation violated: pgbench_history table contains {snapshot.history_count} rows from prior executions. "
                f"A baseline starting state must have exactly 0 history rows."
            )

        # 7. PostgreSQL timing configuration checks
        if snapshot.track_io_timing.lower() != "on":
            violations.append(
                f"Configuration invariant violated: track_io_timing is '{snapshot.track_io_timing}', expected 'on'."
            )
        if snapshot.track_wal_io_timing.lower() != "on":
            violations.append(
                f"Configuration invariant violated: track_wal_io_timing is '{snapshot.track_wal_io_timing}', expected 'on'."
            )

        # Note: snapshot.dead_tuples_estimate is diagnostic metadata; not treated as an exact invariant.

        is_valid = len(violations) == 0
        return is_valid, violations

    def capture_database_state(
        self,
        container_name: str,
        scale_factor: int,
    ) -> DatabaseStateSnapshot:
        """
        Queries PostgreSQL inside the target container to capture current row counts,
        ID and balance bounds, content hash aggregates, relation sizes, and configuration settings.
        """
        sql_query = (
            "SELECT "
            "(SELECT count(*) FROM pgbench_accounts), "
            "(SELECT coalesce(min(aid), 0) FROM pgbench_accounts), "
            "(SELECT coalesce(max(aid), 0) FROM pgbench_accounts), "
            "(SELECT coalesce(min(abalance), 0) FROM pgbench_accounts), "
            "(SELECT coalesce(max(abalance), 0) FROM pgbench_accounts), "
            "(SELECT coalesce(sum(abalance), 0) FROM pgbench_accounts), "
            "(SELECT coalesce(sum(hashtext(aid::text || ':' || bid::text || ':' || abalance::text)::bigint), 0) FROM pgbench_accounts), "
            "(SELECT count(*) FROM pgbench_branches), "
            "(SELECT coalesce(min(bid), 0) FROM pgbench_branches), "
            "(SELECT coalesce(max(bid), 0) FROM pgbench_branches), "
            "(SELECT coalesce(min(bbalance), 0) FROM pgbench_branches), "
            "(SELECT coalesce(max(bbalance), 0) FROM pgbench_branches), "
            "(SELECT coalesce(sum(bbalance), 0) FROM pgbench_branches), "
            "(SELECT coalesce(sum(hashtext(bid::text || ':' || bbalance::text)::bigint), 0) FROM pgbench_branches), "
            "(SELECT count(*) FROM pgbench_tellers), "
            "(SELECT coalesce(min(tid), 0) FROM pgbench_tellers), "
            "(SELECT coalesce(max(tid), 0) FROM pgbench_tellers), "
            "(SELECT coalesce(min(tbalance), 0) FROM pgbench_tellers), "
            "(SELECT coalesce(max(tbalance), 0) FROM pgbench_tellers), "
            "(SELECT coalesce(sum(tbalance), 0) FROM pgbench_tellers), "
            "(SELECT coalesce(sum(hashtext(tid::text || ':' || bid::text || ':' || tbalance::text)::bigint), 0) FROM pgbench_tellers), "
            "(SELECT count(*) FROM pgbench_history), "
            "pg_total_relation_size('pgbench_accounts'), "
            "pg_total_relation_size('pgbench_branches'), "
            "pg_total_relation_size('pgbench_tellers'), "
            "pg_total_relation_size('pgbench_history'), "
            "pg_database_size('aadsbench'), "
            "coalesce((SELECT sum(pg_indexes_size(relid))::bigint FROM pg_stat_user_tables WHERE relname LIKE 'pgbench_%'), 0), "
            "coalesce((SELECT sum(n_dead_tup)::bigint FROM pg_stat_user_tables WHERE relname LIKE 'pgbench_%'), 0), "
            "current_setting('shared_buffers'), "
            "current_setting('work_mem'), "
            "current_setting('max_connections'), "
            "current_setting('checkpoint_timeout'), "
            "current_setting('synchronous_commit'), "
            "current_setting('autovacuum'), "
            "current_setting('track_io_timing'), "
            "current_setting('track_wal_io_timing');"
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
            if len(parts) < 37:
                raise ValueError(f"Unexpected database state output format (got {len(parts)} parts, expected >=37): '{res.stdout.strip()}'")

            return DatabaseStateSnapshot(
                scale_factor=scale_factor,
                accounts_count=int(parts[0]),
                min_aid=int(parts[1]),
                max_aid=int(parts[2]),
                min_abalance=int(parts[3]),
                max_abalance=int(parts[4]),
                sum_abalance=int(parts[5]),
                accounts_hash=int(parts[6]),
                branches_count=int(parts[7]),
                min_bid=int(parts[8]),
                max_bid=int(parts[9]),
                min_bbalance=int(parts[10]),
                max_bbalance=int(parts[11]),
                sum_bbalance=int(parts[12]),
                branches_hash=int(parts[13]),
                tellers_count=int(parts[14]),
                min_tid=int(parts[15]),
                max_tid=int(parts[16]),
                min_tbalance=int(parts[17]),
                max_tbalance=int(parts[18]),
                sum_tbalance=int(parts[19]),
                tellers_hash=int(parts[20]),
                history_count=int(parts[21]),
                accounts_size_bytes=int(parts[22]),
                branches_size_bytes=int(parts[23]),
                tellers_size_bytes=int(parts[24]),
                history_size_bytes=int(parts[25]),
                database_size_bytes=int(parts[26]),
                indexes_size_bytes=int(parts[27]),
                dead_tuples_estimate=int(parts[28]),
                shared_buffers=parts[29],
                work_mem=parts[30],
                max_connections=parts[31],
                checkpoint_timeout=parts[32],
                synchronous_commit=parts[33],
                autovacuum=parts[34],
                track_io_timing=parts[35],
                track_wal_io_timing=parts[36],
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
        publish_host_port: bool = False,
    ) -> Tuple[float, DatabaseStateSnapshot]:
        """
        Starts a fresh PostgreSQL container with timing flags enabled, initializes pgbench dataset
        for scale_factor, and verifies the initial baseline state.
        Returns:
            Tuple of (initialization_duration_seconds, initial_baseline_snapshot)
        """
        # 1. Start fresh container with timing instrumentation enabled using immutable digest reference (P-03)
        if "@" in self.default_image:
            immutable_image_ref = self.default_image
        elif self.pinned_image_digest:
            repo_base = self.default_image.split(":")[0]
            immutable_image_ref = f"{repo_base}@{self.pinned_image_digest}"
        else:
            immutable_image_ref = self.default_image

        start_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--cpus", str(self.cpu_limit),
            "--memory", str(self.memory_limit),
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e", "POSTGRES_DB=aadsbench",
        ]
        if publish_host_port:
            start_cmd.extend(["-p", "127.0.0.1::5432"])
        start_cmd.extend([
            immutable_image_ref,
            "-c", "track_io_timing=on",
            "-c", "track_wal_io_timing=on",
        ])

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

        # Resolve host port if published
        host_port: Optional[int] = None
        if publish_host_port:
            port_res = subprocess.run(
                ["docker", "port", container_name, "5432/tcp"],
                capture_output=True, text=True, timeout=5,
            )
            if port_res.returncode == 0 and port_res.stdout.strip():
                for line in port_res.stdout.splitlines():
                    if ":" in line:
                        p_str = line.strip().split(":")[-1]
                        if p_str.isdigit():
                            host_port = int(p_str)
                            break

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
            if host_port is not None:
                snapshot.host_port = host_port
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
