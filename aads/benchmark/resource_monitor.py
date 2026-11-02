"""
Active Container Resource and CFS Throttling Monitor.
Continuous background sampler for CPU, memory, and cgroup v2 metrics during real benchmark execution.

Collects:
- Container CPU utilization (derived from cgroup v2 usage_usec delta)
- Host CPU utilization (derived from /proc/stat delta)
- Cumulative container CPU usage (usage_usec)
- CPU quota and period (cpu.max)
- cgroup v2 nr_throttled and throttled_usec (cpu.stat)
- Container memory usage (memory.current) and limit (memory.max)
- Monotonic timestamps and sample jitter tracking
"""
import csv
import json
import logging
import math
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class ResourceSample:
    """A single point-in-time resource measurement during benchmark execution."""

    def __init__(
        self,
        sample_index: int,
        timestamp_monotonic: float,
        timestamp_utc: str,
        execution_id: str,
        experiment_id: str,
        container_name: str,
        container_id: Optional[str] = None,
        container_cpu_pct: Optional[float] = None,
        host_cpu_pct: Optional[float] = None,
        cumulative_cpu_usage_usec: Optional[int] = None,
        cpu_quota_usec: Optional[int] = None,
        cpu_period_usec: Optional[int] = None,
        cgroup_nr_throttled: Optional[int] = None,
        cgroup_throttled_usec: Optional[int] = None,
        cgroup_nr_periods: Optional[int] = None,
        memory_usage_bytes: Optional[int] = None,
        memory_limit_bytes: Optional[int] = None,
        memory_usage_mb: Optional[float] = None,
        memory_limit_mb: Optional[float] = None,
        memory_pct: Optional[float] = None,
        sampler_error: Optional[str] = None,
    ):
        self.sample_index = sample_index
        self.timestamp_monotonic = timestamp_monotonic
        self.timestamp_utc = timestamp_utc
        self.execution_id = execution_id
        self.experiment_id = experiment_id
        self.container_name = container_name
        self.container_id = container_id
        self.container_cpu_pct = container_cpu_pct
        self.host_cpu_pct = host_cpu_pct
        self.cumulative_cpu_usage_usec = cumulative_cpu_usage_usec
        self.cpu_quota_usec = cpu_quota_usec
        self.cpu_period_usec = cpu_period_usec
        self.cgroup_nr_throttled = cgroup_nr_throttled
        self.cgroup_throttled_usec = cgroup_throttled_usec
        self.cgroup_nr_periods = cgroup_nr_periods
        self.memory_usage_bytes = memory_usage_bytes
        self.memory_limit_bytes = memory_limit_bytes
        self.memory_usage_mb = memory_usage_mb
        self.memory_limit_mb = memory_limit_mb
        self.memory_pct = memory_pct
        self.sampler_error = sampler_error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_index": self.sample_index,
            "timestamp_monotonic": round(self.timestamp_monotonic, 6),
            "timestamp_utc": self.timestamp_utc,
            "execution_id": self.execution_id,
            "experiment_id": self.experiment_id,
            "container_name": self.container_name,
            "container_id": self.container_id,
            "container_cpu_pct": round(self.container_cpu_pct, 2) if self.container_cpu_pct is not None else None,
            "host_cpu_pct": round(self.host_cpu_pct, 2) if self.host_cpu_pct is not None else None,
            "cumulative_cpu_usage_usec": self.cumulative_cpu_usage_usec,
            "cpu_quota_usec": self.cpu_quota_usec,
            "cpu_period_usec": self.cpu_period_usec,
            "cgroup_nr_throttled": self.cgroup_nr_throttled,
            "cgroup_throttled_usec": self.cgroup_throttled_usec,
            "cgroup_nr_periods": self.cgroup_nr_periods,
            "memory_usage_bytes": self.memory_usage_bytes,
            "memory_limit_bytes": self.memory_limit_bytes,
            "memory_usage_mb": round(self.memory_usage_mb, 2) if self.memory_usage_mb is not None else None,
            "memory_limit_mb": round(self.memory_limit_mb, 2) if self.memory_limit_mb is not None else None,
            "memory_pct": round(self.memory_pct, 2) if self.memory_pct is not None else None,
            "sampler_error": self.sampler_error,
        }


