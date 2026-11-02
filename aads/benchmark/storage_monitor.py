"""
Storage I/O Observability and Bottleneck Detection (Phase 4F.3 - Workstream 3).

Measures container cgroup v2 io.stat and host /proc/diskstats before and after benchmark execution:
- Container read/write bytes, read/write IOPS, discard operations
- Host disk read/write throughput, sectors transferred, queue depth, await latency, and busy time
- Enforces strict interpretation rules: separates WAL logical generation from physical storage bottlenecks.
- Conservative multi-queue storage pressure classification (Phase 4F.3.2 FIX 01 & FIX 06).
"""
from enum import Enum
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StoragePressureClassification(str, Enum):
    """Conservative epistemological taxonomy for storage bottleneck assertions."""
    INSUFFICIENT_STORAGE_EVIDENCE = "INSUFFICIENT_STORAGE_EVIDENCE"
    NO_STORAGE_PRESSURE_OBSERVED = "NO_STORAGE_PRESSURE_OBSERVED"
    STORAGE_PRESSURE_SUSPECTED = "STORAGE_PRESSURE_SUSPECTED"
    STORAGE_PRESSURE_SUPPORTED = "STORAGE_PRESSURE_SUPPORTED"


class StorageSnapshot:
    """Exact point-in-time snapshot of cgroup and host storage counters."""

    def __init__(
        self,
        timestamp_monotonic: float,
        timestamp_utc: str,
        cgroup_io_stat: Optional[Dict[str, Dict[str, int]]] = None,
        host_diskstats: Optional[Dict[str, Dict[str, int]]] = None,
        primary_device: Optional[str] = None,
        filesystem_type: Optional[str] = None,
        cgroup_dir: Optional[str] = None,
        unavailable_metrics: Optional[List[str]] = None,
    ):
        self.timestamp_monotonic = timestamp_monotonic
        self.timestamp_utc = timestamp_utc
        self.cgroup_io_stat = cgroup_io_stat or {}
        self.host_diskstats = host_diskstats or {}
        self.primary_device = primary_device
        self.filesystem_type = filesystem_type
        self.cgroup_dir = cgroup_dir
        self.unavailable_metrics = unavailable_metrics or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_monotonic": round(self.timestamp_monotonic, 6),
            "timestamp_utc": self.timestamp_utc,
            "cgroup_dir": self.cgroup_dir,
            "cgroup_io_stat": self.cgroup_io_stat,
            "host_diskstats": self.host_diskstats,
            "primary_device": self.primary_device,
            "filesystem_type": self.filesystem_type,
            "unavailable_metrics": self.unavailable_metrics,
        }


