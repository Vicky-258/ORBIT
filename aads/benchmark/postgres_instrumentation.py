"""
PostgreSQL Engine Observability and Lock/Wait Instrumentation (Phase 4F.3 - Workstream 2).

Collects internal PostgreSQL 16 statistics before, during, and after benchmark execution:
- Lock and wait-event observations (pg_stat_activity, pg_locks, wait_event_type, wait_event)
- WAL generation and synchronization (pg_stat_wal: records, bytes, fpi, write/sync times)
- Checkpoint and background writer statistics (pg_stat_checkpointer, pg_stat_bgwriter)
- Database and table-level statistics (pg_stat_database, pg_stat_user_tables)
- I/O activity statistics (pg_stat_io)
- Verification of mandatory timing flags (track_io_timing, track_wal_io_timing) [FIX 02]
- Low-overhead persistent monitoring coprocess session with telemetry [FIX 04]

Provides delta computation and periodic sampling to distinguish lock contention from CPU/IO bounds.
"""
import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PostgresSnapshot:
    """Point-in-time snapshot of PostgreSQL internal statistics and timing configurations."""

    def __init__(
        self,
        timestamp_monotonic: float,
        timestamp_utc: str,
        wal_stats: Optional[Dict[str, Any]] = None,
        checkpointer_stats: Optional[Dict[str, Any]] = None,
        bgwriter_stats: Optional[Dict[str, Any]] = None,
        database_stats: Optional[Dict[str, Any]] = None,
        table_stats: Optional[Dict[str, Dict[str, Any]]] = None,
        io_stats: Optional[Dict[str, Any]] = None,
        activity_stats: Optional[List[Dict[str, Any]]] = None,
        locks_stats: Optional[List[Dict[str, Any]]] = None,
        database_settings: Optional[Dict[str, str]] = None,
        unavailable_metrics: Optional[List[str]] = None,
    ):
        self.timestamp_monotonic = timestamp_monotonic
        self.timestamp_utc = timestamp_utc
        self.wal_stats = wal_stats or {}
        self.checkpointer_stats = checkpointer_stats or {}
        self.bgwriter_stats = bgwriter_stats or {}
        self.database_stats = database_stats or {}
        self.table_stats = table_stats or {}
        self.io_stats = io_stats or {}
        self.activity_stats = activity_stats or []
        self.locks_stats = locks_stats or []
        self.database_settings = database_settings or {}
        self.unavailable_metrics = unavailable_metrics or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_monotonic": round(self.timestamp_monotonic, 6),
            "timestamp_utc": self.timestamp_utc,
            "wal_stats": self.wal_stats,
            "checkpointer_stats": self.checkpointer_stats,
            "bgwriter_stats": self.bgwriter_stats,
            "database_stats": self.database_stats,
            "table_stats": self.table_stats,
            "io_stats": self.io_stats,
            "activity_stats": self.activity_stats,
            "locks_stats": self.locks_stats,
            "database_settings": self.database_settings,
            "unavailable_metrics": self.unavailable_metrics,
        }


