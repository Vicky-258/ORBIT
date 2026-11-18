"""
Dynamic Domain Understanding Module for ORBIT (Phase: Hybrid Workload Intelligence).
Extracts rich, domain-independent representations of arbitrary user applications.

Design Principle:
Application domains are completely free-form and open-ended.
ORBIT never forces applications into a fixed set of domain categories.
"""
import re
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage
from orbit.agent.provider import LLMProviderManager, ExecutionMode

logger = logging.getLogger("orbit.agent.domain_understanding")


class DomainOfflineError(RuntimeError):
    """Raised when live LLM is offline and test_mode is False."""
    pass


class DomainIdentity(BaseModel):
    """Structured, domain-independent representation of the user application."""
    domain_identity: str = Field(description="Normalized snake_case application identity, e.g. 'hotel_discovery_platform'")
    description: str = Field(description="Clear explanation of the application's business and technical purpose")
    primary_purpose: str = Field(description="Core value proposition or primary mission of the system")
    target_users: List[str] = Field(default_factory=list, description="Primary actors or user categories")
    core_functionalities: List[str] = Field(default_factory=list, description="Explicit capabilities and operations")
    domain_entities: List[str] = Field(default_factory=list, description="Core business entities and data models")
    major_user_journeys: List[str] = Field(default_factory=list, description="Primary end-to-end user workflows")
    data_operations: List[str] = Field(default_factory=list, description="Specific data read/write/streaming operations")
    external_dependencies: List[str] = Field(default_factory=list, description="External systems or APIs, e.g. 'map_provider'")
    functional_requirements: List[str] = Field(default_factory=list, description="Functional requirements extracted from input")
    non_functional_requirements: List[str] = Field(default_factory=list, description="Performance, budget, and SLA constraints")


DOMAIN_EXTRACTION_SYSTEM_PROMPT = """You are the ORBIT Domain Understanding Agent.
Your responsibility is to analyze user requests for arbitrary software applications and extract a rich, structured domain representation.

CRITICAL GUIDELINES:
1. Do NOT constrain the application to any predefined domain list. The domain identity must be specific to what the user describes (e.g. 'hotel_discovery_platform', 'drone_delivery_tracking', 'ai_video_education_platform').
2. Preserve the user's actual application intent accurately.
3. Identify external third-party dependencies explicitly (e.g. map providers, payment gateways, video CDNs).
4. Distinguish core functionalities from business domain entities.
5. Never invent fictional business requirements that the user did not specify.
"""


