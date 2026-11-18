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

from orbit.core.schemas import (
    WorkloadSpec,
    ArchitectureGraph,
    InformationProvenance,
    ProvenanceItem,
)
from orbit.generator.candidate_generator import ArchitectureGenerator
from orbit.agent.provider import LLMProviderManager, ExecutionMode

logger = logging.getLogger("orbit.agent.architecture_agent")

SYSTEM_PROMPT = """You are the ORBIT (Orchestrated Reasoning and Benchmarking for Infrastructure Testing) Architecture Agent.
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
    value: Any = Field(description="Stated value from user")


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
        """Strictly returns only verified user-stated facts. Defaults never leak in."""
        return {item.key: item.value for item in self.user_fact_items}


def parse_natural_traffic(text: str) -> Optional[Tuple[float, float, str]]:
    """
    Parses user-scale expressions like '200K active daily users', '100k DAU', '5M MAU'.
    Returns: (avg_rps, peak_rps, derivation_explanation)
    """
    # 1. DAU expressions
    dau_match = re.search(
        r"([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?\s*(?:active\s+daily\s+users?|daily\s+active\s+users?|dau|active\s+users?\s+daily)",
        text,
        re.IGNORECASE,
    )
    if not dau_match:
        dau_match = re.search(
            r"(?:around|targets?|serving|for)\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?\s*(?:active\s+users?|users?|subscribers?)",
            text,
            re.IGNORECASE,
        )

    if dau_match:
        val = float(dau_match.group(1).replace(",", ""))
        unit = (dau_match.group(2) or "").lower()
        if unit in ("k", "thousand"):
            users = val * 1_000
        elif unit in ("m", "million"):
            users = val * 1_000_000
        else:
            users = val

        # Standard interaction model: ~25 actions/user/day distributed across 86,400s
        avg_rps = max(1.0, round((users * 25.0) / 86400.0, 1))
        peak_rps = max(2.0, round(avg_rps * 3.0, 1))
        explanation = f"Derived from {int(users):,} active daily users (~25 actions/day): ~{avg_rps} avg RPS (peak ~{peak_rps} RPS)"
        return avg_rps, peak_rps, explanation

    # 2. MAU expressions
    mau_match = re.search(
        r"([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?\s*(?:monthly\s+active\s+users?|mau)",
        text,
        re.IGNORECASE,
    )
    if mau_match:
        val = float(mau_match.group(1).replace(",", ""))
        unit = (mau_match.group(2) or "").lower()
        if unit in ("k", "thousand"):
            users = val * 1_000
        elif unit in ("m", "million"):
            users = val * 1_000_000
        else:
            users = val

        # Assume 20% DAU/MAU stickiness
        dau_equiv = users * 0.20
        avg_rps = max(1.0, round((dau_equiv * 25.0) / 86400.0, 1))
        peak_rps = max(2.0, round(avg_rps * 3.0, 1))
        explanation = f"Derived from {int(users):,} MAU (assuming 20% DAU/MAU stickiness): ~{avg_rps} avg RPS (peak ~{peak_rps} RPS)"
        return avg_rps, peak_rps, explanation

    return None


def rank_and_evaluate_ambiguity(
    has_throughput: bool,
    has_latency: bool,
    has_budget: bool,
    has_read_write: bool,
    threshold: float = 0.50,
) -> Tuple[float, List[str]]:
    """
    Evaluates operational ambiguity score A in [0.0, 1.0].
    Weights:
      Throughput: 0.40
      Latency SLA: 0.30
      Budget Cap: 0.20
      Read/Write Ratio: 0.10
    Returns: (ambiguity_score, ranked_clarification_questions)
    """
    ranked_questions: List[Tuple[float, str]] = []
    score = 0.0

    if not has_throughput:
        score += 0.40
        ranked_questions.append((0.40, "What is your target steady-state throughput or user volume (e.g. 500 requests/sec, or 100K daily active users)?"))

    if not has_latency:
        score += 0.30
        ranked_questions.append((0.30, "What is your acceptable p95 response time latency SLA (e.g. under 50ms, 100ms, or relaxed)?"))

    if not has_budget:
        score += 0.20
        ranked_questions.append((0.20, "What is your monthly cloud infrastructure budget limit (e.g. $150/mo, $300/mo, or unconstrained)?"))

    if not has_read_write:
        score += 0.10
        ranked_questions.append((0.10, "What is the approximate read vs write distribution (e.g. 90% reads / 10% writes)?"))

    score = round(score, 2)
    # Sort by weight descending so most critical unknown is asked first
    ranked_questions.sort(key=lambda x: x[0], reverse=True)
    questions = [q[1] for q in ranked_questions[:3]] if score >= threshold else []

    return score, questions


SYSTEM_ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "DECOUPLED_ASYNC_COMPUTE": {
        "description": "Heavy compute, AI generation, video rendering, batch processing, background jobs",
        "default_read_ratio": 0.20,
        "default_write_ratio": 0.80,
        "default_p95_sla_ms": 50.0,
        "keywords": ["video", "videos", "render", "rendering", "generation", "generate", "generating", "ai", "background", "async", "asynchronous", "worker", "workers", "queue", "queues", "batch", "encode", "encoding", "export", "transcode"],
    },
    "TRANSACTIONAL_OLTP": {
        "description": "Strict ACID transactional consistency, financial ledgers, bookings, checkout, order mutations",
        "default_read_ratio": 0.50,
        "default_write_ratio": 0.50,
        "default_p95_sla_ms": 150.0,
        "keywords": ["booking", "bookings", "reservation", "reservations", "payment", "payments", "bank", "banking", "financial", "finance", "transaction", "transactions", "transactional", "checkout", "order", "orders", "ledger", "wallet", "crypto", "oltp"],
    },
    "WRITE_HEAVY_INGESTION": {
        "description": "Continuous telemetry, sensor ingestion, clickstream analytics, logs",
        "default_read_ratio": 0.10,
        "default_write_ratio": 0.90,
        "default_p95_sla_ms": 100.0,
        "keywords": ["telemetry", "iot", "sensor", "sensors", "analytics", "tracking", "log", "logs", "logging", "metrics", "metric", "ingest", "ingestion", "stream", "streams"],
    },
    "REALTIME_STREAM_TRACKING": {
        "description": "Real-time state synchronization, live vehicle GPS tracking, chat messaging, multiplayer state",
        "default_read_ratio": 0.50,
        "default_write_ratio": 0.50,
        "default_p95_sla_ms": 40.0,
        "keywords": ["live", "real-time", "realtime", "chat", "chats", "messaging", "message", "messages", "gps", "drone", "drones", "vehicle", "vehicles", "websocket", "websockets"],
    },
    "READ_HEAVY_INTERACTIVE": {
        "description": "Read-dominated browsing with hot cacheable data (ratings, reviews, catalog, feeds, maps, listings)",
        "default_read_ratio": 0.90,
        "default_write_ratio": 0.10,
        "default_p95_sla_ms": 100.0,
        "keywords": ["hotel", "hotels", "rating", "ratings", "review", "reviews", "map", "maps", "listing", "listings", "catalog", "catalogs", "browse", "browsing", "photo", "photos", "image", "images", "feed", "feeds", "social", "search", "searching", "shop", "shopping", "ecommerce", "store"],
    },
}


def extract_dynamic_domain(text: str) -> str:
    """Extracts open-ended application domain from prompt text."""
    text_clean = text.lower().strip()
    if "ecommerce" in text_clean or "e-commerce" in text_clean or "shop" in text_clean or "store" in text_clean:
        return "ecommerce"
    if "transactional" in text_clean or "banking" in text_clean or "payment" in text_clean or "financial" in text_clean:
        return "transactional"
    if "background" in text_clean or "worker" in text_clean or "queue" in text_clean:
        return "background_processing"
    if "analytics" in text_clean or "logging" in text_clean or "telemetry" in text_clean:
        return "analytics_pipeline"

    # Dynamic extraction for open-ended product requests
    match = re.search(
        r"(?:backend\s+for\s+(?:an?|the)?|build\s+(?:an?|the)?|building\s+(?:an?|the)?|create\s+(?:an?|the)?)\s*([a-zA-Z0-9\s\-]+?)(?:\s+(?:that|where|targeting|which|to|\.|\,)|$)",
        text.strip(),
        re.IGNORECASE,
    )
    if match:
        slug = re.sub(r"[\s\-]+", "_", match.group(1).strip()).lower()
        if len(slug) >= 3 and slug not in ("system", "application", "backend", "app", "service"):
            return slug

    if "photo" in text_clean or "image" in text_clean or "feed" in text_clean or "social" in text_clean:
        return "social_media_feed"

    return "general_web_service"


def classify_system_archetype(text: str) -> Tuple[str, Dict[str, Any]]:
    """Maps free-form application text to a calibrated engineering archetype."""
    text_lower = text.lower()
    for arch_name, info in SYSTEM_ARCHETYPES.items():
        for kw in info["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                return arch_name, info
    return "GENERAL_WEB_SERVICE", {
        "description": "Standard interactive CRUD web service with balanced reads and writes",
        "default_read_ratio": 0.70,
        "default_write_ratio": 0.30,
        "default_p95_sla_ms": 100.0,
    }


class ArchitectureAgent:
    """Agent that translates natural-language prompts into validated ORBIT specifications."""

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()
        self.generator = ArchitectureGenerator()

    @staticmethod
    def fallback_parse(request_text: str, already_clarified: bool = False) -> WorkloadExtractionResult:
        """
        Deterministic regex, natural scale inference, and ambiguity ranking parser.
        Safely extracts numerical engineering constraints or flags ambiguity via ranked questions.
        """
        text = request_text.lower().strip()
        user_facts: Dict[str, Any] = {}
        agent_assumptions: List[str] = []

        # Check for empty query
        if not text or len(text.split()) < 2:
            return WorkloadExtractionResult(
                clarification_questions=[
                    "What is your target steady-state throughput or user volume (e.g. 500 requests/sec, or 100K daily active users)?",
                    "What is your acceptable p95 latency threshold (e.g. under 50ms, 100ms)?",
                    "What is your monthly infrastructure budget limit (e.g. $250/month)?",
                ],
                ambiguities=["Request lacks operational targets and load parameters."],
                user_facts={},
                agent_assumptions=[],
            )

        # 1. Throughput (RPS or DAU/MAU)
        rps: Optional[float] = None
        peak_factor: Optional[float] = None
        has_throughput = False

        rps_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:rps|req/s|requests?\s*(?:per|/)\s*sec|qps)", text)
        if rps_match:
            rps = float(rps_match.group(1))
            user_facts["request_rate_rps"] = rps
            has_throughput = True
        else:
            traffic_derived = parse_natural_traffic(text)
            if traffic_derived:
                avg_r, peak_r, explanation = traffic_derived
                rps = avg_r
                peak_factor = round(peak_r / max(1.0, rps), 2)
                user_facts["request_rate_rps"] = rps
                user_facts["peak_load_factor"] = peak_factor
                agent_assumptions.append(explanation)
                has_throughput = True

        # Peak load factor if explicitly given
        peak_match = re.search(r"peak\s*(\d+(?:\.\d+)?)\s*(?:rps|req/s|qps)", text)
        if peak_match:
            peak_rps = float(peak_match.group(1))
            peak_factor = round(peak_rps / max(1.0, rps if rps else 1.0), 2)
            user_facts["peak_load_factor"] = peak_factor

        # 2. Latency Target (p95 ms)
        p95: Optional[float] = None
        has_latency = False
        lat_match = re.search(r"(?:p95|latency|sla|response\s*time)?\s*(?:under|<=|<|below|of|target:?|is)?\s*(\d+(?:\.\d+)?)\s*ms", text)
        if lat_match:
            p95 = float(lat_match.group(1))
            user_facts["p95_latency_target_ms"] = p95
            has_latency = True

        # 3. Monthly Budget (USD)
        budget: Optional[float] = None
        has_budget = False
        budget_match = re.search(r"\$\s*(\d+(?:\.\d+)?)|(?:budget|cost|cap)?\s*(\d+(?:\.\d+)?)\s*(?:usd|dollars|/month|/mo)", text)
        if budget_match:
            b_val = budget_match.group(1) or budget_match.group(2)
            budget = float(b_val)
            user_facts["max_monthly_budget_usd"] = budget
            has_budget = True

        # 4. Read / Write Ratio
        read_ratio = 0.90
        write_ratio = 0.10
        has_read_write = False

        ratio_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        read_pct_match = re.search(r"(\d+)%\s*(?:reads?|read)", text)
        write_pct_match = re.search(r"(\d+)%\s*(?:writes?|write)", text)

        if read_pct_match and write_pct_match:
            r_pct = float(read_pct_match.group(1))
            w_pct = float(write_pct_match.group(1))
            total = r_pct + w_pct
            if total > 0:
                read_ratio = round(r_pct / total, 2)
                write_ratio = round(w_pct / total, 2)
                user_facts["read_ratio"] = read_ratio
                user_facts["write_ratio"] = write_ratio
                has_read_write = True
        elif read_pct_match:
            r_pct = float(read_pct_match.group(1))
            read_ratio = max(0.01, min(0.99, r_pct / 100.0))
            write_ratio = round(1.0 - read_ratio, 2)
            user_facts["read_ratio"] = read_ratio
            user_facts["write_ratio"] = write_ratio
            has_read_write = True
        elif ratio_match:
            r1, r2 = float(ratio_match.group(1)), float(ratio_match.group(2))
            total = r1 + r2
            if total > 0:
                read_ratio = round(r1 / total, 2)
                write_ratio = round(1.0 - read_ratio, 2)
                user_facts["read_ratio"] = read_ratio
                user_facts["write_ratio"] = write_ratio
                has_read_write = True
        elif "read-heavy" in text or "read heavy" in text:
            read_ratio = 0.90
            write_ratio = 0.10
            user_facts["read_ratio"] = read_ratio
            user_facts["write_ratio"] = write_ratio
            has_read_write = True
        elif "write-heavy" in text or "write heavy" in text:
            read_ratio = 0.40
            write_ratio = 0.60
            user_facts["read_ratio"] = read_ratio
            user_facts["write_ratio"] = write_ratio
            has_read_write = True

        # 5. Dynamic Domain & System Archetype Inference
        app_type = extract_dynamic_domain(text)
        if app_type != "general_web_service":
            user_facts["app_type"] = app_type
        else:
            agent_assumptions.append("Application domain defaulted to General Web Service")

        archetype_name, archetype_info = classify_system_archetype(text)
        agent_assumptions.append(f"System Archetype identified: {archetype_name} ({archetype_info['description']})")

        if not has_read_write:
            read_ratio = archetype_info["default_read_ratio"]
            write_ratio = archetype_info["default_write_ratio"]
            has_read_write = True

        # 6. Ambiguity Ranking & Threshold Evaluation
        clarification_questions: List[str] = []
        ambiguities: List[str] = []

        if not already_clarified:
            amb_score, ranked_q = rank_and_evaluate_ambiguity(
                has_throughput=has_throughput,
                has_latency=has_latency,
                has_budget=has_budget,
                has_read_write=has_read_write,
                threshold=0.50,
            )
            if ranked_q:
                clarification_questions = ranked_q
                ambiguities.append(f"Ambiguity score {amb_score:.2f} >= 0.50. Clarification required on ranked operational dimensions.")

        # 7. Safe Default Fallback if proceeding without clarification
        if not clarification_questions:
            if rps is None:
                rps = 500.0
                agent_assumptions.append("Default load assumed: 500.0 RPS")
            if peak_factor is None:
                peak_factor = 2.0
                agent_assumptions.append("Peak burst headroom assumed: 2.0x")
            if p95 is None:
                p95 = 50.0
                agent_assumptions.append("Default p95 latency target assumed: 50.0 ms")
            if budget is None:
                budget = 250.0
                agent_assumptions.append("Default budget cap assumed: $250.00/mo")
            if "Default read/write split" not in "".join(agent_assumptions) and not has_read_write:
                agent_assumptions.append(f"Default read/write split: {int(read_ratio*100)}% Reads / {int(write_ratio*100)}% Writes")
        else:
            # When clarifying, preserve peak_factor if derived, or 2.0
            if peak_factor is None:
                peak_factor = 2.0

        # Tailor soft preferences by domain requirements & system archetype
        if app_type == "background_processing" or archetype_name in ("DECOUPLED_ASYNC_COMPUTE", "WRITE_HEAVY_INGESTION"):
            soft_prefs = {"cost": 0.25, "latency": 0.65, "simplicity": 0.10}
        elif app_type == "transactional" or archetype_name == "TRANSACTIONAL_OLTP":
            soft_prefs = {"cost": 0.40, "latency": 0.35, "simplicity": 0.25}
        elif app_type == "ecommerce":
            soft_prefs = {"cost": 0.30, "latency": 0.50, "simplicity": 0.20}
        else:
            soft_prefs = {"cost": 0.35, "latency": 0.45, "simplicity": 0.20}

        agent_assumptions.append("Cache hit rate expectation: 85%")

        return WorkloadExtractionResult(
            app_type=app_type,
            request_rate_rps=rps,
            peak_load_factor=peak_factor,
            read_ratio=read_ratio,
            write_ratio=write_ratio,
            dataset_records=1_000_000,
            p95_latency_target_ms=p95,
            min_throughput_rps=round(rps * 0.9, 1) if rps else 450.0,
            max_monthly_budget_usd=budget,
            cache_assumed_hit_rate=0.85,
            soft_preferences=soft_prefs,
            user_facts=user_facts,
            agent_assumptions=agent_assumptions,
            clarification_questions=clarification_questions,
            ambiguities=ambiguities,
        )

    def parse_request(
        self,
        request_text: str,
        already_clarified: bool = False,
    ) -> Tuple[Optional[WorkloadSpec], List[str], List[str], ExecutionMode]:
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
                extracted = self.fallback_parse(request_text, already_clarified=already_clarified)
                mode = ExecutionMode.FALLBACK
        else:
            extracted = self.fallback_parse(request_text, already_clarified=already_clarified)
            mode = ExecutionMode.FALLBACK

        # If clarification questions were generated and not already clarified
        if extracted.clarification_questions and not already_clarified:
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