class PostgresMetricsDelta:
    """Exact deltas computed between pre-trial and post-trial PostgreSQL statistics."""

    def __init__(
        self,
        duration_seconds: float,
        delta_wal_bytes: int = 0,
        delta_wal_records: int = 0,
        delta_wal_fpi: int = 0,
        delta_wal_write: int = 0,
        delta_wal_sync: int = 0,
        delta_wal_write_time_ms: float = 0.0,
        delta_wal_sync_time_ms: float = 0.0,
        delta_checkpoints_timed: int = 0,
        delta_checkpoints_req: int = 0,
        delta_checkpoint_write_time_ms: float = 0.0,
        delta_checkpoint_sync_time_ms: float = 0.0,
        delta_checkpoint_buffers_written: int = 0,
        delta_bgwriter_buffers_clean: int = 0,
        delta_bgwriter_maxwritten_clean: int = 0,
        delta_xact_commit: int = 0,
        delta_xact_rollback: int = 0,
        delta_blks_read: int = 0,
        delta_blks_hit: int = 0,
        delta_deadlocks: int = 0,
        delta_conflicts: int = 0,
        delta_table_inserts: Optional[Dict[str, int]] = None,
        delta_table_updates: Optional[Dict[str, int]] = None,
        delta_table_dead_tup: Optional[Dict[str, int]] = None,
        delta_io_reads: int = 0,
        delta_io_writes: int = 0,
        delta_io_fsyncs: int = 0,
        observed_lock_waits: int = 0,
        observed_wait_events: Optional[Dict[str, int]] = None,
        lock_contention_classification: str = "NO_CONTENTION_OBSERVED",
        unsupported_or_missing_views: Optional[List[str]] = None,
        timing_instrumentation_active: bool = True,
    ):
        self.duration_seconds = duration_seconds
        self.delta_wal_bytes = delta_wal_bytes
        self.delta_wal_records = delta_wal_records
        self.delta_wal_fpi = delta_wal_fpi
        self.delta_wal_write = delta_wal_write
        self.delta_wal_sync = delta_wal_sync
        self.delta_wal_write_time_ms = delta_wal_write_time_ms
        self.delta_wal_sync_time_ms = delta_wal_sync_time_ms
        self.delta_checkpoints_timed = delta_checkpoints_timed
        self.delta_checkpoints_req = delta_checkpoints_req
        self.delta_checkpoint_write_time_ms = delta_checkpoint_write_time_ms
        self.delta_checkpoint_sync_time_ms = delta_checkpoint_sync_time_ms
        self.delta_checkpoint_buffers_written = delta_checkpoint_buffers_written
        self.delta_bgwriter_buffers_clean = delta_bgwriter_buffers_clean
        self.delta_bgwriter_maxwritten_clean = delta_bgwriter_maxwritten_clean
        self.delta_xact_commit = delta_xact_commit
        self.delta_xact_rollback = delta_xact_rollback
        self.delta_blks_read = delta_blks_read
        self.delta_blks_hit = delta_blks_hit
        self.delta_deadlocks = delta_deadlocks
        self.delta_conflicts = delta_conflicts
        self.delta_table_inserts = delta_table_inserts or {}
        self.delta_table_updates = delta_table_updates or {}
        self.delta_table_dead_tup = delta_table_dead_tup or {}
        self.delta_io_reads = delta_io_reads
        self.delta_io_writes = delta_io_writes
        self.delta_io_fsyncs = delta_io_fsyncs
        self.observed_lock_waits = observed_lock_waits
        self.observed_wait_events = observed_wait_events or {}
        self.lock_contention_classification = lock_contention_classification
        self.unsupported_or_missing_views = unsupported_or_missing_views or []
        self.timing_instrumentation_active = timing_instrumentation_active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "duration_seconds": round(self.duration_seconds, 3),
            "timing_instrumentation_active": self.timing_instrumentation_active,
            "wal": {
                "delta_wal_bytes": self.delta_wal_bytes,
                "delta_wal_mb": round(self.delta_wal_bytes / (1024.0 * 1024.0), 3),
                "wal_rate_mb_per_sec": round((self.delta_wal_bytes / (1024.0 * 1024.0)) / max(0.001, self.duration_seconds), 3),
                "delta_wal_records": self.delta_wal_records,
                "delta_wal_fpi": self.delta_wal_fpi,
                "delta_wal_write": self.delta_wal_write,
                "delta_wal_sync": self.delta_wal_sync,
                "delta_wal_write_time_ms": round(self.delta_wal_write_time_ms, 2) if self.timing_instrumentation_active else None,
                "delta_wal_sync_time_ms": round(self.delta_wal_sync_time_ms, 2) if self.timing_instrumentation_active else None,
            },
            "checkpoints_and_bgwriter": {
                "delta_checkpoints_timed": self.delta_checkpoints_timed,
                "delta_checkpoints_req": self.delta_checkpoints_req,
                "delta_checkpoint_write_time_ms": round(self.delta_checkpoint_write_time_ms, 2) if self.timing_instrumentation_active else None,
                "delta_checkpoint_sync_time_ms": round(self.delta_checkpoint_sync_time_ms, 2) if self.timing_instrumentation_active else None,
                "delta_checkpoint_buffers_written": self.delta_checkpoint_buffers_written,
                "delta_bgwriter_buffers_clean": self.delta_bgwriter_buffers_clean,
                "delta_bgwriter_maxwritten_clean": self.delta_bgwriter_maxwritten_clean,
            },
            "database": {
                "delta_xact_commit": self.delta_xact_commit,
                "delta_xact_rollback": self.delta_xact_rollback,
                "delta_blks_read": self.delta_blks_read,
                "delta_blks_hit": self.delta_blks_hit,
                "buffer_hit_ratio_pct": (
                    round((self.delta_blks_hit / (self.delta_blks_hit + self.delta_blks_read)) * 100.0, 2)
                    if (self.delta_blks_hit + self.delta_blks_read) > 0
                    else 100.0
                ),
                "cache_hit_ratio_pct": (
                    round((self.delta_blks_hit / (self.delta_blks_hit + self.delta_blks_read)) * 100.0, 2)
                    if (self.delta_blks_hit + self.delta_blks_read) > 0
                    else 100.0
                ),
                "delta_deadlocks": self.delta_deadlocks,
                "delta_conflicts": self.delta_conflicts,
            },
            "tables": {
                "inserts": self.delta_table_inserts,
                "updates": self.delta_table_updates,
                "dead_tuples": self.delta_table_dead_tup,
            },
            "engine_io": {
                "delta_io_reads": self.delta_io_reads,
                "delta_io_writes": self.delta_io_writes,
                "delta_io_fsyncs": self.delta_io_fsyncs,
            },
            "concurrency_and_locks": {
                "observed_lock_waits": self.observed_lock_waits,
                "observed_wait_events": self.observed_wait_events,
                "lock_contention_classification": self.lock_contention_classification,
            },
            "unsupported_or_missing_views": self.unsupported_or_missing_views,
        }


