"""
Bounded Benchmark Execution Interface (Hardened for Phase 4D.2).
Safely executes authorized component benchmarks within strict resource envelopes.
Enforces:
- Strict authorization proposal ID binding (authorization.proposal_id == proposal.proposal_id)
- Single-use authorization lifecycle (replays rejected)
- Resource envelope validation (max runtime, allowed components, concurrency clamping)
- Timeout enforcement and guaranteed container cleanup
- Strict parameter bounds (no arbitrary shell execution)
- Immediate persistence of raw measurement records with provenance
"""
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set

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
    Fails closed on unauthorized, mismatched, or replayed requests.
    """

    ALLOWED_COMPONENTS = {"postgres_db", "redis_cache", "postgresql_db"}

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
            memory_limit="1024m",
            timeout_seconds=600,
        )
        self.synthetic_runner = synthetic_runner or SyntheticBenchmarkRunner()
        self.default_execution_mode = default_execution_mode
        self.used_authorization_ids: Set[str] = set()

    def execute_experiment(
        self,
        proposal: ExperimentProposal,
        authorization: Optional[AuthorizationRecord] = None,
    ) -> ExperimentExecutionResult:
        """
        Executes an experiment proposal if and only if valid, matching, unconsumed authorization is provided.
        Returns ExperimentExecutionResult with generated experiment record IDs and execution status.
        """
        exec_id = f"exec_{uuid.uuid4().hex[:10]}"
        start_t = time.perf_counter()
        now_str = datetime.now(timezone.utc).isoformat()

        # 1. Authorization presence check
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

        # 2. Single-use authorization check (Prevent authorization replay)
        if (
            authorization.authorization_id in self.used_authorization_ids
            or authorization.status == AuthorizationStatus.EXHAUSTED
        ):
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="AUTHORIZATION_EXHAUSTED",
                raw_records_count=0,
                experiment_ids=[],
                error_message=(
                    f"Execution blocked: Authorization record '{authorization.authorization_id}' "
                    "has already been consumed (single-use authorization lifecycle enforced)."
                ),
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        # Check registry for persisted authorization status if supported
        if hasattr(self.registry, "get_authorization"):
            existing_auth = self.registry.get_authorization(authorization.authorization_id)
            if existing_auth:
                auth_status = existing_auth.get("status") if isinstance(existing_auth, dict) else getattr(existing_auth, "status", None)
                status_str = auth_status.value if hasattr(auth_status, "value") else str(auth_status)
                if status_str == AuthorizationStatus.EXHAUSTED.value:
                    self.used_authorization_ids.add(authorization.authorization_id)
                    return ExperimentExecutionResult(
                        execution_id=exec_id,
                        proposal_id=proposal.proposal_id,
                        authorization_id=authorization.authorization_id,
                        status="AUTHORIZATION_EXHAUSTED",
                        raw_records_count=0,
                        experiment_ids=[],
                        error_message=(
                            f"Execution blocked: Authorization record '{authorization.authorization_id}' "
                            "is recorded as EXHAUSTED in the component registry."
                        ),
                        execution_duration_seconds=0.0,
                        timestamp_utc=now_str,
                        provenance="none",
                    )

        # 3. Authorization proposal ID binding check (Reject mismatched authorizations)
        if authorization.proposal_id != proposal.proposal_id:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="AUTHORIZATION_MISMATCH",
                raw_records_count=0,
                experiment_ids=[],
                error_message=(
                    f"Execution blocked: Authorization record was issued for proposal '{authorization.proposal_id}', "
                    f"which does not match target proposal '{proposal.proposal_id}'."
                ),
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        # 4. Authorization status check
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

        # 5. Component allowlist validation
        comp_key = proposal.target_component.strip().lower()
        if comp_key not in self.ALLOWED_COMPONENTS:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="UNAUTHORIZED_COMPONENT",
                raw_records_count=0,
                experiment_ids=[],
                error_message=f"Execution blocked: Component '{proposal.target_component}' is not in approved benchmark allowlist.",
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        # 6. Resource envelope check
        if proposal.timeout_seconds > authorization.max_runtime_seconds:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="RESOURCE_LIMIT_EXCEEDED",
                raw_records_count=0,
                experiment_ids=[],
                error_message=(
                    f"Execution blocked: Proposal requested timeout ({proposal.timeout_seconds:.1f}s) "
                    f"exceeds authorized max runtime limit ({authorization.max_runtime_seconds:.1f}s)."
                ),
                execution_duration_seconds=0.0,
                timestamp_utc=now_str,
                provenance="none",
            )

        # 7. Select runner based on authorized mode
        mode = authorization.execution_mode.lower()
        runner: BenchmarkRunner
        provenance: str

        if mode == "docker":
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
        elif mode == "synthetic":
            runner = self.synthetic_runner
            provenance = "synthetic_fixture"
        else:
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="UNSUPPORTED_EXECUTION_MODE",
                raw_records_count=0,
                experiment_ids=[],
                error_message=f"Execution mode '{authorization.execution_mode}' is not supported.",
                execution_duration_seconds=round(time.perf_counter() - start_t, 3),
                timestamp_utc=now_str,
                provenance="none",
            )

        # 8. Parameter bounds enforcement
        concurrencies = [min(max(c, 1), 64) for c in (proposal.concurrency_levels or [1, 4, 8, 16])]
        read_ratio = max(0.0, min(1.0, proposal.read_ratio))
        replications = min(max(proposal.replications, 1), 5)

        # 9. Execute benchmark with timeout protection
        try:
            records: List[ExperimentRecord] = runner.run_benchmark_matrix(
                component_name=proposal.target_component,
                version=proposal.version,
                concurrency_levels=concurrencies,
                read_ratios=[read_ratio],
                target_rps_levels=[proposal.target_rps] if proposal.target_rps else None,
                replications=replications,
                duration_seconds=getattr(proposal, "duration_seconds", 30),
                warmup_seconds=getattr(proposal, "warmup_seconds", 10),
                scale_factor=getattr(proposal, "scale_factor", 2),
                artifacts_dir=getattr(proposal, "artifacts_dir", None),
                execution_id=exec_id,
            )
        except (TimeoutError, subprocess.TimeoutExpired) as timeout_exc:
            duration = round(time.perf_counter() - start_t, 3)
            return ExperimentExecutionResult(
                execution_id=exec_id,
                proposal_id=proposal.proposal_id,
                authorization_id=authorization.authorization_id,
                status="TIMED_OUT",
                raw_records_count=0,
                experiment_ids=[],
                error_message=f"Benchmark execution timed out: {str(timeout_exc)}",
                execution_duration_seconds=duration,
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                provenance=provenance,
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

        # 10. Mark authorization as consumed (single-use lifecycle)
        self.used_authorization_ids.add(authorization.authorization_id)
        authorization.status = AuthorizationStatus.EXHAUSTED
        if hasattr(self.registry, "save_authorization"):
            self.registry.save_authorization(authorization)

        # 11. Immutably persist records to registry with authorization lineage
        saved_ids = []
        for r in records:
            r.proposal_id = proposal.proposal_id
            r.authorization_id = authorization.authorization_id
            r.execution_id = exec_id
            r.execution_mode = authorization.execution_mode
            r.notes = (r.notes or "") + f" [AuthID:{authorization.authorization_id}] [ExecID:{exec_id}]"
            self.registry.save_experiment(r)
            saved_ids.append(r.experiment_id)

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
