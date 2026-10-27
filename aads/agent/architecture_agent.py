"""
Architecture Agent.
Converts natural-language system requirements into validated WorkloadSpec objects
and candidate architecture graphs using LangChain structured outputs or deterministic fallback.
"""
import re
import logging
from typing import Tuple, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from aads.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    InformationProvenance,
    ProvenanceItem,
)
from aads.generator.candidate_generator import ArchitectureGenerator
from aads.agent.provider import LLMProviderManager, ExecutionMode

logger = logging.getLogger("aads.agent.architecture_agent")

SYSTEM_PROMPT = """You are the AADS (Agentic Architecture Design & Simulation) Architecture Agent.
Your responsibility is to analyze user requests for backend system architecture designs and extract structured engineering workload requirements.

Guidelines:
1. Extract numerical values for throughput (RPS), peak load factor, read/write ratios, p95 latency SLA target (ms), minimum throughput (RPS), and monthly budget cap ($).
2. Distinguish facts explicitly stated by the user (user_facts) from engineering defaults or assumptions (agent_assumptions).
3. If the request is too vague, ambiguous, or lacks critical operational targets (e.g., no throughput or latency expectations), provide 2-3 focused clarification questions in clarification_questions.
4. Do NOT hallucinate benchmark numbers, simulation outputs, or component capacities.
5. Soft preferences should balance cost, latency, and simplicity (must sum to 1.0).
"""


class SoftPreferences(BaseModel):
    cost: float = Field(default=0.35, description="Cost weight (0.0 - 1.0)")
    latency: float = Field(default=0.45, description="Latency weight (0.0 - 1.0)")
    simplicity: float = Field(default=0.20, description="Simplicity weight (0.0 - 1.0)")

    def __getitem__(self, key: str) -> float:
        return getattr(self, key)

    def get(self, key: str, default: float = 0.0) -> float:
        return getattr(self, key, default)

    def items(self):
        return [("cost", self.cost), ("latency", self.latency), ("simplicity", self.simplicity)]


class UserFactItem(BaseModel):
    key: str = Field(description="Parameter key e.g. request_rate_rps, p95_latency_target_ms, read_ratio")
    value: str = Field(description="Stated value from user")


class WorkloadExtractionResult(BaseModel):
    """Structured extraction of workload requirements from natural language."""
    app_type: str = Field(default="social_media_feed", description="Target application domain or workload type")
    request_rate_rps: Optional[float] = Field(default=None, description="Target steady-state throughput in requests/sec")
    peak_load_factor: Optional[float] = Field(default=None, description="Multiplier for peak traffic burst headroom")
    read_ratio: Optional[float] = Field(default=None, description="Proportion of read operations (0.0 - 1.0)")
    write_ratio: Optional[float] = Field(default=None, description="Proportion of write operations (0.0 - 1.0)")
    dataset_records: Optional[int] = Field(default=None, description="Estimated total dataset size in records/items")
    p95_latency_target_ms: Optional[float] = Field(default=None, description="Target p95 latency threshold in milliseconds")
    min_throughput_rps: Optional[float] = Field(default=None, description="Minimum acceptable throughput in requests/sec")
    max_monthly_budget_usd: Optional[float] = Field(default=None, description="Maximum monthly infrastructure budget in USD")
    cache_assumed_hit_rate: Optional[float] = Field(default=None, description="Assumed cache hit rate (0.0 - 1.0)")
    soft_preferences: SoftPreferences = Field(
        default_factory=SoftPreferences,
        description="User preference weights across cost, latency, and simplicity (sum to 1.0)",
    )
    user_fact_items: List[UserFactItem] = Field(
        default_factory=list,
        description="Requirements explicitly stated by the user",
    )
    agent_assumptions: List[str] = Field(default_factory=list, description="Defaults or assumptions inferred by the agent")
    clarification_questions: List[str] = Field(default_factory=list, description="Targeted questions to ask user if clarification is needed")
    ambiguities: List[str] = Field(default_factory=list, description="Ambiguities or conflicts detected in the request")

    def __init__(self, **data: Any):
        if "user_facts" in data and "user_fact_items" not in data:
            uf = data.pop("user_facts")
            if isinstance(uf, dict):
                data["user_fact_items"] = [UserFactItem(key=str(k), value=str(v)) for k, v in uf.items()]
        super().__init__(**data)

    @property
    def user_facts(self) -> Dict[str, Any]:
        facts: Dict[str, Any] = {item.key: item.value for item in self.user_fact_items}
        if self.request_rate_rps is not None and "request_rate_rps" not in facts:
            facts["request_rate_rps"] = self.request_rate_rps
        if self.p95_latency_target_ms is not None and "p95_latency_target_ms" not in facts:
            facts["p95_latency_target_ms"] = self.p95_latency_target_ms
        if self.max_monthly_budget_usd is not None and "max_monthly_budget_usd" not in facts:
            facts["max_monthly_budget_usd"] = self.max_monthly_budget_usd
        if self.read_ratio is not None and "read_ratio" not in facts:
            facts["read_ratio"] = self.read_ratio
        if self.write_ratio is not None and "write_ratio" not in facts:
            facts["write_ratio"] = self.write_ratio
        return facts