class CgroupSnapshot:
    """Exact point-in-time snapshot of cgroup counters (e.g. start/end of trial)."""

    def __init__(
        self,
        timestamp_monotonic: float,
        timestamp_utc: str,
        usage_usec: Optional[int] = None,
        user_usec: Optional[int] = None,
        system_usec: Optional[int] = None,
        nr_periods: Optional[int] = None,
        nr_throttled: Optional[int] = None,
        throttled_usec: Optional[int] = None,
        quota_usec: Optional[int] = None,
        period_usec: Optional[int] = None,
        memory_current_bytes: Optional[int] = None,
        memory_max_bytes: Optional[int] = None,
    ):
        self.timestamp_monotonic = timestamp_monotonic
        self.timestamp_utc = timestamp_utc
        self.usage_usec = usage_usec
        self.user_usec = user_usec
        self.system_usec = system_usec
        self.nr_periods = nr_periods
        self.nr_throttled = nr_throttled
        self.throttled_usec = throttled_usec
        self.quota_usec = quota_usec
        self.period_usec = period_usec
        self.memory_current_bytes = memory_current_bytes
        self.memory_max_bytes = memory_max_bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp_monotonic": round(self.timestamp_monotonic, 6),
            "timestamp_utc": self.timestamp_utc,
            "usage_usec": self.usage_usec,
            "user_usec": self.user_usec,
            "system_usec": self.system_usec,
            "nr_periods": self.nr_periods,
            "nr_throttled": self.nr_throttled,
            "throttled_usec": self.throttled_usec,
            "quota_usec": self.quota_usec,
            "period_usec": self.period_usec,
            "memory_current_bytes": self.memory_current_bytes,
            "memory_max_bytes": self.memory_max_bytes,
        }


class TrialMonitoringSummary:
    """Aggregated monitoring metrics and cgroup deltas for a single trial."""

    def __init__(
        self,
        experiment_id: str,
        execution_id: str,
        container_name: str,
        duration_seconds: float,
        sample_count: int,
        missed_samples: int,
        target_interval_sec: float,
        actual_mean_interval_ms: Optional[float] = None,
        actual_interval_std_ms: Optional[float] = None,
        cpu_time_consumed_seconds: Optional[float] = None,
        throttling_events_count: Optional[int] = None,
        throttled_time_seconds: Optional[float] = None,
        throttling_event_rate_per_sec: Optional[float] = None,
        cpu_quota_utilization_pct: Optional[float] = None,
        mean_container_cpu_pct: Optional[float] = None,
        peak_container_cpu_pct: Optional[float] = None,
        mean_host_cpu_pct: Optional[float] = None,
        peak_host_cpu_pct: Optional[float] = None,
        mean_memory_mb: Optional[float] = None,
        peak_memory_mb: Optional[float] = None,
        memory_limit_mb: Optional[float] = None,
        peak_memory_pct: Optional[float] = None,
        start_snapshot: Optional[Dict[str, Any]] = None,
        end_snapshot: Optional[Dict[str, Any]] = None,
        unreliable_or_missing_metrics: Optional[List[str]] = None,
    ):
        self.experiment_id = experiment_id
        self.execution_id = execution_id
        self.container_name = container_name
        self.duration_seconds = duration_seconds
        self.sample_count = sample_count
        self.missed_samples = missed_samples
        self.target_interval_sec = target_interval_sec
        self.actual_mean_interval_ms = actual_mean_interval_ms
        self.actual_interval_std_ms = actual_interval_std_ms
        self.cpu_time_consumed_seconds = cpu_time_consumed_seconds
        self.throttling_events_count = throttling_events_count
        self.throttled_time_seconds = throttled_time_seconds
        self.throttling_event_rate_per_sec = throttling_event_rate_per_sec
        self.cpu_quota_utilization_pct = cpu_quota_utilization_pct
        self.mean_container_cpu_pct = mean_container_cpu_pct
        self.peak_container_cpu_pct = peak_container_cpu_pct
        self.mean_host_cpu_pct = mean_host_cpu_pct
        self.peak_host_cpu_pct = peak_host_cpu_pct
        self.mean_memory_mb = mean_memory_mb
        self.peak_memory_mb = peak_memory_mb
        self.memory_limit_mb = memory_limit_mb
        self.peak_memory_pct = peak_memory_pct
        self.start_snapshot = start_snapshot
        self.end_snapshot = end_snapshot
        self.unreliable_or_missing_metrics = unreliable_or_missing_metrics or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "execution_id": self.execution_id,
            "container_name": self.container_name,
            "duration_seconds": round(self.duration_seconds, 3),
            "sample_count": self.sample_count,
            "missed_samples": self.missed_samples,
            "target_interval_sec": self.target_interval_sec,
            "actual_mean_interval_ms": round(self.actual_mean_interval_ms, 2) if self.actual_mean_interval_ms is not None else None,
            "actual_interval_std_ms": round(self.actual_interval_std_ms, 2) if self.actual_interval_std_ms is not None else None,
            "cpu_time_consumed_seconds": round(self.cpu_time_consumed_seconds, 6) if self.cpu_time_consumed_seconds is not None else None,
            "throttling_events_count": self.throttling_events_count,
            "throttled_time_seconds": round(self.throttled_time_seconds, 6) if self.throttled_time_seconds is not None else None,
            "throttling_event_rate_per_sec": round(self.throttling_event_rate_per_sec, 2) if self.throttling_event_rate_per_sec is not None else None,
            "cpu_quota_utilization_pct": round(self.cpu_quota_utilization_pct, 2) if self.cpu_quota_utilization_pct is not None else None,
            "mean_container_cpu_pct": round(self.mean_container_cpu_pct, 2) if self.mean_container_cpu_pct is not None else None,
            "peak_container_cpu_pct": round(self.peak_container_cpu_pct, 2) if self.peak_container_cpu_pct is not None else None,
            "mean_host_cpu_pct": round(self.mean_host_cpu_pct, 2) if self.mean_host_cpu_pct is not None else None,
            "peak_host_cpu_pct": round(self.peak_host_cpu_pct, 2) if self.peak_host_cpu_pct is not None else None,
            "mean_memory_mb": round(self.mean_memory_mb, 2) if self.mean_memory_mb is not None else None,
            "peak_memory_mb": round(self.peak_memory_mb, 2) if self.peak_memory_mb is not None else None,
            "memory_limit_mb": round(self.memory_limit_mb, 2) if self.memory_limit_mb is not None else None,
            "peak_memory_pct": round(self.peak_memory_pct, 2) if self.peak_memory_pct is not None else None,
            "start_snapshot": self.start_snapshot,
            "end_snapshot": self.end_snapshot,
            "unreliable_or_missing_metrics": self.unreliable_or_missing_metrics,
        }