class StorageMetricsDelta:
    """Deltas and throughput rates between pre-trial and post-trial storage snapshots."""

    def __init__(
        self,
        duration_seconds: float,
        delta_rbytes: int = 0,
        delta_wbytes: int = 0,
        delta_rios: int = 0,
        delta_wios: int = 0,
        delta_dbytes: int = 0,
        host_reads_completed: int = 0,
        host_writes_completed: int = 0,
        host_read_sectors: int = 0,
        host_write_sectors: int = 0,
        host_read_ms: float = 0.0,
        host_write_ms: float = 0.0,
        host_io_ms: float = 0.0,
        host_weighted_io_ms: float = 0.0,
        avg_queue_depth: float = 0.0,
        avg_await_ms: float = 0.0,
        primary_device: Optional[str] = None,
        filesystem_type: Optional[str] = None,
        is_storage_bound: bool = False,
        pressure_classification: StoragePressureClassification = StoragePressureClassification.NO_STORAGE_PRESSURE_OBSERVED,
        classification_reason: str = "NO_STORAGE_BOTTLENECK_DETECTED",
        unreliable_or_missing_metrics: Optional[List[str]] = None,
    ):
        self.duration_seconds = duration_seconds
        self.delta_rbytes = delta_rbytes
        self.delta_wbytes = delta_wbytes
        self.delta_rios = delta_rios
        self.delta_wios = delta_wios
        self.delta_dbytes = delta_dbytes
        self.host_reads_completed = host_reads_completed
        self.host_writes_completed = host_writes_completed
        self.host_read_sectors = host_read_sectors
        self.host_write_sectors = host_write_sectors
        self.host_read_ms = host_read_ms
        self.host_write_ms = host_write_ms
        self.host_io_ms = host_io_ms
        self.host_weighted_io_ms = host_weighted_io_ms
        self.avg_queue_depth = avg_queue_depth
        self.avg_await_ms = avg_await_ms
        self.primary_device = primary_device
        self.filesystem_type = filesystem_type
        self.is_storage_bound = is_storage_bound
        self.pressure_classification = pressure_classification
        self.classification_reason = classification_reason
        self.unreliable_or_missing_metrics = unreliable_or_missing_metrics or []

    def to_dict(self) -> Dict[str, Any]:
        dur = max(0.001, self.duration_seconds)
        r_mb = self.delta_rbytes / (1024.0 * 1024.0)
        w_mb = self.delta_wbytes / (1024.0 * 1024.0)
        return {
            "duration_seconds": round(dur, 3),
            "container_io": {
                "read_bytes": self.delta_rbytes,
                "read_mb": round(r_mb, 3),
                "read_mb_per_sec": round(r_mb / dur, 3),
                "read_iops": round(self.delta_rios / dur, 1),
                "write_bytes": self.delta_wbytes,
                "write_mb": round(w_mb, 3),
                "write_mb_per_sec": round(w_mb / dur, 3),
                "write_iops": round(self.delta_wios / dur, 1),
                "discard_bytes": self.delta_dbytes,
            },
            "host_io": {
                "primary_device": self.primary_device,
                "filesystem_type": self.filesystem_type,
                "host_reads_completed": self.host_reads_completed,
                "host_writes_completed": self.host_writes_completed,
                "host_read_mb": round((self.host_read_sectors * 512) / (1024.0 * 1024.0), 3),
                "host_write_mb": round((self.host_write_sectors * 512) / (1024.0 * 1024.0), 3),
                "host_io_time_ms": round(self.host_io_ms, 2),
                "host_io_utilization_pct": round((self.host_io_ms / (dur * 1000.0)) * 100.0, 2),
                "avg_queue_depth": round(self.avg_queue_depth, 2),
                "avg_await_ms": round(self.avg_await_ms, 2),
            },
            "bottleneck_assessment": {
                "is_storage_bound": self.is_storage_bound,
                "pressure_classification": (
                    self.pressure_classification.value
                    if isinstance(self.pressure_classification, StoragePressureClassification)
                    else str(self.pressure_classification)
                ),
                "classification_reason": self.classification_reason,
            },
            "unreliable_or_missing_metrics": self.unreliable_or_missing_metrics,
        }


