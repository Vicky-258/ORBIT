"""
Phase 4F.4 — Final 12-Trial Execution Engine & Manifest Orchestrator.

Implements the frozen 12-trial empirical campaign comparing PostgreSQL 16 performance
under 1.0 vCPU vs 2.0 vCPU quotas across read_only_select and balanced_oltp_tpcb workloads.

Strict methodology & safety invariants:
- Frozen deterministic randomized sequence (seed 4104)
- Strong authorization binding with validated CampaignAuthorizationRecord (FIX 01)
- Actual benchmark client process cgroup isolation verification (FIX 02)
- Strict metric provenance without fabricated fallbacks and tx log count reconciliation (FIX 03)
- Effective resource and image verification before warm-up (FIX 04)
- Complete lifecycle cleanup across monitors, samplers, and containers (FIX 05)
- Durable failure evidence and incremental campaign state persistence (FIX 06)
- Strict campaign completion validation (FIX 07)
"""
import json
import logging
import math
import os
import platform
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field

from aads.benchmark.cfs_correlation import (
    CFSAssociationLevel,
    CFSCorrelationAnalyzer,
    TransactionRecord,
)
from aads.benchmark.docker_runner import PgbenchOutputParser
from aads.benchmark.postgres_instrumentation import (
    PostgresMetricsCollector,
    PostgresMetricsDelta,
    PostgresPeriodicSampler,
    PostgresSnapshot,
)
from aads.benchmark.resource_monitor import ContainerResourceMonitor
from aads.benchmark.storage_monitor import (
    StorageMetricsDelta,
    StorageMonitor,
    StorageSnapshot,
)
from aads.benchmark.trial_isolation import (
    DatabaseStateSnapshot,
    TrialIsolationError,
    TrialIsolationManager,
)
from aads.benchmark.workload_profiles import resolve_workload_profile, WorkloadProfile

logger = logging.getLogger(__name__)

EXPECTED_MANIFEST_SHA256 = "69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6"
EXPECTED_EXECUTION_SCOPE = "PHASE_4F4_12_TRIAL_EMPIRICAL_CAMPAIGN"
EXPECTED_PHASE = "4F.4"

# Frozen randomized sequence with seed 4104 (Section 4 of Manifest)
FROZEN_12_TRIAL_SCHEDULE: List[Dict[str, Any]] = [
    {"seq": 1, "trial_id": "ro_2cpu_r1", "profile": "read_only_select", "cpu_limit": "2.0", "rep": 1},
    {"seq": 2, "trial_id": "ro_1cpu_r1", "profile": "read_only_select", "cpu_limit": "1.0", "rep": 1},
    {"seq": 3, "trial_id": "tpcb_2cpu_r1", "profile": "balanced_oltp_tpcb", "cpu_limit": "2.0", "rep": 1},
    {"seq": 4, "trial_id": "ro_2cpu_r2", "profile": "read_only_select", "cpu_limit": "2.0", "rep": 2},
    {"seq": 5, "trial_id": "tpcb_2cpu_r2", "profile": "balanced_oltp_tpcb", "cpu_limit": "2.0", "rep": 2},
    {"seq": 6, "trial_id": "tpcb_1cpu_r1", "profile": "balanced_oltp_tpcb", "cpu_limit": "1.0", "rep": 1},
    {"seq": 7, "trial_id": "ro_2cpu_r3", "profile": "read_only_select", "cpu_limit": "2.0", "rep": 3},
    {"seq": 8, "trial_id": "ro_1cpu_r3", "profile": "read_only_select", "cpu_limit": "1.0", "rep": 3},
    {"seq": 9, "trial_id": "tpcb_1cpu_r3", "profile": "balanced_oltp_tpcb", "cpu_limit": "1.0", "rep": 3},
    {"seq": 10, "trial_id": "tpcb_1cpu_r2", "profile": "balanced_oltp_tpcb", "cpu_limit": "1.0", "rep": 2},
    {"seq": 11, "trial_id": "ro_1cpu_r2", "profile": "read_only_select", "cpu_limit": "1.0", "rep": 2},
    {"seq": 12, "trial_id": "tpcb_2cpu_r3", "profile": "balanced_oltp_tpcb", "cpu_limit": "2.0", "rep": 3},
]


class CampaignAuthorizationRecord(BaseModel):
    """
    Strong authorization record for Phase 4F.4 empirical execution.
    Enforces atomic, single-use binding to manifest, proposal, phase, scope, and operator.
    """
    phase: str = Field(default=EXPECTED_PHASE)
    proposal_id: str
    authorization_id: str
    manifest_sha256: str
    execution_scope: str = Field(default=EXPECTED_EXECUTION_SCOPE)
    operator_identity: str
    authorized_at_utc: str
    expires_at_utc: Optional[str] = None
    revoked: bool = False
    consumed: bool = False
    consumed_at_utc: Optional[str] = None
    consumed_by_execution_id: Optional[str] = None

    def validate_for_execution(
        self,
        expected_manifest_sha256: str = EXPECTED_MANIFEST_SHA256,
        expected_proposal_id: Optional[str] = None,
        expected_phase: str = EXPECTED_PHASE,
        expected_scope: str = EXPECTED_EXECUTION_SCOPE,
    ) -> None:
        if self.phase != expected_phase:
            raise ValueError(
                f"Authorization phase mismatch: expected '{expected_phase}', got '{self.phase}'."
            )
        if self.execution_scope != expected_scope:
            raise ValueError(
                f"Authorization scope mismatch: expected '{expected_scope}', got '{self.execution_scope}'."
            )
        if not self.authorization_id or not self.authorization_id.strip():
            raise ValueError("Authorization record missing valid authorization_id.")
        if not self.proposal_id or not self.proposal_id.strip():
            raise ValueError("Authorization record missing valid proposal_id.")
        if expected_proposal_id and self.proposal_id != expected_proposal_id:
            raise ValueError(
                f"Authorization proposal_id mismatch: expected '{expected_proposal_id}', got '{self.proposal_id}'."
            )
        if not self.operator_identity or not self.operator_identity.strip():
            raise ValueError("Authorization record missing operator_identity.")
        if self.manifest_sha256.lower() != expected_manifest_sha256.lower():
            raise ValueError(
                f"Authorization manifest SHA256 mismatch: expected '{expected_manifest_sha256}', got '{self.manifest_sha256}'."
            )
        if self.revoked:
            raise ValueError(f"Authorization '{self.authorization_id}' has been REVOKED.")
        if self.consumed:
            raise ValueError(
                f"Authorization '{self.authorization_id}' has ALREADY BEEN CONSUMED "
                f"at {self.consumed_at_utc} by execution '{self.consumed_by_execution_id}'."
            )
        if self.expires_at_utc:
            now_iso = datetime.now(timezone.utc).isoformat()
            if self.expires_at_utc < now_iso:
                raise ValueError(
                    f"Authorization '{self.authorization_id}' EXPIRED at {self.expires_at_utc} (current: {now_iso})."
                )

    def consume(self, execution_id: str, file_path: Optional[Path] = None) -> None:
        if self.consumed:
            raise ValueError(f"Authorization '{self.authorization_id}' already consumed.")
        self.consumed = True
        self.consumed_at_utc = datetime.now(timezone.utc).isoformat()
        self.consumed_by_execution_id = execution_id
        if file_path:
            p = Path(file_path)
            if p.exists():
                tmp = p.with_suffix(".tmp")
                tmp.write_text(self.model_dump_json(indent=2))
                tmp.replace(p)