class PostgresMetricsCollector:
    """Interrogates PostgreSQL internal system catalogs and performance views."""

    @staticmethod
    def _execute_sql(container_name: str, query: str, timeout: int = 8) -> Optional[str]:
        cmd = [
            "docker", "exec", container_name,
            "psql", "-U", "postgres", "-d", "aadsbench", "-t", "-A", "-F", "|", "-c", query,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return res.stdout.strip()
            logger.debug(f"psql query error ({query}): {res.stderr.strip()}")
            return None
        except Exception as e:
            logger.debug(f"psql execution failed: {e}")
            return None

    @classmethod
    def take_snapshot(cls, container_name: str) -> PostgresSnapshot:
        """Captures a full snapshot of PostgreSQL 16 internal performance views."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        unavailable: List[str] = []

        # 0. Check mandatory timing flags (FIX 02)
        settings: Dict[str, str] = {}
        try:
            cfg_out = cls._execute_sql(
                container_name,
                "SELECT current_setting('track_io_timing'), current_setting('track_wal_io_timing');"
            )
            if cfg_out:
                parts = cfg_out.split("|")
                if len(parts) >= 2:
                    settings["track_io_timing"] = parts[0]
                    settings["track_wal_io_timing"] = parts[1]
                    if parts[0].lower() != "on":
                        unavailable.append("track_io_timing_disabled")
                    if parts[1].lower() != "on":
                        unavailable.append("track_wal_io_timing_disabled")
            else:
                unavailable.append("settings_query_failed")
        except Exception:
            unavailable.append("settings_query_failed")

        # 1. pg_stat_wal
        wal_stats: Dict[str, Any] = {}
        try:
            wal_out = cls._execute_sql(
                container_name,
                "SELECT wal_records, wal_fpi, wal_bytes, wal_buffers_full, wal_write, wal_sync, wal_write_time, wal_sync_time FROM pg_stat_wal;"
            )
            if wal_out:
                parts = wal_out.split("|")
                if len(parts) >= 8:
                    wal_stats = {
                        "wal_records": int(parts[0]),
                        "wal_fpi": int(parts[1]),
                        "wal_bytes": int(parts[2]),
                        "wal_buffers_full": int(parts[3]),
                        "wal_write": int(parts[4]),
                        "wal_sync": int(parts[5]),
                        "wal_write_time": float(parts[6]),
                        "wal_sync_time": float(parts[7]),
                    }
                else:
                    unavailable.append("pg_stat_wal")
            else:
                unavailable.append("pg_stat_wal")
        except Exception:
            unavailable.append("pg_stat_wal")

        # 2. pg_stat_checkpointer (PG 16) with fallback to pg_stat_bgwriter
        chk_stats: Dict[str, Any] = {}
        try:
            chk_out = cls._execute_sql(
                container_name,
                "SELECT num_timed, num_requested, restartpoints_timed, restartpoints_req, restartpoints_done, write_time, sync_time, buffers_written FROM pg_stat_checkpointer;"
            )
            if chk_out:
                parts = chk_out.split("|")
                if len(parts) >= 8:
                    chk_stats = {
                        "num_timed": int(parts[0]),
                        "num_requested": int(parts[1]),
                        "restartpoints_timed": int(parts[2]),
                        "restartpoints_req": int(parts[3]),
                        "restartpoints_done": int(parts[4]),
                        "write_time": float(parts[5]),
                        "sync_time": float(parts[6]),
                        "buffers_written": int(parts[7]),
                    }
                else:
                    unavailable.append("pg_stat_checkpointer")
            else:
                bg_chk_out = cls._execute_sql(
                    container_name,
                    "SELECT checkpoints_timed, checkpoints_req, checkpoint_write_time, checkpoint_sync_time, buffers_checkpoint FROM pg_stat_bgwriter;"
                )
                if bg_chk_out:
                    parts = bg_chk_out.split("|")
                    if len(parts) >= 5:
                        chk_stats = {
                            "num_timed": int(parts[0]),
                            "num_requested": int(parts[1]),
                            "write_time": float(parts[2]),
                            "sync_time": float(parts[3]),
                            "buffers_written": int(parts[4]),
                        }
                    else:
                        unavailable.append("pg_stat_checkpointer")
                else:
                    unavailable.append("pg_stat_checkpointer")
        except Exception:
            unavailable.append("pg_stat_checkpointer")

        # 3. pg_stat_bgwriter
        bg_stats: Dict[str, Any] = {}
        try:
            bg_out = cls._execute_sql(
                container_name,
                "SELECT buffers_clean, maxwritten_clean, buffers_alloc FROM pg_stat_bgwriter;"
            )
            if bg_out:
                parts = bg_out.split("|")
                if len(parts) >= 3:
                    bg_stats = {
                        "buffers_clean": int(parts[0]),
                        "maxwritten_clean": int(parts[1]),
                        "buffers_alloc": int(parts[2]),
                    }
                else:
                    unavailable.append("pg_stat_bgwriter")
            else:
                unavailable.append("pg_stat_bgwriter")
        except Exception:
            unavailable.append("pg_stat_bgwriter")

        # 4. pg_stat_database
        db_stats: Dict[str, Any] = {}
        try:
            db_out = cls._execute_sql(
                container_name,
                "SELECT xact_commit, xact_rollback, blks_read, blks_hit, tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted, conflicts, deadlocks "
                "FROM pg_stat_database WHERE datname = 'aadsbench';"
            )
            if db_out:
                parts = db_out.split("|")
                if len(parts) >= 11:
                    db_stats = {
                        "xact_commit": int(parts[0]),
                        "xact_rollback": int(parts[1]),
                        "blks_read": int(parts[2]),
                        "blks_hit": int(parts[3]),
                        "tup_returned": int(parts[4]),
                        "tup_fetched": int(parts[5]),
                        "tup_inserted": int(parts[6]),
                        "tup_updated": int(parts[7]),
                        "tup_deleted": int(parts[8]),
                        "conflicts": int(parts[9]),
                        "deadlocks": int(parts[10]),
                    }
                else:
                    unavailable.append("pg_stat_database")
            else:
                unavailable.append("pg_stat_database")
        except Exception:
            unavailable.append("pg_stat_database")

        # 5. pg_stat_user_tables
        table_stats: Dict[str, Dict[str, Any]] = {}
        try:
            tbl_out = cls._execute_sql(
                container_name,
                "SELECT relname, n_tup_ins, n_tup_upd, n_tup_del, n_tup_hot_upd, n_live_tup, n_dead_tup, seq_scan, idx_scan "
                "FROM pg_stat_user_tables;"
            )
            if tbl_out:
                for line in tbl_out.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 9:
                        relname = parts[0]
                        table_stats[relname] = {
                            "n_tup_ins": int(parts[1]),
                            "n_tup_upd": int(parts[2]),
                            "n_tup_del": int(parts[3]),
                            "n_tup_hot_upd": int(parts[4]),
                            "n_live_tup": int(parts[5]),
                            "n_dead_tup": int(parts[6]),
                            "seq_scan": int(parts[7]),
                            "idx_scan": int(parts[8]),
                        }
            else:
                unavailable.append("pg_stat_user_tables")
        except Exception:
            unavailable.append("pg_stat_user_tables")

        # 6. pg_stat_io (PG 16)
        io_stats: Dict[str, Any] = {}
        try:
            io_out = cls._execute_sql(
                container_name,
                "SELECT sum(reads), sum(writes), sum(fsyncs) FROM pg_stat_io;"
            )
            if io_out:
                parts = io_out.split("|")
                if len(parts) >= 3 and parts[0].isdigit():
                    io_stats = {
                        "reads": int(parts[0]) if parts[0].isdigit() else 0,
                        "writes": int(parts[1]) if parts[1].isdigit() else 0,
                        "fsyncs": int(parts[2]) if parts[2].isdigit() else 0,
                    }
            else:
                unavailable.append("pg_stat_io")
        except Exception:
            unavailable.append("pg_stat_io")

        # 7. pg_stat_activity & pg_locks snapshot
        act_stats: List[Dict[str, Any]] = []
        try:
            act_out = cls._execute_sql(
                container_name,
                "SELECT pid, state, wait_event_type, wait_event FROM pg_stat_activity WHERE datname = 'aadsbench' AND pid != pg_backend_pid();"
            )
            if act_out:
                for line in act_out.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        act_stats.append({
                            "pid": int(parts[0]) if parts[0].isdigit() else parts[0],
                            "state": parts[1],
                            "wait_event_type": parts[2] if parts[2] else "None",
                            "wait_event": parts[3] if parts[3] else "None",
                        })
        except Exception:
            pass

        locks_stats: List[Dict[str, Any]] = []
        try:
            locks_out = cls._execute_sql(
                container_name,
                "SELECT locktype, mode, granted, count(*) FROM pg_locks WHERE database = (SELECT oid FROM pg_database WHERE datname = 'aadsbench') GROUP BY 1, 2, 3;"
            )
            if locks_out:
                for line in locks_out.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        locks_stats.append({
                            "locktype": parts[0],
                            "mode": parts[1],
                            "granted": parts[2] == "t",
                            "count": int(parts[3]) if parts[3].isdigit() else 1,
                        })
        except Exception:
            pass

        return PostgresSnapshot(
            timestamp_monotonic=now_mono,
            timestamp_utc=now_utc,
            wal_stats=wal_stats,
            checkpointer_stats=chk_stats,
            bgwriter_stats=bg_stats,
            database_stats=db_stats,
            table_stats=table_stats,
            io_stats=io_stats,
            activity_stats=act_stats,
            locks_stats=locks_stats,
            database_settings=settings,
            unavailable_metrics=unavailable,
        )

    @staticmethod
    def compute_deltas(
        start: PostgresSnapshot,
        end: PostgresSnapshot,
        periodic_lock_waits: int = 0,
        periodic_wait_events: Optional[Dict[str, int]] = None,
        lock_wait_samples: Optional[int] = None,
        wait_event_samples: Optional[Dict[str, int]] = None,
    ) -> PostgresMetricsDelta:
        """Calculates exact deltas between start and end snapshots."""
        duration = max(0.001, end.timestamp_monotonic - start.timestamp_monotonic)
        waits = lock_wait_samples if lock_wait_samples is not None else periodic_lock_waits
        wait_evs = wait_event_samples if wait_event_samples is not None else (periodic_wait_events or {})

        # Verify timing instrumentation flags
        timing_active = (
            start.database_settings.get("track_io_timing", "on").lower() == "on"
            and start.database_settings.get("track_wal_io_timing", "on").lower() == "on"
            and "track_io_timing_disabled" not in start.unavailable_metrics
            and "track_wal_io_timing_disabled" not in start.unavailable_metrics
        )

        # WAL deltas
        s_wal = start.wal_stats
        e_wal = end.wal_stats
        delta_wal_bytes = max(0, e_wal.get("wal_bytes", 0) - s_wal.get("wal_bytes", 0))
        delta_wal_records = max(0, e_wal.get("wal_records", 0) - s_wal.get("wal_records", 0))
        delta_wal_fpi = max(0, e_wal.get("wal_fpi", 0) - s_wal.get("wal_fpi", 0))
        delta_wal_write = max(0, e_wal.get("wal_write", 0) - s_wal.get("wal_write", 0))
        delta_wal_sync = max(0, e_wal.get("wal_sync", 0) - s_wal.get("wal_sync", 0))
        delta_wal_write_time = max(0.0, e_wal.get("wal_write_time", 0.0) - s_wal.get("wal_write_time", 0.0))
        delta_wal_sync_time = max(0.0, e_wal.get("wal_sync_time", 0.0) - s_wal.get("wal_sync_time", 0.0))

        # Checkpointer deltas
        s_chk = start.checkpointer_stats
        e_chk = end.checkpointer_stats
        delta_chk_timed = max(0, e_chk.get("num_timed", 0) - s_chk.get("num_timed", 0))
        delta_chk_req = max(0, e_chk.get("num_requested", 0) - s_chk.get("num_requested", 0))
        delta_chk_wtime = max(0.0, e_chk.get("write_time", 0.0) - s_chk.get("write_time", 0.0))
        delta_chk_stime = max(0.0, e_chk.get("sync_time", 0.0) - s_chk.get("sync_time", 0.0))
        delta_chk_buf = max(0, e_chk.get("buffers_written", 0) - s_chk.get("buffers_written", 0))

        # Bgwriter deltas
        s_bg = start.bgwriter_stats
        e_bg = end.bgwriter_stats
        delta_bg_clean = max(0, e_bg.get("buffers_clean", 0) - s_bg.get("buffers_clean", 0))
        delta_bg_max = max(0, e_bg.get("maxwritten_clean", 0) - s_bg.get("maxwritten_clean", 0))

        # Database deltas
        s_db = start.database_stats
        e_db = end.database_stats
        delta_commits = max(0, e_db.get("xact_commit", 0) - s_db.get("xact_commit", 0))
        delta_rollbacks = max(0, e_db.get("xact_rollback", 0) - s_db.get("xact_rollback", 0))
        delta_blks_read = max(0, e_db.get("blks_read", 0) - s_db.get("blks_read", 0))
        delta_blks_hit = max(0, e_db.get("blks_hit", 0) - s_db.get("blks_hit", 0))
        delta_deadlocks = max(0, e_db.get("deadlocks", 0) - s_db.get("deadlocks", 0))
        delta_conflicts = max(0, e_db.get("conflicts", 0) - s_db.get("conflicts", 0))

        # Table deltas
        ins_deltas: Dict[str, int] = {}
        upd_deltas: Dict[str, int] = {}
        dead_deltas: Dict[str, int] = {}
        s_tbl = start.table_stats
        e_tbl = end.table_stats
        for tbl, e_stat in e_tbl.items():
            s_stat = s_tbl.get(tbl, {})
            ins_deltas[tbl] = max(0, e_stat.get("n_tup_ins", 0) - s_stat.get("n_tup_ins", 0))
            upd_deltas[tbl] = max(0, e_stat.get("n_tup_upd", 0) - s_stat.get("n_tup_upd", 0))
            dead_deltas[tbl] = max(0, e_stat.get("n_dead_tup", 0) - s_stat.get("n_dead_tup", 0))

        # IO deltas
        s_io = start.io_stats
        e_io = end.io_stats
        delta_io_reads = max(0, e_io.get("reads", 0) - s_io.get("reads", 0))
        delta_io_writes = max(0, e_io.get("writes", 0) - s_io.get("writes", 0))
        delta_io_fsyncs = max(0, e_io.get("fsyncs", 0) - s_io.get("fsyncs", 0))

        # Lock contention classification
        if waits == 0 and not any("Lock" in k or "tuple" in k.lower() for k in wait_evs.keys()):
            lock_class = "NO_CONTENTION_OBSERVED"
        elif waits > 0 or any("Lock" in k for k in wait_evs.keys()):
            lock_class = "CONFIRMED_LOCK_CONTENTION_OBSERVED"
        else:
            lock_class = "LOCK_STATUS_INCONCLUSIVE"

        unsupported = sorted(list(set(start.unavailable_metrics + end.unavailable_metrics)))

        return PostgresMetricsDelta(
            duration_seconds=duration,
            delta_wal_bytes=delta_wal_bytes,
            delta_wal_records=delta_wal_records,
            delta_wal_fpi=delta_wal_fpi,
            delta_wal_write=delta_wal_write,
            delta_wal_sync=delta_wal_sync,
            delta_wal_write_time_ms=delta_wal_write_time,
            delta_wal_sync_time_ms=delta_wal_sync_time,
            delta_checkpoints_timed=delta_chk_timed,
            delta_checkpoints_req=delta_chk_req,
            delta_checkpoint_write_time_ms=delta_chk_wtime,
            delta_checkpoint_sync_time_ms=delta_chk_stime,
            delta_checkpoint_buffers_written=delta_chk_buf,
            delta_bgwriter_buffers_clean=delta_bg_clean,
            delta_bgwriter_maxwritten_clean=delta_bg_max,
            delta_xact_commit=delta_commits,
            delta_xact_rollback=delta_rollbacks,
            delta_blks_read=delta_blks_read,
            delta_blks_hit=delta_blks_hit,
            delta_deadlocks=delta_deadlocks,
            delta_conflicts=delta_conflicts,
            delta_table_inserts=ins_deltas,
            delta_table_updates=upd_deltas,
            delta_table_dead_tup=dead_deltas,
            delta_io_reads=delta_io_reads,
            delta_io_writes=delta_io_writes,
            delta_io_fsyncs=delta_io_fsyncs,
            observed_lock_waits=waits,
            observed_wait_events=wait_evs,
            lock_contention_classification=lock_class,
            unsupported_or_missing_views=unsupported,
            timing_instrumentation_active=timing_active,
        )


class PostgresPeriodicSampler:
    """
    Background sampler querying pg_stat_activity and pg_locks during active benchmark execution.
    Implements a single persistent coprocess session (FIX 04) to avoid per-sample process fork overhead,
    falling back to discrete queries with an extended interval if coprocess creation fails.
    """

    def __init__(self, container_name: str, interval_sec: float = 0.100):
        self.container_name = container_name
        self.interval_sec = interval_sec
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._proc: Optional[subprocess.Popen] = None
        self.sampler_mode: str = "uninitialized"
        self.monitoring_connection_count: int = 0
        self.successful_samples: int = 0
        self.missed_samples: int = 0
        self.total_query_duration_ms: float = 0.0

        self.samples: List[Dict[str, Any]] = []
        self.total_lock_wait_samples = 0
        self.wait_event_counts: Dict[str, int] = {}

    def _start_coprocess(self) -> bool:
        """Initializes a persistent interactive psql session."""
        try:
            cmd = [
                "docker", "exec", "-i", self.container_name,
                "psql", "-U", "postgres", "-d", "aadsbench", "-t", "-A", "-F", "|",
            ]
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            self.sampler_mode = "persistent_coprocess"
            self.monitoring_connection_count = 1
            return True
        except Exception as e:
            logger.warning(f"Persistent psql session initialization failed: {e}. Falling back to discrete queries.")
            self._proc = None
            self.sampler_mode = "discrete_fallback"
            self.interval_sec = max(0.500, self.interval_sec)
            return False

    def _query_coprocess(self) -> Optional[str]:
        """Sends monitoring query over persistent pipe and reads delimited output."""
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return None
        sql = (
            "SELECT (SELECT count(*) FROM pg_locks WHERE NOT granted) || '|' || "
            "coalesce((SELECT string_agg(coalesce(wait_event_type || ':' || wait_event, 'none'), ',') "
            "FROM pg_stat_activity WHERE datname = 'aadsbench' AND pid != pg_backend_pid() AND wait_event IS NOT NULL), ''); "
            "\\echo __END_SAMPLE__\n"
        )
        try:
            self._proc.stdin.write(sql)
            self._proc.stdin.flush()

            output_line: Optional[str] = None
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    break
                stripped = line.strip()
                if stripped == "__END_SAMPLE__":
                    break
                if output_line is None and stripped != "":
                    output_line = stripped
            return output_line
        except Exception as e:
            logger.debug(f"Persistent psql communication error: {e}")
            return None

    def _sample_iteration(self, idx: int) -> None:
        t0 = time.monotonic()
        out: Optional[str] = None

        if self.sampler_mode == "persistent_coprocess" and self._proc:
            out = self._query_coprocess()
            if out is None:
                # Coprocess died; mark missed and switch to discrete fallback
                self.missed_samples += 1
                self.sampler_mode = "discrete_fallback"
                self.interval_sec = max(0.500, self.interval_sec)
                try:
                    if self._proc:
                        self._proc.terminate()
                except Exception:
                    pass
                self._proc = None
                return
        else:
            self.monitoring_connection_count += 1
            sql = (
                "SELECT "
                "(SELECT count(*) FROM pg_locks WHERE NOT granted), "
                "(SELECT string_agg(coalesce(wait_event_type || ':' || wait_event, 'none'), ',') "
                " FROM pg_stat_activity WHERE datname = 'aadsbench' AND pid != pg_backend_pid() AND wait_event IS NOT NULL);"
            )
            out = PostgresMetricsCollector._execute_sql(self.container_name, sql, timeout=3)

        dur_ms = (time.monotonic() - t0) * 1000.0

        if out is not None:
            self.successful_samples += 1
            self.total_query_duration_ms += dur_ms
            parts = out.split("|")
            unlocked_waits = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
            raw_events = parts[1] if len(parts) > 1 and parts[1] else ""

            if unlocked_waits > 0:
                self.total_lock_wait_samples += unlocked_waits

            if raw_events:
                for ev in raw_events.split(","):
                    ev = ev.strip()
                    if ev and ev != "none":
                        self.wait_event_counts[ev] = self.wait_event_counts.get(ev, 0) + 1

            self.samples.append({
                "sample_index": idx,
                "timestamp_monotonic": round(time.monotonic(), 4),
                "ungranted_locks": unlocked_waits,
                "active_wait_events": raw_events,
                "query_duration_ms": round(dur_ms, 2),
            })
        else:
            self.missed_samples += 1

    def _sampling_loop(self) -> None:
        idx = 0
        while not self._stop_event.is_set():
            try:
                self._sample_iteration(idx)
            except Exception as e:
                self.missed_samples += 1
                logger.debug(f"Postgres periodic sample iteration error: {e}")
            idx += 1
            self._stop_event.wait(self.interval_sec)

    def start(self) -> None:
        self._stop_event.clear()
        if not self._start_coprocess():
            self.sampler_mode = "discrete_fallback"
            self.interval_sec = max(0.500, self.interval_sec)

        self._thread = threading.Thread(
            target=self._sampling_loop,
            name=f"PostgresSampler-{self.container_name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> Tuple[int, Dict[str, int], List[Dict[str, Any]]]:
        """Stops the sampling loop, cleanly terminates the coprocess session, and returns results."""
        self._stop_event.set()

        if self._proc:
            try:
                if self._proc.stdin and not self._proc.stdin.closed:
                    self._proc.stdin.write("\\q\n")
                    self._proc.stdin.flush()
                    self._proc.stdin.close()
                self._proc.wait(timeout=1.5)
            except Exception:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
            finally:
                self._proc = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        return self.total_lock_wait_samples, self.wait_event_counts, self.samples

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns instrumentation telemetry and performance statistics for the sampler."""
        mean_dur = (
            round(self.total_query_duration_ms / self.successful_samples, 2)
            if self.successful_samples > 0
            else 0.0
        )
        return {
            "sampling_interval_sec": self.interval_sec,
            "sampler_mode": self.sampler_mode,
            "successful_samples": self.successful_samples,
            "missed_samples": self.missed_samples,
            "total_samples_attempted": self.successful_samples + self.missed_samples,
            "mean_query_duration_ms": mean_dur,
            "total_query_duration_ms": round(self.total_query_duration_ms, 2),
            "monitoring_connection_count": self.monitoring_connection_count,
        }
