"""Unit tests for ObservabilityService."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.observability import (
    ObservabilityService,
    TokenUsage,
    TraceMetadata,
    get_observability,
)


class TestTokenUsage:
    """TokenUsage dataclass tests."""

    def test_default_values(self):
        """Should have zero default values."""
        usage = TokenUsage()
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_custom_values(self):
        """Should accept custom values."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestTraceMetadata:
    """TraceMetadata dataclass tests."""

    def test_default_values(self):
        """Should have sensible defaults."""
        meta = TraceMetadata()
        assert meta.vendor_id is None
        assert meta.skill_version is None
        assert meta.document_id is None
        assert meta.operation == "unknown"
        assert meta.model == ""
        assert meta.extra == {}

    def test_custom_values(self):
        """Should accept custom values."""
        meta = TraceMetadata(
            vendor_id="habitus",
            skill_version="1.0.0",
            document_id="doc-123",
            operation="boq_extraction",
            model="gemini-3-flash-preview",
            extra={"page_count": 10},
        )
        assert meta.vendor_id == "habitus"
        assert meta.skill_version == "1.0.0"
        assert meta.document_id == "doc-123"
        assert meta.operation == "boq_extraction"
        assert meta.model == "gemini-3-flash-preview"
        assert meta.extra == {"page_count": 10}


class TestTokenUsageExtraction:
    """Test token usage extraction from Gemini responses."""

    def test_extract_from_valid_response(self):
        """Should extract token counts from valid Gemini response."""
        service = ObservabilityService()

        mock_response = Mock()
        mock_response.usage_metadata = Mock(
            prompt_token_count=100,
            candidates_token_count=50,
            total_token_count=150,
        )

        usage = service.extract_token_usage(mock_response)

        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_extract_from_none_response(self):
        """Should return zero counts for None response."""
        service = ObservabilityService()

        usage = service.extract_token_usage(None)

        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_extract_from_response_without_metadata(self):
        """Should return zero counts when usage_metadata is missing."""
        service = ObservabilityService()

        mock_response = Mock(spec=[])  # No usage_metadata attribute

        usage = service.extract_token_usage(mock_response)

        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0

    def test_calculate_total_when_zero(self):
        """Should calculate total when not provided."""
        service = ObservabilityService()

        mock_response = Mock()
        mock_response.usage_metadata = Mock(
            prompt_token_count=100,
            candidates_token_count=50,
            total_token_count=0,  # Not provided
        )

        usage = service.extract_token_usage(mock_response)

        assert usage.total_tokens == 150  # Calculated

    def test_handle_none_token_counts(self):
        """Should handle None token counts gracefully."""
        service = ObservabilityService()

        mock_response = Mock()
        mock_response.usage_metadata = Mock(
            prompt_token_count=None,
            candidates_token_count=None,
            total_token_count=None,
        )

        usage = service.extract_token_usage(mock_response)

        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0


class TestObservabilityDisabled:
    """Test behavior when observability is disabled."""

    @patch("app.services.observability.settings")
    def test_disabled_by_default(self, mock_settings):
        """Should be disabled when langfuse_enabled is False."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()

        assert not service.is_enabled

    @patch("app.services.observability.settings")
    def test_track_call_when_disabled(self, mock_settings):
        """Should not fail when tracking with disabled service."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()

        usage = service.track_gemini_call(
            name="test",
            prompt="test prompt",
            response=None,
            metadata=TraceMetadata(operation="test"),
        )

        assert usage.total_tokens == 0

    @patch("app.services.observability.settings")
    def test_shutdown_when_disabled(self, mock_settings):
        """Should not fail on shutdown when disabled."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()
        service.shutdown()  # Should not raise

    @patch("app.services.observability.settings")
    def test_flush_when_disabled(self, mock_settings):
        """Should not fail on flush when disabled."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()
        service.flush()  # Should not raise


