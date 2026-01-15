"""Gemini AI client with retry logic and observability.

This module provides a reusable client for interacting with Google's Gemini API,
including:
- Automatic retry with exponential backoff
- Timeout handling
- Observability tracking via Langfuse
- Error classification and handling

Usage:
    client = GeminiClient()
    response = await client.generate_content(
        prompt="Extract items from this PDF...",
        operation="boq_extraction",
        document_id="doc-123",
    )
"""

import asyncio
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Optional

from ..config import settings
from ..utils import ErrorCode, raise_error
from .observability import get_observability, TraceMetadata

logger = logging.getLogger(__name__)


@dataclass
class GeminiResponse:
    """Wrapper for Gemini API response with metadata."""

    text: str
    raw_response: Any
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GeminiClient:
    """Client for Google Gemini API with retry and observability.

    Features:
        - Automatic retry with exponential backoff for transient errors
        - Configurable timeout
        - Observability tracking via Langfuse
        - Error classification (retryable vs non-retryable)

    Example:
        client = GeminiClient()
        response = await client.generate_content(
            prompt="Your prompt here",
            operation="extraction",
            document_id="doc-123",
        )
        print(response.text)
    """

    # Errors that should trigger retry
    RETRYABLE_ERROR_PATTERNS = frozenset([
        "rate",
        "504",
        "499",
        "cancelled",
        "deadline",
        "unavailable",
        "timeout",
    ])

    # Errors that should not be retried
    FATAL_ERROR_PATTERNS = {
        "api key": (ErrorCode.GEMINI_API_ERROR, "Gemini API Key 未設定或無效"),
        "quota": (ErrorCode.GEMINI_QUOTA_EXCEEDED, "Gemini API 配額已用盡"),
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        max_retries: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ):
        """Initialize Gemini client.

        Args:
            model_name: Gemini model to use (default: from settings)
            max_retries: Maximum retry attempts (default: from settings)
            timeout_seconds: Timeout per request (default: from settings)
        """
        self.model_name = model_name or settings.gemini_model
        self.max_retries = max_retries if max_retries is not None else settings.gemini_max_retries
        self.timeout_seconds = timeout_seconds or settings.gemini_timeout_seconds

        self._client = None
        self._genai = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Gemini client."""
        try:
            from google import genai

            self._genai = genai
            if settings.gemini_api_key:
                self._client = genai.Client(api_key=settings.gemini_api_key)
                logger.info(f"GeminiClient initialized: model={self.model_name}")
            else:
                logger.warning("Gemini API key not configured")
        except ImportError:
            logger.warning("google-genai package not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")

    @property
    def is_available(self) -> bool:
        """Check if the client is properly initialized."""
        return self._client is not None

    def _create_config(self, system_prompt: Optional[str]) -> Any:
        """Create generation config with optional system instruction."""
        if not system_prompt or not self._genai:
            return None

        try:
            return self._genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
            )
        except Exception as e:
            logger.warning(f"Failed to create config with system instruction: {e}")
            return None

    def _is_retryable_error(self, error_str: str) -> bool:
        """Check if an error is retryable."""
        error_lower = error_str.lower()
        return any(pattern in error_lower for pattern in self.RETRYABLE_ERROR_PATTERNS)

    def _check_fatal_error(self, error_str: str) -> None:
        """Check for fatal errors and raise appropriate exception."""
        error_lower = error_str.lower()
        for pattern, (error_code, message) in self.FATAL_ERROR_PATTERNS.items():
            if pattern in error_lower:
                raise_error(error_code, message)

    async def generate_content(
        self,
        prompt: str,
        operation: str = "generate",
        document_id: str = "",
        system_prompt: Optional[str] = None,
        vendor_id: Optional[str] = None,
        skill_version: Optional[str] = None,
    ) -> GeminiResponse:
        """Generate content using Gemini API with retry logic.

        Args:
            prompt: The prompt to send to Gemini
            operation: Operation name for logging/tracking
            document_id: Document ID for logging
            system_prompt: Optional system instruction
            vendor_id: Optional vendor ID for tracking
            skill_version: Optional skill version for tracking

        Returns:
            GeminiResponse with text and token usage

        Raises:
            APIError: If all retries fail or fatal error occurs
        """
        if not self.is_available:
            raise_error(
                ErrorCode.GEMINI_API_ERROR,
                "Gemini API 未配置，無法處理請求",
            )

        observability = get_observability()
        generate_config = self._create_config(system_prompt)
        last_error: Optional[str] = None

        trace_metadata = TraceMetadata(
            vendor_id=vendor_id,
            skill_version=skill_version,
            document_id=document_id,
            operation=operation,
            model=self.model_name,
            retry_count=0,
            environment=settings.environment,
        )

        for attempt in range(self.max_retries + 1):
            start_time = datetime.now(timezone.utc)
            trace_metadata.retry_count = attempt

            try:
                logger.info(
                    f"Gemini API call: operation={operation}, document={document_id}, "
                    f"attempt={attempt + 1}/{self.max_retries + 1}, timeout={self.timeout_seconds}s"
                )

                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._client.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=generate_config,
                    ),
                    timeout=self.timeout_seconds,
                )

                # Track successful call
                usage = observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=response,
                    metadata=trace_metadata,
                    start_time=start_time,
                )

                logger.info(
                    f"Gemini API success: operation={operation}, "
                    f"tokens={{input: {usage.prompt_tokens}, output: {usage.completion_tokens}}}"
                )

                return GeminiResponse(
                    text=response.text,
                    raw_response=response,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )

            except asyncio.TimeoutError:
                last_error = f"API 呼叫超時（{self.timeout_seconds} 秒）"
                logger.warning(f"Gemini timeout: document={document_id}, attempt={attempt + 1}")

                observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=None,
                    metadata=trace_metadata,
                    start_time=start_time,
                    error=last_error,
                )

                if attempt < self.max_retries:
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                error_str = str(e)

                observability.track_gemini_call(
                    name=operation,
                    prompt=prompt,
                    response=None,
                    metadata=trace_metadata,
                    start_time=start_time,
                    error=error_str,
                )

                # Check for fatal errors
                self._check_fatal_error(error_str)

                last_error = error_str
                logger.warning(f"Gemini error: document={document_id}, error={e}")

                # Retry if retryable
                if self._is_retryable_error(error_str) and attempt < self.max_retries:
                    wait_time = 2 ** (attempt + 1)
                    logger.info(f"Retrying in {wait_time}s (transient error)...")
                    await asyncio.sleep(wait_time)
                    continue

                # Non-retryable error
                raise_error(ErrorCode.GEMINI_API_ERROR, f"Gemini 解析失敗：{error_str}")

        # All retries exhausted
        raise_error(
            ErrorCode.GEMINI_API_ERROR,
            f"Gemini API 呼叫失敗（已重試 {self.max_retries} 次）：{last_error}",
        )

    async def generate_content_simple(
        self,
        prompt: str,
        timeout: int = 30,
    ) -> Optional[str]:
        """Simple content generation without retry (for optional operations).

        Args:
            prompt: The prompt to send
            timeout: Timeout in seconds (default: 30)

        Returns:
            Response text or None if failed
        """
        if not self.is_available:
            return None

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self.model_name,
                    contents=prompt,
                ),
                timeout=timeout,
            )
            return response.text
        except Exception as e:
            logger.warning(f"Simple generate failed: {e}")
            return None


# Singleton instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """Get or create the singleton GeminiClient instance."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiClient()
    return _gemini_client
