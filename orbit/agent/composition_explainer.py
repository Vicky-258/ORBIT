"""
Architectural Decision Explainer for ORBIT (Phase: Hybrid Workload Intelligence).
Synthesizes transparent explanations detailing why archetypes were chosen,
why primitives were selected, trade-offs made, and simulation bottleneck observations.

Design Principle:
ORBIT is never a black box.
Every recommendation is traceable to engineering principles, workload physics, and simulation results.
"""
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from orbit.catalog.archetypes import get_archetype
from orbit.catalog.workload_profile import WorkloadProfile
from orbit.catalog.primitives import get_primitive
from orbit.agent.domain_understanding import DomainIdentity
from orbit.sdk.models import TopologyGraph
from orbit.core.schemas import SimulationResult

logger = logging.getLogger("orbit.agent.composition_explainer")


class WorkloadMappingExplanation(BaseModel):
    workload_id: str
    operation_name: str
    archetype_id: str
    rationale: str
    key_drivers: List[str]


class CompositionExplanation(BaseModel):
    """Complete transparent explanation trace of an architectural composition."""
    domain_summary: str
    workload_mappings: List[WorkloadMappingExplanation]
    primitive_selection_reasons: Dict[str, str]
    data_consistency_tradeoffs: List[str]
    scaling_and_bottleneck_risks: List[str]
    explicit_assumptions: List[str]
    markdown_report: str


