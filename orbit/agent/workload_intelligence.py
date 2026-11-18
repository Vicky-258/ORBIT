"""
Workload Intelligence Coordinator for ORBIT (Phase: Hybrid Workload Intelligence).
Coordinates Dynamic Domain Understanding, Workload Decomposition,
Archetype Classification, and Workload Profile Generation.
"""
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from orbit.agent.provider import LLMProviderManager
from orbit.agent.domain_understanding import DomainUnderstandingAgent, DomainIdentity
from orbit.agent.workload_decomposer import WorkloadDecomposer, WorkloadDecompositionResult, DecomposedWorkload
from orbit.catalog.archetypes import ArchetypeID, get_archetype
from orbit.catalog.workload_profile import WorkloadProfile, generate_workload_profile

logger = logging.getLogger("orbit.agent.workload_intelligence")


class ApplicationWorkloadAnalysis(BaseModel):
    """Complete workload intelligence output for an application."""
    domain: DomainIdentity
    decomposition: WorkloadDecompositionResult
    profiles: List[WorkloadProfile]
    total_estimated_rps: float
    user_facts_count: int
    assumptions_count: int


class WorkloadIntelligencePipeline:
    """End-to-end pipeline converting free-form application text into validated workload profiles."""

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()
        self.domain_agent = DomainUnderstandingAgent(provider_mgr=self.provider_mgr)
        self.decomposer = WorkloadDecomposer(provider_mgr=self.provider_mgr)

    def analyze(
        self,
        user_prompt: str,
        user_facts: Optional[Dict[str, Any]] = None,
        test_mode: bool = False,
    ) -> ApplicationWorkloadAnalysis:
        """
        Executes full Workload Intelligence lifecycle:
        1. Dynamic domain extraction
        2. Multi-workload decomposition
        3. Standardized archetype classification
        4. Measurable workload profile generation with provenance
        """
        user_facts = user_facts or {}

        # 1. Dynamic Domain Understanding
        domain = self.domain_agent.analyze_domain(user_prompt, test_mode=test_mode)

        # 2. Multi-workload Decomposition
        decomp = self.decomposer.decompose(domain, user_prompt, test_mode=test_mode)

        # 3 & 4. Workload Profile Generation per workload
        profiles: List[WorkloadProfile] = []
        total_rps = 0.0
        assumptions_count = 0
        facts_count = len(user_facts)

        for w in decomp.workloads:
            # Generate simulation profile
            profile = generate_workload_profile(
                workload_id=w.workload_id,
                operation_name=w.operation_name,
                description=w.description,
                archetype_id=w.classified_archetype_id,
                user_facts=user_facts,
                domain_hints={
                    "consistency": w.consistency_requirements,
                    "latency_sensitivity": w.latency_sensitivity,
                },
            )
            profiles.append(profile)
            total_rps += profile.traffic.arrival_rate_rps
            assumptions_count += sum(1 for p in profile.provenance_map.values() if p.is_assumed)

        return ApplicationWorkloadAnalysis(
            domain=domain,
            decomposition=decomp,
            profiles=profiles,
            total_estimated_rps=round(total_rps, 2),
            user_facts_count=facts_count,
            assumptions_count=assumptions_count,
        )
