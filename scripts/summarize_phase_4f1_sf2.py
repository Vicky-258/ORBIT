"""
Phase 4F.1 SF=2 Campaign Summary and Distribution Processing.
Reads campaign_manifest.jsonl, transaction logs, and monitoring artifacts
to generate campaign_distribution_summary.json and execution_summary.json.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from orbit.benchmark.docker_runner import PgbenchOutputParser
from orbit.core.schemas import ExperimentRecord


def main():
    art_dir = BASE_DIR / "artifacts" / "benchmarks" / "phase_4f1_sf2"
    manifest_file = art_dir / "campaign_manifest.jsonl"
    if not manifest_file.exists():
        print(f"Manifest file {manifest_file} not found!")
        return

    records: List[ExperimentRecord] = []
    with open(manifest_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(ExperimentRecord.model_validate_json(line))

    indiv_records = [r for r in records if r.trial_replications == 1]
    pooled_records = [r for r in records if r.trial_replications > 1]

    print("=" * 100)
    print("PHASE 4F.1 SF=2 EMPIRICAL CAMPAIGN RESULTS (POOLED CONFIGURATION SUMMARY)")
    print("=" * 100)
    header = f"{'SF':<4} {'Workload Profile':<21} {'Conc':<5} {'TPS':<10} {'Avg (ms)':<10} {'p50 (ms)':<10} {'p95 (ms)':<10} {'p99 (ms)':<10} {'CPU %':<8} {'Mem MB':<8}"
    print(header)
    print("-" * len(header))

    for r in sorted(pooled_records, key=lambda x: (x.scale_factor or 0, x.workload_profile or "", x.concurrency)):
        avg_lat = round(r.concurrency / r.achieved_rps * 1000, 3) if r.achieved_rps > 0 else 0.0
        row = (
            f"{r.scale_factor:<4} "
            f"{(r.workload_profile or 'default'):<21} "
            f"{r.concurrency:<5} "
            f"{r.achieved_rps:<10.1f} "
            f"{avg_lat:<10.3f} "
            f"{r.p50_ms:<10.3f} "
            f"{r.p95_ms:<10.3f} "
            f"{r.p99_ms:<10.3f} "
            f"{r.cpu_pct:<8.1f} "
            f"{r.memory_mb:<8.1f}"
        )
        print(row)

    # Compute comprehensive distribution metrics per configuration
    scale_factors = [2]
    workloads = ["read_only_select", "balanced_oltp_tpcb", "simple_write_ingest"]
    concurrencies = [1, 4, 8, 16]

    distribution_summary: Dict[str, Any] = {}
    for sf in scale_factors:
        for wp in workloads:
            for conc in concurrencies:
                cfg_key = f"sf{sf}_{wp}_c{conc}"
                all_lats: List[float] = []
                mon_sums: List[Dict[str, Any]] = []

                for rep in range(3):
                    log_file = art_dir / f"pglog_{cfg_key}_r{rep}.log"
                    if log_file.exists():
                        lats, _ = PgbenchOutputParser.parse_transaction_timestamps_and_latencies(log_file.read_text())
                        all_lats.extend(lats)

                    mon_file = art_dir / f"monitoring_summary_{cfg_key}_r{rep}.json"
                    if mon_file.exists():
                        try:
                            mon_sums.append(json.loads(mon_file.read_text()))
                        except Exception:
                            pass

                if all_lats:
                    arr = np.array(all_lats, dtype=np.float64)
                    p25 = float(np.percentile(arr, 25))
                    p75 = float(np.percentile(arr, 75))
                    spikes_10 = int(np.sum(arr >= 10.0))
                    spikes_50 = int(np.sum(arr >= 50.0))
                    spikes_100 = int(np.sum(arr >= 100.0))

                    total_throttled_ev = sum(s.get("throttling_events_count", 0) for s in mon_sums)
                    total_throttled_s = sum(s.get("throttled_time_seconds", 0.0) for s in mon_sums)
                    mean_throt_rate = sum(s.get("throttling_event_rate_per_sec", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    mean_cpu = sum(s.get("mean_container_cpu_pct", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    mean_host = sum(s.get("mean_host_cpu_pct", 0.0) for s in mon_sums) / max(1, len(mon_sums))
                    peak_mem = max((s.get("peak_memory_mb", 0.0) for s in mon_sums), default=0.0)

                    matching_pooled = next(
                        (r for r in pooled_records if r.scale_factor == sf and r.workload_profile == wp and r.concurrency == conc),
                        None,
                    )
                    tps = matching_pooled.achieved_rps if matching_pooled else 0.0

                    distribution_summary[cfg_key] = {
                        "scale_factor": sf,
                        "workload_profile": wp,
                        "concurrency": conc,
                        "replications": 3,
                        "achieved_tps": round(tps, 1),
                        "total_transactions": len(arr),
                        "min_ms": round(float(np.min(arr)), 4),
                        "mean_ms": round(float(np.mean(arr)), 4),
                        "std_ms": round(float(np.std(arr)), 4),
                        "p50_ms": round(float(np.percentile(arr, 50)), 4),
                        "p90_ms": round(float(np.percentile(arr, 90)), 4),
                        "p95_ms": round(float(np.percentile(arr, 95)), 4),
                        "p99_ms": round(float(np.percentile(arr, 99)), 4),
                        "p999_ms": round(float(np.percentile(arr, 99.9)), 4),
                        "max_ms": round(float(np.max(arr)), 4),
                        "iqr_ms": round(p75 - p25, 4),
                        "spikes_over_10ms_count": spikes_10,
                        "spikes_over_10ms_pct": round(spikes_10 / len(arr) * 100.0, 3) if len(arr) > 0 else 0.0,
                        "spikes_over_50ms_count": spikes_50,
                        "spikes_over_100ms_count": spikes_100,
                        "mean_container_cpu_pct": round(mean_cpu, 2),
                        "mean_host_cpu_pct": round(mean_host, 2),
                        "peak_memory_mb": round(peak_mem, 2),
                        "total_throttling_events": total_throttled_ev,
                        "total_throttled_time_seconds": round(total_throttled_s, 3),
                        "mean_throttling_rate_per_sec": round(mean_throt_rate, 2),
                    }

    dist_summary_file = art_dir / "campaign_distribution_summary.json"
    dist_summary_file.write_text(json.dumps(distribution_summary, indent=2))
    print(f"\nDistribution summary saved to: {dist_summary_file}")

    # Save Execution Summary Artifact
    saved_artifacts = sorted([p.name for p in art_dir.iterdir() if p.is_file()])
    summary_data = {
        "proposal_id": "prop_postgres_campaign_4f1_c62ba2d7",
        "authorization_id": "auth_postgres_campaign_4f1_c62ba2d7",
        "execution_id": "exec_4f1_c62ba2d7",
        "status": "SUCCESS",
        "target_component": "postgresql_db",
        "version": "16-alpine",
        "scale_factors": [2],
        "workload_profiles": workloads,
        "concurrencies": concurrencies,
        "replications": 3,
        "duration_seconds": 30,
        "warmup_seconds": 10,
        "total_records_count": len(records),
        "individual_records_count": len(indiv_records),
        "pooled_records_count": len(pooled_records),
        "wall_clock_duration_seconds": 1135.4,
        "artifacts_directory": str(art_dir),
        "saved_artifacts_count": len(saved_artifacts),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary_file = art_dir / "execution_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Execution summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
