"""LangFuse observability service for tracking LLM calls."""

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, Optional

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage information from Gemini response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class TraceMetadata:
    """Metadata for a trace.

    Attributes:
        vendor_id: Vendor identifier (e.g., "habitus")
        skill_version: Version of the skill YAML used
        document_id: Source document ID
        operation: Operation name (e.g., "boq_extraction")
        model: LLM model name
        file_name: Original file name being processed
        page_count: Number of pages in PDF
        retry_count: Number of retries attempted
        environment: Environment (dev/staging/prod)
        extra: Additional custom metadata
    """

    vendor_id: Optional[str] = None
    skill_version: Optional[str] = None
    document_id: Optional[str] = None
    operation: str = "unknown"
    model: str = ""
    file_name: Optional[str] = None
    page_count: Optional[int] = None
    retry_count: int = 0
    environment: str = "development"
    extra: Dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """Service for tracking LLM calls using LangFuse."""

    def __init__(self):
        """Initialize LangFuse client if enabled."""
        self._langfuse = None
        self._enabled = settings.langfuse_enabled

        if self._enabled:
            self._init_langfuse()

    def _init_langfuse(self) -> None:
        """Initialize LangFuse client."""
        try:
            from langfuse import Langfuse

            if not settings.langfuse_public_key or not settings.langfuse_secret_key:
                logger.warning("LangFuse API keys not configured, disabling observability")
                self._enabled = False
                return

            self._langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                release=settings.langfuse_release,
            )
            logger.info("LangFuse observability initialized")

        except ImportError:
            logger.warning("langfuse package not installed, disabling observability")
            self._enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize LangFuse: {e}")
            self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Check if observability is enabled."""
        return self._enabled and self._langfuse is not None

    def extract_token_usage(self, response: Any) -> TokenUsage:
        """Extract token usage from Gemini response.

        Args:
            response: Gemini GenerateContentResponse

        Returns:
            TokenUsage with extracted counts
        """
        usage = TokenUsage()

        try:
            if hasattr(response, "usage_metadata"):
                metadata = response.usage_metadata
                usage.prompt_tokens = getattr(metadata, "prompt_token_count", 0) or 0
                usage.completion_tokens = getattr(metadata, "candidates_token_count", 0) or 0
                usage.total_tokens = getattr(metadata, "total_token_count", 0) or 0

                # Fallback: calculate total if not provided
                if usage.total_tokens == 0:
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        except Exception as e:
            logger.warning(f"Failed to extract token usage: {e}")

        return usage

    @contextmanager
    def trace_generation(
        self,
        name: str,
        metadata: Optional[TraceMetadata] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Context manager for tracing a generation (LLM call).

        Args:
            name: Name of the generation (e.g., "boq_extraction", "metadata_extraction")
            metadata: Optional trace metadata

        Yields:
            Dict to store generation results (response, usage, etc.)

        Example:
            with observability.trace_generation("boq_extraction", metadata) as ctx:
                response = model.generate_content(prompt)
                ctx["response"] = response
                ctx["prompt"] = prompt
        """
        ctx: Dict[str, Any] = {
            "response": None,
            "prompt": None,
            "error": None,
            "start_time": datetime.utcnow(),
        }

        try:
            yield ctx
        except Exception as e:
            ctx["error"] = str(e)
            raise
        finally:
            self._record_generation(name, ctx, metadata)

    def _record_generation(
        self,
        name: str,
        ctx: Dict[str, Any],
        metadata: Optional[TraceMetadata] = None,
    ) -> None:
        """Record generation to LangFuse.

        Args:
            name: Generation name
            ctx: Context dict with response, prompt, error
            metadata: Trace metadata
        """
        if not self.is_enabled:
            return

        try:
            meta = metadata or TraceMetadata()
            response = ctx.get("response")
            prompt = ctx.get("prompt")
            error = ctx.get("error")
            start_time = ctx.get("start_time", datetime.utcnow())
            end_time = datetime.utcnow()

            # Extract token usage if response available
            usage = self.extract_token_usage(response) if response else TokenUsage()

            # Extract response text
            output_text = None
            if response and hasattr(response, "text"):
                try:
                    output_text = response.text
                except Exception:
                    pass

            # Calculate latency
            latency_ms = (end_time - start_time).total_seconds() * 1000

            # Build metadata dict, filtering out None values for cleaner display
            trace_metadata = {
                k: v for k, v in {
                    "vendor_id": meta.vendor_id,
                    "skill_version": meta.skill_version,
                    "document_id": meta.document_id,
                    "operation": meta.operation,
                    "file_name": meta.file_name,
                    "page_count": meta.page_count,
                    "retry_count": meta.retry_count,
                    "environment": meta.environment,
                    "latency_ms": round(latency_ms, 2),
                    "status": "error" if error else "success",
                    **meta.extra,
                }.items() if v is not None
            }
            if error:
                trace_metadata["error"] = error

            # Create generation using start_observation (Langfuse SDK v3.x recommended API)
            generation = self._langfuse.start_observation(
                name=name,
                as_type="generation",
                model=meta.model or settings.gemini_model,
                input=prompt,
                output=output_text,
                metadata=trace_metadata,
                usage_details={
                    "input": usage.prompt_tokens,
                    "output": usage.completion_tokens,
                    "total": usage.total_tokens,
                },
            )
            generation.end()

            logger.debug(
                f"Recorded generation '{name}': "
                f"tokens={usage.total_tokens}, "
                f"vendor={meta.vendor_id}"
            )

        except Exception as e:
            # Never fail the main operation due to observability errors
            logger.warning(f"Failed to record generation to LangFuse: {e}")

    def track_gemini_call(
        self,
        name: str,
        prompt: str,
        response: Any,
        metadata: Optional[TraceMetadata] = None,
        start_time: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> TokenUsage:
        """Track a Gemini API call (non-context-manager version).

        Args:
            name: Generation name
            prompt: Input prompt
            response: Gemini response (can be None if error)
            metadata: Trace metadata
            start_time: When the call started
            error: Error message if call failed

        Returns:
            TokenUsage extracted from response
        """
        usage = self.extract_token_usage(response) if response else TokenUsage()

        if not self.is_enabled:
            return usage

        ctx = {
            "response": response,
            "prompt": prompt,
            "error": error,
            "start_time": start_time or datetime.utcnow(),
        }

        self._record_generation(name, ctx, metadata)
        return usage

    def flush(self) -> None:
        """Flush pending events to LangFuse."""
        if self.is_enabled and self._langfuse:
            try:
                self._langfuse.flush()
            except Exception as e:
                logger.warning(f"Failed to flush LangFuse events: {e}")

    def shutdown(self) -> None:
        """Shutdown LangFuse client."""
        if self._langfuse:
            try:
                self._langfuse.flush()
                self._langfuse.shutdown()
                logger.info("LangFuse client shutdown complete")
            except Exception as e:
                logger.warning(f"Error during LangFuse shutdown: {e}")


# Global singleton instance
_observability_instance: Optional[ObservabilityService] = None


def get_observability() -> ObservabilityService:
    """Get or create observability service instance.

    Returns:
        ObservabilityService singleton
    """
    global _observability_instance

    if _observability_instance is None:
        _observability_instance = ObservabilityService()

    return _observability_instance
