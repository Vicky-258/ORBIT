"""
LLM Provider Abstraction & Fallback Management.
Provides clean initialization of ChatOpenAI when credentials are present,
or returns an explicitly labeled deterministic fallback mode when unavailable.
"""
import os
import re
import time
import logging
from enum import Enum
from typing import Optional, Tuple, Any, Callable, Dict
from langchain_core.language_models.chat_models import BaseChatModel

from aads.core.config import settings, LLMConfig

logger = logging.getLogger("aads.agent.provider")


class ExecutionMode(str, Enum):
    LLM = "LLM"
    FALLBACK = "FALLBACK"



def redact_secrets(text: str) -> str:
    """Redacts potential API keys or tokens from string to prevent credential leakage."""
    if not isinstance(text, str):
        return str(text)
    # Mask OpenAI-style keys (sk-...) and Groq keys (gsk_...)
    text = re.sub(r'sk-[a-zA-Z0-9_\-]{15,}', '[REDACTED_API_KEY]', text)
    text = re.sub(r'gsk_[a-zA-Z0-9_\-]{15,}', '[REDACTED_API_KEY]', text)
    # Mask Authorization headers / bearer tokens
    text = re.sub(r'(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}', r'\1[REDACTED_TOKEN]', text, flags=re.IGNORECASE)
    # Mask any api_key query params or json values
    text = re.sub(r'(["\']?api[_-]?key["\']?\s*[:=]\s*["\'])[^"\'\s]+(["\'])', r'\1[REDACTED_KEY]\2', text, flags=re.IGNORECASE)
    return text