class ContainerResourceMonitor:
    """
    Active continuous resource and throttling monitor for Docker containers.
    Samples cgroup v2 and host metrics every ~500ms using monotonic timing.
    Fails open on missing metrics without interrupting or blocking benchmark execution.
    """

    def __init__(
        self,
        container_name: str,
        interval_sec: float = 0.5,
        execution_id: str = "",
        experiment_id: str = "",
        cgroup_dir: Optional[Union[str, Path]] = None,
        cgroup_root: Path = Path("/sys/fs/cgroup"),
    ):
        self.container_name = container_name
        self.interval_sec = interval_sec
        self.execution_id = execution_id
        self.experiment_id = experiment_id
        self.cgroup_root = Path(cgroup_root)

        # Allow passing an explicit cgroup_dir (e.g. for testing with tmp fixtures)
        self._cgroup_dir: Optional[Path] = Path(cgroup_dir) if cgroup_dir else None
        self._container_id: Optional[str] = None

        self.samples: List[ResourceSample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._start_snapshot: Optional[CgroupSnapshot] = None
        self._end_snapshot: Optional[CgroupSnapshot] = None
        self._last_summary: Optional[TrialMonitoringSummary] = None
        self._start_time_monotonic: float = 0.0
        self._end_time_monotonic: float = 0.0

        # State tracking for delta computation
        self._last_container_usage_usec: Optional[int] = None
        self._last_container_sample_time: Optional[float] = None
        self._last_host_ticks: Optional[Tuple[int, int]] = None  # (active, total)
        self._last_host_sample_time: Optional[float] = None
        self._missed_samples: int = 0
        self._sampler_errors: List[str] = []

    def resolve_cgroup_dir(self) -> Optional[Path]:
        """
        Locates the unified cgroup v2 directory for the target container.
        Supports systemd scope paths, cgroupfs paths, and PID-based cgroup lookups.
        """
        if self._cgroup_dir and self._cgroup_dir.exists():
            return self._cgroup_dir

        # 1. Try to query container ID via docker inspect
        full_id = self._container_id
        pid: Optional[int] = None
        if not full_id:
            try:
                res = subprocess.run(
                    ["docker", "inspect", "-f", "{{.Id}} {{.State.Pid}}", self.container_name],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split()
                    full_id = parts[0]
                    self._container_id = full_id
                    if len(parts) > 1 and parts[1].isdigit():
                        pid = int(parts[1])
            except Exception as e:
                logger.debug(f"Failed to inspect container {self.container_name}: {e}")

        # 2. Check systemd slice scope (standard Docker on cgroup v2)
        if full_id:
            candidate1 = self.cgroup_root / "system.slice" / f"docker-{full_id}.scope"
            if candidate1.exists():
                self._cgroup_dir = candidate1
                return self._cgroup_dir

            # 3. Check cgroupfs path
            candidate2 = self.cgroup_root / "docker" / full_id
            if candidate2.exists():
                self._cgroup_dir = candidate2
                return self._cgroup_dir

        # 4. Check PID cgroup path from /proc/<pid>/cgroup
        if pid and pid > 0:
            proc_cgroup = Path(f"/proc/{pid}/cgroup")
            if proc_cgroup.exists():
                try:
                    for line in proc_cgroup.read_text().splitlines():
                        # cgroup v2 lines look like "0::<path>"
                        parts = line.strip().split("::", 1)
                        if len(parts) == 2 and parts[1]:
                            cg_subpath = parts[1].lstrip("/")
                            candidate3 = self.cgroup_root / cg_subpath
                            if candidate3.exists():
                                self._cgroup_dir = candidate3
                                return self._cgroup_dir
                except Exception as e:
                    logger.debug(f"Failed to read {proc_cgroup}: {e}")

        return None

    def _read_cgroup_cpu_stat(self, cg_dir: Path) -> Dict[str, int]:
        """Reads and parses cgroup v2 cpu.stat file."""
        stat_file = cg_dir / "cpu.stat"
        res: Dict[str, int] = {}
        if not stat_file.exists():
            return res
        try:
            for line in stat_file.read_text().splitlines():
                parts = line.strip().split()
                if len(parts) == 2 and parts[1].isdigit():
                    res[parts[0]] = int(parts[1])
        except Exception as e:
            self._sampler_errors.append(f"cpu.stat read error: {e}")
        return res

    def _read_cgroup_cpu_max(self, cg_dir: Path) -> Tuple[Optional[int], Optional[int]]:
        """Reads quota and period from cgroup v2 cpu.max file."""
        max_file = cg_dir / "cpu.max"
        if not max_file.exists():
            return None, None
        try:
            parts = max_file.read_text().strip().split()
            quota = int(parts[0]) if len(parts) > 0 and parts[0] != "max" else None
            period = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            return quota, period
        except Exception as e:
            self._sampler_errors.append(f"cpu.max read error: {e}")
            return None, None

    def _read_cgroup_memory(self, cg_dir: Path) -> Tuple[Optional[int], Optional[int]]:
        """Reads current memory usage and max memory limit from cgroup v2."""
        cur_file = cg_dir / "memory.current"
        max_file = cg_dir / "memory.max"
        usage: Optional[int] = None
        limit: Optional[int] = None

        if cur_file.exists():
            try:
                val = cur_file.read_text().strip()
                if val.isdigit():
                    usage = int(val)
            except Exception as e:
                self._sampler_errors.append(f"memory.current read error: {e}")

        if max_file.exists():
            try:
                val = max_file.read_text().strip()
                if val.isdigit():
                    limit = int(val)
                elif val == "max":
                    limit = None
            except Exception as e:
                self._sampler_errors.append(f"memory.max read error: {e}")

        return usage, limit

    def _read_host_cpu_ticks(self) -> Optional[Tuple[int, int]]:
        """Reads host CPU ticks (active, total) from /proc/stat."""
        stat_file = Path("/proc/stat")
        if not stat_file.exists():
            return None
        try:
            with open(stat_file, "r") as f:
                first_line = f.readline()
            parts = first_line.strip().split()
            if parts and parts[0] == "cpu" and len(parts) >= 5:
                # user, nice, system, idle, iowait, irq, softirq, steal
                vals = [int(v) for v in parts[1:] if v.isdigit()]
                total = sum(vals)
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                active = total - idle
                return active, total
        except Exception as e:
            self._sampler_errors.append(f"/proc/stat read error: {e}")
        return None

    def take_cgroup_snapshot(self) -> CgroupSnapshot:
        """Captures an exact snapshot of cgroup counters."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cg_dir = self.resolve_cgroup_dir()

        if not cg_dir:
            return CgroupSnapshot(
                timestamp_monotonic=now_mono,
                timestamp_utc=now_utc,
            )

        cpu_stats = self._read_cgroup_cpu_stat(cg_dir)
        quota, period = self._read_cgroup_cpu_max(cg_dir)
        mem_usage, mem_max = self._read_cgroup_memory(cg_dir)

        return CgroupSnapshot(
            timestamp_monotonic=now_mono,
            timestamp_utc=now_utc,
            usage_usec=cpu_stats.get("usage_usec"),
            user_usec=cpu_stats.get("user_usec"),
            system_usec=cpu_stats.get("system_usec"),
            nr_periods=cpu_stats.get("nr_periods"),
            nr_throttled=cpu_stats.get("nr_throttled"),
            throttled_usec=cpu_stats.get("throttled_usec"),
            quota_usec=quota,
            period_usec=period,
            memory_current_bytes=mem_usage,
            memory_max_bytes=mem_max,
        )

    def _collect_sample(self, sample_idx: int) -> ResourceSample:
        """Collects a single periodic sample."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()
        cg_dir = self.resolve_cgroup_dir()
        sampler_err: Optional[str] = None

        container_cpu_pct: Optional[float] = None
        host_cpu_pct: Optional[float] = None
        cum_cpu: Optional[int] = None
        quota: Optional[int] = None
        period: Optional[int] = None
        nr_throttled: Optional[int] = None
        throttled_usec: Optional[int] = None
        nr_periods: Optional[int] = None
        mem_bytes: Optional[int] = None
        mem_limit_bytes: Optional[int] = None
        mem_mb: Optional[float] = None
        mem_limit_mb: Optional[float] = None
        mem_pct: Optional[float] = None

        # 1. Cgroup CPU and Memory
        if cg_dir:
            cpu_stats = self._read_cgroup_cpu_stat(cg_dir)
            quota, period = self._read_cgroup_cpu_max(cg_dir)

            # For fine-grained sampling (<50ms), downsample memory reads to reduce file I/O overhead
            should_sample_mem = (self.interval_sec >= 0.050) or (sample_idx % max(1, int(0.100 / self.interval_sec)) == 0)
            if should_sample_mem or not self.samples:
                mem_bytes, mem_limit_bytes = self._read_cgroup_memory(cg_dir)
            elif self.samples:
                mem_bytes = self.samples[-1].memory_usage_bytes
                mem_limit_bytes = self.samples[-1].memory_limit_bytes

            cum_cpu = cpu_stats.get("usage_usec")
            nr_throttled = cpu_stats.get("nr_throttled")
            throttled_usec = cpu_stats.get("throttled_usec")
            nr_periods = cpu_stats.get("nr_periods")

            # Calculate container CPU utilization % from delta
            if cum_cpu is not None and self._last_container_usage_usec is not None:
                delta_usec = cum_cpu - self._last_container_usage_usec
                delta_t = now_mono - (self._last_container_sample_time or now_mono)
                if delta_t > 0:
                    # CPU utilization relative to 1 core (100% = 1.0 core fully loaded)
                    container_cpu_pct = (delta_usec / (delta_t * 1_000_000.0)) * 100.0
                    container_cpu_pct = max(0.0, container_cpu_pct)

            self._last_container_usage_usec = cum_cpu
            self._last_container_sample_time = now_mono

            # Memory metrics
            if mem_bytes is not None:
                mem_mb = mem_bytes / (1024.0 * 1024.0)
            if mem_limit_bytes is not None:
                mem_limit_mb = mem_limit_bytes / (1024.0 * 1024.0)
            if mem_bytes is not None and mem_limit_bytes and mem_limit_bytes > 0:
                mem_pct = (mem_bytes / mem_limit_bytes) * 100.0
        else:
            sampler_err = "cgroup directory unavailable"

        # 2. Host CPU from /proc/stat (downsample if interval < 50ms)
        should_sample_host = (self.interval_sec >= 0.050) or (sample_idx % max(1, int(0.100 / self.interval_sec)) == 0)
        if should_sample_host or not self.samples:
            host_ticks = self._read_host_cpu_ticks()
            if host_ticks and self._last_host_ticks:
                act_delta = host_ticks[0] - self._last_host_ticks[0]
                tot_delta = host_ticks[1] - self._last_host_ticks[1]
                if tot_delta > 0:
                    host_cpu_pct = (act_delta / tot_delta) * 100.0
                    host_cpu_pct = max(0.0, min(100.0, host_cpu_pct))

            self._last_host_ticks = host_ticks
            self._last_host_sample_time = now_mono
        elif self.samples:
            host_cpu_pct = self.samples[-1].host_cpu_pct

        return ResourceSample(
            sample_index=sample_idx,
            timestamp_monotonic=now_mono,
            timestamp_utc=now_utc,
            execution_id=self.execution_id,
            experiment_id=self.experiment_id,
            container_name=self.container_name,
            container_id=self._container_id,
            container_cpu_pct=container_cpu_pct,
            host_cpu_pct=host_cpu_pct,
            cumulative_cpu_usage_usec=cum_cpu,
            cpu_quota_usec=quota,
            cpu_period_usec=period,
            cgroup_nr_throttled=nr_throttled,
            cgroup_throttled_usec=throttled_usec,
            cgroup_nr_periods=nr_periods,
            memory_usage_bytes=mem_bytes,
            memory_limit_bytes=mem_limit_bytes,
            memory_usage_mb=mem_mb,
            memory_limit_mb=mem_limit_mb,
            memory_pct=mem_pct,
            sampler_error=sampler_err,
        )

    def _sampling_loop(self) -> None:
        """Continuous sampling loop executed on a daemon thread."""
        idx = 0
        last_tick = time.monotonic()

        while not self._stop_event.is_set():
            sample = self._collect_sample(idx)
            self.samples.append(sample)
            idx += 1

            # Check for missed samples or excessive jitter
            now = time.monotonic()
            elapsed_since_tick = now - last_tick
            if elapsed_since_tick > (self.interval_sec * 1.5) and idx > 1:
                missed = int(elapsed_since_tick // self.interval_sec) - 1
                if missed > 0:
                    self._missed_samples += missed
            last_tick = now

            # Jitter-free sleep using Event.wait
            self._stop_event.wait(self.interval_sec)

    def start(self) -> None:
        """Captures initial baseline snapshot and launches active sampling thread."""
        self._start_time_monotonic = time.monotonic()
        self._start_snapshot = self.take_cgroup_snapshot()
        self._last_container_usage_usec = self._start_snapshot.usage_usec
        self._last_container_sample_time = self._start_snapshot.timestamp_monotonic
        self._last_host_ticks = self._read_host_cpu_ticks()
        self._last_host_sample_time = self._start_time_monotonic

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._sampling_loop,
            name=f"ResourceMonitor-{self.container_name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> Tuple[List[ResourceSample], TrialMonitoringSummary]:
        """Stops sampling thread, captures final snapshot, and calculates summary metrics."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        self._end_time_monotonic = time.monotonic()
        self._end_snapshot = self.take_cgroup_snapshot()

        duration = max(0.001, self._end_time_monotonic - self._start_time_monotonic)

        # 1. Delta Calculations from Start/End Snapshots
        cpu_time_consumed: Optional[float] = None
        throttling_events: Optional[int] = None
        throttled_time_sec: Optional[float] = None
        throttling_rate: Optional[float] = None
        quota_util_pct: Optional[float] = None
        unreliable_metrics: List[str] = []

        start = self._start_snapshot
        end = self._end_snapshot

        if start and end and start.usage_usec is not None and end.usage_usec is not None:
            delta_usage = max(0, end.usage_usec - start.usage_usec)
            cpu_time_consumed = delta_usage / 1_000_000.0

            # Quota utilization % = delta_usage / (duration * (quota / period))
            quota = end.quota_usec or (100000 if end.period_usec else None)
            period = end.period_usec or 100000
            if quota and period and period > 0:
                quota_cores = quota / float(period)
                quota_util_pct = (delta_usage / (duration * 1_000_000.0 * quota_cores)) * 100.0
            else:
                unreliable_metrics.append("cpu_quota_utilization (unlimited quota)")
        else:
            unreliable_metrics.append("cgroup_cpu_usage")

        if start and end and start.nr_throttled is not None and end.nr_throttled is not None:
            throttling_events = max(0, end.nr_throttled - start.nr_throttled)
            throttling_rate = throttling_events / duration
        else:
            unreliable_metrics.append("nr_throttled")

        if start and end and start.throttled_usec is not None and end.throttled_usec is not None:
            throttled_time_sec = max(0, end.throttled_usec - start.throttled_usec) / 1_000_000.0
        else:
            unreliable_metrics.append("throttled_usec")

        # 2. Time-series statistics from samples
        container_cpus = [s.container_cpu_pct for s in self.samples if s.container_cpu_pct is not None]
        host_cpus = [s.host_cpu_pct for s in self.samples if s.host_cpu_pct is not None]
        mems = [s.memory_usage_mb for s in self.samples if s.memory_usage_mb is not None]
        mem_pcts = [s.memory_pct for s in self.samples if s.memory_pct is not None]

        mean_container_cpu = float(sum(container_cpus) / len(container_cpus)) if container_cpus else None
        peak_container_cpu = float(max(container_cpus)) if container_cpus else None

        mean_host_cpu = float(sum(host_cpus) / len(host_cpus)) if host_cpus else None
        peak_host_cpu = float(max(host_cpus)) if host_cpus else None

        mean_mem = float(sum(mems) / len(mems)) if mems else None
        peak_mem = float(max(mems)) if mems else None
        peak_mem_pct = float(max(mem_pcts)) if mem_pcts else None

        mem_limit_mb = (end.memory_max_bytes / (1024.0 * 1024.0)) if end and end.memory_max_bytes else None

        # Sample interval statistics
        mean_int_ms: Optional[float] = None
        std_int_ms: Optional[float] = None
        if len(self.samples) > 1:
            diffs_ms = [
                (self.samples[i].timestamp_monotonic - self.samples[i - 1].timestamp_monotonic) * 1000.0
                for i in range(1, len(self.samples))
            ]
            mean_int_ms = sum(diffs_ms) / len(diffs_ms)
            std_int_ms = math.sqrt(sum((x - mean_int_ms) ** 2 for x in diffs_ms) / len(diffs_ms))

        summary = TrialMonitoringSummary(
            experiment_id=self.experiment_id,
            execution_id=self.execution_id,
            container_name=self.container_name,
            duration_seconds=duration,
            sample_count=len(self.samples),
            missed_samples=self._missed_samples,
            target_interval_sec=self.interval_sec,
            actual_mean_interval_ms=mean_int_ms,
            actual_interval_std_ms=std_int_ms,
            cpu_time_consumed_seconds=cpu_time_consumed,
            throttling_events_count=throttling_events,
            throttled_time_seconds=throttled_time_sec,
            throttling_event_rate_per_sec=throttling_rate,
            cpu_quota_utilization_pct=quota_util_pct,
            mean_container_cpu_pct=mean_container_cpu,
            peak_container_cpu_pct=peak_container_cpu,
            mean_host_cpu_pct=mean_host_cpu,
            peak_host_cpu_pct=peak_host_cpu,
            mean_memory_mb=mean_mem,
            peak_memory_mb=peak_mem,
            memory_limit_mb=mem_limit_mb,
            peak_memory_pct=peak_mem_pct,
            start_snapshot=start.to_dict() if start else None,
            end_snapshot=end.to_dict() if end else None,
            unreliable_or_missing_metrics=unreliable_metrics,
        )
        self._last_summary = summary

        return self.samples, summary

    def save_artifacts(self, directory: Union[str, Path], trial_prefix: str) -> Dict[str, str]:
        """
        Saves raw monitoring samples (JSON and CSV) and per-trial summary (JSON).
        Returns a dict of saved file paths.
        """
        out_dir = Path(directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        samples_json_path = out_dir / f"monitoring_samples_{trial_prefix}.json"
        samples_csv_path = out_dir / f"monitoring_samples_{trial_prefix}.csv"
        summary_json_path = out_dir / f"monitoring_summary_{trial_prefix}.json"

        # 1. Samples JSON
        samples_data = [s.to_dict() for s in self.samples]
        samples_json_path.write_text(json.dumps(samples_data, indent=2))

        # 2. Samples CSV
        if self.samples:
            fieldnames = list(self.samples[0].to_dict().keys())
            with open(samples_csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for s in self.samples:
                    writer.writerow(s.to_dict())

        # 3. Summary JSON
        summary = self._last_summary
        if summary is None and self._end_snapshot:
            _, summary = self.stop()

        if summary:
            summary_json_path.write_text(json.dumps(summary.to_dict(), indent=2))

        return {
            "samples_json": str(samples_json_path),
            "samples_csv": str(samples_csv_path),
            "summary_json": str(summary_json_path),
        }

    @staticmethod
    def correlate_latency_spikes(
        latencies_ms: List[float],
        timestamps_epoch_sec: List[float],
        samples: List[ResourceSample],
        spike_threshold_ms: float = 10.0,
        client_ids: Optional[List[int]] = None,
        has_controlled_confirmation: bool = False,
    ) -> Dict[str, Any]:
        """
        Correlates transaction latency spikes (e.g. >= 10 ms) with resource monitoring samples
        and cgroup throttling events based on physical timestamps.
        Integrates with CFSCorrelationAnalyzer for multi-client cluster detection and rigorous evidence classification.
        """
        if not latencies_ms or not timestamps_epoch_sec or len(latencies_ms) != len(timestamps_epoch_sec):
            return {
                "total_transactions": len(latencies_ms),
                "spike_count": 0,
                "correlation_evidence": "Insufficient transaction timestamps for correlation",
                "association_level": "NO_DETECTABLE_ASSOCIATION",
            }

        spikes = [
            (t, lat)
            for t, lat in zip(timestamps_epoch_sec, latencies_ms)
            if lat >= spike_threshold_ms
        ]

        if not spikes:
            return {
                "total_transactions": len(latencies_ms),
                "spike_count": 0,
                "correlation_evidence": "No latency spikes exceeding threshold were observed.",
                "association_level": "NO_DETECTABLE_ASSOCIATION",
            }

        # Filter samples that occurred within trial window
        throttled_samples = [s for s in samples if s.cgroup_nr_throttled and s.cgroup_nr_throttled > 0]

        # Calculate time distribution of spikes
        spike_times = [s[0] for s in spikes]
        inter_spike_intervals_ms = [
            (spike_times[i] - spike_times[i - 1]) * 1000.0
            for i in range(1, len(spike_times))
        ]

        median_spike_int_ms = (
            float(sorted(inter_spike_intervals_ms)[len(inter_spike_intervals_ms) // 2])
            if inter_spike_intervals_ms
            else 0.0
        )

        within_100ms_window = (
            sum(1 for x in inter_spike_intervals_ms if 90.0 <= x <= 110.0) / len(inter_spike_intervals_ms) * 100.0
            if inter_spike_intervals_ms
            else 0.0
        )

        # Classification based on temporal alignment
        if within_100ms_window >= 90.0 and len(throttled_samples) > 0:
            assoc = "CONTROLLED_CAUSAL_EVIDENCE" if has_controlled_confirmation else "STRONG_TEMPORAL_ASSOCIATION"
        elif within_100ms_window >= 50.0 or len(throttled_samples) > 0:
            assoc = "TEMPORAL_ASSOCIATION"
        else:
            assoc = "NO_DETECTABLE_ASSOCIATION"

        return {
            "total_transactions": len(latencies_ms),
            "spike_threshold_ms": spike_threshold_ms,
            "spike_count": len(spikes),
            "spike_percentage": round((len(spikes) / len(latencies_ms)) * 100.0, 3),
            "median_inter_spike_interval_ms": round(median_spike_int_ms, 2),
            "pct_spikes_matching_100ms_cfs_period": round(within_100ms_window, 1),
            "throttling_samples_detected": len(throttled_samples),
            "evidence_supported": within_100ms_window >= 90.0 and len(throttled_samples) > 0,
            "association_level": assoc,
        }
