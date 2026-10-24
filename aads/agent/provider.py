"""
LLM Provider Abstraction & Fallback Management.
Provides clean initialization of ChatOpenAI when credentials are present,
or returns an explicitly labeled deterministic fallback mode when unavailable.
"""
import os
import logging
from enum import Enum
from typing import Optional, Tuple, Any, Callable, Dict
from langchain_core.language_models.chat_models import BaseChatModel

from aads.core.config import settings, LLMConfig

logger = logging.getLogger("aads.agent.provider")


class ExecutionMode(str, Enum):
    LLM = "LLM"
    FALLBACK = "FALLBACK"


class LLMProviderManager:
    """Manages LLM provider access with deterministic labeled fallback."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or settings.llm
        self._cached_model: Optional[BaseChatModel] = None
        self._mode: Optional[ExecutionMode] = None
        self._reason: str = ""
        self._detect_provider()

    def _detect_provider(self):
        # Check explicit force fallback switch or absence of API key
        agent_mode_env = os.getenv("AADS_AGENT_MODE", "").lower()
        if self.config.force_fallback or agent_mode_env == "fallback":
            self._mode = ExecutionMode.FALLBACK
            self._reason = "AADS_FORCE_FALLBACK or AADS_AGENT_MODE=fallback explicitly configured"
            logger.info(f"Operating in deterministic fallback mode ({self._reason}).")
            return

        api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            self._mode = ExecutionMode.FALLBACK
            self._reason = "OPENAI_API_KEY not configured in environment"
            logger.info("OPENAI_API_KEY not configured: operating in deterministic labeled fallback mode.")
            return

        try:
            from langchain_openai import ChatOpenAI

            kwargs: dict = {
                "model": self.config.openai_model_name,
                "temperature": self.config.temperature,
                "timeout": self.config.timeout_seconds,
                "max_retries": self.config.max_retries,
                "api_key": api_key,
            }
            if self.config.openai_api_base:
                kwargs["base_url"] = self.config.openai_api_base

            self._cached_model = ChatOpenAI(**kwargs)
            self._mode = ExecutionMode.LLM
            self._reason = f"Configured via {self.config.openai_model_name}"
            logger.info(f"Initialized ChatOpenAI model: {self.config.openai_model_name}")
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
        return {
            "is_fallback": mode == ExecutionMode.FALLBACK,
            "execution_mode": mode.value,
            "provider": "OpenAI" if mode == ExecutionMode.LLM else "Local Deterministic Heuristic",
            "model_name": self.config.openai_model_name if mode == ExecutionMode.LLM else "rule_based_parser",
            "reason": self._reason,
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
