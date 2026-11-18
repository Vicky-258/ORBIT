"""
Workload Decomposition Module for ORBIT (Phase: Hybrid Workload Intelligence).
Decomposes an application into multiple independent, concurrent workloads.

Design Principle:
An application is NOT a single archetype.
An application contains multiple independent operations that behave differently under traffic.
"""
import re
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage
from orbit.agent.provider import LLMProviderManager, ExecutionMode
from orbit.agent.domain_understanding import DomainIdentity
from orbit.catalog.archetypes import (
    ArchetypeID,
    classify_workload_text,
    get_archetype,
)

logger = logging.getLogger("orbit.agent.workload_decomposer")


class WorkloadDecompositionOfflineError(RuntimeError):
    """Raised when live LLM is offline and test_mode is False."""
    pass


class DecomposedWorkload(BaseModel):
    """An independent operational workload identified within an application."""
    workload_id: str = Field(description="Unique snake_case identifier e.g. 'course_browsing', 'video_generation'")
    operation_name: str = Field(description="Human-readable title e.g. 'Course Catalog Browsing'")
    description: str = Field(description="Detailed operational description of what this workload does")
    classified_archetype_id: ArchetypeID = Field(description="Mapped universal system archetype")
    
    input_data_characteristics: str = Field(default="Standard HTTP JSON request payload")
    output_data_characteristics: str = Field(default="JSON response payload")
    read_write_behavior: str = Field(default="read_dominant", description="read_dominant, write_dominant, balanced_oltp, event_stream")
    computational_characteristics: str = Field(default="io_bound", description="io_bound, cpu_intensive, light_crud")
    latency_sensitivity: str = Field(default="normal_interactive", description="critical_low_latency, normal_interactive, asynchronous_delayed")
    consistency_requirements: str = Field(default="eventual_consistency", description="strict_acid, eventual_consistency, read_your_writes")
    dependencies: List[str] = Field(default_factory=list, description="IDs of other workloads this depends on")
    expected_traffic_characteristics: Optional[str] = Field(default=None, description="e.g. 'high frequency steady state', 'bursty'")


class WorkloadDecompositionResult(BaseModel):
    """Full decomposition of an application into its constituent workloads."""
    application_domain: str
    workloads: List[DecomposedWorkload] = Field(min_length=1)
    shared_infrastructure_notes: Optional[str] = None


WORKLOAD_DECOMPOSITION_SYSTEM_PROMPT = """You are the ORBIT Workload Decomposition Agent.
Your responsibility is to analyze a software application description and decompose it into distinct, independent operational workloads.

CRITICAL GUIDELINES:
1. Do NOT assign one single archetype to the entire application. An application typically contains 2 to 5 distinct workloads.
2. For each distinct user journey or major operation (e.g. search vs payment vs background job vs live chat), create a separate DecomposedWorkload.
3. Classify each workload into one of the 6 canonical archetypes:
   - READ_HEAVY_INTERACTIVE: Browsing, search, feeds, catalog lookups.
   - DECOUPLED_ASYNC_COMPUTE: Heavy compute, video transcoding, AI generation, batch jobs.
   - TRANSACTIONAL_OLTP: Bookings, payments, checkout, ledger transfers requiring ACID.
   - WRITE_HEAVY_INGESTION: High-volume telemetry, clickstream, logs, sensor data.
   - REALTIME_STREAM_TRACKING: Live GPS tracking, chat, persistent websockets, multiplayer state.
   - GENERAL_WEB_SERVICE: Basic CRUD, user profiles, settings.
4. Identify dependencies between workloads (e.g., checkout depends on cart).
5. Never invent workloads not implied by the user's description.
"""