def _heuristic_domain_extraction(text: str) -> DomainIdentity:
    """
    Deterministic linguistic extractor used strictly for automated testing when offline.
    Extracts dynamic domain identity, verbs as functionalities, nouns as entities,
    and external services without hardcoded templates.
    """
    text_lower = text.lower()

    # 1. Infer dynamic domain identity from phrases
    domain_id = "general_application"
    match = re.search(r"(?:build|design|create|architect|implement)\s+(?:a|an)\s+([a-zA-Z0-9_\-\s]+?)(?:\s+where|\s+that|\s+for|\s+with|\.|\,|$)", text, re.IGNORECASE)
    if match:
        raw_name = match.group(1).strip()
        # Clean words
        clean_words = [w for w in re.split(r"[\s\-_]+", raw_name) if w and w.lower() not in ("a", "an", "the", "system", "platform", "backend", "application", "service")]
        if clean_words:
            domain_id = "_".join(clean_words).lower()
            if not domain_id.endswith(("_platform", "_system", "_app")):
                domain_id += "_platform"
        elif raw_name:
            domain_id = re.sub(r"[^\w]+", "_", raw_name.strip()).lower()
    else:
        # Fallback to key entity clustering
        words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", text_lower) if w not in ("and", "the", "for", "with", "that", "this", "can", "user", "users", "app", "build")]
        if words:
            domain_id = f"{words[0]}_platform"

    # 2. Extract functionalities by identifying action phrases
    functionalities: List[str] = []
    action_keywords = [
        ("browse", "browsing"),
        ("search", "search"),
        ("compare", "comparison"),
        ("view", "viewing"),
        ("upload", "upload"),
        ("review", "review_submission"),
        ("book", "booking"),
        ("pay", "payment"),
        ("generate", "generation"),
        ("track", "tracking"),
        ("stream", "streaming"),
        ("chat", "communication"),
        ("ingest", "telemetry_ingestion"),
    ]
    for kw, label in action_keywords:
        if re.search(r"\b" + re.escape(kw), text_lower):
            if label not in functionalities:
                functionalities.append(label)

    # 3. Extract domain entities
    entities: List[str] = []
    entity_keywords = [
        "hotel", "user", "review", "rating", "booking", "location", "map",
        "course", "video", "student", "payment", "classroom", "drone",
        "gps", "package", "order", "delivery", "account", "balance", "player",
        "game", "session", "match", "transaction", "telemetry", "metric"
    ]
    for ek in entity_keywords:
        if re.search(r"\b" + re.escape(ek) + r"(?:s|es)?\b", text_lower):
            if ek not in entities:
                entities.append(ek)

    # 4. Extract external dependencies
    ext_deps: List[str] = []
    if "map" in text_lower or "maps" in text_lower or "gps" in text_lower:
        ext_deps.append("map_provider")
    if "pay" in text_lower or "payment" in text_lower or "stripe" in text_lower:
        ext_deps.append("payment_gateway")
    if "video" in text_lower or "transcode" in text_lower:
        ext_deps.append("object_storage_cdn")

    return DomainIdentity(
        domain_identity=domain_id,
        description=f"A system designed for {text.strip()[:140]}...",
        primary_purpose=f"Provide capabilities for {', '.join(functionalities) if functionalities else 'user workflows'}.",
        target_users=["end_users", "administrators"],
        core_functionalities=functionalities or ["core_service_processing"],
        domain_entities=entities or ["data_record"],
        major_user_journeys=[f"Execute {f}" for f in functionalities[:3]] if functionalities else ["Standard user journey"],
        data_operations=[f"{f}_operation" for f in functionalities] if functionalities else ["read_write_operations"],
        external_dependencies=ext_deps,
        functional_requirements=[f"System must support {f}" for f in functionalities],
        non_functional_requirements=["High availability", "Scalable throughput"],
    )


class DomainUnderstandingAgent:
    """Agent that extracts structured domain identity and functional requirements."""

    def __init__(self, provider_mgr: Optional[LLMProviderManager] = None):
        self.provider_mgr = provider_mgr or LLMProviderManager()

    def analyze_domain(self, text: str, test_mode: bool = False) -> DomainIdentity:
        """
        Analyzes the application text and extracts a DomainIdentity.
        In production (test_mode=False): Requires live LLM connectivity. If LLM is offline,
        raises DomainOfflineError rather than fabricating inaccurate results.
        In test mode (test_mode=True): Uses deterministic linguistic heuristics.
        """
        if test_mode:
            logger.info("Executing deterministic linguistic domain extractor (test_mode=True).")
            return _heuristic_domain_extraction(text)

        mode = self.provider_mgr.get_execution_mode()

        if mode == ExecutionMode.LLM:
            llm = self.provider_mgr.get_chat_model()
            if llm:
                try:
                    structured_llm = llm.with_structured_output(DomainIdentity)
                    messages = [
                        SystemMessage(content=DOMAIN_EXTRACTION_SYSTEM_PROMPT),
                        HumanMessage(content=text),
                    ]
                    result = structured_llm.invoke(messages)
                    if isinstance(result, DomainIdentity):
                        return result
                    if isinstance(result, dict):
                        return DomainIdentity(**result)
                except Exception as exc:
                    logger.warning(f"Live LLM domain extraction failed: {exc}")
                    raise DomainOfflineError(
                        f"LLM domain extraction failed: {exc}. ORBIT does not return fabricated mock domains in production."
                    ) from exc

        raise DomainOfflineError(
            "ORBIT Domain Intelligence requires an active LLM provider (e.g. GROQ_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY). "
            "To prevent inaccurate architectural recommendations, ORBIT does not return hardcoded fallback domains in live mode. "
            "Configure your API credentials in .env or run with test_mode=True in automated unit tests."
        )
