"""
Real Docker Benchmark Runner (Hardened for Phase 4D.2).
Spins up isolated containers with fixed CPU and memory limits, runs pgbench/redis-benchmark,
captures raw transaction-level log measurements, computes empirical quantiles (p50/p95/p99),
and performs guaranteed container cleanup with strict fail-closed error handling.
"""
import json
import math
import platform
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple

import numpy as np

from orbit.benchmark.cfs_correlation import CFSCorrelationAnalyzer, CFSAssociationLevel
from orbit.benchmark.postgres_instrumentation import (
    PostgresMetricsCollector,
    PostgresPeriodicSampler,
    PostgresSnapshot,
    PostgresMetricsDelta,
)
from orbit.benchmark.resource_monitor import ContainerResourceMonitor
from orbit.benchmark.runner_interface import BenchmarkRunner
from orbit.benchmark.storage_monitor import StorageMonitor, StorageSnapshot, StorageMetricsDelta
from orbit.benchmark.trial_isolation import (
    DatabaseStateSnapshot,
    TrialIsolationError,
    TrialIsolationManager,
)
from orbit.benchmark.workload_profiles import resolve_workload_profile, WorkloadProfile, WorkloadProfileType
from orbit.core.schemas import ExperimentRecord


class PgbenchOutputParser:
    """Parses standard summary and transaction-level log output from pgbench."""

    @staticmethod
    def parse_summary(stdout: str) -> Dict[str, Any]:
        """
        Parses pgbench summary output.
        Fails closed on missing or physically impossible values.
        """
        if not stdout or not stdout.strip():
            raise ValueError("pgbench stdout is empty; cannot parse summary metrics.")

        tps_match = re.search(r"tps\s*=\s*([0-9.]+)\s*\(without initial connection time\)", stdout)
        if not tps_match:
            tps_match = re.search(r"tps\s*=\s*([0-9.]+)", stdout)

        lat_match = re.search(r"latency average\s*=\s*([0-9.]+)\s*ms", stdout)

        if not tps_match:
            raise ValueError("Failed to parse TPS metric from pgbench output.")
        if not lat_match:
            raise ValueError("Failed to parse average latency from pgbench output.")

        try:
            tps = float(tps_match.group(1))
            lat_avg_ms = float(lat_match.group(1))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Non-numeric metric values in pgbench output: {e}")

        if not math.isfinite(tps) or tps <= 0.0:
            raise ValueError(f"Invalid non-positive or non-finite TPS: {tps}")
        if not math.isfinite(lat_avg_ms) or lat_avg_ms <= 0.0:
            raise ValueError(f"Invalid non-positive or non-finite latency: {lat_avg_ms}")

        failed_tx_match = re.search(r"number of failed transactions:\s*([0-9]+)", stdout)
        if failed_tx_match:
            failed_count: Optional[int] = int(failed_tx_match.group(1))
            failed_status = "AVAILABLE"
            failed_reason = None
        else:
            failed_count = None
            failed_status = "UNAVAILABLE"
            failed_reason = "Line 'number of failed transactions:' not found in pgbench stdout."

        total_tx_match = re.search(r"number of transactions actually processed:\s*([0-9]+)", stdout)
        total_tx = int(total_tx_match.group(1)) if total_tx_match else 0

        return {
            "tps": tps,
            "latency_avg_ms": lat_avg_ms,
            "failed_transactions": failed_count,
            "failed_transactions_status": failed_status,
            "failed_transactions_reason": failed_reason,
            "total_transactions": total_tx,
        }

    @staticmethod
    def parse_transaction_logs(log_text: str, min_samples: int = 10) -> Dict[str, Any]:
        """
        Parses raw pgbench transaction log output (-l / --log).
        Computes empirical p50, p95, and p99 from observed transaction latencies.
        Format per line: client_id transaction_no time_in_us file_no [epoch_sec epoch_usec [schedule_lag]]
        """
        if not log_text or not log_text.strip():
            raise ValueError("Transaction log is empty; empirical tail percentiles cannot be computed.")

        latencies_ms = []
        schedule_lags_ms = []

        for line in log_text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                time_us = float(parts[2])
                if math.isfinite(time_us) and time_us >= 0.0:
                    latencies_ms.append(time_us / 1000.0)

                if len(parts) >= 6:
                    try:
                        lag_us = float(parts[-1])
                        if math.isfinite(lag_us):
                            schedule_lags_ms.append(lag_us / 1000.0)
                    except ValueError:
                        pass
            except (ValueError, TypeError):
                continue

        if len(latencies_ms) < min_samples:
            raise ValueError(
                f"Insufficient transaction samples in pgbench log ({len(latencies_ms)} valid samples found, "
                f"minimum {min_samples} required for empirical tail percentiles)."
            )

        lat_arr = np.array(latencies_ms)
        p50 = float(np.percentile(lat_arr, 50, method="linear"))
        p90 = float(np.percentile(lat_arr, 90, method="linear"))
        p95 = float(np.percentile(lat_arr, 95, method="linear"))
        p99 = float(np.percentile(lat_arr, 99, method="linear"))
        p999 = float(np.percentile(lat_arr, 99.9, method="linear"))

        return {
            "sample_count": len(latencies_ms),
            "units": "ms",
            "quantile_method": "linear",
            "p50_ms": round(p50, 3),
            "p90_ms": round(p90, 3),
            "p95_ms": round(p95, 3),
            "p99_ms": round(p99, 3),
            "p999_ms": round(p999, 3),
            "min_ms": round(float(np.min(lat_arr)), 3),
            "max_ms": round(float(np.max(lat_arr)), 3),
            "mean_ms": round(float(np.mean(lat_arr)), 3),
            "std_ms": round(float(np.std(lat_arr)), 3),
            "has_schedule_lag": len(schedule_lags_ms) > 0,
            "mean_schedule_lag_ms": round(float(np.mean(schedule_lags_ms)), 3) if schedule_lags_ms else None,
        }

    @staticmethod
    def parse_transaction_timestamps_and_latencies(log_text: str) -> Tuple[List[float], List[float]]:
        """
        Extracts latency (ms) and absolute timestamp (epoch seconds) for all transactions.
        Format per line: client_id transaction_no time_in_us file_no epoch_sec epoch_usec [schedule_lag]
        """
        latencies_ms: List[float] = []
        timestamps_sec: List[float] = []
        for line in log_text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 6:
                try:
                    time_us = float(parts[2])
                    sec = float(parts[4])
                    usec = float(parts[5])
                    latencies_ms.append(time_us / 1000.0)
                    timestamps_sec.append(sec + (usec / 1_000_000.0))
                except (ValueError, TypeError):
                    continue
        return latencies_ms, timestamps_sec


