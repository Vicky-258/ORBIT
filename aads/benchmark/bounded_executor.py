"""
Bounded Benchmark Execution Interface (Phase 4D).
Safely executes authorized component benchmarks within strict resource envelopes.
Enforces:
- Explicit authorization gating (never runs real benchmarks without authorization record)
- Resource limits (CPU, memory, timeouts)
- Guaranteed cleanup of containers
- Strict parameter bounds (no arbitrary shell execution)
- Immediate persistence of raw measurement records with provenance
"""
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from aads.agent.schemas import (
    ExperimentProposal,
    AuthorizationRecord,
    AuthorizationStatus,
    ExperimentExecutionResult,
)
from aads.benchmark.docker_runner import DockerBenchmarkRunner
from aads.benchmark.synthetic_runner import SyntheticBenchmarkRunner
from aads.benchmark.runner_interface import BenchmarkRunner
from aads.core.schemas import ExperimentRecord
from aads.registry.component_registry import ComponentRegistry


class BoundedBenchmarkExecutor:
    """
    Executes benchmark proposals within verified authorization and safety boundaries.
    """

    def __init__(
        self,
        registry: Optional[ComponentRegistry] = None,
        docker_runner: Optional[DockerBenchmarkRunner] = None,
        synthetic_runner: Optional[SyntheticBenchmarkRunner] = None,
        default_execution_mode: str = "synthetic",
    ):
        self.registry = registry or ComponentRegistry()
        self.docker_runner = docker_runner or DockerBenchmarkRunner(
            cpu_limit="1.0",
            memory_limit="512m",
            timeout_seconds=60,
        )
        self.synthetic_runner = synthetic_runner or SyntheticBenchmarkRunner()
        self.default_execution_mode = default_execution_mode

    def execute_experiment(
        self,
        proposal: ExperimentProposal,
        authorization: Optional[AuthorizationRecord] = None,
    ) -> ExperimentExecutionResult:
        """
        Executes an experiment proposal if valid authorization is provided.
        Returns ExperimentExecutionResult with generated experiment record IDs.
        """
        exec_id = f"exec_{uuid.uuid4().hex[:10]}"
        start_t = time.perf_counter()
        now_str = datetime.now(timezone.utc).isoformat()

        # 1. Authorization check
        if authorization is None:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=None,
                status="UNAUTHORIZED",
                raw_records_count=0,
                experiment_ids=[],
                error_message="Execution blocked: No authorization record provided. Real or synthetic benchmarks require explicit authorization.",
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        if authorization.status != AuthorizationStatus.AUTHORIZED:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="UNAUTHORIZED",
                raw_records_count=0,
                experiment_ids=[],
                error_message=f"Execution blocked: Authorization record status is '{authorization.status.value}'.",
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        # 2. Select runner based on authorized mode
        mode = authorization.execution_mode.lower()
        runner: BenchmarkRunner
        provenance: str

        if mode == "docker":
            # Real container benchmark requested
            health = self.docker_runner.health_check()
            if not health.get("docker_available"):
                return ExperimentExecutionResult(
                    execution_id=exec_id,
                    proposal_id=proposal.proposal_id,
                    authorization_id=authorization.authorization_id,
                    status="FAILED",
                    raw_records_count=0,
                    experiment_ids=[],
                    error_message=f"Docker runner selected but daemon is unavailable: {health.get('docker_version')}",
                    execution_duration_seconds=round(time.perf_counter() - start_t, 3),
                    timestamp_utc=now_str,
                    provenance="none",
                )
            runner = self.docker_runner
            provenance = "measured_docker"
        else:
            # Synthetic fixture runner for credential-free and offline execution
            runner = self.synthetic_runner
            provenance = "synthetic_fixture"

        # 3. Parameter bounds enforcement
        concurrencies = [min(max(c, 1), 64) for c in (proposal.concurrency_levels or [1, 4, 8, 16])]
        read_ratio = max(0.0, min(1.0, proposal.read_ratio))
        replications = min(max(proposal.replications, 1), 5)

        # 4. Execute benchmark with timeout protection
        try:
            records: List[ExperimentRecord] = runner.run_benchmark_matrix(
                component_name=proposal.target_component,
                version=proposal.version,
                concurrency_levels=concurrencies,
                read_ratios=[read_ratio],
                target_rps_levels=[proposal.target_rps] if proposal.target_rps else None,
                replications=replications,
            )
        except Exception as exc:
            duration = round(time.perf_counter() - start_t, 3)
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="FAILED",
                raw_records_count=0,
                experiment_ids=[],
                error_message=f"Benchmark execution failed: {str(exc)}",
                execution_duration_seconds=duration,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                provenance=provenance,
            )

        duration = round(time.perf_counter() - start_t, 3)

        # 5. Immutably persist records to registry with authorization lineage
        saved_ids = []
        for r in records:
            # Stamp with authorization metadata
            r.notes = (r.notes or "") + f" [AuthID:{authorization.authorization_id}] [ExecID:{exec_id}]"
            self.registry.save_experiment(r)
            saved_ids.append(r.experiment_id)

        # Record authorization in registry if supported
        if hasattr(self.registry, "save_authorization"):
            self.registry.save_authorization(authorization)

        return ExperimentExecutionResult(
            execution_id=exec_id,
            proposal_id=proposal.proposal_id,
            authorization_id=authorization.authorization_id,
            status="SUCCESS",
            raw_records_count=len(records),
            experiment_ids=saved_ids,
            error_message=None,
            execution_duration_seconds=duration,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            provenance=provenance,
        )