def _heuristic_workload_decomposition(
    domain: DomainIdentity,
    text: str,
) -> WorkloadDecompositionResult:
    """
    Deterministic decomposition used for unit tests when offline.
    Maps core functionalities of the domain into independently classified workloads.
    """
    workloads: List[DecomposedWorkload] = []
    seen_ids = set()

    # Heuristic template definitions mapping functionality keywords to engineering attributes
    functionality_specs = [
        # 1. Browsing / Search
        (
            ["browse", "search", "view", "catalog", "feed", "discovery", "ratings"],
            "browsing",
            "Catalog Browsing & Search",
            "Read-intensive browsing and retrieval of content records and ratings.",
            ArchetypeID.READ_HEAVY_INTERACTIVE,
            "read_dominant",
            "io_bound",
            "critical_low_latency",
            "eventual_consistency",
        ),
        # 2. Asynchronous compute / AI / Video
        (
            ["video", "generate", "ai", "transcode", "batch", "render", "export", "background"],
            "generation",
            "Asynchronous Heavy Compute & Generation",
            "Long-running computational tasks buffered via queues and executed by background workers.",
            ArchetypeID.DECOUPLED_ASYNC_COMPUTE,
            "write_dominant",
            "cpu_intensive",
            "asynchronous_delayed",
            "eventual_consistency",
        ),
        # 3. Transactional / Payment / Booking
        (
            ["book", "booking", "pay", "payment", "checkout", "reservation", "order", "transfer", "ledger"],
            "transactions",
            "Transactional Operations & Bookings",
            "Strict ACID transactional modifications requiring database locking and atomic consistency.",
            ArchetypeID.TRANSACTIONAL_OLTP,
            "balanced_oltp",
            "io_bound",
            "normal_interactive",
            "strict_acid",
        ),
        # 4. Telemetry / Ingestion
        (
            ["ingest", "telemetry", "log", "sensor", "tracking", "metric", "clickstream"],
            "telemetry_ingestion",
            "Write-Heavy Telemetry Ingestion",
            "Continuous ingestion of high-volume data streams into write-optimized storage buffers.",
            ArchetypeID.WRITE_HEAVY_INGESTION,
            "write_dominant",
            "io_bound",
            "normal_interactive",
            "eventual_consistency",
        ),
        # 5. Live realtime tracking / Chat / WebSockets
        (
            ["gps", "live location", "live tracking", "websocket", "chat", "realtime", "real-time", "multiplayer", "presence"],
            "realtime_tracking",
            "Real-Time State & Location Synchronization",
            "Low-latency bidirectional state updates across persistent client connections.",
            ArchetypeID.REALTIME_STREAM_TRACKING,
            "balanced_oltp",
            "io_bound",
            "critical_low_latency",
            "eventual_consistency",
        ),
        # 6. Reviews / User content upload
        (
            ["review", "upload", "comment", "submission"],
            "content_submission",
            "User Content Submission",
            "Submission and persistence of user reviews, ratings, and media.",
            ArchetypeID.GENERAL_WEB_SERVICE,
            "balanced_oltp",
            "light_crud",
            "normal_interactive",
            "eventual_consistency",
        ),
    ]

    text_lower = text.lower()

    for kws, wid_suffix, title, desc, aid, rw, comp, lat, cons in functionality_specs:
        matched = False
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"(?:s|es|ing|ed)?\b", text_lower):
                matched = True
                break

        if matched:
            wid = f"{domain.domain_identity}_{wid_suffix}".replace("__", "_")
            if wid not in seen_ids:
                seen_ids.add(wid)
                workloads.append(
                    DecomposedWorkload(
                        workload_id=wid,
                        operation_name=title,
                        description=desc,
                        classified_archetype_id=aid,
                        read_write_behavior=rw,
                        computational_characteristics=comp,
                        latency_sensitivity=lat,
                        consistency_requirements=cons,
                    )
                )

    # If no specific patterns matched, provide a general web service workload
    if not workloads:
        workloads.append(
            DecomposedWorkload(
                workload_id=f"{domain.domain_identity}_core_service",
                operation_name="Core Application Workload",
                description="General request-response service processing user operations.",
                classified_archetype_id=ArchetypeID.GENERAL_WEB_SERVICE,
                read_write_behavior="balanced_oltp",
                computational_characteristics="light_crud",
                latency_sensitivity="normal_interactive",
                consistency_requirements="eventual_consistency",
            )
        )

    # Establish dependencies if both browsing and booking exist
    browsing_w = next((w for w in workloads if w.classified_archetype_id == ArchetypeID.READ_HEAVY_INTERACTIVE), None)
    for w in workloads:
        if w.classified_archetype_id in (ArchetypeID.TRANSACTIONAL_OLTP, ArchetypeID.DECOUPLED_ASYNC_COMPUTE):
            if browsing_w and browsing_w.workload_id != w.workload_id:
                w.dependencies.append(browsing_w.workload_id)

    return WorkloadDecompositionResult(
        application_domain=domain.domain_identity,
        workloads=workloads,
        shared_infrastructure_notes="Identified shared API ingress and potential database/cache partitioning opportunities.",
    )


class WorkloadDecomposer:
    """Decomposes an application into multiple independent workloads."""

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()

    def decompose(
        self,
        domain: DomainIdentity,
        user_prompt: str,
        test_mode: bool = False,
    ) -> WorkloadDecompositionResult:
        """
        Decomposes the application domain and user prompt into independent workloads.
        In live production: Requires LLM structured output.
        In automated unit testing (test_mode=True): Uses deterministic decomposition.
        """
        if test_mode:
            logger.info("Executing deterministic linguistic workload decomposition (test_mode=True).")
            return _heuristic_workload_decomposition(domain, user_prompt)

        mode = self.provider_mgr.get_execution_mode()

        if mode == ExecutionMode.LLM:
            llm = self.provider_mgr.get_chat_model()
            if llm:
                try:
                    structured_llm = llm.with_structured_output(WorkloadDecompositionResult)
                    prompt_content = (
                        f"Application Domain: {domain.domain_identity}\n"
                        f"Description: {domain.description}\n"
                        f"Core Functionalities: {', '.join(domain.core_functionalities)}\n"
                        f"Domain Entities: {', '.join(domain.domain_entities)}\n"
                        f"Original User Prompt: {user_prompt}"
                    )
                    messages = [
                        SystemMessage(content=WORKLOAD_DECOMPOSITION_SYSTEM_PROMPT),
                        HumanMessage(content=prompt_content),
                    ]
                    result = structured_llm.invoke(messages)
                    if isinstance(result, WorkloadDecompositionResult):
                        return result
                    if isinstance(result, dict):
                        return WorkloadDecompositionResult(**result)
                except Exception as exc:
                    logger.warning(f"Live LLM workload decomposition failed: {exc}")
                    raise WorkloadDecompositionOfflineError(
                        f"LLM workload decomposition failed: {exc}. ORBIT does not return fabricated mock decompositions in production."
                    ) from exc

        raise WorkloadDecompositionOfflineError(
            "ORBIT Workload Decomposition requires an active LLM provider (e.g. GROQ_API_KEY, OPENAI_API_KEY). "
            "To prevent inaccurate architectural recommendations, ORBIT does not return hardcoded fallback decompositions in live mode. "
            "Configure your API credentials in .env or run with test_mode=True in automated unit tests."
        )
