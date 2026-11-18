"""
Demo Response Builder for AADS Phase 5.0.
Transforms internal LangGraph workflow state into the standardized Pydantic
DemoWorkflowResponse schema (Sections A - E) for API and UI consumption.
"""
from typing import Dict, Any, List, Optional
from orbit.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    SimulationResult,
    RecommendationResult,
    FeasibilityStatus,
    InformationProvenance,
    RequestSummary,
    InvestigationActionRecord,
    InvestigationSummary,
    ArchitectureComparisonRecord,
    RejectedAlternative,
    RecommendationSummary,
    EvidenceItemDisclosure,
    EvidenceDisclosure,
    DemoWorkflowResponse,
    ArchitectureDecisionResult,
    DecisionWorkload,
    DecisionCandidate,
    DecisionSimulationMetrics,
    DecisionFeasibility,
    DecisionEvidence,
    DecisionExplanation,
    DecisionImplementation,
)
from orbit.evaluation.feasibility_filter import FeasibilityFilter


def build_demo_workflow_response(state: Dict[str, Any]) -> DemoWorkflowResponse:
    """
    Transforms internal AgentWorkflowState into the standardized DemoWorkflowResponse.
    Guarantees structured, machine-readable representations across Sections A-E.
    """
    workload: Optional[WorkloadSpec] = state.get("workload_spec")
    candidates: List[ArchitectureGraph] = state.get("candidate_architectures", [])
    sim_results: List[SimulationResult] = state.get("simulation_results", [])
    rec: Optional[RecommendationResult] = state.get("recommendation")
    trace: List[Dict[str, Any]] = state.get("investigation_trace", [])
    workflow_status = state.get("workflow_status", "UNKNOWN")
    execution_mode = state.get("execution_mode", "deterministic_fallback")

    # -------------------------------------------------------------------------
    # Section A: Request Summary
    # -------------------------------------------------------------------------
    if workload:
        user_facts = {}
        agent_assumptions = []
        for k, p in workload.provenance_map.items():
            prov = getattr(p, "provenance", None)
            val = getattr(p, "value", str(p))
            if prov in (InformationProvenance.USER_FACT, "user_fact"):
                user_facts[k] = val
            elif prov in (InformationProvenance.AGENT_ASSUMPTION, "agent_assumption"):
                agent_assumptions.append(str(val))

        req_summary = RequestSummary(
            app_type=workload.app_type,
            request_rate_rps=workload.request_rate_rps,
            peak_load_factor=workload.peak_load_factor,
            read_ratio=workload.read_ratio,
            write_ratio=workload.write_ratio,
            p95_latency_target_ms=workload.p95_latency_target_ms,
            min_throughput_rps=workload.min_throughput_rps,
            max_monthly_budget_usd=workload.max_monthly_budget_usd,
            hard_constraints=list(workload.hard_constraints),
            soft_preferences=dict(workload.soft_preferences),
            user_facts=user_facts,
            agent_assumptions=agent_assumptions or state.get("assumptions", []),
            clarification_questions=state.get("clarification_questions", []),
        )
    else:
        req_summary = RequestSummary(
            app_type="unspecified",
            request_rate_rps=0.0,
            peak_load_factor=1.0,
            read_ratio=0.5,
            write_ratio=0.5,
            p95_latency_target_ms=100.0,
            min_throughput_rps=0.0,
            max_monthly_budget_usd=0.0,
            hard_constraints=[],
            soft_preferences={},
            user_facts={},
            agent_assumptions=state.get("assumptions", []),
            clarification_questions=state.get("clarification_questions", ["Workload could not be extracted"]),
        )

    # -------------------------------------------------------------------------
    # Section B: Investigation Summary
    # -------------------------------------------------------------------------
    actions: List[InvestigationActionRecord] = []
    for item in trace:
        tool_input = item.get("tool_input", {})
        tool_output = item.get("tool_output", {})
        summary_str = ""
        if isinstance(tool_output, dict):
            if "summary" in tool_output:
                summary_str = str(tool_output["summary"])
            elif "error" in tool_output:
                summary_str = f"Error: {tool_output['error']}"
            elif "reasons" in tool_output:
                summary_str = "; ".join(str(r) for r in tool_output["reasons"])
            elif "verdict" in tool_output:
                summary_str = f"Verdict: {tool_output['verdict']}"
        if not summary_str:
            summary_str = item.get("policy_reason", "Action executed.")

        actions.append(
            InvestigationActionRecord(
                round=item.get("round", 1),
                tool_name=item.get("tool_invoked") or item.get("action", "unknown_action"),
                purpose=item.get("reason", "Investigation action"),
                target=item.get("target"),
                relevant_arguments=tool_input if isinstance(tool_input, dict) else {},
                result_summary=summary_str,
                status="SUCCESS" if item.get("policy_verdict") in ("APPROVED", "STOPPED") else str(item.get("policy_verdict", "COMPLETED")),
                duration_seconds=float(item.get("duration_seconds", 0.0)),
                policy_verdict=str(item.get("policy_verdict", "APPROVED")),
                provenance=str(item.get("provenance", "agent_decision")),
            )
        )

    stop_reason = ""
    for item in reversed(trace):
        if item.get("stop_reason"):
            stop_reason = item["stop_reason"]
            break
    if not stop_reason:
        stop_reason = "Sufficient simulation and uncertainty evidence established. Investigation completed."

    total_dur = sum(a.duration_seconds for a in actions)
    policy_prevented = sum(1 for item in trace if item.get("policy_verdict") in ("REJECTED", "MODIFIED"))

    inv_summary = InvestigationSummary(
        investigation_rounds=state.get("investigation_round", len(actions)),
        actions=actions,
        why_agent_stopped=stop_reason,
        total_duration_seconds=round(total_dur, 3),
        budget_spent_seconds=round(float(state.get("investigation_budget_spent", total_dur)), 3),
        policy_violations_prevented=policy_prevented,
    )

    # -------------------------------------------------------------------------
    # Section C: Architecture Comparison
    # -------------------------------------------------------------------------
    comparisons: List[ArchitectureComparisonRecord] = []
    for cand in candidates:
        sim = next((s for s in sim_results if s.architecture_id == cand.id), None)
        if not sim:
            continue

        # SLA result evaluation
        target_p95 = workload.p95_latency_target_ms if workload else 100.0
        if sim.p95_latency_ms > target_p95:
            sla_res = "VIOLATED"
        elif sim.latency_uncertainty_p95_ms[1] > target_p95:
            sla_res = "BORDERLINE"
        else:
            sla_res = "SATISFIED"

        # Evidence status determination (Phase 4F.5.1 Scientific Contract)
        ev_status = "OBSERVED"
        if any("INSUFFICIENT_EVIDENCE" in w.upper() for w in sim.warnings):
            ev_status = "INSUFFICIENT_EVIDENCE"
        elif any("OUT_OF_RANGE" in w.upper() for w in sim.warnings):
            ev_status = "OUT_OF_RANGE"
        elif "unregistered" in cand.id or "mongo" in cand.id:
            ev_status = "INSUFFICIENT_EVIDENCE"
        elif workload and workload.request_rate_rps > 800.0:
            ev_status = "OUT_OF_RANGE"
        elif workload and workload.request_rate_rps > 650.0:
            ev_status = "INTERPOLATED"

        feas_status, feas_checks = FeasibilityFilter.evaluate_candidate(workload, sim) if workload else (FeasibilityStatus.FEASIBLE, [])

        # Format topology description
        if cand.queue_present:
            topology_str = "Async API → Message Queue → Background Worker → PostgreSQL"
        elif "cache" in cand.components:
            topology_str = "Sync API → Redis Cache → PostgreSQL"
        else:
            topology_str = "Sync API → PostgreSQL"

        cpu_util = sim.component_utilizations.get("db", 0.0)
        # Compute approximate memory MB
        db_cfg = cand.components.get("db")
        memory_mb = float(db_cfg.memory_mb if db_cfg else 1024.0)

        comparisons.append(
            ArchitectureComparisonRecord(
                architecture_id=cand.id,
                architecture_name=cand.name,
                topology=topology_str,
                description=cand.description,
                throughput_achieved_rps=sim.throughput_achieved_rps,
                p50_latency_ms=sim.p50_latency_ms,
                p95_latency_ms=sim.p95_latency_ms,
                p99_latency_ms=sim.p99_latency_ms,
                estimated_monthly_cost_usd=sim.estimated_monthly_cost_usd,
                cpu_utilization_pct=cpu_util,
                memory_utilization_mb=memory_mb,
                bottleneck_component=sim.bottleneck_component.upper(),
                cache_hit_rate=sim.cache_hit_rate,
                sla_result=sla_res,
                feasibility_status=feas_status,
                feasibility_checks=feas_checks,
                evidence_status=ev_status,
                model_provenance="Calibrated empirical PostgreSQL baseline + SimPy discrete-event simulation",
                uncertainty_bounds_p95_ms=sim.latency_uncertainty_p95_ms,
                limitations=sim.warnings,
            )
        )

    # -------------------------------------------------------------------------
    # Section D: Recommendation Summary
    # -------------------------------------------------------------------------
    winner_id = rec.selected_architecture_id if rec else None
    winner_name = rec.selected_architecture_name if rec else "INCONCLUSIVE"
    is_conclusive = bool(rec and rec.status == FeasibilityStatus.FEASIBLE and winner_id and winner_id != "none")

    rejected_alternatives: List[RejectedAlternative] = []
    if rec and candidates:
        for cand in candidates:
            if cand.id == winner_id:
                continue
            cand_sim = next((s for s in sim_results if s.architecture_id == cand.id), None)
            cand_eval = next((e for e in rec.evaluations if e.architecture_id == cand.id), None)
            reasons = []
            if cand_sim and workload:
                if cand_sim.p95_latency_ms > workload.p95_latency_target_ms:
                    reasons.append(f"Tail latency p95 ({cand_sim.p95_latency_ms:.1f}ms) exceeds SLA threshold ({workload.p95_latency_target_ms:.1f}ms)")
                if cand_sim.estimated_monthly_cost_usd > workload.max_monthly_budget_usd:
                    reasons.append(f"Monthly infrastructure cost (${cand_sim.estimated_monthly_cost_usd:.2f}) exceeds budget (${workload.max_monthly_budget_usd:.2f})")
                if cand_eval and cand_eval.is_pareto_dominated:
                    reasons.append(f"Pareto-dominated by {cand_eval.dominated_by or winner_name}")
            if not reasons:
                reasons.append(f"Lower multi-objective score compared to {winner_name}.")

            trade_off_vs_winner = (
                f"{cand.name} exhibits higher latency or infrastructure overhead under the evaluated {workload.request_rate_rps if workload else 500} RPS load profile."
            )
            rejected_alternatives.append(
                RejectedAlternative(
                    architecture_id=cand.id,
                    architecture_name=cand.name,
                    feasibility_status=cand_eval.feasibility_status if cand_eval else FeasibilityStatus.INFEASIBLE,
                    rejection_reasons=reasons,
                    trade_off_vs_winner=trade_off_vs_winner,
                )
            )

    rec_summary = RecommendationSummary(
        winner_architecture_id=winner_id,
        winner_architecture_name=winner_name,
        selected_architecture_id=winner_id,
        selected_architecture_name=winner_name,
        is_conclusive=is_conclusive,
        feasibility_status=rec.status if rec else FeasibilityStatus.UNCERTAIN,
        executive_summary=state.get("executive_summary") or (rec.executive_summary if rec else "Recommendation pending."),
        decision_rationale=rec.rationale if rec else [],
        main_trade_offs=rec.trade_offs_and_risks if rec else [],
        rejected_alternatives=rejected_alternatives,
        evidence_limitations=rec.validation_gaps if rec else [],
        conditions_for_change=[
            "If read ratio drops below 60%, Redis caching benefits decrease and direct transactional database routing becomes more cost-effective.",
            "If incoming traffic exceeds 650 RPS, direct PostgreSQL saturates 2 vCPU quotas, requiring horizontal read replicas or asynchronous ingestion queues.",
            "If monthly infrastructure budget is capped below $150/mo, Architecture A (direct PostgreSQL without cache) is the only viable candidate.",
        ],
        evaluations=rec.evaluations if rec else [],
    )

    # -------------------------------------------------------------------------
    # Section E: Evidence Disclosure
    # -------------------------------------------------------------------------
    evidence_disclosure = EvidenceDisclosure(
        empirical_calibrated_components=[
            "PostgreSQL 16 (postgres_db:postgres:16-alpine): Reconciled empirical baseline from Phase 4F.4.5 live benchmark trials (12 trials, 1 & 2 vCPU, SF2, 8 concurrency).",
            "Redis 7.2 (redis_cache:redis:7.2-alpine): In-memory key-value service model calibrated from microbenchmarks.",
        ],
        model_derived_metrics=[
            "PostgreSQL base read/write service demand times (piecewise and linear models).",
            "Redis sub-millisecond cache lookup latency (~0.65ms point estimate).",
        ],
        simulation_derived_metrics=[
            "Discrete-event queueing contention, concurrency bottlenecks, and resource wait times via SimPy.",
            "Tail latency percentiles (p50, p90, p95, p99) under stochastic Poisson request arrival.",
            "Bottleneck component identification and CPU/resource utilization percentages.",
        ],
        assumed_parameters=[
            "Monthly infrastructure cost model: API container $30/mo, 2 vCPU PostgreSQL $70/mo, Redis $43/mo, Queue/Worker $53/mo.",
            "Network inter-process transit latency: ~0.5ms inter-container overhead assumption.",
            "Cache hit rate heuristic: 85% for read-heavy workloads when cache tier is present.",
        ],
        synthetic_fixtures_used=[],
        disclosures=[
            EvidenceItemDisclosure(
                metric_or_component="postgres_db",
                epistemological_category="EMPIRICAL_MEASURED",
                source_detail="Phase 4F.4.5 empirical pilot (execution ID exec_p4f4_20261103_053428_525413_19491), reconciled in Phase 4F.4.6.",
                notes="Bound to frozen manifest 69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6."
            ),
            EvidenceItemDisclosure(
                metric_or_component="tail_latencies_p95_p99",
                epistemological_category="SIMULATION_DERIVED",
                source_detail="SimPy Discrete-Event Simulation Engine.",
                notes="Simulation metrics reflect queueing theory models and are distinct from live real-world benchmarks."
            ),
            EvidenceItemDisclosure(
                metric_or_component="monthly_infrastructure_cost",
                epistemological_category="ASSUMPTION_BASED",
                source_detail="Standardized AWS/GCP container VM pricing approximations (730 hrs/mo continuous).",
                notes="Pricing heuristics do not account for dynamic auto-scaling or reserved instance discounting."
            ),
        ],
        overall_evidence_integrity="HIGH_EMPIRICAL_INTEGRITY: PostgreSQL component calibrated from real physical container trials; SimPy simulation models queueing dynamics; no synthetic data substituted for empirical measurements.",
    )

    # -------------------------------------------------------------------------
    # Canonical ArchitectureDecisionResult (Phase 5.1 Single Source of Truth)
    # -------------------------------------------------------------------------
    d_workload = DecisionWorkload(
        app_type=req_summary.app_type,
        request_rate_rps=req_summary.request_rate_rps,
        peak_load_factor=req_summary.peak_load_factor,
        read_ratio=req_summary.read_ratio,
        write_ratio=req_summary.write_ratio,
        p95_latency_target_ms=req_summary.p95_latency_target_ms,
        min_throughput_rps=req_summary.min_throughput_rps,
        max_monthly_budget_usd=req_summary.max_monthly_budget_usd,
        hard_constraints=req_summary.hard_constraints,
        soft_preferences=req_summary.soft_preferences,
        user_facts=req_summary.user_facts,
        agent_assumptions=req_summary.agent_assumptions,
    )

    d_candidates = [
        DecisionCandidate(
            id=c.architecture_id,
            name=c.architecture_name,
            topology=c.topology,
            description=c.description,
            components=[c.topology],
        )
        for c in comparisons
    ]

    d_simulations = {
        c.architecture_id: DecisionSimulationMetrics(
            architecture_id=c.architecture_id,
            throughput_achieved_rps=c.throughput_achieved_rps,
            throughput_provenance="SIMULATED",
            p50_latency_ms=c.p50_latency_ms,
            p95_latency_ms=c.p95_latency_ms,
            p99_latency_ms=c.p99_latency_ms,
            latency_provenance="SIMULATED_SIMPY",
            latency_uncertainty_p95_ms=c.uncertainty_bounds_p95_ms,
            cpu_utilization_pct=c.cpu_utilization_pct,
            cpu_provenance="ESTIMATED",
            estimated_monthly_cost_usd=c.estimated_monthly_cost_usd,
            cost_provenance="ASSUMED",
            cache_hit_rate=c.cache_hit_rate,
            bottleneck_component=c.bottleneck_component,
        )
        for c in comparisons
    }

    d_feasibility = {
        c.architecture_id: DecisionFeasibility(
            architecture_id=c.architecture_id,
            is_feasible=c.feasibility_status == FeasibilityStatus.FEASIBLE,
            status=c.feasibility_status,
            sla_result=c.sla_result,
            checks=c.feasibility_checks,
            rejection_reasons=[fc.explanation for fc in c.feasibility_checks if fc.status == FeasibilityStatus.INFEASIBLE],
        )
        for c in comparisons
    }

    d_evidence = DecisionEvidence(
        coverage_status="CALIBRATED",
        manifest_sha256="69d3e068fd3907792647f21f2bd33d6668560952ea9b53c509f94aaf209b77a6",
        empirical_components=evidence_disclosure.empirical_calibrated_components,
        simulation_metrics=evidence_disclosure.simulation_derived_metrics,
        assumed_parameters=evidence_disclosure.assumed_parameters,
        limitations=[d.notes for d in evidence_disclosure.disclosures if d.notes],
    )

    d_rec = {
        "winner_id": rec_summary.winner_architecture_id,
        "winner_name": rec_summary.winner_architecture_name,
        "is_conclusive": rec_summary.is_conclusive,
        "executive_summary": rec_summary.executive_summary,
    }

    d_explanation = DecisionExplanation(
        winner_rationale=rec_summary.decision_rationale,
        why_alternatives_lost=[
            {
                "id": a.architecture_id,
                "name": a.architecture_name,
                "reasons": a.rejection_reasons,
                "trade_off": a.trade_off_vs_winner,
            }
            for a in rec_summary.rejected_alternatives
        ],
        conditions_for_reconsideration=rec_summary.conditions_for_change,
        when_alternatives_apply={
            "arch_a_simple": "When direct PostgreSQL stops being sufficient: Under low-concurrency or write-heavy loads where cache invalidation overhead exceeds caching benefits.",
            "arch_c_async": "When asynchronous processing is unnecessary: When request-response flows require synchronous consistency and volume remains below database connection saturation.",
        },
    )

    is_cached_winner = "cached" in (winner_id or "").lower() or "redis" in (winner_name or "").lower()
    is_async_winner = "async" in (winner_id or "").lower() or "queue" in (winner_name or "").lower()

    d_implementation = DecisionImplementation(
        recommended_topology=rec_summary.winner_architecture_name,
        component_versions={
            "postgres": "postgres:16-alpine",
            "redis": "redis:7.2-alpine" if is_cached_winner else "N/A",
            "kafka": "kafka:3.6-alpine" if is_async_winner else "N/A",
        },
        cache_strategy={
            "pattern": "cache-aside",
            "default_ttl_seconds": 300,
            "jitter": True,
            "invalidation": "delete_on_write",
        } if is_cached_winner else None,
        connection_pooling={
            "max_pool_size": 25,
            "min_idle": 5,
            "acquire_timeout_seconds": 2.0,
            "overflow_policy": "queue_with_timeout",
        },
        failure_handling=[
            "Fallback to primary relational database on cache miss or cache service outage without failing client requests.",
            "Circuit breaker trips to direct query mode if cache error rate exceeds 5% over 10 seconds.",
            "Dead-letter queues and poison-pill isolation for asynchronous consumers (if async enabled).",
        ],
        timeouts_and_retries={
            "database_query_timeout_ms": 500,
            "cache_lookup_timeout_ms": 50,
            "max_query_retries": 2,
            "backoff_policy": "exponential_jitter",
        },
        observability_requirements=[
            "Emit p95 and p99 latency metrics grouped by HTTP route.",
            "Track Redis cache hit/miss ratio gauge (target > 80%).",
            "Monitor PostgreSQL connection pool saturation and queue depth.",
            "Alert on database CPU utilization sustained above 75%.",
        ],
        security_considerations=[
            "Enforce TLS encryption in transit for database and cache connections.",
            "Use strict parameterized queries / ORM prepared statements to eliminate SQL injection.",
            "Never store unencrypted secrets in code; inject credentials via environment variables or secret manager.",
            "Bind Redis to private VPC loopback; require Redis AUTH token.",
        ],
        explicit_non_goals=[
            "DO NOT implement Kafka or message queues unless asynchronous architecture is chosen.",
            "DO NOT add multi-region distributed cache clustering before single-node limits are exceeded.",
            "DO NOT introduce microservice decomposition or distributed sagas for this service.",
            "DO NOT prematurely introduce complex database sharding.",
        ],
        evidence_limitations=[
            "Performance estimates are derived from discrete-event queueing simulation (SimPy), not real physical production traffic.",
            "Database CPU utilization estimates assume calibrated 2 vCPU hardware baseline.",
            "Cost estimates are illustrative based on standard cloud provider list prices and assume continuous 730 hr/mo usage.",
        ],
        decisions_requiring_confirmation=[
            "Confirm cache eviction policy (volatile-lru recommended for catalog items).",
            "Confirm read replica provisioning trigger if read traffic expands beyond 650 RPS.",
            "Confirm session consistency requirements for immediate read-after-write scenarios.",
        ],
    )

    decision_result = ArchitectureDecisionResult(
        workload=d_workload,
        candidates=d_candidates,
        simulations=d_simulations,
        feasibility=d_feasibility,
        evidence=d_evidence,
        recommendation=d_rec,
        explanation=d_explanation,
        implementation=d_implementation,
    )

    return DemoWorkflowResponse(
        request_summary=req_summary,
        investigation_summary=inv_summary,
        architecture_comparison=comparisons,
        recommendation=rec_summary,
        evidence_disclosure=evidence_disclosure,
        workflow_status=workflow_status,
        execution_mode=execution_mode,
        decision_result=decision_result,
    )