class Phase4F4Runner:
    """Orchestrates Phase 4F.4 controlled empirical campaign with complete safety hardening."""

    def __init__(
        self,
        pinned_image: str = "postgres:16-alpine",
        pinned_digest: str = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685",
        scale_factor: int = 2,
        memory_limit: str = "1024m",
        concurrency: int = 8,
        threads: int = 2,
        warmup_seconds: int = 10,
        duration_seconds: int = 30,
        random_seed: int = 4104,
    ):
        self.pinned_image = pinned_image
        self.pinned_digest = pinned_digest
        self.scale_factor = scale_factor
        self.memory_limit = memory_limit
        self.concurrency = concurrency
        self.threads = threads
        self.warmup_seconds = warmup_seconds
        self.duration_seconds = duration_seconds
        self.random_seed = random_seed

    @staticmethod
    def get_host_metadata() -> Dict[str, Any]:
        """Collects environmental metadata from the host operating system."""
        cpu_model = "unknown"
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        cpu_model = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass

        docker_ver = "unknown"
        try:
            res = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                docker_ver = res.stdout.strip()
        except Exception:
            pass

        pgbench_ver = "unknown"
        pgbench_path = shutil.which("pgbench")
        if pgbench_path:
            try:
                res = subprocess.run([pgbench_path, "--version"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    pgbench_ver = res.stdout.strip()
            except Exception:
                pass

        return {
            "cpu_model": cpu_model,
            "architecture": platform.machine(),
            "kernel_release": platform.release(),
            "os_system": platform.system(),
            "docker_version": docker_ver,
            "pgbench_binary": pgbench_path,
            "pgbench_version": pgbench_ver,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def verify_prerequisites(self) -> Dict[str, Any]:
        """
        Executes preflight verification checks for Phase 4F.4:
        1. Docker daemon availability
        2. Image digest verification
        3. Host-side pgbench availability (client isolation requirement)
        """
        issues: List[str] = []
        host_meta = self.get_host_metadata()

        # Check Docker daemon
        docker_ok = False
        try:
            res_dock = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=5)
            if res_dock.returncode == 0:
                docker_ok = True
            else:
                issues.append(f"Docker info returned nonzero exit code {res_dock.returncode}: {res_dock.stderr.strip()}")
        except Exception as e:
            issues.append(f"Docker daemon connection failed: {e}")

        # Check pinned image digest
        image_ok = False
        if docker_ok:
            try:
                res_img = subprocess.run(
                    ["docker", "images", "--digests", "--format", "{{.Repository}}:{{.Tag}} {{.Digest}}"],
                    capture_output=True, text=True, timeout=5
                )
                if res_img.returncode == 0:
                    for line in res_img.stdout.splitlines():
                        if "postgres:16-alpine" in line and self.pinned_digest in line:
                            image_ok = True
                            break
                    if not image_ok:
                        issues.append(f"Pinned image digest '{self.pinned_digest}' not found for postgres:16-alpine.")
            except Exception as e:
                issues.append(f"Failed to inspect Docker images: {e}")

        # Check host-side pgbench (client isolation)
        pgbench_ok = bool(host_meta.get("pgbench_binary"))
        if not pgbench_ok:
            issues.append("Host-side pgbench binary not found. Client isolation requires pgbench to run on host outside container.")

        return {
            "prerequisites_met": len(issues) == 0,
            "docker_daemon_available": docker_ok,
            "pinned_image_verified": image_ok,
            "host_pgbench_available": pgbench_ok,
            "issues": issues,
            "host_metadata": host_meta,
        }

    @staticmethod
    def read_process_cgroup(pid: int) -> str:
        """Reads /proc/<pid>/cgroup for a process."""
        cgroup_path = Path(f"/proc/{pid}/cgroup")
        if not cgroup_path.exists():
            raise RuntimeError(f"Cannot read cgroup for process {pid}: {cgroup_path} does not exist.")
        return cgroup_path.read_text().strip()

    @staticmethod
    def verify_benchmark_process_isolation(
        client_pid: int,
        container_cg_dir: Path,
        bench_cmd: List[str],
        cgroup_root: Path = Path("/sys/fs/cgroup"),
    ) -> Dict[str, Any]:
        """
        Verifies that the pgbench client process is strictly running outside
        the PostgreSQL container's cgroup (FIX 02).
        Fails closed with RuntimeError if isolation cannot be established.
        """
        try:
            raw_cgroup = Phase4F4Runner.read_process_cgroup(client_pid)
        except Exception as e:
            raise RuntimeError(f"Client cgroup isolation check failed: cannot read cgroup for pgbench PID {client_pid}: {e}")

        if not raw_cgroup:
            raise RuntimeError(f"Client cgroup isolation check failed: empty cgroup file for pgbench PID {client_pid}.")

        client_subpaths: List[str] = []
        for line in raw_cgroup.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) >= 3 and parts[2]:
                client_subpaths.append(parts[2].lstrip("/"))

        if not client_subpaths:
            raise RuntimeError(f"Client cgroup isolation check failed: unable to parse cgroup path from '{raw_cgroup}'.")

        client_cg_path = cgroup_root / client_subpaths[0]
        container_cg_path = container_cg_dir.resolve()

        if client_cg_path.resolve() == container_cg_path:
            raise RuntimeError(
                f"Client cgroup isolation violation: pgbench PID {client_pid} is inside the container cgroup ({container_cg_path})."
            )

        if str(client_cg_path.resolve()).startswith(str(container_cg_path)):
            raise RuntimeError(
                f"Client cgroup isolation violation: pgbench PID {client_pid} is a descendant of the container cgroup ({container_cg_path})."
            )

        procs_file = container_cg_dir / "cgroup.procs"
        if procs_file.exists():
            try:
                container_pids = [int(p) for p in procs_file.read_text().splitlines() if p.strip().isdigit()]
                if client_pid in container_pids:
                    raise RuntimeError(
                        f"Client cgroup isolation violation: pgbench PID {client_pid} is listed in container cgroup.procs."
                    )
            except Exception as e:
                if "isolation violation" in str(e):
                    raise
                logger.warning(f"Unable to read container cgroup.procs for isolation check: {e}")

        return {
            "client_pid": client_pid,
            "client_command": " ".join(bench_cmd),
            "client_cgroup_raw": raw_cgroup,
            "client_cgroup_path": str(client_cg_path),
            "container_cgroup_path": str(container_cg_path),
            "isolated": True,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def verify_container_effective_resources(
        container_name: str,
        cg_dir: Path,
        expected_cpu_limit: float,
        expected_memory_limit_str: str,
        expected_image_digest: str,
    ) -> Dict[str, Any]:
        """
        Verifies running container image digest, cgroup v2 cpu.max, memory.max,
        and PostgreSQL process placement in cgroup.procs (FIX 04).
        Aborts trial fail-closed if any mismatch is detected.
        """
        inspect_res = subprocess.run(
            ["docker", "inspect", "-f", "{{.Id}} {{.Image}} {{.State.Pid}}", container_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if inspect_res.returncode != 0:
            raise RuntimeError(f"Resource verification failed: unable to inspect container {container_name}: {inspect_res.stderr.strip()}")

        parts = inspect_res.stdout.strip().split()
        if len(parts) < 3:
            raise RuntimeError(f"Resource verification failed: unexpected docker inspect output '{inspect_res.stdout.strip()}'.")

        container_id, image_id, pid_str = parts[0], parts[1], parts[2]
        if not pid_str.isdigit() or int(pid_str) <= 0:
            raise RuntimeError(f"Resource verification failed: container {container_name} has invalid main PID '{pid_str}'.")
        main_pid = int(pid_str)

        # Image digest verification
        img_inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{range .RepoDigests}}{{.}} {{end}}", image_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        observed_digests = img_inspect.stdout.strip() if img_inspect.returncode == 0 else ""
        if expected_image_digest not in observed_digests and expected_image_digest not in image_id:
            raise RuntimeError(
                f"Image digest mismatch for container {container_name}: "
                f"expected '{expected_image_digest}', observed '{observed_digests or image_id}'."
            )

        # Cgroup directory check
        if not cg_dir.exists() or not cg_dir.is_dir():
            raise RuntimeError(f"Container cgroup directory {cg_dir} does not exist.")

        # cpu.max check
        cpu_max_file = cg_dir / "cpu.max"
        if not cpu_max_file.exists():
            raise RuntimeError(f"Container cgroup missing cpu.max file at {cpu_max_file}.")
        cpu_max_raw = cpu_max_file.read_text().strip()
        cpu_max_parts = cpu_max_raw.split()
        if len(cpu_max_parts) < 2:
            raise RuntimeError(f"Invalid format in cpu.max: '{cpu_max_raw}'.")

        quota_str, period_str = cpu_max_parts[0], cpu_max_parts[1]
        try:
            period_usec = int(period_str)
            expected_quota_usec = int(round(expected_cpu_limit * period_usec))
            if quota_str == "max":
                raise RuntimeError(f"Container {container_name} has unlimited CPU quota (max); expected {expected_quota_usec}.")
            actual_quota_usec = int(quota_str)
            if actual_quota_usec != expected_quota_usec:
                raise RuntimeError(
                    f"CPU quota mismatch for {container_name}: expected {expected_quota_usec} usec ({expected_cpu_limit} vCPU), "
                    f"observed {actual_quota_usec} usec (period {period_usec} usec)."
                )
        except ValueError as e:
            raise RuntimeError(f"Failed to parse cpu.max values '{cpu_max_raw}': {e}")

        # memory.max check
        mem_max_file = cg_dir / "memory.max"
        if not mem_max_file.exists():
            raise RuntimeError(f"Container cgroup missing memory.max file at {mem_max_file}.")
        mem_max_raw = mem_max_file.read_text().strip()
        expected_bytes = 1073741824  # default 1024m
        if expected_memory_limit_str.lower().endswith("m"):
            mb = int(expected_memory_limit_str[:-1])
            expected_bytes = mb * 1024 * 1024

        if mem_max_raw == "max":
            raise RuntimeError(f"Container {container_name} has unlimited memory.max; expected {expected_bytes} bytes.")
        try:
            actual_mem_bytes = int(mem_max_raw)
            if actual_mem_bytes != expected_bytes:
                raise RuntimeError(
                    f"Memory limit mismatch for {container_name}: expected {expected_bytes} bytes ({expected_memory_limit_str}), "
                    f"observed {actual_mem_bytes} bytes."
                )
        except ValueError as e:
            raise RuntimeError(f"Failed to parse memory.max '{mem_max_raw}': {e}")

        # Process placement in cgroup.procs
        procs_file = cg_dir / "cgroup.procs"
        if not procs_file.exists():
            raise RuntimeError(f"Container cgroup missing cgroup.procs at {procs_file}.")
        cgroup_pids = [int(p) for p in procs_file.read_text().splitlines() if p.strip().isdigit()]
        if main_pid not in cgroup_pids:
            raise RuntimeError(
                f"PostgreSQL container main PID {main_pid} not placed in container cgroup.procs ({procs_file})."
            )

        return {
            "container_id": container_id,
            "image_id": image_id,
            "main_pid": main_pid,
            "cpu_quota_usec": actual_quota_usec,
            "cpu_period_usec": period_usec,
            "memory_max_bytes": actual_mem_bytes,
            "cgroup_procs_count": len(cgroup_pids),
            "verification_passed": True,
        }

    @staticmethod
    def _persist_campaign_state(
        root: Path,
        execution_id: str,
        trial_records: List[Dict[str, Any]],
        frozen_schedule: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Persists incremental campaign progress distinguishing all trial states (FIX 06)."""
        executed_ids = {t["trial_id"] for t in trial_records}
        state = {
            "execution_id": execution_id,
            "last_updated_utc": datetime.now(timezone.utc).isoformat(),
            "trials_total_scheduled": len(frozen_schedule),
            "trials_executed_count": len(trial_records),
            "trials_completed": [t for t in trial_records if t["status"] == "SUCCESS"],
            "trials_failed": [t for t in trial_records if t["status"] == "FAILED"],
            "trials_aborted": [t for t in trial_records if t["status"] == "ABORTED"],
            "trials_incomplete": [t for t in trial_records if t["status"] == "INCOMPLETE"],
            "trials_never_started": [t for t in frozen_schedule if t["trial_id"] not in executed_ids],
        }
        (root / "campaign_state_partial.json").write_text(json.dumps(state, indent=2))
        return state

    def execute_single_trial(
        self,
        trial_def: Dict[str, Any],
        artifacts_dir: Path,
        execution_id: str,
    ) -> Dict[str, Any]:
        """
        Executes a single trial according to the Phase 4F.4 14-step per-trial lifecycle.
        Enforces complete safety, client isolation, resource verification, and lifecycle cleanup.
        """
        seq = trial_def["seq"]
        trial_id = trial_def["trial_id"]
        profile_name = trial_def["profile"]
        cpu_quota = trial_def["cpu_limit"]
        rep = trial_def["rep"]

        profile = resolve_workload_profile(profile_name)
        trial_art_dir = artifacts_dir / trial_id
        trial_art_dir.mkdir(parents=True, exist_ok=True)

        container_name = f"aads-p4f4-{trial_id}-{time.strftime('%H%M%S')}"
        log_prefix = str(trial_art_dir / f"pgbench_{trial_id}")

        pgbench_bin = shutil.which("pgbench")
        if not pgbench_bin:
            raise RuntimeError(f"Trial {trial_id} aborted: host-side pgbench is unavailable (client isolation violation).")

        mgr = TrialIsolationManager(
            default_image=self.pinned_image,
            pinned_image_digest=self.pinned_digest,
            cpu_limit=cpu_quota,
            memory_limit=self.memory_limit,
        )

        timing_data: Dict[str, float] = {}
        cleanup_errors: List[str] = []
        container_started = False
        monitor_started = False
        sampler_started = False
        monitor: Optional[ContainerResourceMonitor] = None
        sampler: Optional[PostgresPeriodicSampler] = None
        current_stage = "STARTUP"
        trial_exc: Optional[Exception] = None
        captured_stdout = ""
        captured_stderr = ""
        proc_returncode: Optional[int] = None
        isolation_record: Optional[Dict[str, Any]] = None
        sanitized_conn = ""
        redacted_bench_cmd = ""

        try:
            # 1. Container Initialization
            current_stage = "CONTAINER_INIT"
            init_duration, baseline_snapshot = mgr.initialize_fresh_container(
                container_name=container_name,
                scale_factor=self.scale_factor,
                timeout_seconds=60,
                publish_host_port=True,
            )
            container_started = True
            timing_data["init_duration_sec"] = round(init_duration, 3)

            host_port = baseline_snapshot.host_port
            if not host_port:
                raise RuntimeError(f"Trial {trial_id}: Failed to resolve published PostgreSQL port on 127.0.0.1.")

            conn_args = ["-h", "127.0.0.1", "-p", str(host_port), "-U", "postgres", "aadsbench"]
            sanitized_conn = f"postgresql://postgres@127.0.0.1:{host_port}/aadsbench"

            # 2. Cgroup Resolution
            current_stage = "CGROUP_RESOLUTION"
            monitor = ContainerResourceMonitor(
                container_name=container_name,
                interval_sec=0.020,
                execution_id=execution_id,
                experiment_id=trial_id,
            )
            cg_dir = monitor.resolve_cgroup_dir()
            if not cg_dir or not cg_dir.exists():
                raise RuntimeError(f"Trial {trial_id}: Required container cgroup directory could not be resolved.")

            # FIX 04: Effective Resource & Image Verification before warm-up
            current_stage = "RESOURCE_VERIFICATION"
            resource_verif = self.verify_container_effective_resources(
                container_name=container_name,
                cg_dir=cg_dir,
                expected_cpu_limit=float(cpu_quota),
                expected_memory_limit_str=self.memory_limit,
                expected_image_digest=self.pinned_digest,
            )
            (trial_art_dir / "resource_verification.json").write_text(json.dumps(resource_verif, indent=2))

            # 3. Pre-trial Snapshots
            current_stage = "PRE_SNAPSHOTS"
            pre_pg = PostgresMetricsCollector.take_snapshot(container_name)
            pre_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)

            # 4. Start Background Monitors & Samplers
            current_stage = "MONITOR_START"
            monitor.start()
            monitor_started = True

            sampler = PostgresPeriodicSampler(container_name=container_name, interval_sec=0.100)
            sampler.start()
            sampler_started = True

            # 5. Warm-up
            current_stage = "WARMUP"
            warmup_cmd = (
                [pgbench_bin, "-c", str(self.concurrency), "-j", str(self.threads), "-T", str(self.warmup_seconds)]
                + profile.command_flags
                + conn_args
            )
            res_warm = subprocess.run(warmup_cmd, capture_output=True, text=True, timeout=self.warmup_seconds + 15)
            if res_warm.returncode != 0:
                captured_stdout = res_warm.stdout
                captured_stderr = res_warm.stderr
                proc_returncode = res_warm.returncode
                raise RuntimeError(f"Trial {trial_id}: Warm-up failed (exit code {res_warm.returncode}): {res_warm.stderr.strip()}")

            # 6. Measured Benchmark Execution with Client Isolation (FIX 02)
            current_stage = "BENCHMARK_ISOLATION"
            bench_cmd = (
                [
                    pgbench_bin,
                    "-c", str(self.concurrency),
                    "-j", str(self.threads),
                    "-T", str(self.duration_seconds),
                    "-l",
                    f"--log-prefix={log_prefix}",
                ]
                + profile.command_flags
                + conn_args
            )
            redacted_bench_cmd = f"pgbench -c {self.concurrency} -j {self.threads} -T {self.duration_seconds} {' '.join(profile.command_flags)} -l --log-prefix={log_prefix} {sanitized_conn}"

            t_bench_start = time.monotonic()
            proc = subprocess.Popen(
                bench_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                isolation_record = self.verify_benchmark_process_isolation(
                    client_pid=proc.pid,
                    container_cg_dir=cg_dir,
                    bench_cmd=bench_cmd,
                )
                (trial_art_dir / "client_isolation.json").write_text(json.dumps(isolation_record, indent=2))
            except Exception as e:
                proc.kill()
                proc.wait()
                raise RuntimeError(f"Trial {trial_id} client isolation check failed: {e}") from e

            current_stage = "BENCHMARK_EXECUTION"
            try:
                captured_stdout, captured_stderr = proc.communicate(timeout=self.duration_seconds + 25)
                proc_returncode = proc.returncode
            except subprocess.TimeoutExpired as exc:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    captured_stdout, captured_stderr = proc.communicate(timeout=5)
                except Exception:
                    pass
                proc_returncode = -1
                raise RuntimeError(
                    f"Trial {trial_id}: Benchmark execution timed out after {self.duration_seconds + 25} seconds."
                ) from exc
            finally:
                timing_data["benchmark_wall_duration_sec"] = round(time.monotonic() - t_bench_start, 3)
                if monitor_started and monitor:
                    samples, mon_summary = monitor.stop()
                    monitor_started = False
                else:
                    samples, mon_summary = [], None
                if sampler_started and sampler:
                    total_waits, wait_counts, lock_samples = sampler.stop()
                    sampler_started = False
                else:
                    total_waits, wait_counts, lock_samples = 0, {}, []

            if proc_returncode != 0:
                raise RuntimeError(f"Trial {trial_id}: Benchmark execution failed (exit code {proc_returncode}): {captured_stderr.strip()}")

            bench_summary = PgbenchOutputParser.parse_summary(captured_stdout)

            # 7. Collect and parse transaction logs (FIX 03)
            current_stage = "LOG_COLLECTION_AND_PARSING"
            log_files = list(trial_art_dir.glob(f"pgbench_{trial_id}.*"))
            log_text_chunks = []
            for lf in sorted(log_files):
                if lf.suffix in (".stdout", ".stderr", ".json", ".txt"):
                    continue
                try:
                    txt = lf.read_text()
                    if txt.strip():
                        log_text_chunks.append(txt)
                except Exception:
                    pass

            if not log_text_chunks:
                raise ValueError(f"Trial {trial_id}: Missing raw transaction logs after execution.")

            full_log_text = "\n".join(log_text_chunks)
            tx_records = CFSCorrelationAnalyzer.parse_pgbench_log_records(full_log_text)
            log_stats = PgbenchOutputParser.parse_transaction_logs(full_log_text)

            # 8. Post-trial snapshots and deltas
            current_stage = "POST_SNAPSHOTS"
            post_pg = PostgresMetricsCollector.take_snapshot(container_name)
            pg_delta = PostgresMetricsCollector.compute_deltas(
                start=pre_pg,
                end=post_pg,
                lock_wait_samples=total_waits,
                wait_event_samples=wait_counts,
            )

            post_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)
            storage_delta = StorageMonitor.compute_deltas(start=pre_storage, end=post_storage)
            sampler_telemetry = sampler.get_telemetry() if sampler else {}

            post_db_state = None
            db_diff = {}
            try:
                post_db_state = mgr.capture_database_state(container_name, self.scale_factor)
                db_diff = baseline_snapshot.diff(post_db_state)
            except Exception:
                pass

            # 9. CFS correlation analysis
            current_stage = "CFS_ANALYSIS"
            cfs_analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)
            cfs_res = cfs_analyzer.analyze(
                transactions=tx_records,
                cgroup_samples=[s.to_dict() for s in samples],
            )

            # 10. Strict Metric Extraction & Reconciliation (FIX 03)
            current_stage = "METRIC_VALIDATION"
            tps = bench_summary.get("tps")
            total_tx = bench_summary.get("total_transactions")
            failed_tx = bench_summary.get("failed_transactions")
            lat_avg_ms = bench_summary.get("latency_avg_ms")
            p50_ms = log_stats.get("p50_ms")
            p90_ms = log_stats.get("p90_ms")
            p95_ms = log_stats.get("p95_ms")
            p99_ms = log_stats.get("p99_ms")
            p999_ms = log_stats.get("p999_ms")
            max_ms = log_stats.get("max_ms")
            std_ms = log_stats.get("std_ms")
            log_sample_count = log_stats.get("sample_count", 0)

            # Reconcile raw transaction log count with benchmark total
            if total_tx is not None and log_sample_count != total_tx:
                raise ValueError(
                    f"Trial {trial_id} transaction count reconciliation failure: "
                    f"raw log samples ({log_sample_count}) != benchmark reported transactions ({total_tx})."
                )

            metric_provenance = {
                "tps": {"value": tps, "status": "AVAILABLE" if tps is not None else "UNAVAILABLE", "source": "pgbench_summary_stdout"},
                "total_transactions": {"value": total_tx, "status": "AVAILABLE" if total_tx is not None else "UNAVAILABLE", "source": "pgbench_summary_stdout"},
                "failed_transactions": {
                    "value": failed_tx,
                    "status": bench_summary.get("failed_transactions_status", "AVAILABLE" if failed_tx is not None else "UNAVAILABLE"),
                    "source": "pgbench_summary_stdout",
                    "reason": bench_summary.get("failed_transactions_reason"),
                },
                "latency_avg_ms": {"value": lat_avg_ms, "status": "AVAILABLE" if lat_avg_ms is not None else "UNAVAILABLE", "source": "pgbench_summary_stdout"},
                "p50_ms": {"value": p50_ms, "status": "AVAILABLE" if p50_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.percentile(50, method='linear')"},
                "p90_ms": {"value": p90_ms, "status": "AVAILABLE" if p90_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.percentile(90, method='linear')"},
                "p95_ms": {"value": p95_ms, "status": "AVAILABLE" if p95_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.percentile(95, method='linear')"},
                "p99_ms": {"value": p99_ms, "status": "AVAILABLE" if p99_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.percentile(99, method='linear')"},
                "p999_ms": {"value": p999_ms, "status": "AVAILABLE" if p999_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.percentile(99.9, method='linear')"},
                "max_ms": {"value": max_ms, "status": "AVAILABLE" if max_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.max()"},
                "std_ms": {"value": std_ms, "status": "AVAILABLE" if std_ms is not None else "UNAVAILABLE", "source": "raw_transaction_logs", "formula": "numpy.std()"},
            }

            missing_metrics = [k for k, v in metric_provenance.items() if v["value"] is None]
            if missing_metrics:
                raise ValueError(
                    f"Trial {trial_id} missing required metrics without fallback: {', '.join(missing_metrics)}. "
                    "Every metric must have a documented source and calculation."
                )

            # 11. Persist Artifacts
            current_stage = "ARTIFACT_PERSISTENCE"
            (trial_art_dir / "pgbench.stdout").write_text(captured_stdout or "")
            (trial_art_dir / "pgbench.stderr").write_text(captured_stderr or "")
            (trial_art_dir / "command.txt").write_text(redacted_bench_cmd)
            if monitor:
                monitor.save_artifacts(trial_art_dir, trial_id)
            (trial_art_dir / "correlation_analysis.json").write_text(json.dumps(cfs_res, indent=2))
            (trial_art_dir / "postgres_snapshot_pre.json").write_text(json.dumps(pre_pg.to_dict(), indent=2))
            (trial_art_dir / "postgres_snapshot_post.json").write_text(json.dumps(post_pg.to_dict(), indent=2))
            (trial_art_dir / "postgres_metrics_delta.json").write_text(json.dumps(pg_delta.to_dict(), indent=2))
            (trial_art_dir / "postgres_sampler_telemetry.json").write_text(json.dumps(sampler_telemetry, indent=2))
            (trial_art_dir / "storage_snapshot_pre.json").write_text(json.dumps(pre_storage.to_dict(), indent=2))
            (trial_art_dir / "storage_snapshot_post.json").write_text(json.dumps(post_storage.to_dict(), indent=2))
            (trial_art_dir / "storage_metrics_delta.json").write_text(json.dumps(storage_delta.to_dict(), indent=2))
            (trial_art_dir / "database_state_baseline.json").write_text(json.dumps(baseline_snapshot.to_dict(), indent=2))
            if post_db_state:
                (trial_art_dir / "database_state_post.json").write_text(json.dumps(post_db_state.to_dict(), indent=2))
            (trial_art_dir / "database_state_diff.json").write_text(json.dumps(db_diff, indent=2))
            (trial_art_dir / "metric_provenance.json").write_text(json.dumps(metric_provenance, indent=2))

            result_record = {
                "sequence": seq,
                "trial_id": trial_id,
                "execution_id": execution_id,
                "workload_profile": profile_name,
                "cpu_quota_cores": float(cpu_quota),
                "replication": rep,
                "status": "SUCCESS",
                "container_name": container_name,
                "host_port": host_port,
                "client_placement": "host",
                "client_isolation": isolation_record,
                "bench_command": redacted_bench_cmd,
                "tps": tps,
                "total_transactions": total_tx,
                "failed_transactions": failed_tx,
                "latency_avg_ms": lat_avg_ms,
                "p50_ms": p50_ms,
                "p90_ms": p90_ms,
                "p95_ms": p95_ms,
                "p99_ms": p99_ms,
                "p999_ms": p999_ms,
                "max_ms": max_ms,
                "std_ms": std_ms,
                "metric_provenance": metric_provenance,
                "cgroup_cpu": {
                    "mean_cpu_pct": mon_summary.mean_container_cpu_pct if mon_summary else None,
                    "throttling_events": mon_summary.throttling_events_count if mon_summary else None,
                    "throttled_sec": mon_summary.throttled_time_seconds if mon_summary else None,
                },
                "storage": storage_delta.to_dict(),
                "postgres_deltas": pg_delta.to_dict(),
                "cfs_correlation": cfs_res,
                "sampler_telemetry": sampler_telemetry,
                "baseline_fingerprint": baseline_snapshot.content_fingerprint,
                "timing": timing_data,
                "artifacts_path": str(trial_art_dir),
                "cleanup_result": {"success": True, "cleanup_errors": []},
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

            (trial_art_dir / "trial_summary.json").write_text(json.dumps(result_record, indent=2))
            return result_record

        except Exception as e:
            trial_exc = e
            logger.error(f"Trial {trial_id} failed during {current_stage}: {e}")

        finally:
            # FIX 05: Complete Lifecycle Cleanup
            if sampler_started and sampler:
                try:
                    sampler.stop()
                except Exception as e:
                    cleanup_errors.append(f"Sampler stop failed: {e}")

            if monitor_started and monitor:
                try:
                    monitor.stop()
                except Exception as e:
                    cleanup_errors.append(f"Monitor stop failed: {e}")

            if container_started:
                try:
                    mgr.cleanup_container(container_name)
                except Exception as e:
                    cleanup_errors.append(f"Container cleanup failed: {e}")

        # If trial failed, persist durable failure evidence (FIX 06)
        if trial_exc is not None:
            if current_stage in ("RESOURCE_VERIFICATION", "BENCHMARK_ISOLATION"):
                terminal_status = "ABORTED"
            elif current_stage in ("CONTAINER_INIT", "CGROUP_RESOLUTION"):
                terminal_status = "INCOMPLETE"
            else:
                terminal_status = "FAILED"

            if captured_stdout:
                (trial_art_dir / "pgbench.stdout").write_text(captured_stdout)
            if captured_stderr:
                (trial_art_dir / "pgbench.stderr").write_text(captured_stderr)
            if redacted_bench_cmd:
                (trial_art_dir / "command.txt").write_text(redacted_bench_cmd)

            failure_record = {
                "sequence": seq,
                "trial_id": trial_id,
                "execution_id": execution_id,
                "workload_profile": profile_name,
                "cpu_quota_cores": float(cpu_quota),
                "replication": rep,
                "status": terminal_status,
                "failure_stage": current_stage,
                "exception_type": type(trial_exc).__name__,
                "exception_message": str(trial_exc),
                "returncode": proc_returncode,
                "stdout": captured_stdout,
                "stderr": captured_stderr,
                "cleanup_result": {
                    "success": len(cleanup_errors) == 0,
                    "cleanup_errors": cleanup_errors,
                },
                "artifacts_path": str(trial_art_dir),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            (trial_art_dir / "trial_failure.json").write_text(json.dumps(failure_record, indent=2))
            (trial_art_dir / "trial_summary.json").write_text(json.dumps(failure_record, indent=2))
            return failure_record

        raise RuntimeError(f"Unexpected termination for trial {trial_id}.")

    def execute_campaign(
        self,
        authorization: Union[CampaignAuthorizationRecord, Dict[str, Any], Path, str],
        artifacts_root: Optional[Path] = None,
        on_trial_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        expected_proposal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the complete Phase 4F.4 12-trial campaign under operator authorization.
        Strict fail-closed: rejects missing, expired, reused, or mismatched authorization (FIX 01).
        """
        if isinstance(authorization, bool) or authorization is None:
            raise RuntimeError(
                "Phase 4F.4 execution NOT AUTHORIZED. "
                "A validated CampaignAuthorizationRecord is required; Boolean authorization is rejected."
            )

        auth_path: Optional[Path] = None
        if isinstance(authorization, (str, Path)):
            auth_path = Path(authorization)
            if not auth_path.exists():
                raise RuntimeError(f"Authorization file not found: {auth_path}")
            auth_data = json.loads(auth_path.read_text())
            auth_record = CampaignAuthorizationRecord(**auth_data)
        elif isinstance(authorization, dict):
            auth_record = CampaignAuthorizationRecord(**authorization)
        elif isinstance(authorization, CampaignAuthorizationRecord):
            auth_record = authorization
        else:
            raise RuntimeError(f"Invalid authorization type: {type(authorization).__name__}")

        # Validate authorization fields
        auth_record.validate_for_execution(
            expected_manifest_sha256=EXPECTED_MANIFEST_SHA256,
            expected_proposal_id=expected_proposal_id,
            expected_phase=EXPECTED_PHASE,
            expected_scope=EXPECTED_EXECUTION_SCOPE,
        )

        root = artifacts_root or Path("/home/vicky/v_drive/Codes/AADS/artifacts/phase_4f4_empirical")
        root.mkdir(parents=True, exist_ok=True)
        execution_id = f"exec_p4f4_{time.strftime('%Y%m%d_%H%M%S')}"

        # Atomically consume authorization
        auth_record.consume(execution_id=execution_id, file_path=auth_path)
        (root / "consumed_authorization.json").write_text(auth_record.model_dump_json(indent=2))

        # 1. Preflight checks
        preflight = self.verify_prerequisites()
        (root / "preflight_verification.json").write_text(json.dumps(preflight, indent=2))
        if not preflight["prerequisites_met"]:
            raise RuntimeError(f"Phase 4F.4 Preflight Verification Failed: {'; '.join(preflight['issues'])}")

        trial_results: List[Dict[str, Any]] = []

        # 2. Execute trials in exact frozen sequence, persisting campaign state incrementally (FIX 06)
        for trial_def in FROZEN_12_TRIAL_SCHEDULE:
            logger.info(f"Executing sequence {trial_def['seq']}/12: Trial {trial_def['trial_id']} ({trial_def['profile']}, {trial_def['cpu_limit']} vCPU, Rep {trial_def['rep']})")
            trial_res = self.execute_single_trial(
                trial_def=trial_def,
                artifacts_dir=root / "trials",
                execution_id=execution_id,
            )
            trial_results.append(trial_res)

            # Persist campaign state incrementally after every trial
            self._persist_campaign_state(
                root=root,
                execution_id=execution_id,
                trial_records=trial_results,
                frozen_schedule=FROZEN_12_TRIAL_SCHEDULE,
            )

            if on_trial_complete and callable(on_trial_complete):
                on_trial_complete(trial_res)

        # FIX 07: Strict campaign completion validation
        completion_issues: List[str] = []
        if len(FROZEN_12_TRIAL_SCHEDULE) != 12:
            completion_issues.append(f"Manifest schedule does not have 12 trials: {len(FROZEN_12_TRIAL_SCHEDULE)}")
        if len(trial_results) != 12:
            completion_issues.append(f"Expected 12 executed trials, got {len(trial_results)}")

        failed_trials = [t for t in trial_results if t.get("status") != "SUCCESS"]
        if failed_trials:
            completion_issues.append(f"{len(failed_trials)} trials failed or aborted: {[t['trial_id'] for t in failed_trials]}")

        conditions: Dict[str, List[Dict[str, Any]]] = {
            "ro_1cpu": [t for t in trial_results if t.get("status") == "SUCCESS" and t["workload_profile"] == "read_only_select" and t["cpu_quota_cores"] == 1.0],
            "ro_2cpu": [t for t in trial_results if t.get("status") == "SUCCESS" and t["workload_profile"] == "read_only_select" and t["cpu_quota_cores"] == 2.0],
            "tpcb_1cpu": [t for t in trial_results if t.get("status") == "SUCCESS" and t["workload_profile"] == "balanced_oltp_tpcb" and t["cpu_quota_cores"] == 1.0],
            "tpcb_2cpu": [t for t in trial_results if t.get("status") == "SUCCESS" and t["workload_profile"] == "balanced_oltp_tpcb" and t["cpu_quota_cores"] == 2.0],
        }

        for cond_name, trials in conditions.items():
            if len(trials) != 3:
                completion_issues.append(f"Condition '{cond_name}' has {len(trials)} successful replications; required 3.")

        for t in trial_results:
            if not t.get("cleanup_result", {}).get("success", False):
                completion_issues.append(f"Trial {t['trial_id']} has cleanup errors: {t['cleanup_result'].get('cleanup_errors')}")

        campaign_status = "COMPLETED" if not completion_issues else "FAILED"

        if campaign_status != "COMPLETED":
            partial_summary = {
                "execution_id": execution_id,
                "manifest_status": campaign_status,
                "completion_issues": completion_issues,
                "total_trials": len(trial_results),
                "successful_trials": sum(1 for t in trial_results if t.get("status") == "SUCCESS"),
                "failed_trials": len(failed_trials),
                "schedule": FROZEN_12_TRIAL_SCHEDULE,
                "conditions": None,
                "comparisons": None,
                "provenance": {
                    "host_metadata": preflight["host_metadata"],
                    "pinned_image": self.pinned_image,
                    "pinned_digest": self.pinned_digest,
                    "scale_factor": self.scale_factor,
                    "clients": self.concurrency,
                    "threads": self.threads,
                    "warmup_sec": self.warmup_seconds,
                    "measurement_sec": self.duration_seconds,
                    "random_seed": self.random_seed,
                },
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            (root / "campaign_summary.json").write_text(json.dumps(partial_summary, indent=2))
            raise RuntimeError(f"Phase 4F.4 Campaign Execution Failed: {'; '.join(completion_issues)}")

        # 3. Aggregate condition comparisons (Only when ALL 12 trials are SUCCESS)
        condition_summaries: Dict[str, Any] = {}
        for cond_name, trials in conditions.items():
            tps_vals = [t["tps"] for t in trials]
            lat_vals = [t["latency_avg_ms"] for t in trials]
            p95_vals = [t["p95_ms"] for t in trials]
            p99_vals = [t["p99_ms"] for t in trials]
            p999_vals = [t["p999_ms"] for t in trials]
            cpu_vals = [t["cgroup_cpu"]["mean_cpu_pct"] for t in trials if t["cgroup_cpu"]["mean_cpu_pct"] is not None]
            throt_sec_vals = [t["cgroup_cpu"]["throttled_sec"] or 0.0 for t in trials]

            condition_summaries[cond_name] = {
                "trial_count": len(trials),
                "replications": [t["trial_id"] for t in trials],
                "tps": {
                    "values": tps_vals,
                    "mean": round(float(np.mean(tps_vals)), 1),
                    "median": round(float(np.median(tps_vals)), 1),
                    "std": round(float(np.std(tps_vals)), 2),
                },
                "latency_mean_ms": {
                    "values": lat_vals,
                    "mean": round(float(np.mean(lat_vals)), 3),
                    "median": round(float(np.median(lat_vals)), 3),
                    "std": round(float(np.std(lat_vals)), 3),
                },
                "p95_ms": {
                    "values": p95_vals,
                    "mean": round(float(np.mean(p95_vals)), 3),
                    "median": round(float(np.median(p95_vals)), 3),
                },
                "p99_ms": {
                    "values": p99_vals,
                    "mean": round(float(np.mean(p99_vals)), 3),
                    "median": round(float(np.median(p99_vals)), 3),
                },
                "p999_ms": {
                    "values": p999_vals,
                    "mean": round(float(np.mean(p999_vals)), 3),
                    "median": round(float(np.median(p999_vals)), 3),
                },
                "cpu_utilization_pct": {
                    "values": cpu_vals,
                    "mean": round(float(np.mean(cpu_vals)), 1) if cpu_vals else None,
                },
                "throttled_seconds": {
                    "values": throt_sec_vals,
                    "mean": round(float(np.mean(throt_sec_vals)), 3),
                },
            }

        # Compute quota impact comparisons (1.0 vs 2.0 vCPU)
        comparisons = {
            "read_only_select": {
                "tps_delta": round(condition_summaries["ro_2cpu"]["tps"]["mean"] - condition_summaries["ro_1cpu"]["tps"]["mean"], 1),
                "tps_pct_change": round(((condition_summaries["ro_2cpu"]["tps"]["mean"] - condition_summaries["ro_1cpu"]["tps"]["mean"]) / condition_summaries["ro_1cpu"]["tps"]["mean"]) * 100.0, 2),
                "mean_latency_delta_ms": round(condition_summaries["ro_2cpu"]["latency_mean_ms"]["mean"] - condition_summaries["ro_1cpu"]["latency_mean_ms"]["mean"], 3),
                "mean_latency_pct_change": round(((condition_summaries["ro_2cpu"]["latency_mean_ms"]["mean"] - condition_summaries["ro_1cpu"]["latency_mean_ms"]["mean"]) / condition_summaries["ro_1cpu"]["latency_mean_ms"]["mean"]) * 100.0, 2),
                "throttled_time_reduction_sec": round(condition_summaries["ro_1cpu"]["throttled_seconds"]["mean"] - condition_summaries["ro_2cpu"]["throttled_seconds"]["mean"], 3),
            },
            "balanced_oltp_tpcb": {
                "tps_delta": round(condition_summaries["tpcb_2cpu"]["tps"]["mean"] - condition_summaries["tpcb_1cpu"]["tps"]["mean"], 1),
                "tps_pct_change": round(((condition_summaries["tpcb_2cpu"]["tps"]["mean"] - condition_summaries["tpcb_1cpu"]["tps"]["mean"]) / condition_summaries["tpcb_1cpu"]["tps"]["mean"]) * 100.0, 2),
                "mean_latency_delta_ms": round(condition_summaries["tpcb_2cpu"]["latency_mean_ms"]["mean"] - condition_summaries["tpcb_1cpu"]["latency_mean_ms"]["mean"], 3),
                "mean_latency_pct_change": round(((condition_summaries["tpcb_2cpu"]["latency_mean_ms"]["mean"] - condition_summaries["tpcb_1cpu"]["latency_mean_ms"]["mean"]) / condition_summaries["tpcb_1cpu"]["latency_mean_ms"]["mean"]) * 100.0, 2),
                "throttled_time_reduction_sec": round(condition_summaries["tpcb_1cpu"]["throttled_seconds"]["mean"] - condition_summaries["tpcb_2cpu"]["throttled_seconds"]["mean"], 3),
            },
        }

        campaign_summary = {
            "execution_id": execution_id,
            "manifest_status": "COMPLETED",
            "total_trials": len(trial_results),
            "successful_trials": sum(1 for t in trial_results if t["status"] == "SUCCESS"),
            "failed_trials": 0,
            "schedule": FROZEN_12_TRIAL_SCHEDULE,
            "conditions": condition_summaries,
            "comparisons": comparisons,
            "provenance": {
                "host_metadata": preflight["host_metadata"],
                "pinned_image": self.pinned_image,
                "pinned_digest": self.pinned_digest,
                "scale_factor": self.scale_factor,
                "clients": self.concurrency,
                "threads": self.threads,
                "warmup_sec": self.warmup_seconds,
                "measurement_sec": self.duration_seconds,
                "random_seed": self.random_seed,
            },
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

        (root / "campaign_summary.json").write_text(json.dumps(campaign_summary, indent=2))
        return campaign_summary