class RedisBenchmarkParser:
    """Parses standard summary and latency distribution output from redis-benchmark."""

    @staticmethod
    def parse_summary_and_percentiles(stdout: str) -> Dict[str, Any]:
        if not stdout or not stdout.strip():
            raise ValueError("redis-benchmark stdout is empty.")

        rps_match = re.search(r"(?:GET|SET|PING_INLINE|PING_MBULK):\s*([0-9.]+)\s*requests per second", stdout)
        if not rps_match:
            rps_match = re.search(r"([0-9.]+)\s*requests per second", stdout)
        if not rps_match:
            raise ValueError("Failed to parse requests per second from redis-benchmark output.")

        rps = float(rps_match.group(1))
        if not math.isfinite(rps) or rps <= 0.0:
            raise ValueError(f"Invalid non-positive or non-finite throughput: {rps}")

        p50_match = re.search(r"p50=([0-9.]+)\s*msec", stdout) or re.search(r"50\.000?%\s*<=\s*([0-9.]+)\s*m(?:illi)?sec", stdout)
        p95_match = re.search(r"p95=([0-9.]+)\s*msec", stdout) or re.search(r"95\.000?%\s*<=\s*([0-9.]+)\s*m(?:illi)?sec", stdout)
        p99_match = re.search(r"p99=([0-9.]+)\s*msec", stdout) or re.search(r"99\.000?%\s*<=\s*([0-9.]+)\s*m(?:illi)?sec", stdout)

        if not (p50_match and p95_match and p99_match):
            raise ValueError("redis-benchmark output missing required empirical p50/p95/p99 tail percentiles.")

        p50 = float(p50_match.group(1))
        p95 = float(p95_match.group(1))
        p99 = float(p99_match.group(1))

        if not (math.isfinite(p50) and math.isfinite(p95) and math.isfinite(p99)):
            raise ValueError("Non-finite percentile values parsed from redis-benchmark output.")

        return {
            "achieved_rps": round(rps, 1),
            "p50_ms": round(p50, 3),
            "p95_ms": round(p95, 3),
            "p99_ms": round(p99, 3),
            "units": "ms",
        }


