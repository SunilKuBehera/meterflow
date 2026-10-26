"""AI provider factory.

Selects the appropriate provider based on ``AI_PROVIDER`` and ``USAGE_MODE``
environment settings. During Phase 8 only ``mock`` provider in ``simulated``
mode is supported; ``ollama`` and ``gemini`` raise ``AIProviderUnavailableError``
with a clear message pointing to their future implementation phases.

Usage::

    from integrations.ai.factory import get_ai_provider
    provider = get_ai_provider()
    response = provider.generate("Hello", max_tokens=100)
"""

from core.config import get_settings
from integrations.ai.ollama_provider import get_ollama_provider
from integrations.ai.provider import (
    AIProvider,
    AIProviderUnavailableError,
    MockAIProvider,
)


def get_ai_provider(settings=None) -> AIProvider:
    """Return an AI provider based on environment configuration.

    Implements the provider selection policy:
    - ``AI_PROVIDER=mock`` + ``USAGE_MODE=simulated`` → ``MockAIProvider``
    - ``AI_PROVIDER=mock`` + ``USAGE_MODE=real`` → unavailable (mock cannot
      report real usage)
    - ``AI_PROVIDER=ollama`` → ``OllamaAIProvider`` when the configured model
      is available on the local Ollama server; otherwise ``None`` so the
      caller falls back to ``MockAIProvider``.
    - ``AI_PROVIDER=gemini`` → unavailable (Phase 10+)

    Returns:
        An ``AIProvider`` instance or ``None`` when the requested provider is
        not available. Callers should treat ``None`` as "use the mock provider."

    Raises:
        AIProviderUnavailableError: If ``AI_PROVIDER=mock`` is used with
            ``USAGE_MODE=real``.
    """
    s = settings or get_settings()

    if s.AI_PROVIDER == "mock":
        if s.USAGE_MODE == "real":
            raise AIProviderUnavailableError(
                "AI_PROVIDER=mock cannot operate in real usage mode. "
                "Set USAGE_MODE=simulated for development, or use ollama/gemini "
                "(available in later phases)."
            )
        return MockAIProvider(max_output_tokens=s.AI_MAX_OUTPUT_TOKENS)

    if s.AI_PROVIDER == "ollama":
        provider = get_ollama_provider(s)
        if provider is not None:
            return provider
        # Ollama not available → fall through to return None below

    if s.AI_PROVIDER == "gemini":
        raise AIProviderUnavailableError(
            "Gemini provider integration is not available in this phase. "
            "It will be implemented after the core Ollama path is tested."
        )

    # Ollama returned None, or an unrecognized provider: fall back to mock
    # so the application never crashes without an AI provider.
    return MockAIProvider(max_output_tokens=s.AI_MAX_OUTPUT_TOKENS)


def describe_provider(settings=None) -> dict:
    """Return a snapshot of the provider configuration and availability.

    This endpoint must not raise even when the provider is unavailable,
    allowing the health check to report the current state.
    """
    s = settings or get_settings()
    result = {
        "provider": s.AI_PROVIDER,
        "model": s.OLLAMA_MODEL,
        "usage_mode": s.USAGE_MODE,
        "available": False,
        "detail": None,
    }

    try:
        provider = get_ai_provider(s)
        if provider is not None:
            result["available"] = bool(provider.validate_connection())
            result["model"] = provider.model
            result["detail"] = f"Provider '{provider.name}' is configured."
        else:
            result["detail"] = "No AI provider available; using mock provider."
    except AIProviderUnavailableError as e:
        result["detail"] = str(e)

    return result
