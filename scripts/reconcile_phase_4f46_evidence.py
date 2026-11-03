#!/usr/bin/env python3
"""
Phase 4F.4.6 — Offline Evidence Reconciliation Runner.

Executes reproducible evidence reconciliation of Phase 4F.4.5 empirical artifacts,
producing 8 validated JSON deliverables in artifacts/phase_4f46/reconciliation/.
Strict offline execution: no Docker, no pgbench, no model mutations.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aads.benchmark.evidence_reconciliation import run_full_reconciliation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase_4f46_reconciler")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 4F.4.6 Evidence Reconciliation")
    parser.add_argument(
        "--execution-dir",
        default="artifacts/phase_4f4_empirical/exec_p4f4_20261103_053428_525413_19491",
        help="Path to Phase 4F.4.5 campaign execution root",
    )
    parser.add_argument(
        "--manifest-path",
        default="artifacts/manifests/phase_4f4_execution_manifest.json",
        help="Path to frozen Phase 4F.4 execution manifest",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/phase_4f46/reconciliation",
        help="Directory to save reconciled JSON deliverables",
    )
    parser.add_argument(
        "--registry-path",
        default="data/registry.db",
        help="Path to active model registry database",
    )
    args = parser.parse_args()

    logger.info("Starting Phase 4F.4.6 Evidence Reconciliation...")
    logger.info("Execution directory: %s", args.execution_dir)
    logger.info("Output directory:    %s", args.output_dir)

    result = run_full_reconciliation(
        execution_dir=args.execution_dir,
        manifest_path=args.manifest_path,
        output_dir=args.output_dir,
        registry_path=args.registry_path,
    )

    summary = result["summary"]
    logger.info("Reconciliation Status: %s", summary["reconciliation_status"])
    logger.info("Trials Reconciled:     %d / %d", summary["total_trials_reconciled"], summary["total_trials_scheduled"])
    logger.info("Raw Transactions:      %d", summary["total_raw_transactions_parsed"])
    logger.info("Discrepancies:         %d", summary["total_discrepancies_identified"])
    logger.info("Model Registry:        %s (%d models)", summary["model_registry_integrity"]["status"], summary["model_registry_integrity"]["model_count"])
    logger.info("Manifest Verified:     %s", summary["manifest_verified"])

    print("\n" + "=" * 60)
    print("PHASE 4F.4.6 RECONCILIATION SUMMARY")
    print("=" * 60)
    print(f"Status:                    {summary['reconciliation_status']}")
    print(f"Manifest Verified:         {summary['manifest_verified']}")
    print(f"Total Trials Reconciled:   {summary['total_trials_reconciled']} / 12")
    print(f"Total Raw Transactions:    {summary['total_raw_transactions_parsed']:,}")
    print(f"Failed Transactions:       {summary['total_failed_transactions']}")
    print(f"Malformed Records:         {summary['total_malformed_records']}")
    print(f"Model Registry Intact:     {summary['model_registry_integrity']['intact']} (24 models)")
    print(f"Artifacts Generated:       {len(result['written_artifacts'])}")
    for name, path in result["written_artifacts"].items():
        print(f"  - {name} -> {path}")
    print("=" * 60)

    if summary["reconciliation_status"] != "COMPLETE":
        logger.error("Reconciliation did not complete cleanly!")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