class StorageMonitor:
    """Collects storage metrics from cgroup v2 io.stat and host /proc/diskstats."""

    @staticmethod
    def _read_cgroup_io_stat(cg_dir: Path) -> Dict[str, Dict[str, int]]:
        """Parses cgroup v2 io.stat file (major:minor rbytes=X wbytes=Y rios=A wios=B)."""
        res: Dict[str, Dict[str, int]] = {}
        io_file = cg_dir / "io.stat"
        if not io_file.exists():
            return res
        try:
            for line in io_file.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    dev_data: Dict[str, int] = {}
                    for kv in parts[1:]:
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            if v.isdigit():
                                dev_data[k] = int(v)
                    res[dev_id] = dev_data
        except Exception as e:
            logger.debug(f"Failed to read cgroup io.stat: {e}")
        return res

    @staticmethod
    def _read_host_diskstats() -> Tuple[Dict[str, Dict[str, int]], Optional[str]]:
        """Reads /proc/diskstats and identifies the primary storage device."""
        res: Dict[str, Dict[str, int]] = {}
        primary_dev: Optional[str] = None
        stat_file = Path("/proc/diskstats")
        if not stat_file.exists():
            return res, None

        try:
            for line in stat_file.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) >= 14:
                    dev_name = parts[2]
                    # Filter for real block devices (ignore loop, ram, dm)
                    if any(dev_name.startswith(p) for p in ["nvme", "sd", "vd"]):
                        data = {
                            "reads_completed": int(parts[3]),
                            "read_sectors": int(parts[5]),
                            "read_ms": int(parts[6]),
                            "writes_completed": int(parts[7]),
                            "write_sectors": int(parts[9]),
                            "write_ms": int(parts[10]),
                            "io_ms": int(parts[12]),
                            "weighted_io_ms": int(parts[13]),
                        }
                        res[dev_name] = data
                        if not primary_dev or "0n1" in dev_name or dev_name in ("sda", "vda"):
                            primary_dev = dev_name
        except Exception as e:
            logger.debug(f"Failed to read /proc/diskstats: {e}")

        return res, primary_dev

    @staticmethod
    def _detect_filesystem_type() -> Optional[str]:
        """Detects root filesystem type from /proc/mounts."""
        mounts = Path("/proc/mounts")
        if not mounts.exists():
            return None
        try:
            for line in mounts.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "/":
                    return parts[2]
        except Exception:
            pass
        return None

    @classmethod
    def take_snapshot(cls, cg_dir: Optional[Path] = None) -> StorageSnapshot:
        """
        Captures a storage snapshot.
        Enforces explicit unavailable status if cg_dir is None, missing, or inaccessible.
        """
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        unavailable: List[str] = []

        cgroup_io: Dict[str, Dict[str, int]] = {}
        if cg_dir is None:
            unavailable.append("cgroup_io_stat")
        elif not cg_dir.exists():
            unavailable.append("cgroup_io_stat")
        else:
            cgroup_io = cls._read_cgroup_io_stat(cg_dir)
            if not cgroup_io:
                unavailable.append("cgroup_io_stat")

        diskstats, prim_dev = cls._read_host_diskstats()
        if not diskstats:
            unavailable.append("host_diskstats")

        fs_type = cls._detect_filesystem_type()

        return StorageSnapshot(
            timestamp_monotonic=now_mono,
            timestamp_utc=now_utc,
            cgroup_io_stat=cgroup_io,
            host_diskstats=diskstats,
            primary_device=prim_dev,
            filesystem_type=fs_type,
            cgroup_dir=str(cg_dir) if cg_dir else None,
            unavailable_metrics=unavailable,
        )

    @classmethod
    def compute_deltas(
        cls,
        start: StorageSnapshot,
        end: StorageSnapshot,
    ) -> StorageMetricsDelta:
        """
        Computes deltas and evaluates storage bottleneck status using conservative multi-queue metrics.
        """
        dur = max(0.001, end.timestamp_monotonic - start.timestamp_monotonic)

        # 1. Container cgroup I/O deltas
        tot_rbytes = 0
        tot_wbytes = 0
        tot_rios = 0
        tot_wios = 0
        tot_dbytes = 0

        for dev_id, e_stat in end.cgroup_io_stat.items():
            s_stat = start.cgroup_io_stat.get(dev_id, {})
            tot_rbytes += max(0, e_stat.get("rbytes", 0) - s_stat.get("rbytes", 0))
            tot_wbytes += max(0, e_stat.get("wbytes", 0) - s_stat.get("wbytes", 0))
            tot_rios += max(0, e_stat.get("rios", 0) - s_stat.get("rios", 0))
            tot_wios += max(0, e_stat.get("wios", 0) - s_stat.get("wios", 0))
            tot_dbytes += max(0, e_stat.get("dbytes", 0) - s_stat.get("dbytes", 0))

        # 2. Host I/O deltas for primary device
        host_reads = 0
        host_writes = 0
        host_r_sec = 0
        host_w_sec = 0
        host_r_ms = 0.0
        host_w_ms = 0.0
        host_io_ms = 0.0
        host_weighted_ms = 0.0
        prim_dev = end.primary_device or start.primary_device

        if prim_dev and prim_dev in end.host_diskstats:
            e_h = end.host_diskstats[prim_dev]
            s_h = start.host_diskstats.get(prim_dev, {})
            host_reads = max(0, e_h.get("reads_completed", 0) - s_h.get("reads_completed", 0))
            host_writes = max(0, e_h.get("writes_completed", 0) - s_h.get("writes_completed", 0))
            host_r_sec = max(0, e_h.get("read_sectors", 0) - s_h.get("read_sectors", 0))
            host_w_sec = max(0, e_h.get("write_sectors", 0) - s_h.get("write_sectors", 0))
            host_r_ms = max(0.0, float(e_h.get("read_ms", 0) - s_h.get("read_ms", 0)))
            host_w_ms = max(0.0, float(e_h.get("write_ms", 0) - s_h.get("write_ms", 0)))
            host_io_ms = max(0.0, float(e_h.get("io_ms", 0) - s_h.get("io_ms", 0)))
            host_weighted_ms = max(0.0, float(e_h.get("weighted_io_ms", 0) - s_h.get("weighted_io_ms", 0)))

        # 3. Derived multi-queue storage metrics
        total_ops = host_reads + host_writes
        total_op_time_ms = host_r_ms + host_w_ms
        avg_await_ms = (total_op_time_ms / total_ops) if total_ops > 0 else 0.0
        avg_queue_depth = (host_weighted_ms / (dur * 1000.0)) if dur > 0 else 0.0
        io_util_pct = (host_io_ms / (dur * 1000.0)) * 100.0 if dur > 0 else 0.0
        container_write_rate_mb = (tot_wbytes / (1024.0 * 1024.0 * dur)) if dur > 0 else 0.0

        unreliable = sorted(list(set(start.unavailable_metrics + end.unavailable_metrics)))

        # 4. Conservative Classification Rules (Phase 4F.3.2 FIX 06)
        if "host_diskstats" in unreliable or not end.host_diskstats:
            classification = StoragePressureClassification.INSUFFICIENT_STORAGE_EVIDENCE
            is_bound = False
            reason = "Missing host diskstats prevents reliable physical storage bottleneck assessment."
        elif io_util_pct >= 70.0 and avg_queue_depth >= 2.0 and avg_await_ms >= 10.0:
            classification = StoragePressureClassification.STORAGE_PRESSURE_SUPPORTED
            is_bound = True
            reason = (
                f"Sustained storage saturation supported by combined metrics: "
                f"host busy time {io_util_pct:.1f}% >= 70%, avg queue depth {avg_queue_depth:.2f} >= 2.0, "
                f"and avg request latency {avg_await_ms:.2f}ms >= 10.0ms."
            )
        elif container_write_rate_mb > 200.0 and avg_queue_depth >= 2.0:
            classification = StoragePressureClassification.STORAGE_PRESSURE_SUPPORTED
            is_bound = True
            reason = (
                f"Sustained container write saturation supported: "
                f"throughput {container_write_rate_mb:.1f} MB/s > 200 MB/s with queue depth {avg_queue_depth:.2f} >= 2.0."
            )
        elif io_util_pct >= 50.0 or avg_queue_depth >= 1.0 or avg_await_ms >= 15.0:
            classification = StoragePressureClassification.STORAGE_PRESSURE_SUSPECTED
            is_bound = False
            reason = (
                f"Storage pressure suspected but unconfirmed: "
                f"host busy time {io_util_pct:.1f}%, avg queue depth {avg_queue_depth:.2f}, "
                f"avg request latency {avg_await_ms:.2f}ms. Does not meet concurrent saturation criteria."
            )
        else:
            classification = StoragePressureClassification.NO_STORAGE_PRESSURE_OBSERVED
            is_bound = False
            reason = (
                f"No physical storage bottleneck detected: "
                f"host busy time {io_util_pct:.1f}% < 50%, avg queue depth {avg_queue_depth:.2f} < 1.0, "
                f"avg latency {avg_await_ms:.2f}ms. Write activity absorbed by page cache without sustained queues."
            )

        return StorageMetricsDelta(
            duration_seconds=dur,
            delta_rbytes=tot_rbytes,
            delta_wbytes=tot_wbytes,
            delta_rios=tot_rios,
            delta_wios=tot_wios,
            delta_dbytes=tot_dbytes,
            host_reads_completed=host_reads,
            host_writes_completed=host_writes,
            host_read_sectors=host_r_sec,
            host_write_sectors=host_w_sec,
            host_read_ms=host_r_ms,
            host_write_ms=host_w_ms,
            host_io_ms=host_io_ms,
            host_weighted_io_ms=host_weighted_ms,
            avg_queue_depth=avg_queue_depth,
            avg_await_ms=avg_await_ms,
            primary_device=prim_dev,
            filesystem_type=end.filesystem_type,
            is_storage_bound=is_bound,
            pressure_classification=classification,
            classification_reason=reason,
            unreliable_or_missing_metrics=unreliable,
        )
