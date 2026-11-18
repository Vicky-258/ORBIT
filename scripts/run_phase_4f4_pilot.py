#!/usr/bin/env python3
"""
Phase 4F.4.5 — Authorized Live PostgreSQL Pilot Execution Script.

Executes the frozen 12-trial empirical campaign comparing PostgreSQL 16 performance
under 1.0 vCPU vs 2.0 vCPU quotas across read_only_select and balanced_oltp_tpcb workloads.

Strict methodology & safety invariants:
- Frozen deterministic randomized sequence (seed 4104)
- Cross-process atomic authorization consumption using fcntl.flock(LOCK_EX) and durable fsync
- Exact on-disk manifest integrity: byte-level SHA256 verification and single-parse execution
- Immutable container image reference using repository@digest pinning
- Unique execution-ID namespaced artifact directories
- Strict telemetry availability: missing CPU throttling is never defaulted to 0.0
- Client process cgroup isolation verification (/proc/<pid>/cgroup)
- Complete per-trial lifecycle cleanup across monitors, samplers, and containers
- Model promotion DISABLED; Registry mutation DISABLED
"""
import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orbit.benchmark.phase_4f4_runner import (
    DEFAULT_MANIFEST_PATH,
    EXPECTED_MANIFEST_SHA256,
    Phase4F4Runner,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Phase4F4Pilot")


def parse_args():
    parser = argparse.ArgumentParser(description="Phase 4F.4.5 Authorized Live PostgreSQL Pilot")
    parser.add_argument(
        "--authorization",
        type=str,
        default=str(PROJECT_ROOT / "artifacts" / "authorizations" / "phase_4f4_operator_authorization.json"),
        help="Path to validated CampaignAuthorizationRecord JSON file",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=str(DEFAULT_MANIFEST_PATH),
        help="Path to frozen Phase 4F.4 execution manifest JSON file",
    )
    parser.add_argument(
        "--artifacts-root",
        type=str,
        default=None,
        help="Custom artifacts root (defaults to artifacts/phase_4f4_empirical/{execution_id})",
    )
    return parser.parse_args()


def on_trial_complete(trial: dict):
    trial_id = trial.get("trial_id")
    seq = trial.get("sequence")
    profile = trial.get("workload_profile")
    cpu = trial.get("cpu_quota_cores")
    rep = trial.get("replication")
    status = trial.get("status")
    tps = trial.get("tps")
    lat = trial.get("latency_avg_ms")
    throt = trial.get("cgroup_cpu", {}).get("throttled_sec")
    throt_status = trial.get("cgroup_cpu", {}).get("throttling_status")

    logger.info(
        f"[TRIAL {seq}/12 COMPLETE] {trial_id} ({profile}, {cpu} vCPU, rep {rep}) "
        f"-> Status: {status} | TPS: {tps} | Latency: {lat} ms | "
        f"Throttled: {throt}s ({throt_status})"
    )


def main():
    args = parse_args()
    logger.info("=" * 70)
    logger.info("AADS Phase 4F.4.5 — Authorized Live PostgreSQL Pilot Execution")
    logger.info("=" * 70)
    logger.info(f"Manifest Path:      {args.manifest}")
    logger.info(f"Expected SHA256:    {EXPECTED_MANIFEST_SHA256}")
    logger.info(f"Authorization Path: {args.authorization}")

    auth_path = Path(args.authorization).resolve()
    if not auth_path.exists():
        logger.error(f"Authorization file not found at {auth_path}")
        sys.exit(1)

    runner = Phase4F4Runner()

    logger.info("Starting execution campaign under operator authorization...")
    t_start = time.time()
    try:
        summary = runner.execute_campaign(
            authorization=auth_path,
            manifest_path=Path(args.manifest),
            artifacts_root=Path(args.artifacts_root) if args.artifacts_root else None,
            on_trial_complete=on_trial_complete,
        )
        wall_time = time.time() - t_start
        logger.info("=" * 70)
        logger.info(f"CAMPAIGN EXECUTION {summary.get('manifest_status')} in {wall_time:.1f}s")
        logger.info(f"Execution ID:       {summary.get('execution_id')}")
        logger.info(f"Total Trials:       {summary.get('total_trials')}")
        logger.info(f"Successful Trials:  {summary.get('successful_trials')}")
        logger.info(f"Failed Trials:      {summary.get('failed_trials')}")
        logger.info("=" * 70)
        logger.info("Condition Summaries:")
        for cond_name, c_data in summary.get("conditions", {}).items():
            tps_mean = c_data.get("tps", {}).get("mean")
            lat_mean = c_data.get("latency_mean_ms", {}).get("mean")
            throt_info = c_data.get("throttled_seconds", {})
            throt_mean = throt_info.get("mean")
            throt_st = throt_info.get("status")
            logger.info(
                f"  - {cond_name:12s}: TPS={tps_mean:8.1f} | Latency={lat_mean:6.3f} ms | "
                f"Throttled={throt_mean}s ({throt_st})"
            )
        logger.info("-" * 70)
        logger.info("Comparisons (1.0 vs 2.0 vCPU):")
        for comp_name, comp_data in summary.get("comparisons", {}).items():
            logger.info(
                f"  - {comp_name:20s}: TPS delta={comp_data.get('tps_delta'):+8.1f} ({comp_data.get('tps_pct_change'):+6.2f}%) | "
                f"Latency delta={comp_data.get('mean_latency_delta_ms'):+6.3f} ms ({comp_data.get('mean_latency_pct_change'):+6.2f}%) | "
                f"Throttling reduction={comp_data.get('throttled_time_reduction_sec')}s"
            )
        logger.info("=" * 70)
    except Exception as e:
        wall_time = time.time() - t_start
        logger.error(f"Campaign execution failed after {wall_time:.1f}s: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