class ArchitectureAgent:
    """Agent that translates natural-language prompts into validated AADS specifications."""

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()
        self.generator = ArchitectureGenerator()

    @staticmethod
    def fallback_parse(request_text: str) -> WorkloadExtractionResult:
        """
        Deterministic regex and heuristic parser when LLM is unavailable.
        Safely extracts numerical engineering constraints or flags ambiguity.
        """
        text = request_text.lower().strip()
        user_facts: Dict[str, Any] = {}
        agent_assumptions: List[str] = []

        # Check for empty or purely conversational queries lacking technical parameters
        tech_keywords = ["rps", "req", "request", "read", "write", "latency", "ms", "budget", "cost", "dollar", "$", "feed", "cache", "database", "load"]
        has_tech_intent = any(k in text for k in tech_keywords)

        if not text or not has_tech_intent or len(text.split()) < 3:
            return WorkloadExtractionResult(
                clarification_questions=[
                    "What is your target steady-state throughput (e.g., 500 requests/second)?",
                    "What is your acceptable p95 latency threshold (e.g., under 50ms)?",
                    "What is your monthly infrastructure budget limit (e.g., $250/month)?",
                ],
                ambiguities=["Request lacks operational targets and load parameters."],
                user_facts={},
                agent_assumptions=[],
            )

        # 1. Throughput (RPS)
        rps_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rps|req/s|requests?\s*(?:per|/)\s*sec|qps)", text)
        if rps_match:
            rps = float(rps_match.group(1))
            user_facts["request_rate_rps"] = rps
        else:
            rps = 500.0
            agent_assumptions.append("Default load assumed: 500.0 RPS")

        # Peak load factor
        peak_match = re.search(r"peak\s*(\d+(?:\.\d+)?)\s*(?:rps|req/s|qps)", text)
        if peak_match:
            peak_rps = float(peak_match.group(1))
            peak_factor = round(peak_rps / max(1.0, rps), 2)
            user_facts["peak_load_factor"] = peak_factor
        else:
            peak_factor = 2.0
            agent_assumptions.append("Peak burst headroom assumed: 2.0x")

        # 2. Latency Target (p95 ms)
        lat_match = re.search(r"(?:p95|latency|sla|response\s*time)?\s*(?:under|<=|<|below|of)?\s*(\d+(?:\.\d+)?)\s*ms", text)
        if lat_match:
            p95 = float(lat_match.group(1))
            user_facts["p95_latency_target_ms"] = p95
        else:
            p95 = 50.0
            agent_assumptions.append("Default p95 latency target assumed: 50.0 ms")

        # 3. Monthly Budget (USD)
        budget_match = re.search(r"\$\s*(\d+(?:\.\d+)?)|(?:budget|cost|cap)?\s*(\d+(?:\.\d+)?)\s*(?:usd|dollars|/month|/mo)", text)
        if budget_match:
            b_val = budget_match.group(1) or budget_match.group(2)
            budget = float(b_val)
            user_facts["max_monthly_budget_usd"] = budget
        else:
            budget = 250.0
            agent_assumptions.append("Default budget cap assumed: $250.00/mo")

        # 4. Read / Write Ratio
        read_ratio = 0.90
        write_ratio = 0.10
        ratio_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        read_pct_match = re.search(r"(\d+)%\s*(?:reads?|read)", text)

        if read_pct_match:
            r_pct = float(read_pct_match.group(1))
            read_ratio = max(0.01, min(0.99, r_pct / 100.0))
            write_ratio = round(1.0 - read_ratio, 2)
            user_facts["read_ratio"] = read_ratio
            user_facts["write_ratio"] = write_ratio
        elif ratio_match:
            r1, r2 = float(ratio_match.group(1)), float(ratio_match.group(2))
            total = r1 + r2
            if total > 0:
                read_ratio = round(r1 / total, 2)
                write_ratio = round(1.0 - read_ratio, 2)
                user_facts["read_ratio"] = read_ratio
                user_facts["write_ratio"] = write_ratio
        else:
            agent_assumptions.append("Default read/write split: 90% Reads / 10% Writes")

        # 5. Domain / App type
        app_type = "social_media_feed"
        if "ecommerce" in text or "shop" in text or "store" in text:
            app_type = "ecommerce"
            user_facts["app_type"] = app_type
        elif "analytics" in text or "logging" in text or "telemetry" in text:
            app_type = "analytics_pipeline"
            user_facts["app_type"] = app_type
        else:
            agent_assumptions.append("Application domain defaulted to Social Media Feed")

        agent_assumptions.append("Cache hit rate expectation: 85%")

        return WorkloadExtractionResult(
            app_type=app_type,
            request_rate_rps=rps,
            peak_load_factor=peak_factor,
            read_ratio=read_ratio,
            write_ratio=write_ratio,
            dataset_records=1_000_000,
            p95_latency_target_ms=p95,
            min_throughput_rps=round(rps * 0.9, 1),
            max_monthly_budget_usd=budget,
            cache_assumed_hit_rate=0.85,
            soft_preferences={"cost": 0.35, "latency": 0.45, "simplicity": 0.20},
            user_facts=user_facts,
            agent_assumptions=agent_assumptions,
            clarification_questions=[],
            ambiguities=[],
        )

    def parse_request(self, request_text: str) -> Tuple[Optional[WorkloadSpec], List[str], List[str], ExecutionMode]:
        """
        Parses natural language prompt into WorkloadSpec, questions, assumptions, and execution mode.
        """
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"User Architecture Request:\n{request_text}"),
        ]

        if self.provider_mgr.is_llm_available():
            mode = ExecutionMode.LLM
            try:
                model = self.provider_mgr.get_chat_model()
                structured = model.with_structured_output(WorkloadExtractionResult)
                extracted = structured.invoke(messages)
                if extracted is None:
                    raise ValueError("LLM returned empty structured output")
            except Exception as e:
                logger.warning(f"LLM extraction failed ({e}), falling back to deterministic parser.")
                extracted = self.fallback_parse(request_text)
                mode = ExecutionMode.FALLBACK
        else:
            extracted = self.fallback_parse(request_text)
            mode = ExecutionMode.FALLBACK

        # If clarification questions were generated and key parameters are absent
        if extracted.clarification_questions and (extracted.request_rate_rps is None or extracted.p95_latency_target_ms is None):
            return None, extracted.clarification_questions, extracted.agent_assumptions, mode

        # Construct WorkloadSpec
        read_r = extracted.read_ratio if extracted.read_ratio is not None else 0.90
        write_r = extracted.write_ratio if extracted.write_ratio is not None else 0.10
        total_r = read_r + write_r
        if total_r > 0:
            read_r = round(read_r / total_r, 4)
            write_r = round(1.0 - read_r, 4)

        rps = extracted.request_rate_rps if extracted.request_rate_rps and extracted.request_rate_rps > 0 else 500.0
        p95 = extracted.p95_latency_target_ms if extracted.p95_latency_target_ms and extracted.p95_latency_target_ms > 0 else 50.0
        min_tp = extracted.min_throughput_rps if extracted.min_throughput_rps and extracted.min_throughput_rps > 0 else round(rps * 0.9, 1)
        budget = extracted.max_monthly_budget_usd if extracted.max_monthly_budget_usd and extracted.max_monthly_budget_usd > 0 else 250.0

        prov_map = {}
        for k, v in extracted.user_facts.items():
            prov_map[k] = ProvenanceItem(
                key=k,
                provenance=InformationProvenance.USER_FACT,
                value=v,
                description=f"User provided {k}",
            )
        # Always track standard assumptions
        prov_map["cache_assumed_hit_rate"] = ProvenanceItem(
            key="cache_assumed_hit_rate",
            provenance=InformationProvenance.AGENT_ASSUMPTION,
            value=extracted.cache_assumed_hit_rate or 0.85,
            description="Agent assumption: 85% cache hit rate for social media feeds",
        )
        prov_map["peak_load_factor"] = ProvenanceItem(
            key="peak_load_factor",
            provenance=InformationProvenance.AGENT_ASSUMPTION,
            value=extracted.peak_load_factor or 2.0,
            description="Agent assumption: 2x peak burst headroom",
        )
        if "request_rate_rps" not in prov_map:
            prov_map["request_rate_rps"] = ProvenanceItem(
                key="request_rate_rps",
                provenance=InformationProvenance.AGENT_ASSUMPTION,
                value=rps,
                description="Default load assumed",
            )
        for idx, assump in enumerate(extracted.agent_assumptions):
            prov_map[f"assumption_{idx}"] = ProvenanceItem(
                key=f"assumption_{idx}",
                provenance=InformationProvenance.AGENT_ASSUMPTION,
                value=assump,
                description="Engineering assumption or default",
            )

        workload = WorkloadSpec(
            app_type=extracted.app_type,
            request_rate_rps=rps,
            peak_load_factor=extracted.peak_load_factor or 2.0,
            read_ratio=read_r,
            write_ratio=write_r,
            dataset_records=extracted.dataset_records or 1_000_000,
            p95_latency_target_ms=p95,
            min_throughput_rps=min_tp,
            max_monthly_budget_usd=budget,
            cache_assumed_hit_rate=extracted.cache_assumed_hit_rate or 0.85,
            soft_preferences=extracted.soft_preferences.model_dump() if hasattr(extracted.soft_preferences, "model_dump") else (dict(extracted.soft_preferences) if isinstance(extracted.soft_preferences, dict) else {"cost": 0.35, "latency": 0.45, "simplicity": 0.20}),
            provenance_map=prov_map,
        )
        return workload, extracted.clarification_questions, extracted.agent_assumptions, mode

    def generate_and_validate_candidates(
        self,
        include_async: bool = True,
        include_unsupported: bool = False,
    ) -> Tuple[List[ArchitectureGraph], Dict[str, Any]]:
        """Generates candidate architectures and validates topology DAGs."""
        candidates = self.generator.generate_candidates(
            include_async=include_async,
            include_unsupported=include_unsupported,
        )
        errors = []
        for c in candidates:
            try:
                self.generator.validate_graph(c)
            except Exception as e:
                errors.append(f"Validation failed for {c.id}: {str(e)}")

        val_meta = {
            "valid": len(errors) == 0,
            "candidate_count": len(candidates),
            "errors": errors,
        }
        return candidates, val_meta
