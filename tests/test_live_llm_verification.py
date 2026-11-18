"""
Unit tests for explicit opt-in live LLM provider verification (Phase 4A Part 1).
Validates missing credentials, error categorization, secret redaction, and mocked structured responses.
Guarantees NO external network requests are made during testing.
"""
import pytest
from unittest.mock import MagicMock, patch

from orbit.agent.provider import (
    LLMProviderManager,
    verify_live_llm,
    redact_secrets,
)
from orbit.agent.architecture_agent import WorkloadExtractionResult
from orbit.core.config import LLMConfig


def test_missing_credentials(monkeypatch):
    """Test 1: Provider verification cleanly reports MISSING_CREDENTIALS when unset."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("AADS_AGENT_MODE", "auto")
    cfg = LLMConfig(openai_api_key=None, force_fallback=False)

    res = verify_live_llm(config=cfg)
    assert res["success"] is False
    assert res["status"] == "MISSING_CREDENTIALS"
    assert "API_KEY" in res["error_message"]
    assert "API_KEY" in res["instructions"]
    assert res["source"] == "LIVE_LLM_VERIFICATION"
    assert res["extracted_fields"] is None


def test_forced_fallback_flag(monkeypatch):
    """Test 2: Provider verification identifies when fallback is explicitly forced."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-for-unit-test-12345678")
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "true")
    cfg = LLMConfig(openai_api_key="sk-mock-key-for-unit-test-12345678", force_fallback=True)

    res = verify_live_llm(config=cfg)
    assert res["success"] is False
    assert res["status"] == "FORCED_FALLBACK"
    assert "AADS_FORCE_FALLBACK" in res["error_message"]
    assert res["is_fallback"] is True


def test_successful_mocked_live_verification(monkeypatch):
    """Test 3: Provider verification succeeds with valid structured response from mocked client."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-valid-key-123456789012345")
    monkeypatch.setenv("AADS_FORCE_FALLBACK", "false")
    monkeypatch.setenv("AADS_AGENT_MODE", "auto")

    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured

    mock_structured.invoke.return_value = WorkloadExtractionResult(
        app_type="social_media_feed",
        request_rate_rps=200.0,
        read_ratio=0.90,
        write_ratio=0.10,
        p95_latency_target_ms=40.0,
        max_monthly_budget_usd=100.0,
    )

    with patch("langchain_openai.ChatOpenAI", return_value=mock_chat):
        mgr = LLMProviderManager(config=LLMConfig(openai_api_key="sk-mock-valid-key-123456789012345", force_fallback=False))
        res = mgr.verify_live_connectivity()

        assert res["success"] is True
        assert res["status"] == "SUCCESS"
        assert res["extracted_fields"] is not None
        assert res["extracted_fields"]["request_rate_rps"] == 200.0
        assert res["extracted_fields"]["read_ratio"] == 0.90
        assert res["error_message"] is None


def test_authentication_error_handling(monkeypatch):
    """Test 4: Provider verification classifies HTTP 401 as AUTHENTICATION_ERROR."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-invalid-test-key-123456789012")

    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = RuntimeError("Error 401: Invalid API Key provided (invalid_api_key)")

    with patch("langchain_openai.ChatOpenAI", return_value=mock_chat):
        mgr = LLMProviderManager(config=LLMConfig(openai_api_key="sk-invalid-test-key-123456789012", force_fallback=False))
        res = mgr.verify_live_connectivity()

        assert res["success"] is False
        assert res["status"] == "AUTHENTICATION_ERROR"
        assert "401" in res["error_message"]


def test_rate_limit_error_handling(monkeypatch):
    """Test 5: Provider verification classifies HTTP 429 as RATE_LIMIT_ERROR."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-123456789012")

    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = RuntimeError("Error 429: Rate limit exceeded or quota exhausted")

    with patch("langchain_openai.ChatOpenAI", return_value=mock_chat):
        mgr = LLMProviderManager(config=LLMConfig(openai_api_key="sk-mock-key-123456789012", force_fallback=False))
        res = mgr.verify_live_connectivity()

        assert res["success"] is False
        assert res["status"] == "RATE_LIMIT_ERROR"
        assert "429" in res["error_message"]


def test_timeout_error_handling(monkeypatch):
    """Test 6: Provider verification classifies request timeouts as TIMEOUT_ERROR."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-123456789012")

    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured
    mock_structured.invoke.side_effect = TimeoutError("Request timed out after 15.0 seconds")

    with patch("langchain_openai.ChatOpenAI", return_value=mock_chat):
        mgr = LLMProviderManager(config=LLMConfig(openai_api_key="sk-mock-key-123456789012", force_fallback=False))
        res = mgr.verify_live_connectivity()

        assert res["success"] is False
        assert res["status"] == "TIMEOUT_ERROR"
        assert "timed out" in res["error_message"].lower()


def test_secret_redaction():
    """Test 7: Secrets and API keys are redacted from error messages."""
    raw_error = "Failed to connect with key sk-proj-supersecretkey1234567890abcdef and Bearer eyJhbGciOiJIUzI1NiJ9.testtoken"
    sanitized = redact_secrets(raw_error)

    assert "sk-proj-supersecretkey1234567890abcdef" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


def test_validation_failure_on_corrupt_output(monkeypatch):
    """Test 8: Rejects output missing critical SLA parameters."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-key-123456789012")

    mock_chat = MagicMock()
    mock_structured = MagicMock()
    mock_chat.with_structured_output.return_value = mock_structured

    # Corrupt extraction: missing request_rate_rps
    mock_structured.invoke.return_value = WorkloadExtractionResult(
        app_type="social_media_feed",
        request_rate_rps=None,
    )

    with patch("langchain_openai.ChatOpenAI", return_value=mock_chat):
        mgr = LLMProviderManager(config=LLMConfig(openai_api_key="sk-mock-key-123456789012", force_fallback=False))
        res = mgr.verify_live_connectivity()

        assert res["success"] is False
        assert res["status"] == "VALIDATION_FAILED"
        assert "missing valid request_rate_rps" in res["error_message"]
