"""
LLM Client Wrapper for Google Gemini API

Uses the new google.genai package (replaces deprecated google.generativeai).
Provides:
- Unified client initialization
- Retry logic with exponential backoff
- Rate limit (429) handling
- Token usage tracking
"""

import logging
import time
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Thin wrapper around google.genai.Client for Gemini API calls.

    Handles:
    - Client initialization with API key
    - Model configuration (temperature, max tokens, etc.)
    - Retry logic with exponential backoff
    - Rate limit (429) handling
    - Token usage tracking
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-pro",
        temperature: float = 0.1,
        top_p: float = 0.95,
        max_output_tokens: int = 65536,
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: int = 5,
        timeout: int = 120,
    ):
        """
        Initialize Gemini client.

        Args:
            api_key: Google AI API key
            model_name: Model to use (default: gemini-2.5-pro)
            temperature: Sampling temperature (0.0-1.0)
            top_p: Nucleus sampling parameter
            max_output_tokens: Maximum tokens in response
            system_instruction: System prompt for the model
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (seconds)
            timeout: API call timeout (seconds)
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

        # Generation config
        self.generation_config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        )

        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self._last_usage = {}

        logger.info(f"Initialized GeminiClient with model: {model_name}, timeout: {timeout}s")

    def generate_content(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> types.GenerateContentResponse:
        """
        Generate content with retry logic and rate limit handling.

        Args:
            prompt: User prompt to send to the model
            timeout: Override default timeout for this call
            max_retries: Override default max retries for this call

        Returns:
            GenerateContentResponse from the API

        Raises:
            Exception: If all retries fail
        """
        timeout = timeout or self.timeout
        max_retries = max_retries or self.max_retries
        last_error = None

        # Build contents with system instruction if provided
        contents = []
        if self.system_instruction:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(text=self.system_instruction)],
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        )

        for attempt in range(max_retries):
            try:
                # Make API call
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=self.generation_config,
                )

                # Track token usage
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    input_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)
                    total_tokens = getattr(usage, 'total_token_count', 0)

                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    self.total_tokens += total_tokens

                    self._last_usage = {
                        'input_tokens': input_tokens,
                        'output_tokens': output_tokens,
                        'total_tokens': total_tokens,
                    }

                    logger.debug(f"Token usage: {input_tokens} input, {output_tokens} output, {total_tokens} total")

                return response

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Check if it's a rate limit error (429)
                is_rate_limit = (
                    "429" in error_str
                    or "ResourceExhausted" in error_str
                    or "RESOURCE_EXHAUSTED" in error_str
                )

                # Check if it's a transient error
                is_transient = (
                    "ServiceUnavailable" in error_str
                    or "DeadlineExceeded" in error_str
                    or "UNAVAILABLE" in error_str
                    or "DEADLINE_EXCEEDED" in error_str
                )

                if is_rate_limit:
                    logger.warning(f"Rate limit error (429) on attempt {attempt + 1}/{max_retries}")
                elif is_transient:
                    logger.warning(f"Transient API error on attempt {attempt + 1}/{max_retries}: {e}")
                else:
                    # Non-retryable error
                    logger.error(f"Non-retryable API error: {e}")
                    raise

                if attempt < max_retries - 1:
                    # Exponential backoff: 5s, 10s, 20s, 40s (capped at 60s)
                    wait_time = self.retry_delay * (2 ** attempt)

                    if is_rate_limit:
                        # Longer wait for rate limits
                        wait_time = min(wait_time * 2, 60)

                    logger.info(f"Retrying in {wait_time} seconds... (exponential backoff)")
                    time.sleep(wait_time)
                else:
                    if is_rate_limit:
                        logger.error("Rate limit (429) persists after all retries. Consider reducing batch size.")
                    else:
                        logger.error(f"Transient error persists: {e}")

        # All retries exhausted
        logger.error(f"All {max_retries} retries failed")
        raise last_error or Exception("API failed after all retries")

    def get_token_usage(self) -> Dict[str, int]:
        """
        Get cumulative token usage statistics.

        Returns:
            Dictionary with total_input_tokens, total_output_tokens, total_tokens
        """
        return {
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_tokens': self.total_tokens,
        }

    def get_last_usage(self) -> Dict[str, int]:
        """
        Get token usage from the last API call.

        Returns:
            Dictionary with input_tokens, output_tokens, total_tokens from last call
        """
        return self._last_usage.copy()

    def reset_usage(self):
        """Reset token usage counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
        self._last_usage = {}
