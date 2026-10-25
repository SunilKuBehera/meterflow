"""AI provider interface and deterministic mock implementation.

The provider abstraction isolates the *mechanism* of calling an AI model from
the *domain* of metering, quota, and pricing. Every provider returns a typed
``AIResponse`` with explicit token counts so the use case can record usage and
price it deterministically.

Token accounting convention
---------------------------
- ``prompt_tokens``: non-cached input tokens.
- ``cached_prompt_tokens``: cached input tokens (priced at a separate rate).
- ``completion_tokens``: output tokens.
- ``reasoning_tokens``: internal reasoning tokens (priced at the output rate).

A provider reports its own token counts when available. When it cannot, the
caller must mark the response ``usage_source="estimated"`` and never present
estimated counts as exact provider usage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AIProviderError(Exception):
    """Raised when an AI provider fails to produce a response."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when an AI provider is not configured or reachable."""


# Named estimator used by providers that cannot report exact prompt tokens.
# ~4 characters per token is a documented, stable heuristic.
CHARS_PER_TOKEN_ESTIMATOR = "chars_per_token_v1"


@dataclass
class AIResponse:
    """Structured result returned by every provider."""

    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int = 0
    reasoning_tokens: int = 0
    finish_reason: str = "stop"
    usage_source: str = "provider"

    @property
    def total_tokens(self) -> int:
        return (
            self.prompt_tokens
            + self.cached_prompt_tokens
            + self.completion_tokens
            + self.reasoning_tokens
        )


class AIProvider(ABC):
    """Interface every AI provider implementation must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name (e.g. ``"mock"``, ``"ollama"``)."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the default model name used by this provider."""

    @property
    def max_output_tokens(self) -> int:
        """Maximum output tokens this provider will ever return.

        The use case validates ``max_tokens`` against this bound before
        calling :meth:`generate`.
        """
        return 4096

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Estimate prompt tokens using the documented ``CHARS_PER_TOKEN`` heuristic.

        Mark estimated counts as such (``usage_source="estimated"``) when the
        provider has no exact tokenizer available.
        """
        return max(1, (len(prompt) + 3) // 4)

    def validate_connection(self) -> bool:
        """Return ``True`` when the provider is reachable and configured."""
        return True

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AIResponse:
        """Generate a response from the AI model.

        Args:
            prompt: The prompt to send to the model.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            An :class:`AIResponse` with the generated content and token counts.

        Raises:
            AIProviderError: If the request cannot be fulfilled.
        """


class MockAIProvider(AIProvider):
    """Deterministic mock AI provider for development and testing.

    This provider makes no network calls and requires no API key. Its output
    is derived from a SHA-256 digest of the canonical request, so identical
    requests always produce identical responses. Suitable for the default
    ``USAGE_MODE=simulated`` path.

    Args:
        model: Model name reported in responses.
        max_output_tokens: Hard upper bound on ``max_tokens``.
    """

    def __init__(
        self,
        model: str = "mock-model",
        max_output_tokens: int = 4096,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_output_tokens(self) -> int:
        return self._max_output_tokens

    def validate_connection(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AIResponse:
        import hashlib

        if max_tokens > self._max_output_tokens:
            raise AIProviderError(
                f"max_tokens {max_tokens} exceeds provider bound "
                f"{self._max_output_tokens}"
            )

        # Deterministic digest over the canonical request. The temperature is
        # included so distinct sampling parameters yield distinct outputs.
        digest_input = f"{self._model}|{prompt}|{max_tokens}|{temperature}"
        digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

        prompt_tokens = self.estimate_prompt_tokens(prompt)
        # Completion tokens are deterministic and bounded by [1, max_tokens].
        completion_tokens = 1 + (int(digest[:8], 16) % max(1, max_tokens))

        # Deterministic content: one word per completion token, derived from
        # the digest so the same request always yields the same text.
        words = self._derive_words(digest, completion_tokens)
        content = " ".join(words)

        return AIResponse(
            content=content,
            model=self._model,
            provider=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=0,
            reasoning_tokens=0,
            finish_reason="stop",
            usage_source="simulated",
        )

    @staticmethod
    def _derive_words(digest: str, count: int) -> list[str]:
        """Derive a deterministic word list from a digest hex string."""
        syllables = [
            "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
            "golf", "hotel", "india", "juliet", "kilo", "lima", "mike",
            "november", "oscar", "papa", "quebec", "romeo", "sierra", "tango",
            "uniform", "victor", "whiskey", "xray", "yankee", "zulu",
        ]
        words: list[str] = []
        for i in range(count):
            words.append(syllables[int(digest[i % len(digest)], 16) % len(syllables)])
        return words