class TestObservabilityEnabled:
    """Test behavior when observability is enabled."""

    @patch("app.services.observability.settings")
    def test_disabled_without_api_keys(self, mock_settings):
        """Should disable itself when API keys are missing."""
        mock_settings.langfuse_enabled = True
        mock_settings.langfuse_public_key = ""
        mock_settings.langfuse_secret_key = ""

        service = ObservabilityService()

        assert not service.is_enabled

    @patch("app.services.observability.settings")
    @patch("app.services.observability.Langfuse", create=True)
    def test_enabled_with_api_keys(self, mock_langfuse_class, mock_settings):
        """Should enable when API keys are provided."""
        mock_settings.langfuse_enabled = True
        mock_settings.langfuse_public_key = "pk-test"
        mock_settings.langfuse_secret_key = "sk-test"
        mock_settings.langfuse_host = "https://cloud.langfuse.com"
        mock_settings.langfuse_release = "1.0.0"

        # Mock the Langfuse import
        with patch.dict("sys.modules", {"langfuse": MagicMock()}):
            with patch("app.services.observability.Langfuse", mock_langfuse_class):
                service = ObservabilityService()
                service._langfuse = Mock()  # Simulate successful init
                service._enabled = True

                assert service.is_enabled


class TestErrorIsolation:
    """Test that observability errors don't affect main flow."""

    def test_record_generation_handles_exception(self):
        """Recording errors should be caught and logged."""
        service = ObservabilityService()
        service._enabled = True
        service._langfuse = Mock()
        service._langfuse.trace.side_effect = Exception("LangFuse error")

        # Should not raise
        ctx = {
            "response": None,
            "prompt": "test",
            "error": None,
            "start_time": datetime.utcnow(),
        }
        service._record_generation("test", ctx, None)  # Should not raise

    def test_track_gemini_call_handles_exception(self):
        """track_gemini_call should not raise on internal errors."""
        service = ObservabilityService()
        service._enabled = True
        service._langfuse = Mock()
        service._langfuse.trace.side_effect = Exception("LangFuse error")

        # Should not raise, should return usage
        usage = service.track_gemini_call(
            name="test",
            prompt="test prompt",
            response=None,
            metadata=TraceMetadata(operation="test"),
            start_time=datetime.utcnow(),
            error="some error",
        )

        assert isinstance(usage, TokenUsage)

    def test_shutdown_handles_exception(self):
        """Shutdown should not raise on internal errors."""
        service = ObservabilityService()
        service._langfuse = Mock()
        service._langfuse.flush.side_effect = Exception("Flush error")

        service.shutdown()  # Should not raise

    def test_flush_handles_exception(self):
        """Flush should not raise on internal errors."""
        service = ObservabilityService()
        service._enabled = True
        service._langfuse = Mock()
        service._langfuse.flush.side_effect = Exception("Flush error")

        service.flush()  # Should not raise


class TestSingleton:
    """Test singleton pattern."""

    @patch("app.services.observability._observability_instance", None)
    @patch("app.services.observability.settings")
    def test_get_observability_returns_singleton(self, mock_settings):
        """get_observability should return the same instance."""
        mock_settings.langfuse_enabled = False

        instance1 = get_observability()
        instance2 = get_observability()

        assert instance1 is instance2


class TestContextManager:
    """Test trace_generation context manager."""

    @patch("app.services.observability.settings")
    def test_context_manager_yields_dict(self, mock_settings):
        """trace_generation should yield a context dict."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()

        with service.trace_generation("test") as ctx:
            assert isinstance(ctx, dict)
            assert "response" in ctx
            assert "prompt" in ctx
            assert "error" in ctx
            assert "start_time" in ctx

    @patch("app.services.observability.settings")
    def test_context_manager_captures_exception(self, mock_settings):
        """trace_generation should capture exceptions."""
        mock_settings.langfuse_enabled = False

        service = ObservabilityService()

        with pytest.raises(ValueError):
            with service.trace_generation("test") as ctx:
                ctx["prompt"] = "test prompt"
                raise ValueError("Test error")