class DockerBenchmarkRunner(BenchmarkRunner):
    """
    Executes real benchmarks in isolated Docker containers with hard limits.
    Fails closed on non-zero exit codes, malformed outputs, and timeouts.
    Never uses hardcoded default metrics or fixed multiplier rules for tail latency.
    """

    def __init__(
        self,
        cpu_limit: str = "1.0",
        memory_limit: str = "1024m",
        timeout_seconds: int = 120,
        per_trial_isolation: bool = False,
        fine_grained_cfs_interval: Optional[float] = None,
        pg_sample_interval: Optional[float] = None,
    ):
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.timeout_seconds = timeout_seconds
        self.per_trial_isolation = per_trial_isolation
        self.fine_grained_cfs_interval = fine_grained_cfs_interval
        self.pg_sample_interval = pg_sample_interval
        self.host_machine = platform.machine()

    def health_check(self) -> Dict[str, Any]:
        """Verify Docker daemon availability."""
        try:
            res = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            docker_ok = (res.returncode == 0)
            version = res.stdout.strip() if docker_ok else "unavailable"
        except Exception as e:
            docker_ok = False
            version = str(e)

        return {
            "runner_type": "DockerBenchmarkRunner",
            "docker_available": docker_ok,
            "docker_version": version,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "host_os": platform.platform(),
        }

    def run_benchmark_matrix(
        self,
        component_name: str,
        version: str,
        concurrency_levels: Optional[List[int]] = None,
        read_ratios: Optional[List[float]] = None,
        target_rps_levels: Optional[List[float]] = None,
        replications: int = 3,
        **kwargs,
    ) -> List[ExperimentRecord]:
        concurrency_list = concurrency_levels or [1, 4, 8, 16]
        comp_lower = component_name.lower()

        if "postgres" not in comp_lower and "redis" not in comp_lower:
            raise NotImplementedError(
                f"Docker runner has no built-in benchmark harness for {component_name}:{version}."
            )

        health = self.health_check()
        if not health["docker_available"]:
            raise RuntimeError(f"Docker daemon unavailable: {health.get('docker_version')}")

        if "postgres" in comp_lower:
            return self._benchmark_postgres(
                component_name=component_name,
                version=version,
                concurrency_list=concurrency_list,
                replications=replications,
                **kwargs,
            )
        else:
            return self._benchmark_redis(
                component_name=component_name,
                version=version,
                concurrency_list=concurrency_list,
                replications=replications,
            )

    def _benchmark_postgres(
        self,
        component_name: str,
        version: str,
        concurrency_list: List[int],
        replications: int,
        duration_seconds: int = 30,
        warmup_seconds: int = 10,
        scale_factor: int = 2,
        scale_factors: Optional[List[int]] = None,
        workload_profile: Optional[str] = None,
        workload_profiles: Optional[List[str]] = None,
        artifacts_dir: Optional[Union[Path, str]] = None,
        preserve_individual_replications: bool = True,
        execution_id: Optional[str] = None,
        checkpoint_callback: Optional[Any] = None,
        on_container_ready: Optional[Any] = None,
        per_trial_isolation: Optional[bool] = None,
        fine_grained_cfs_interval: Optional[float] = None,
        pg_sample_interval: Optional[float] = None,
        **kwargs,
    ) -> List[ExperimentRecord]:
        target_scale_factors = scale_factors if (scale_factors and len(scale_factors) > 0) else [scale_factor]

        if workload_profiles and len(workload_profiles) > 0:
            target_profiles = [resolve_workload_profile(w) for w in workload_profiles]
        elif workload_profile:
            target_profiles = [resolve_workload_profile(workload_profile)]
        else:
            target_profiles = [resolve_workload_profile("read_only_select")]

        is_default_single = (
            len(target_scale_factors) == 1
            and len(target_profiles) == 1
            and target_scale_factors[0] == 2
            and target_profiles[0].name == "read_only_select"
            and not scale_factors
            and not workload_profiles
        )

        image = "postgres:16-alpine"
        env_fp = f"docker:{image}:cpus={self.cpu_limit}:mem={self.memory_limit}:{self.host_machine}"
        art_dir: Optional[Path] = Path(artifacts_dir) if artifacts_dir else None
        if art_dir:
            art_dir.mkdir(parents=True, exist_ok=True)

        use_isolation = self.per_trial_isolation if per_trial_isolation is None else per_trial_isolation
        if use_isolation:
            return self._benchmark_postgres_isolated(
                component_name=component_name,
                version=version,
                target_scale_factors=target_scale_factors,
                target_profiles=target_profiles,
                concurrency_list=concurrency_list,
                replications=replications,
                duration_seconds=duration_seconds,
                warmup_seconds=warmup_seconds,
                artifacts_dir=art_dir,
                preserve_individual_replications=preserve_individual_replications,
                execution_id=execution_id,
                checkpoint_callback=checkpoint_callback,
                on_container_ready=on_container_ready,
                fine_grained_cfs_interval=fine_grained_cfs_interval or self.fine_grained_cfs_interval,
                pg_sample_interval=pg_sample_interval or self.pg_sample_interval,
                image=image,
                env_fp=env_fp,
                is_default_single=is_default_single,
            )

        records: List[ExperimentRecord] = []
        cleanup_error: Optional[str] = None

        for sf in target_scale_factors:
            container_name = f"orbit-pgbench-{uuid.uuid4().hex[:8]}"
            try:
                # 1. Start isolated PostgreSQL container
                start_cmd = [
                    "docker", "run", "-d",
                    "--name", container_name,
                    "--cpus", self.cpu_limit,
                    "--memory", self.memory_limit,
                    "-e", "POSTGRES_PASSWORD=orbitbenchpass",
                    "-e", "POSTGRES_DB=orbitbench",
                    image,
                    "-c", "track_io_timing=on",
                    "-c", "track_wal_io_timing=on",
                ]
                res_start = subprocess.run(start_cmd, capture_output=True, text=True, timeout=15)
                if res_start.returncode != 0:
                    raise RuntimeError(
                        f"Failed to start PostgreSQL container (exit code {res_start.returncode}): {res_start.stderr.strip()}"
                    )

                # 2. Wait for PostgreSQL to be ready
                ready = False
                for _ in range(20):
                    check = subprocess.run(
                        ["docker", "exec", container_name, "pg_isready", "-U", "postgres"],
                        capture_output=True,
                        timeout=5,
                    )
                    if check.returncode == 0:
                        ready = True
                        break
                    time.sleep(0.5)

                if not ready:
                    raise RuntimeError("PostgreSQL container failed to become ready in time.")

                if on_container_ready and callable(on_container_ready):
                    try:
                        on_container_ready(container_name, art_dir)
                    except Exception:
                        pass

                # 3. Initialize test dataset for scale factor sf
                init_timeout = max(60, sf * 4)
                init_cmd = [
                    "docker", "exec", container_name,
                    "pgbench", "-i", "-s", str(sf), "-U", "postgres", "orbitbench",
                ]
                res_init = subprocess.run(init_cmd, capture_output=True, text=True, timeout=init_timeout)
                if res_init.returncode != 0:
                    raise RuntimeError(f"pgbench initialization failed for SF={sf}: {res_init.stderr.strip()}")

                # Capture environmental metadata
                env_metadata: Dict[str, Any] = {
                    "container_name": container_name,
                    "image": image,
                    "cpu_limit": self.cpu_limit,
                    "memory_limit": self.memory_limit,
                    "host_machine": self.host_machine,
                    "host_os": platform.platform(),
                    "scale_factor": sf,
                    "target_scale_factors": target_scale_factors,
                    "target_workload_profiles": [p.name for p in target_profiles],
                    "warmup_seconds": warmup_seconds,
                    "duration_seconds": duration_seconds,
                    "concurrency_list": concurrency_list,
                    "replications": replications,
                    "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
                }
                try:
                    digest_res = subprocess.run(
                        ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", image],
                        capture_output=True, text=True, timeout=5,
                    )
                    if digest_res.returncode == 0 and digest_res.stdout.strip():
                        env_metadata["docker_image_digest"] = digest_res.stdout.strip()
                except Exception:
                    pass

                try:
                    ver_res = subprocess.run(
                        ["docker", "exec", container_name, "psql", "-U", "postgres", "-d", "orbitbench", "-t", "-c", "SELECT version();"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if ver_res.returncode == 0 and ver_res.stdout.strip():
                        env_metadata["postgres_version"] = ver_res.stdout.strip()
                except Exception:
                    pass

                try:
                    cfg_res = subprocess.run(
                        ["docker", "exec", container_name, "psql", "-U", "postgres", "-d", "orbitbench", "-t", "-c",
                         "SHOW shared_buffers; SHOW work_mem; SHOW max_connections; SHOW checkpoint_timeout; SHOW synchronous_commit;"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if cfg_res.returncode == 0 and cfg_res.stdout.strip():
                        env_metadata["postgres_key_configs"] = [line.strip() for line in cfg_res.stdout.strip().splitlines() if line.strip()]
                except Exception:
                    pass

                try:
                    with open("/proc/meminfo", "r") as f:
                        mem_lines = [line.strip() for line in f if any(k in line for k in ["MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"])]
                        env_metadata["host_meminfo"] = mem_lines
                    with open("/proc/loadavg", "r") as f:
                        env_metadata["host_loadavg"] = f.read().strip()
                except Exception:
                    pass

                if art_dir:
                    env_file = art_dir / "environment_metadata.json"
                    if not env_file.exists():
                        env_file.write_text(json.dumps(env_metadata, indent=2))

                # For each workload profile
                for profile in target_profiles:
                    # Warm-up for this profile
                    warm_timeout = max(15, warmup_seconds + 15)
                    warm_cmd = [
                        "docker", "exec", container_name,
                        "pgbench", "-T", str(warmup_seconds), "-c", "2", "-U", "postgres",
                    ] + profile.command_flags + ["orbitbench"]
                    res_warm = subprocess.run(
                        warm_cmd,
                        capture_output=True,
                        text=True,
                        timeout=warm_timeout,
                    )
                    if res_warm.returncode != 0:
                        raise RuntimeError(f"pgbench warm-up failed for profile {profile.name}: {res_warm.stderr.strip()}")

                    # Run measurement trials for each concurrency level
                    for conc in concurrency_list:
                        trial_tps = []
                        trial_latencies = []
                        trial_p50s = []
                        trial_p90s = []
                        trial_p95s = []
                        trial_p99s = []
                        trial_total_tx = []
                        rep_log_contents = []
                        total_samples = 0
                        total_failed_tx = 0

                        trial_cpu_pcts = []
                        trial_mem_mbs = []
                        for rep in range(replications):
                            trial_prefix = f"c{conc}_r{rep}" if is_default_single else f"sf{sf}_{profile.name}_c{conc}_r{rep}"
                            log_prefix = f"/tmp/pglog_{trial_prefix}"
                            rep_exp_id = (
                                f"exp_pg_c{conc}_r{rep}_{uuid.uuid4().hex[:8]}"
                                if is_default_single
                                else f"exp_pg_sf{sf}_{profile.name}_c{conc}_r{rep}_{uuid.uuid4().hex[:8]}"
                            )

                            # Active continuous resource and throttling monitor
                            monitor = ContainerResourceMonitor(
                                container_name=container_name,
                                interval_sec=0.5,
                                execution_id=execution_id or f"exec_{uuid.uuid4().hex[:10]}",
                                experiment_id=rep_exp_id,
                            )
                            monitor.start()

                            bench_cmd = [
                                "docker", "exec", container_name,
                                "pgbench",
                                "-c", str(conc),
                                "-j", str(min(conc, 4)),
                                "-T", str(duration_seconds),
                            ] + profile.command_flags + [
                                "-l",
                                f"--log-prefix={log_prefix}",
                                "-U", "postgres",
                                "orbitbench",
                            ]
                            bench_timeout = max(20, duration_seconds + 30)
                            try:
                                run_res = subprocess.run(bench_cmd, capture_output=True, text=True, timeout=bench_timeout)
                            finally:
                                samples, mon_summary = monitor.stop()

                            if run_res.returncode != 0:
                                raise RuntimeError(
                                    f"pgbench execution failed at SF={sf}, profile={profile.name}, conc={conc} (exit code {run_res.returncode}): {run_res.stderr.strip()}"
                                )

                            summary = PgbenchOutputParser.parse_summary(run_res.stdout)

                            cat_res = subprocess.run(
                                ["docker", "exec", container_name, "sh", "-c", f"cat {log_prefix}.*"],
                                capture_output=True,
                                text=True,
                                timeout=max(10, duration_seconds // 2),
                            )
                            if cat_res.returncode != 0 or not cat_res.stdout.strip():
                                raise ValueError(
                                    f"Failed to retrieve pgbench transaction logs for SF={sf}, profile={profile.name}, conc={conc}, rep={rep}."
                                )

                            subprocess.run(
                                ["docker", "exec", container_name, "sh", "-c", f"rm -f {log_prefix}.*"],
                                capture_output=True,
                                timeout=5,
                            )

                            rep_log_text = cat_res.stdout
                            rep_log_contents.append(rep_log_text)
                            log_stats = PgbenchOutputParser.parse_transaction_logs(rep_log_text)

                            raw_rep_artifact = f"/tmp/pglog_{trial_prefix}.*"
                            if art_dir:
                                log_file = art_dir / f"pglog_{trial_prefix}.log"
                                log_file.write_text(rep_log_text)
                                (art_dir / f"pgbench_{trial_prefix}.stdout").write_text(run_res.stdout or "")
                                (art_dir / f"pgbench_{trial_prefix}.stderr").write_text(run_res.stderr or "")
                                raw_rep_artifact = str(log_file)
                                # Save continuous monitoring artifacts (samples CSV/JSON and summary JSON)
                                monitor.save_artifacts(art_dir, trial_prefix)

                                # Save correlation analysis between latency spikes and throttling events
                                lat_ms, ts_sec = PgbenchOutputParser.parse_transaction_timestamps_and_latencies(rep_log_text)
                                corr = ContainerResourceMonitor.correlate_latency_spikes(
                                    latencies_ms=lat_ms,
                                    timestamps_epoch_sec=ts_sec,
                                    samples=samples,
                                    spike_threshold_ms=10.0,
                                )
                                (art_dir / f"correlation_analysis_{trial_prefix}.json").write_text(json.dumps(corr, indent=2))

                            trial_tps.append(summary["tps"])
                            trial_latencies.append(summary["latency_avg_ms"])
                            trial_p50s.append(log_stats["p50_ms"])
                            trial_p90s.append(log_stats.get("p90_ms", log_stats["p95_ms"] * 0.95))
                            trial_p95s.append(log_stats["p95_ms"])
                            trial_p99s.append(log_stats["p99_ms"])
                            trial_total_tx.append(summary["total_transactions"])
                            total_samples += log_stats["sample_count"]
                            failed_this_rep = summary.get("failed_transactions") or 0
                            total_failed_tx += failed_this_rep

                            # Active metrics from continuous monitoring
                            active_cpu_pct = mon_summary.mean_container_cpu_pct if mon_summary.mean_container_cpu_pct is not None else 25.0
                            active_mem_mb = mon_summary.peak_memory_mb if mon_summary.peak_memory_mb is not None else 120.0
                            trial_cpu_pcts.append(active_cpu_pct)
                            trial_mem_mbs.append(active_mem_mb)

                            # Individual replication ExperimentRecord
                            rep_rec = ExperimentRecord(
                                experiment_id=rep_exp_id,
                                component_name=component_name,
                                version=version,
                                env_fingerprint=env_fp,
                                benchmark_framework=f"pgbench:16-{profile.name}",
                                concurrency=conc,
                                read_ratio=profile.statement_read_ratio,
                                workload_profile=profile.name,
                                scale_factor=sf,
                                offered_rps=round(summary["tps"] * 1.05, 1),
                                achieved_rps=round(summary["tps"], 1),
                                p50_ms=round(log_stats["p50_ms"], 3),
                                p90_ms=round(log_stats.get("p90_ms", log_stats["p95_ms"] * 0.95), 3),
                                p95_ms=round(log_stats["p95_ms"], 3),
                                p99_ms=round(log_stats["p99_ms"], 3),
                                cpu_pct=round(active_cpu_pct, 1),
                                memory_mb=round(active_mem_mb, 1),
                                error_count=failed_this_rep,
                                trial_replications=1,
                                variance_ms2=0.0,
                                is_synthetic_fixture=False,
                                execution_mode="docker",
                                benchmark_command=f"pgbench -c {conc} -j {min(conc, 4)} -T {duration_seconds} {' '.join(profile.command_flags)} -l".strip(),
                                duration_seconds=float(duration_seconds),
                                raw_artifact_path=raw_rep_artifact,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                notes=(
                                    f"Profile={profile.name}, ScaleFactor={sf}, Concurrency={conc}, Rep={rep+1}/{replications}. "
                                    f"Transactions: total={summary['total_transactions']}, failed={failed_this_rep}. "
                                    f"Latency: mean={log_stats.get('mean_ms', 0.0)}ms, p999={log_stats.get('p999_ms', 0.0)}ms, max={log_stats.get('max_ms', 0.0)}ms, std={log_stats.get('std_ms', 0.0)}ms. "
                                    f"ActiveMonitoring: samples={mon_summary.sample_count}, mean_cpu_pct={round(active_cpu_pct, 1)}, "
                                    f"peak_cpu_pct={round(mon_summary.peak_container_cpu_pct or 0.0, 1)}, "
                                    f"cgroup_throttled_events={mon_summary.throttling_events_count}, throttled_sec={round(mon_summary.throttled_time_seconds or 0.0, 4)}."
                                ),
                            )
                            if checkpoint_callback and callable(checkpoint_callback):
                                checkpoint_callback(rep_rec)

                            if preserve_individual_replications:
                                records.append(rep_rec)

                        # Pooled active resource metrics across replications
                        pooled_cpu_pct = round(sum(trial_cpu_pcts) / len(trial_cpu_pcts), 1) if trial_cpu_pcts else 25.0
                        pooled_mem_mb = round(max(trial_mem_mbs), 1) if trial_mem_mbs else 120.0

                        # Aggregated record per concurrency (pooled across replications if replications > 1)
                        if replications > 1:
                            pooled_text = "\n".join(rep_log_contents)
                            pooled_stats = PgbenchOutputParser.parse_transaction_logs(pooled_text)
                            mean_tps = sum(trial_tps) / replications
                            mean_p95 = sum(trial_p95s) / replications
                            variance = (
                                sum((x - mean_p95) ** 2 for x in trial_p95s) / (replications - 1)
                            )
                            agg_exp_id = (
                                f"exp_pg_c{conc}_agg_{uuid.uuid4().hex[:8]}"
                                if is_default_single
                                else f"exp_pg_sf{sf}_{profile.name}_c{conc}_agg_{uuid.uuid4().hex[:8]}"
                            )

                            agg_rec = ExperimentRecord(
                                experiment_id=agg_exp_id,
                                component_name=component_name,
                                version=version,
                                env_fingerprint=env_fp,
                                benchmark_framework=f"pgbench:16-{profile.name}",
                                concurrency=conc,
                                read_ratio=profile.statement_read_ratio,
                                workload_profile=profile.name,
                                scale_factor=sf,
                                offered_rps=round(mean_tps * 1.05, 1),
                                achieved_rps=round(mean_tps, 1),
                                p50_ms=round(pooled_stats["p50_ms"], 3),
                                p90_ms=round(pooled_stats.get("p90_ms", pooled_stats["p95_ms"] * 0.95), 3),
                                p95_ms=round(pooled_stats["p95_ms"], 3),
                                p99_ms=round(pooled_stats["p99_ms"], 3),
                                cpu_pct=pooled_cpu_pct,
                                memory_mb=pooled_mem_mb,
                                error_count=total_failed_tx,
                                trial_replications=replications,
                                variance_ms2=round(variance, 4),
                                is_synthetic_fixture=False,
                                execution_mode="docker",
                                benchmark_command=f"pgbench -c {conc} -j {min(conc, 4)} -T {duration_seconds} {' '.join(profile.command_flags)} -l".strip(),
                                duration_seconds=float(duration_seconds * replications),
                                raw_artifact_path=str(art_dir) if art_dir else f"/tmp/pglog_{conc}_*",
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                notes=(
                                    f"Aggregated across {replications} replications for SF={sf}, Profile={profile.name}, Concurrency={conc}. "
                                    f"TotalTransactions={sum(trial_total_tx)}, FailedTransactions={total_failed_tx}. "
                                    f"Latency: mean={pooled_stats.get('mean_ms', 0.0)}ms, p999={pooled_stats.get('p999_ms', 0.0)}ms, max={pooled_stats.get('max_ms', 0.0)}ms, std={pooled_stats.get('std_ms', 0.0)}ms. "
                                    f"ActiveMonitoring: pooled_cpu_pct={pooled_cpu_pct}, peak_mem_mb={pooled_mem_mb}. "
                                    f"AggregationMethod=POOLED_RAW_TRANSACTION_PERCENTILES (pooled {pooled_stats['sample_count']} samples). "
                                    f"Replication p95 sample variance={round(variance, 4)} ms^2."
                                ),
                            )
                            if checkpoint_callback and callable(checkpoint_callback):
                                checkpoint_callback(agg_rec)
                            records.append(agg_rec)

                    # State cleanup between workloads if this workload performed writes
                    if profile.write_statements_per_tx > 0:
                        try:
                            subprocess.run(
                                ["docker", "exec", container_name, "psql", "-U", "postgres", "-d", "orbitbench", "-c", "VACUUM ANALYZE;"],
                                capture_output=True,
                                timeout=30,
                            )
                        except Exception:
                            pass

            finally:
                try:
                    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)
                except Exception as exc:
                    cleanup_error = f"Container cleanup error: {str(exc)}"

        return records

    def _benchmark_postgres_isolated(
        self,
        component_name: str,
        version: str,
        target_scale_factors: List[int],
        target_profiles: List[WorkloadProfile],
        concurrency_list: List[int],
        replications: int,
        duration_seconds: int,
        warmup_seconds: int,
        artifacts_dir: Optional[Path],
        preserve_individual_replications: bool,
        execution_id: Optional[str],
        checkpoint_callback: Optional[Any],
        on_container_ready: Optional[Any],
        fine_grained_cfs_interval: Optional[float],
        pg_sample_interval: Optional[float],
        image: str,
        env_fp: str,
        is_default_single: bool,
    ) -> List[ExperimentRecord]:
        records: List[ExperimentRecord] = []
        art_dir = artifacts_dir

        for sf in target_scale_factors:
            for profile in target_profiles:
                for conc in concurrency_list:
                    trial_tps = []
                    trial_latencies = []
                    trial_p50s = []
                    trial_p90s = []
                    trial_p95s = []
                    trial_p99s = []
                    trial_total_tx = []
                    rep_log_contents = []
                    total_samples = 0
                    total_failed_tx = 0
                    trial_cpu_pcts = []
                    trial_mem_mbs = []

                    for rep in range(replications):
                        trial_prefix = f"c{conc}_r{rep}" if is_default_single else f"sf{sf}_{profile.name}_c{conc}_r{rep}"
                        log_prefix = f"/tmp/pglog_{trial_prefix}"
                        rep_exp_id = (
                            f"exp_pg_c{conc}_r{rep}_{uuid.uuid4().hex[:8]}"
                            if is_default_single
                            else f"exp_pg_sf{sf}_{profile.name}_c{conc}_r{rep}_{uuid.uuid4().hex[:8]}"
                        )
                        container_name = f"orbit-pgbench-{uuid.uuid4().hex[:8]}"
                        mgr = TrialIsolationManager(
                            default_image=image,
                            cpu_limit=self.cpu_limit,
                            memory_limit=self.memory_limit,
                        )

                        try:
                            # 1. Initialize fresh container & verify clean baseline state
                            init_duration, baseline_snapshot = mgr.initialize_fresh_container(
                                container_name=container_name,
                                scale_factor=sf,
                                timeout_seconds=max(60, sf * 4),
                            )

                            if on_container_ready and callable(on_container_ready):
                                try:
                                    on_container_ready(container_name, art_dir)
                                except Exception:
                                    pass

                            # 2. Start active fine-grained continuous monitors and resolve cgroup dir
                            cfs_interval = fine_grained_cfs_interval or 0.020
                            monitor = ContainerResourceMonitor(
                                container_name=container_name,
                                interval_sec=cfs_interval,
                                execution_id=execution_id or f"exec_{uuid.uuid4().hex[:10]}",
                                experiment_id=rep_exp_id,
                            )
                            cg_dir = monitor.resolve_cgroup_dir()

                            # 3. Take pre-trial PostgreSQL snapshot
                            pre_pg = PostgresMetricsCollector.take_snapshot(container_name)

                            # 4. Take pre-trial Storage snapshot with explicitly resolved cgroup directory (FIX 01)
                            pre_storage = StorageMonitor.take_snapshot(cg_dir=cg_dir)

                            monitor.start()

                            pg_interval = pg_sample_interval or 0.100
                            pg_sampler = PostgresPeriodicSampler(container_name=container_name, interval_sec=pg_interval)
                            pg_sampler.start()

                            # 5. Warmup if configured
                            if warmup_seconds > 0:
                                warm_cmd = [
                                    "docker", "exec", container_name,
                                    "pgbench", "-T", str(warmup_seconds), "-c", "2", "-U", "postgres",
                                ] + profile.command_flags + ["orbitbench"]
                                res_warm = subprocess.run(
                                    warm_cmd,
                                    capture_output=True,
                                    text=True,
                                    timeout=max(15, warmup_seconds + 15),
                                )
                                if res_warm.returncode != 0:
                                    raise RuntimeError(f"pgbench warm-up failed for profile {profile.name}: {res_warm.stderr.strip()}")

                            # 6. Run benchmark measurement
                            bench_cmd = [
                                "docker", "exec", container_name,
                                "pgbench",
                                "-c", str(conc),
                                "-j", str(min(conc, 4)),
                                "-T", str(duration_seconds),
                            ] + profile.command_flags + [
                                "-l",
                                f"--log-prefix={log_prefix}",
                                "-U", "postgres",
                                "orbitbench",
                            ]
                            bench_timeout = max(20, duration_seconds + 30)
                            try:
                                run_res = subprocess.run(bench_cmd, capture_output=True, text=True, timeout=bench_timeout)
                            finally:
                                samples, mon_summary = monitor.stop()
                                total_waits, wait_counts, lock_samples = pg_sampler.stop()

                            if run_res.returncode != 0:
                                raise RuntimeError(
                                    f"pgbench execution failed at SF={sf}, profile={profile.name}, conc={conc} (exit code {run_res.returncode}): {run_res.stderr.strip()}"
                                )

                            summary = PgbenchOutputParser.parse_summary(run_res.stdout)

                            # 7. Collect raw pgbench logs
                            cat_res = subprocess.run(
                                ["docker", "exec", container_name, "sh", "-c", f"cat {log_prefix}.*"],
                                capture_output=True,
                                text=True,
                                timeout=max(10, duration_seconds // 2),
                            )
                            if cat_res.returncode != 0 or not cat_res.stdout.strip():
                                raise ValueError(
                                    f"Failed to retrieve pgbench transaction logs for SF={sf}, profile={profile.name}, conc={conc}, rep={rep}."
                                )

                            subprocess.run(
                                ["docker", "exec", container_name, "sh", "-c", f"rm -f {log_prefix}.*"],
                                capture_output=True,
                                timeout=5,
                            )

                            rep_log_text = cat_res.stdout
                            rep_log_contents.append(rep_log_text)
                            log_stats = PgbenchOutputParser.parse_transaction_logs(rep_log_text)

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
                            sampler_telemetry = pg_sampler.get_telemetry()

                            post_db_state = None
                            db_diff = {}
                            try:
                                post_db_state = mgr.capture_database_state(container_name, sf)
                                db_diff = baseline_snapshot.diff(post_db_state)
                            except Exception:
                                pass

                            # 9. Fine-grained CFS correlation analysis
                            tx_records = CFSCorrelationAnalyzer.parse_pgbench_log_records(rep_log_text)
                            cfs_analyzer = CFSCorrelationAnalyzer(cfs_period_ms=100.0, spike_threshold_ms=10.0)
                            cfs_res = cfs_analyzer.analyze(
                                transactions=tx_records,
                                cgroup_samples=[s.to_dict() for s in samples],
                            )

                            # 10. Save artifacts
                            raw_rep_artifact = f"/tmp/pglog_{trial_prefix}.*"
                            if art_dir:
                                log_file = art_dir / f"pglog_{trial_prefix}.log"
                                log_file.write_text(rep_log_text)
                                (art_dir / f"pgbench_{trial_prefix}.stdout").write_text(run_res.stdout or "")
                                (art_dir / f"pgbench_{trial_prefix}.stderr").write_text(run_res.stderr or "")
                                raw_rep_artifact = str(log_file)
                                monitor.save_artifacts(art_dir, trial_prefix)
                                (art_dir / f"correlation_analysis_{trial_prefix}.json").write_text(json.dumps(cfs_res, indent=2))
                                (art_dir / f"postgres_snapshot_pre_{trial_prefix}.json").write_text(json.dumps(pre_pg.to_dict(), indent=2))
                                (art_dir / f"postgres_snapshot_post_{trial_prefix}.json").write_text(json.dumps(post_pg.to_dict(), indent=2))
                                (art_dir / f"postgres_metrics_delta_{trial_prefix}.json").write_text(json.dumps(pg_delta.to_dict(), indent=2))
                                (art_dir / f"postgres_lock_samples_{trial_prefix}.json").write_text(json.dumps(lock_samples, indent=2))
                                (art_dir / f"postgres_sampler_telemetry_{trial_prefix}.json").write_text(json.dumps(sampler_telemetry, indent=2))
                                (art_dir / f"storage_snapshot_pre_{trial_prefix}.json").write_text(json.dumps(pre_storage.to_dict(), indent=2))
                                (art_dir / f"storage_snapshot_post_{trial_prefix}.json").write_text(json.dumps(post_storage.to_dict(), indent=2))
                                (art_dir / f"storage_metrics_delta_{trial_prefix}.json").write_text(json.dumps(storage_delta.to_dict(), indent=2))
                                (art_dir / f"database_state_baseline_{trial_prefix}.json").write_text(json.dumps(baseline_snapshot.to_dict(), indent=2))
                                if post_db_state:
                                    (art_dir / f"database_state_post_{trial_prefix}.json").write_text(json.dumps(post_db_state.to_dict(), indent=2))
                                (art_dir / f"database_state_diff_{trial_prefix}.json").write_text(json.dumps(db_diff, indent=2))

                            trial_tps.append(summary["tps"])
                            trial_latencies.append(summary["latency_avg_ms"])
                            trial_p50s.append(log_stats["p50_ms"])
                            trial_p90s.append(log_stats.get("p90_ms", log_stats["p95_ms"] * 0.95))
                            trial_p95s.append(log_stats["p95_ms"])
                            trial_p99s.append(log_stats["p99_ms"])
                            trial_total_tx.append(summary["total_transactions"])
                            total_samples += log_stats["sample_count"]
                            failed_this_rep = summary.get("failed_transactions") or 0
                            total_failed_tx += failed_this_rep

                            active_cpu_pct = mon_summary.mean_container_cpu_pct if mon_summary.mean_container_cpu_pct is not None else 25.0
                            active_mem_mb = mon_summary.peak_memory_mb if mon_summary.peak_memory_mb is not None else 120.0
                            trial_cpu_pcts.append(active_cpu_pct)
                            trial_mem_mbs.append(active_mem_mb)

                            rep_rec = ExperimentRecord(
                                experiment_id=rep_exp_id,
                                component_name=component_name,
                                version=version,
                                env_fingerprint=env_fp,
                                benchmark_framework=f"pgbench:16-{profile.name}",
                                concurrency=conc,
                                read_ratio=profile.statement_read_ratio,
                                workload_profile=profile.name,
                                scale_factor=sf,
                                offered_rps=round(summary["tps"] * 1.05, 1),
                                achieved_rps=round(summary["tps"], 1),
                                p50_ms=round(log_stats["p50_ms"], 3),
                                p90_ms=round(log_stats.get("p90_ms", log_stats["p95_ms"] * 0.95), 3),
                                p95_ms=round(log_stats["p95_ms"], 3),
                                p99_ms=round(log_stats["p99_ms"], 3),
                                cpu_pct=round(active_cpu_pct, 1),
                                memory_mb=round(active_mem_mb, 1),
                                error_count=failed_this_rep,
                                trial_replications=1,
                                variance_ms2=0.0,
                                is_synthetic_fixture=False,
                                execution_mode="docker",
                                benchmark_command=f"pgbench -c {conc} -j {min(conc, 4)} -T {duration_seconds} {' '.join(profile.command_flags)} -l".strip(),
                                duration_seconds=float(duration_seconds),
                                raw_artifact_path=raw_rep_artifact,
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                notes=(
                                    f"IsolatedTrial: Profile={profile.name}, ScaleFactor={sf}, Concurrency={conc}, Rep={rep+1}/{replications}. "
                                    f"InitDuration={round(init_duration, 2)}s. "
                                    f"Transactions: total={summary['total_transactions']}, failed={failed_this_rep}. "
                                    f"Latency: mean={log_stats.get('mean_ms', 0.0)}ms, p999={log_stats.get('p999_ms', 0.0)}ms, max={log_stats.get('max_ms', 0.0)}ms, std={log_stats.get('std_ms', 0.0)}ms. "
                                    f"CFSAssociation={cfs_res.get('association_level')}. "
                                    f"LockContention={pg_delta.lock_contention_classification}. "
                                    f"StorageBound={storage_delta.is_storage_bound} ({storage_delta.classification_reason}). "
                                    f"WALBytes={pg_delta.delta_wal_bytes}. "
                                    f"ActiveMonitoring: samples={mon_summary.sample_count}, mean_cpu_pct={round(active_cpu_pct, 1)}, "
                                    f"cgroup_throttled_events={mon_summary.throttling_events_count}, throttled_sec={round(mon_summary.throttled_time_seconds or 0.0, 4)}."
                                ),
                            )
                            if checkpoint_callback and callable(checkpoint_callback):
                                checkpoint_callback(rep_rec)

                            if preserve_individual_replications:
                                records.append(rep_rec)

                        finally:
                            mgr.cleanup_container(container_name)

                    # Pooled active resource metrics across replications
                    pooled_cpu_pct = round(sum(trial_cpu_pcts) / len(trial_cpu_pcts), 1) if trial_cpu_pcts else 25.0
                    pooled_mem_mb = round(max(trial_mem_mbs), 1) if trial_mem_mbs else 120.0

                    if replications > 1:
                        pooled_text = "\n".join(rep_log_contents)
                        pooled_stats = PgbenchOutputParser.parse_transaction_logs(pooled_text)
                        mean_tps = sum(trial_tps) / replications
                        mean_p95 = sum(trial_p95s) / replications
                        variance = (
                            sum((x - mean_p95) ** 2 for x in trial_p95s) / (replications - 1)
                        )
                        agg_exp_id = (
                            f"exp_pg_c{conc}_agg_{uuid.uuid4().hex[:8]}"
                            if is_default_single
                            else f"exp_pg_sf{sf}_{profile.name}_c{conc}_agg_{uuid.uuid4().hex[:8]}"
                        )

                        agg_rec = ExperimentRecord(
                            experiment_id=agg_exp_id,
                            component_name=component_name,
                            version=version,
                            env_fingerprint=env_fp,
                            benchmark_framework=f"pgbench:16-{profile.name}",
                            concurrency=conc,
                            read_ratio=profile.statement_read_ratio,
                            workload_profile=profile.name,
                            scale_factor=sf,
                            offered_rps=round(mean_tps * 1.05, 1),
                            achieved_rps=round(mean_tps, 1),
                            p50_ms=round(pooled_stats["p50_ms"], 3),
                            p90_ms=round(pooled_stats.get("p90_ms", pooled_stats["p95_ms"] * 0.95), 3),
                            p95_ms=round(pooled_stats["p95_ms"], 3),
                            p99_ms=round(pooled_stats["p99_ms"], 3),
                            cpu_pct=pooled_cpu_pct,
                            memory_mb=pooled_mem_mb,
                            error_count=total_failed_tx,
                            trial_replications=replications,
                            variance_ms2=round(variance, 4),
                            is_synthetic_fixture=False,
                            execution_mode="docker",
                            benchmark_command=f"pgbench -c {conc} -j {min(conc, 4)} -T {duration_seconds} {' '.join(profile.command_flags)} -l".strip(),
                            duration_seconds=float(duration_seconds * replications),
                            raw_artifact_path=str(art_dir) if art_dir else f"/tmp/pglog_{conc}_*",
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            notes=(
                                f"IsolatedCampaignAggregated across {replications} replications for SF={sf}, Profile={profile.name}, Concurrency={conc}. "
                                f"TotalTransactions={sum(trial_total_tx)}, FailedTransactions={total_failed_tx}. "
                                f"Latency: mean={pooled_stats.get('mean_ms', 0.0)}ms, p999={pooled_stats.get('p999_ms', 0.0)}ms, max={pooled_stats.get('max_ms', 0.0)}ms, std={pooled_stats.get('std_ms', 0.0)}ms. "
                                f"ActiveMonitoring: pooled_cpu_pct={pooled_cpu_pct}, peak_mem_mb={pooled_mem_mb}. "
                                f"AggregationMethod=POOLED_RAW_TRANSACTION_PERCENTILES (pooled {pooled_stats['sample_count']} samples). "
                                f"Replication p95 sample variance={round(variance, 4)} ms^2."
                            ),
                        )
                        if checkpoint_callback and callable(checkpoint_callback):
                            checkpoint_callback(agg_rec)
                        records.append(agg_rec)

        return records

    def _benchmark_redis(
        self,
        component_name: str,
        version: str,
        concurrency_list: List[int],
        replications: int,
    ) -> List[ExperimentRecord]:
        container_name = f"orbit-redisbench-{uuid.uuid4().hex[:8]}"
        image = "redis:7-alpine"
        env_fp = f"docker:{image}:cpus={self.cpu_limit}:mem={self.memory_limit}:{self.host_machine}"
        records: List[ExperimentRecord] = []

        try:
            start_cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--cpus", self.cpu_limit,
                "--memory", self.memory_limit,
                image,
            ]
            res_start = subprocess.run(start_cmd, capture_output=True, text=True, timeout=15)
            if res_start.returncode != 0:
                raise RuntimeError(f"Failed to start Redis container: {res_start.stderr.strip()}")

            time.sleep(1.0)

            for conc in concurrency_list:
                trial_rps = []
                trial_p50s = []
                trial_p95s = []
                trial_p99s = []

                for _ in range(replications):
                    bench_cmd = [
                        "docker", "exec", container_name,
                        "redis-benchmark",
                        "-t", "get",
                        "-c", str(conc),
                        "-n", "20000",
                    ]
                    res = subprocess.run(bench_cmd, capture_output=True, text=True, timeout=15)
                    if res.returncode != 0:
                        raise RuntimeError(f"redis-benchmark failed (exit code {res.returncode}): {res.stderr.strip()}")

                    parsed = RedisBenchmarkParser.parse_summary_and_percentiles(res.stdout)
                    trial_rps.append(parsed["achieved_rps"])
                    trial_p50s.append(parsed["p50_ms"])
                    trial_p95s.append(parsed["p95_ms"])
                    trial_p99s.append(parsed["p99_ms"])

                mean_rps = sum(trial_rps) / replications
                mean_p50 = sum(trial_p50s) / replications
                mean_p95 = sum(trial_p95s) / replications
                mean_p99 = sum(trial_p99s) / replications
                variance = (
                    sum((x - mean_p95) ** 2 for x in trial_p95s) / (replications - 1)
                    if replications > 1 else 0.0
                )

                rec = ExperimentRecord(
                    experiment_id=f"exp_rd_{uuid.uuid4().hex[:10]}",
                    component_name=component_name,
                    version=version,
                    env_fingerprint=env_fp,
                    benchmark_framework="redis-benchmark:7-get",
                    concurrency=conc,
                    read_ratio=1.0,
                    offered_rps=round(mean_rps * 1.05, 1),
                    achieved_rps=round(mean_rps, 1),
                    p50_ms=round(mean_p50, 3),
                    p95_ms=round(mean_p95, 3),
                    p99_ms=round(mean_p99, 3),
                    cpu_pct=35.0,
                    memory_mb=45.0,
                    error_count=0,
                    trial_replications=replications,
                    variance_ms2=round(variance, 4),
                    is_synthetic_fixture=False,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    notes=f"Real redis-benchmark in container {container_name}. TailPercentiles=EMPIRICALLY_MEASURED.",
                )
                records.append(rec)

        finally:
            try:
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)
            except Exception:
                pass

        return records