class CompositionExplainer:
    """Generates structured, human-readable explanations of architectural decisions."""

    def explain(
        self,
        domain: DomainIdentity,
        workloads: List[WorkloadProfile],
        topology: TopologyGraph,
        simulation_result: Optional[SimulationResult] = None,
    ) -> CompositionExplanation:
        """
        Produces an explanation of the composed architecture and simulation results.
        """
        # 1. Workload to Archetype mappings
        mappings: List[WorkloadMappingExplanation] = []
        for w in workloads:
            arch = get_archetype(w.archetype_id)
            desc = arch.description if arch else "Universal distributed workload pattern."
            drivers = []
            if w.operations.read_ratio >= 0.8:
                drivers.append(f"High read ratio ({int(w.operations.read_ratio * 100)}%)")
            elif w.operations.write_ratio >= 0.7:
                drivers.append(f"Write-dominant ingestion ({int(w.operations.write_ratio * 100)}%)")

            if w.requirements.consistency == "strict_acid":
                drivers.append("Strict ACID consistency requirement")
            elif w.requirements.consistency == "eventual":
                drivers.append("Eventual consistency tolerance")

            if w.computation.compute_intensity == "high":
                drivers.append("CPU/GPU intensive compute decoupled from client loop")

            mappings.append(
                WorkloadMappingExplanation(
                    workload_id=w.workload_id,
                    operation_name=w.operation_name,
                    archetype_id=w.archetype_id.value,
                    rationale=f"Classified as {w.archetype_id.value} because {desc.lower()}",
                    key_drivers=drivers or ["Standard interactive request-response pattern"],
                )
            )

        # 2. Primitive Selection Reasons
        primitive_reasons: Dict[str, str] = {}
        for comp in topology.components:
            cid = comp.id
            mname = comp.model_name
            cat = comp.category.value

            if cid == "api_gw":
                primitive_reasons[cid] = "Unified ingress handling SSL termination, rate limiting, and request routing across workloads."
            elif cid == "ws_gw":
                primitive_reasons[cid] = "WebSocket gateway maintaining stateful duplex connections for real-time telemetry/streaming."
            elif cid == "app_server":
                primitive_reasons[cid] = "Stateless application service executing business logic and data aggregation."
            elif cid == "redis_cache" or cid == "state_cache":
                primitive_reasons[cid] = "In-memory cache absorbing high-frequency reads and ephemeral session states to protect backend datastores."
            elif cid == "postgres_db":
                primitive_reasons[cid] = "ACID-compliant relational database ensuring transactional integrity for bookings, accounts, and primary records."
            elif cid == "task_queue":
                primitive_reasons[cid] = "Asynchronous message queue decoupling long-running compute jobs from client response latency."
            elif cid == "background_worker":
                primitive_reasons[cid] = "Autonomous compute worker draining tasks asynchronously with dedicated resource isolation."
            elif cid == "object_storage":
                primitive_reasons[cid] = "Object storage repository for large, immutable media artifacts and video blobs."
            elif cid == "ingest_stream" or cid == "stream_event":
                primitive_reasons[cid] = "Partitioned event log providing high write throughput for continuous telemetry streams."
            elif cid == "timeseries_db":
                primitive_reasons[cid] = "Partitioned datastore optimized for append-only time-series metrics and rapid ingestion."
            else:
                primitive_reasons[cid] = f"Standard {cat} component providing dedicated capacity for system operations."

        # 3. Consistency Trade-offs
        tradeoffs: List[str] = []
        has_acid = any(w.requirements.consistency == "strict_acid" for w in workloads)
        has_eventual = any(w.requirements.consistency in ("eventual", "eventual_consistency") for w in workloads)
        has_cache = any(c.id == "redis_cache" for c in topology.components)

        if has_acid and has_eventual:
            tradeoffs.append(
                "Hybrid Consistency Model: Selected strict ACID relational database for financial/transactional paths, "
                "while permitting eventual consistency on read browsing and telemetry ingestion to maximize availability."
            )
        elif has_acid:
            tradeoffs.append("Strict Consistency Model: Enforced relational ACID guarantees across all primary operations.")
        else:
            tradeoffs.append("Eventual Consistency Model: Prioritized horizontal scalability and write availability over instantaneous synchronization.")

        if has_cache:
            tradeoffs.append(
                "Cache Freshness Trade-off: Read caching delivers sub-millisecond latencies, but introduces potential cache staleness "
                "requiring time-to-live (TTL) expiration or write-invalidation."
            )

        # 4. Scaling and Bottleneck Risks from Simulation
        risks: List[str] = []
        if simulation_result:
            bottleneck = simulation_result.bottleneck_component
            b_util = simulation_result.component_utilizations.get(bottleneck, 0.0)
            if b_util > 75.0:
                risks.append(
                    f"Resource Saturation: Component '{bottleneck}' reached {b_util}% utilization during simulation, "
                    "representing the primary scaling limit under traffic growth."
                )
            if simulation_result.error_rate_pct > 0.0:
                risks.append(f"Error Rate Warning: Observed {simulation_result.error_rate_pct}% request errors during peak loads.")

            for wid, wstat in simulation_result.workload_metrics.items():
                if wstat.get("sla_compliant") is False:
                    risks.append(
                        f"SLA Violation: Workload '{wid}' observed p95 latency {wstat['p95_latency_ms']}ms exceeding SLA threshold {wstat.get('p95_sla_target_ms')}ms."
                    )
        else:
            risks.append("Simulate topology under load to empirically identify active resource bottlenecks.")

        # 5. Explicit Assumptions
        assumptions: List[str] = []
        for w in workloads:
            for param_name, item in w.provenance_map.items():
                if item.is_assumed:
                    assumptions.append(
                        f"Workload '{w.workload_id}': assumed {param_name}={item.value} (source: {item.source.value}, confidence: {item.confidence})"
                    )

        # 6. Generate Markdown Report
        lines = [
            f"# ORBIT Architecture Decision Report: {domain.domain_identity.replace('_', ' ').title()}",
            "",
            "## 1. Executive Summary",
            f"**Application Domain:** `{domain.domain_identity}`  ",
            f"**Purpose:** {domain.description}  ",
            f"**Total Workloads:** {len(workloads)}  ",
            "",
            "## 2. Workload Classification & Archetype Mapping",
            "| Workload | Archetype | Key Drivers | Rationale |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for m in mappings:
            drivers_str = "<br>".join(m.key_drivers)
            lines.append(f"| `{m.workload_id}` | `{m.archetype_id}` | {drivers_str} | {m.rationale} |")

        lines.extend([
            "",
            "## 3. Infrastructure Primitive Selection",
            "| Component ID | Category | Primitive Model | Selection Rationale |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for comp in topology.components:
            reason = primitive_reasons.get(comp.id, "Standard infrastructure primitive.")
            lines.append(f"| `{comp.id}` | `{comp.category.value}` | `{comp.model_name}` | {reason} |")

        lines.extend([
            "",
            "## 4. Architectural Trade-offs & Consistency",
        ])
        for to in tradeoffs:
            lines.append(f"- {to}")

        lines.extend([
            "",
            "## 5. Simulation & Bottleneck Analysis",
        ])
        if simulation_result:
            lines.append(f"- **Simulated Throughput:** {simulation_result.throughput_achieved_rps} RPS")
            lines.append(f"- **p95 Latency:** {simulation_result.p95_latency_ms} ms")
            lines.append(f"- **Estimated Monthly Cost:** ${simulation_result.estimated_monthly_cost_usd:.2f} USD")
            lines.append(f"- **Identified Bottleneck:** `{simulation_result.bottleneck_component}` ({simulation_result.component_utilizations.get(simulation_result.bottleneck_component, 0)}% utilization)")
        for r in risks:
            lines.append(f"- {r}")

        lines.extend([
            "",
            "## 6. Assumptions & Calibrations",
        ])
        for a in assumptions[:10]:
            lines.append(f"- {a}")
        if len(assumptions) > 10:
            lines.append(f"- *...and {len(assumptions) - 10} additional parameter defaults.*")

        report_md = "\n".join(lines)

        return CompositionExplanation(
            domain_summary=domain.description,
            workload_mappings=mappings,
            primitive_selection_reasons=primitive_reasons,
            data_consistency_tradeoffs=tradeoffs,
            scaling_and_bottleneck_risks=risks,
            explicit_assumptions=assumptions,
            markdown_report=report_md,
        )
