"""
Phase 4F.4 — Final 12-Trial Execution Engine & Manifest Orchestrator.

Implements the frozen 12-trial empirical campaign comparing PostgreSQL 16 performance
under 1.0 vCPU vs 2.0 vCPU quotas across read_only_select and balanced_oltp_tpcb workloads.

Strict methodology & safety invariants:
- Frozen deterministic randomized sequence (seed 4104)
- Guaranteed per-trial database isolation (fresh container, newly initialized SF2 database, SHA256 fingerprint verification)
- Mandatory host-side pgbench client placement (pgbench runs on host outside the container cgroup)
- Full instrumentation: cgroup v2 io.stat, host diskstats, 20ms CFS sampling, persistent coprocess psql sampler, PostgreSQL system views
- Guarded execution: requires explicit authorized=True parameter; raises RuntimeError otherwise.
- Model promotion state: DISABLED. Registry mutation: DISABLED.
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


class Phase4F4Runner:
    """Orchestrates Phase 4F.4 controlled empirical campaign."""

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

    def execute_single_trial(
        self,
        trial_def: Dict[str, Any],
        artifacts_dir: Path,
        execution_id: str,
    ) -> Dict[str, Any]:
        """
        Executes a single trial according to the Phase 4F.4 14-step per-trial lifecycle.
        Enforces client placement on the host outside the PostgreSQL container.
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
        t_total_start = time.monotonic()

        try:
            # 1. Start fresh container, initialize SF2 dataset, and verify baseline invariants & fingerprint
            t0 = time.monotonic()
            init_duration, baseline_snapshot = mgr.initialize_fresh_container(
                container_name=container_name,
                scale_factor=self.scale_factor,
                timeout_seconds=60,
                publish_host_port=True,
            )
            timing_data["init_duration_sec"] = round(init_duration, 3)

            host_port = baseline_snapshot.host_port
            if not host_port:
                raise RuntimeError(f"Trial {trial_id}: Failed to resolve published PostgreSQL port on 127.0.0.1.")

            # Connection parameters (passwordless trust auth inside local bridge)
            conn_args = ["-h", "127.0.0.1", "-p", str(host_port), "-U", "postgres", "aadsbench"]
            sanitized_conn = f"postgresql://postgres@127.0.0.1:{host_port}/aadsbench"

            # 2. Start continuous resource monitors and resolve container cgroup path
            monitor = ContainerResourceMonitor(
                container_name=container_name,
                interval_sec=0.020,
                execution_id=execution_id,
                experiment_id=trial_id,
            )
            cg_dir = monitor.resolve_cgroup_dir()
            if not cg_dir or not cg_dir.exists():
                raise RuntimeError(f"Trial {trial_id}: Required container cgroup directory could not be resolved.")

            # 3. Take pre-trial PostgreSQL snapshot
            pre_pg = PostgresMetricsCollector.take_snapshot(container_name)

            # 4. Take pre-trial Storage snapshot with resolved cgroup directory
            pre_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)

            # Start background continuous monitors
            monitor.start()

            # Start persistent coprocess psql sampler
            sampler = PostgresPeriodicSampler(container_name=container_name, interval_sec=0.100)
            sampler.start()

            # 5. Warm-up (10 seconds)
            warmup_cmd = (
                [pgbench_bin, "-c", str(self.concurrency), "-j", str(self.threads), "-T", str(self.warmup_seconds)]
                + profile.command_flags
                + conn_args
            )
            res_warm = subprocess.run(warmup_cmd, capture_output=True, text=True, timeout=self.warmup_seconds + 15)
            if res_warm.returncode != 0:
                raise RuntimeError(f"Trial {trial_id}: Warm-up failed (exit code {res_warm.returncode}): {res_warm.stderr.strip()}")

            # 6. Measured Benchmark Execution (30 seconds)
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

            # Redacted command string for logs
            redacted_bench_cmd = f"pgbench -c {self.concurrency} -j {self.threads} -T {self.duration_seconds} {' '.join(profile.command_flags)} -l --log-prefix={log_prefix} {sanitized_conn}"

            t_bench_start = time.monotonic()
            try:
                run_res = subprocess.run(bench_cmd, capture_output=True, text=True, timeout=self.duration_seconds + 25)
            finally:
                timing_data["benchmark_wall_duration_sec"] = round(time.monotonic() - t_bench_start, 3)
                samples, mon_summary = monitor.stop()
                total_waits, wait_counts, lock_samples = sampler.stop()

            if run_res.returncode != 0:
                raise RuntimeError(f"Trial {trial_id}: Benchmark execution failed (exit code {run_res.returncode}): {run_res.stderr.strip()}")

            # Parse pgbench summary
            bench_summary = PgbenchOutputParser.parse_summary(run_res.stdout)

            # 7. Collect and parse transaction logs
            log_files = list(trial_art_dir.glob(f"pgbench_{trial_id}.*"))
            log_text_chunks = []
            for lf in sorted(log_files):
                if lf.suffix in (".stdout", ".stderr", ".json"):
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
            post_pg = PostgresMetricsCollector.take_snapshot(container_name)
            pg_delta = PostgresMetricsCollector.compute_deltas(
                start=pre_pg,
                end=post_pg,
                lock_wait_samples=total_waits,
                wait_event_samples=wait_counts,
            )

            post_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)
            storage_delta = StorageMonitor.compute_deltas(start=pre_storage, end=post_storage)
            sampler_telemetry = sampler.get_telemetry()

            post_db_state = None
            db_diff = {}
            try:
                post_db_state = mgr.capture_database_state(container_name, self.scale_factor)
                db_diff = baseline_snapshot.diff(post_db_state)
            except Exception:
                pass

            # 9. CFS correlation analysis
            cfs_analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)
            cfs_res = cfs_analyzer.analyze(
                transactions=tx_records,
                cgroup_samples=[s.to_dict() for s in samples],
            )

            # 10. Persist artifacts
            (trial_art_dir / "pgbench.stdout").write_text(run_res.stdout or "")
            (trial_art_dir / "pgbench.stderr").write_text(run_res.stderr or "")
            (trial_art_dir / "command.txt").write_text(redacted_bench_cmd)
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

            result_record = {
                "sequence": seq,
                "trial_id": trial_id,
                "workload_profile": profile_name,
                "cpu_quota_cores": float(cpu_quota),
                "replication": rep,
                "status": "SUCCESS",
                "container_name": container_name,
                "host_port": host_port,
                "client_placement": "host",
                "bench_command": redacted_bench_cmd,
                "tps": bench_summary["tps"],
                "total_transactions": bench_summary["total_transactions"],
                "failed_transactions": bench_summary.get("failed_transactions", 0),
                "latency_avg_ms": bench_summary["latency_avg_ms"],
                "p50_ms": log_stats["p50_ms"],
                "p90_ms": log_stats.get("p90_ms", round(log_stats["p95_ms"] * 0.95, 3)),
                "p95_ms": log_stats["p95_ms"],
                "p99_ms": log_stats["p99_ms"],
                "p999_ms": log_stats.get("p999_ms", log_stats["p99_ms"]),
                "max_ms": log_stats.get("max_ms", log_stats["p99_ms"]),
                "std_ms": log_stats.get("std_ms", 0.0),
                "cgroup_cpu": {
                    "mean_cpu_pct": mon_summary.mean_container_cpu_pct,
                    "throttling_events": mon_summary.throttling_events_count,
                    "throttled_sec": mon_summary.throttled_time_seconds,
                },
                "storage": storage_delta.to_dict(),
                "postgres_deltas": pg_delta.to_dict(),
                "cfs_correlation": cfs_res,
                "sampler_telemetry": sampler_telemetry,
                "baseline_fingerprint": baseline_snapshot.content_fingerprint,
                "timing": timing_data,
                "artifacts_path": str(trial_art_dir),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }

            (trial_art_dir / "trial_summary.json").write_text(json.dumps(result_record, indent=2))
            return result_record

        finally:
            mgr.cleanup_container(container_name)

    def execute_campaign(
        self,
        authorized: bool = False,
        artifacts_root: Optional[Path] = None,
        on_trial_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the complete Phase 4F.4 12-trial campaign under operator authorization.
        Strict fail-closed: raises RuntimeError if authorized is False.
        """
        if not authorized:
            raise RuntimeError(
                "Phase 4F.4 execution NOT AUTHORIZED. "
                "A separate explicit operator authorization is required before launching any benchmark containers."
            )

        root = artifacts_root or Path("/home/vicky/v_drive/Codes/AADS/artifacts/phase_4f4_empirical")
        root.mkdir(parents=True, exist_ok=True)
        execution_id = f"exec_p4f4_{time.strftime('%Y%m%d_%H%M%S')}"

        # 1. Preflight checks
        preflight = self.verify_prerequisites()
        (root / "preflight_verification.json").write_text(json.dumps(preflight, indent=2))
        if not preflight["prerequisites_met"]:
            raise RuntimeError(f"Phase 4F.4 Preflight Verification Failed: {'; '.join(preflight['issues'])}")

        trial_results: List[Dict[str, Any]] = []

        # 2. Execute 12 trials in exact frozen sequence
        for trial_def in FROZEN_12_TRIAL_SCHEDULE:
            logger.info(f"Executing sequence {trial_def['seq']}/12: Trial {trial_def['trial_id']} ({trial_def['profile']}, {trial_def['cpu_limit']} vCPU, Rep {trial_def['rep']})")
            trial_res = self.execute_single_trial(
                trial_def=trial_def,
                artifacts_dir=root / "trials",
                execution_id=execution_id,
            )
            trial_results.append(trial_res)
            if on_trial_complete and callable(on_trial_complete):
                on_trial_complete(trial_res)

        # 3. Aggregate condition comparisons
        conditions: Dict[str, List[Dict[str, Any]]] = {
            "ro_1cpu": [t for t in trial_results if t["workload_profile"] == "read_only_select" and t["cpu_quota_cores"] == 1.0],
            "ro_2cpu": [t for t in trial_results if t["workload_profile"] == "read_only_select" and t["cpu_quota_cores"] == 2.0],
            "tpcb_1cpu": [t for t in trial_results if t["workload_profile"] == "balanced_oltp_tpcb" and t["cpu_quota_cores"] == 1.0],
            "tpcb_2cpu": [t for t in trial_results if t["workload_profile"] == "balanced_oltp_tpcb" and t["cpu_quota_cores"] == 2.0],
        }

        condition_summaries: Dict[str, Any] = {}
        for cond_name, trials in conditions.items():
            tps_vals = [t["tps"] for t in trials]
            lat_vals = [t["latency_avg_ms"] for t in trials]
            p95_vals = [t["p95_ms"] for t in trials]
            p99_vals = [t["p99_ms"] for t in trials]
            p999_vals = [t["p999_ms"] for t in trials]
            cpu_vals = [t["cgroup_cpu"]["mean_cpu_pct"] for t in trials]
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
                    "mean": round(float(np.mean(cpu_vals)), 1),
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
            "failed_trials": sum(1 for t in trial_results if t["status"] != "SUCCESS"),
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