class LLMProviderManager:
    """Manages LLM provider access with deterministic labeled fallback."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._cached_model: Optional[BaseChatModel] = None
        self._mode: Optional[ExecutionMode] = None
        self._reason: str = ""
        self._detect_provider()

    def _detect_provider(self):
        # Check explicit force fallback switch or absence of API key
        force_fallback_env = os.getenv("AADS_FORCE_FALLBACK", "").lower() in ("true", "1")
        agent_mode_env = os.getenv("AADS_AGENT_MODE", "").lower()
        if self.config.force_fallback or force_fallback_env or agent_mode_env == "fallback":
            self._mode = ExecutionMode.FALLBACK
            self._reason = "AADS_FORCE_FALLBACK or AADS_AGENT_MODE=fallback explicitly configured"
            logger.info(f"Operating in deterministic fallback mode ({self._reason}).")
            return

        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        if not api_key:
            self._mode = ExecutionMode.FALLBACK
            self._reason = "Neither OPENAI_API_KEY nor GROQ_API_KEY configured in environment"
            logger.info("No API key configured: operating in deterministic labeled fallback mode.")
            return

        is_groq = bool(os.getenv("GROQ_API_KEY") or (api_key and api_key.startswith("gsk_")) or ("groq.com" in (self.config.openai_api_base or "")))
        provider_name = "Groq" if is_groq else "OpenAI"
        base_url = self.config.openai_api_base or ("https://api.groq.com/openai/v1" if is_groq else None)
        model_name = self.config.openai_model_name or (("openai/gpt-oss-120b" if is_groq else "gpt-4o-mini"))

        try:
            from langchain_openai import ChatOpenAI

            kwargs: dict = {
                "model": model_name,
                "temperature": self.config.temperature,
                "timeout": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "api_key": api_key,
            }
            if base_url:
                kwargs["base_url"] = base_url

            self._cached_model = ChatOpenAI(**kwargs)
            self._mode = ExecutionMode.LLM
            self._reason = f"Configured via {provider_name}:{model_name}"
            logger.info(f"Initialized {provider_name} model: {model_name}")
        except Exception as e:
            self._mode = ExecutionMode.FALLBACK
            self._reason = f"Provider initialization failed: {str(e)}"
            logger.warning(f"Failed to initialize ChatOpenAI ({e}): switching to fallback mode.")

    def get_execution_mode(self) -> ExecutionMode:
        return self._mode or ExecutionMode.FALLBACK

    def is_llm_available(self) -> bool:
        return self.get_execution_mode() == ExecutionMode.LLM and self._cached_model is not None

    def get_chat_model(self) -> Optional[BaseChatModel]:
        return self._cached_model

    def get_status_summary(self) -> Dict[str, Any]:
        mode = self.get_execution_mode()
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        is_groq = bool(os.getenv("GROQ_API_KEY") or (api_key and api_key.startswith("gsk_")) or ("groq.com" in (self.config.openai_api_base or "")))
        provider_name = "Groq" if is_groq else "OpenAI"
        return {
            "is_fallback": mode == ExecutionMode.FALLBACK,
            "execution_mode": mode.value,
            "provider": provider_name if mode == ExecutionMode.LLM else "Local Deterministic Heuristic",
            "model_name": self.config.openai_model_name if mode == ExecutionMode.LLM else "rule_based_parser",
            "reason": self._reason,
        }

    def verify_live_connectivity(self, custom_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Explicit, opt-in verification of live LLM provider connectivity.
        Executes a single bounded structured request to confirm credentials,
        network reachability, and schema compliance without printing secrets.
        """
        # 1. Credentials presence check
        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        is_groq = bool(os.getenv("GROQ_API_KEY") or (api_key and api_key.startswith("gsk_")) or ("groq.com" in (self.config.openai_api_base or "")))
        provider_name = "Groq" if is_groq else "OpenAI"
        base_url = self.config.openai_api_base or ("https://api.groq.com/openai/v1" if is_groq else None)
        model_name = self.config.openai_model_name or (("openai/gpt-oss-120b" if is_groq else "gpt-4o-mini"))

        if not api_key or not api_key.strip():
            return {
                "success": False,
                "status": "MISSING_CREDENTIALS",
                "provider": provider_name,
                "model_name": model_name,
                "source": "LIVE_LLM_VERIFICATION",
                "error_message": "Neither OPENAI_API_KEY nor GROQ_API_KEY is configured in environment or settings.",
                "instructions": (
                    "Set an API key in your environment:\n"
                    "  export GROQ_API_KEY='gsk_...'\n"
                    "  or\n"
                    "  export OPENAI_API_KEY='sk-...'"
                ),
                "latency_seconds": 0.0,
                "extracted_fields": None,
                "is_fallback": False,
            }

        # 2. Check if explicitly forced into fallback
        force_fallback_env = os.getenv("AADS_FORCE_FALLBACK", "").lower() in ("true", "1")
        agent_mode_env = os.getenv("AADS_AGENT_MODE", "").lower()
        if self.config.force_fallback or force_fallback_env or agent_mode_env == "fallback":
            return {
                "success": False,
                "status": "FORCED_FALLBACK",
                "provider": provider_name,
                "model_name": model_name,
                "source": "LIVE_LLM_VERIFICATION",
                "error_message": "AADS_FORCE_FALLBACK or AADS_AGENT_MODE=fallback is explicitly enabled.",
                "instructions": "Unset AADS_FORCE_FALLBACK and set AADS_AGENT_MODE=auto to enable live calls.",
                "latency_seconds": 0.0,
                "extracted_fields": None,
                "is_fallback": True,
            }

        # 3. Import structured schema and messages
        from langchain_core.messages import SystemMessage, HumanMessage
        from aads.agent.architecture_agent import WorkloadExtractionResult

        test_prompt = custom_prompt or "Social media feed handling 200 RPS with 90% reads, p95 latency 40ms, budget $100/mo"
        messages = [
            SystemMessage(content="You are a system architecture assistant. Extract parameters accurately into the requested schema."),
            HumanMessage(content=test_prompt),
        ]

        start_t = time.perf_counter()
        try:
            # Direct model instantiation with short timeout
            model = self.get_chat_model()
            if model is None:
                from langchain_openai import ChatOpenAI
                kwargs: dict = {
                    "model": model_name,
                    "temperature": 0.0,
                    "timeout": min(self.config.timeout_seconds, 15.0),
                    "max_retries": 1,
                    "api_key": api_key,
                }
                if base_url:
                    kwargs["base_url"] = base_url
                model = ChatOpenAI(**kwargs)

            structured_model = model.with_structured_output(WorkloadExtractionResult)
            extracted = structured_model.invoke(messages)
            elapsed = round(time.perf_counter() - start_t, 3)

            if not isinstance(extracted, WorkloadExtractionResult):
                return {
                    "success": False,
                    "status": "VALIDATION_FAILED",
                    "provider": provider_name,
                    "model_name": model_name,
                    "source": "LIVE_LLM_VERIFICATION",
                    "error_message": f"Returned object of unexpected type: {type(extracted).__name__}",
                    "latency_seconds": elapsed,
                    "extracted_fields": None,
                    "is_fallback": False,
                }

            if extracted.request_rate_rps is None or extracted.request_rate_rps <= 0:
                return {
                    "success": False,
                    "status": "VALIDATION_FAILED",
                    "provider": provider_name,
                    "model_name": model_name,
                    "source": "LIVE_LLM_VERIFICATION",
                    "error_message": "Structured output missing valid request_rate_rps",
                    "latency_seconds": elapsed,
                    "extracted_fields": extracted.model_dump(),
                    "is_fallback": False,
                }

            return {
                "success": True,
                "status": "SUCCESS",
                "provider": provider_name,
                "model_name": model_name,
                "source": "LIVE_LLM_VERIFICATION",
                "latency_seconds": elapsed,
                "extracted_fields": {
                    "app_type": extracted.app_type,
                    "request_rate_rps": extracted.request_rate_rps,
                    "read_ratio": extracted.read_ratio,
                    "p95_latency_target_ms": extracted.p95_latency_target_ms,
                    "max_monthly_budget_usd": extracted.max_monthly_budget_usd,
                },
                "error_message": None,
                "is_fallback": False,
                "note": "Live LLM structured output verified. Bounded token usage incurred.",
            }

        except Exception as exc:
            elapsed = round(time.perf_counter() - start_t, 3)
            err_type = type(exc).__name__
            err_str = redact_secrets(str(exc))

            # Categorize error
            if "Authentication" in err_type or "401" in err_str or "auth" in err_str.lower() or "invalid_api_key" in err_str.lower():
                status = "AUTHENTICATION_ERROR"
            elif "RateLimit" in err_type or "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower():
                status = "RATE_LIMIT_ERROR"
            elif "Timeout" in err_type or "timed out" in err_str.lower():
                status = "TIMEOUT_ERROR"
            elif "Connection" in err_type or "connection" in err_str.lower():
                status = "CONNECTION_ERROR"
            else:
                status = "PROVIDER_ERROR"

            return {
                "success": False,
                "status": status,
                "provider": provider_name,
                "model_name": model_name,
                "source": "LIVE_LLM_VERIFICATION",
                "latency_seconds": elapsed,
                "extracted_fields": None,
                "error_message": f"{err_type}: {err_str}",
                "is_fallback": False,
            }

    def safe_structured_invoke(
        self,
        schema_cls: Any,
        prompt: Any,
        fallback_fn: Callable[[], Any],
    ) -> Tuple[Any, ExecutionMode]:
        """
        Invokes LLM with structured output, automatically recovering via fallback on error.
        """
        if not self.is_llm_available():
            return fallback_fn(), ExecutionMode.FALLBACK

        try:
            structured_llm = self._cached_model.with_structured_output(schema_cls)
            output = structured_llm.invoke(prompt)
            if output is None:
                raise ValueError("LLM returned empty structured output")
            return output, ExecutionMode.LLM
        except Exception as e:
            logger.warning(f"LLM structured invocation failed ({e}): using deterministic fallback.")
            return fallback_fn(), ExecutionMode.FALLBACK


# Backwards compatibility alias
LLMProvider = LLMProviderManager

def verify_live_llm(
    config: Optional[LLMConfig] = None,
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Explicit, opt-in verification of live LLM provider connectivity."""
    mgr = LLMProviderManager(config=config)
    return mgr.verify_live_connectivity(custom_prompt=custom_prompt)

