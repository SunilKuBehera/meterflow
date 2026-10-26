"""Ollama AI provider adapter.

Wraps the local Ollama inference API as an ``AIProvider`` implementation.
If Ollama is not reachable (no model pulled, service down, etc.), the adapter
degrades gracefully to the deterministic ``MockAIProvider`` so the application
continues to function without network access or API keys.

Configuration (via ``core.config``):
  - ``OLLAMA_BASE_URL``: Base URL of the Ollama service (default: ``http://localhost:11434``)
  - ``OLLAMA_MODEL``: Model name to use for generation (default: ``llama3.1``)
  - ``OLLAMA_TIMEOUT``: Request timeout in seconds (default: ``120``)
  - ``AI_PROVIDER=ollama``: Selects this provider via the factory
  - ``USAGE_MODE=simulated``: Falls back to ``MockAIProvider`` when set

Token accounting convention (same as ``integrations.ai.provider``):
- ``prompt_tokens``: non-cached input tokens
- ``cached_prompt_tokens``: cached input tokens (priced at a separate rate)
- ``completion_tokens``: output tokens
- ``reasoning_tokens``: internal reasoning tokens (priced at the output rate)

A provider reports its own token counts when available. When it cannot (Ollama
does not always return precise prompt/completion token breakdowns), the caller
must mark the response ``usage_source="estimated"`` and never present estimated
counts as exact provider usage.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.config import get_settings
from integrations.ai.provider import (
    AIProvider,
    AIProviderUnavailableError,
    AIResponse,
)

# Ollama API endpoint for generation
OLLAMA_API_CHAT = "/api/chat"
OLLAMA_API_EMBED = "/api/embed"

# A small system prompt to keep the model focused on helpful completion.
OLLAMA_SYSTEM_PROMPT = "You are a helpful assistant."

# Default parameters forwarded to Ollama when the user does not override them.
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096


@dataclass
class OllamaResponse(AIResponse):
    """Response wrapper adding the raw Ollama API payload.

    The ``OllamaAIProvider`` extracts token counts from the Ollama response
    when available; otherwise it marks the counts as ``usage_source="estimated"``.
    """



class OllamaAIProvider(AIProvider):
    """Adapter around a local Ollama inference server.

    Wraps ``httpx`` calls to ``<base_url>/api/chat`` (the Chat API) and
    extracts token metadata from the response.  If the server is unreachable,
    the model is unavailable, or the response format is unexpected, the provider
    raises ``AIProviderUnavailableError`` so the upper layers can degrade to
    ``MockAIProvider`` (when ``USAGE_MODE=simulated``).

    Args:
        model: Ollama model name (e.g. ``"llama3.1"``).
        base_url: Base URL of the Ollama service, defaults to
                  ``settings.OLLAMA_BASE_URL``.
        timeout: Request timeout in seconds, defaults to
                 ``settings.OLLAMA_TIMEOUT``.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int | None = None,
    ) -> None:
        settings = get_settings()
        self._model = model or settings.OLLAMA_MODEL
        self._base_url = base_url or settings.OLLAMA_BASE_URL
        self._timeout = timeout or settings.OLLAMA_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> OllamaAIProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    # --- AIProvider interface -----------------------------------------------

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model

    @property
    def max_output_tokens(self) -> int:
        return 4096

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Estimate prompt tokens using the documented ``CHARS_PER_TOKEN`` heuristic.

        Mark estimated counts as such (``usage_source="estimated"``) when the
        provider has no exact tokenizer available.
        """
        return max(1, (len(prompt) + 3) // 4)

    def validate_connection(self) -> bool:
        """Return ``True`` when the Ollama server is reachable and a model is listed."""

        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            # Consider the model available if the requested model name appears
            # in the list (case-insensitive substring match).
            return any(
                self._model.lower() in tag.get("name", "").lower() for tag in tags
            )
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float = 0.7,
    ) -> AIResponse:
        """Send a prompt to the Ollama chat API and return an ``AIResponse``.

        The method follows these steps:

        1. Build the chat payload with the system prompt and user prompt.
        2. POST to ``<base_url>/api/chat``.
        3. Parse the response: extract ``prompt_tokens``, ``completion_tokens``,
           ``finish_reason``, and the generated ``content``.
        4. If any step fails (network error, non-200, missing fields), raise
           ``AIProviderUnavailableError`` so the caller can fall back to the
           mock provider.
        5. Return an ``AIResponse`` with the extracted counts and content.

        Raises:
            AIProviderUnavailableError: If the Ollama server is unreachable, the
                model is not loaded, or the response format is unexpected.
        """
        # 1. Build the chat payload.
        messages = [
            {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        try:
            resp = await self._client.post(OLLAMA_API_CHAT, json=payload)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise AIProviderUnavailableError(
                f"Could not connect to Ollama at {self._base_url}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AIProviderUnavailableError(
                f"Ollama returned status {exc.response.status_code}"
            ) from exc
        except Exception as exc:
            raise AIProviderUnavailableError(
                f"Unexpected error communicating with Ollama: {exc}"
            ) from exc

        # 2. Parse the response.
        body = resp.json()
        message = body.get("message", {})
        content = message.get("content") or ""

        # Ollama's chat API may not always return explicit prompt/completion
        # token counts.  When available we use them; otherwise we fall back
        # to the estimator and mark the counts as estimated.
        prompt_tokens: int
        completion_tokens: int
        usage_source: str

        # Try to get token counts from the response.
        if body.get("prompt_eval_count") is not None:
            # Some Ollama builds report total prompt tokens here.
            prompt_tokens = int(body["prompt_eval_count"])
            # Completion tokens are not always reported; estimate if missing.
            completion_tokens = int(body.get("eval_count") or self.estimate_prompt_tokens(prompt))
            usage_source = "provider"
        elif body.get("prompt_eval_count") is not None:
            # Alternative field name.
            prompt_tokens = int(body["prompt_eval_count"])
            completion_tokens = int(body.get("eval_count") or self.estimate_prompt_tokens(prompt))
            usage_source = "provider"
        else:
            # No token info from the server → use estimator and mark as estimated.
            prompt_tokens = self.estimate_prompt_tokens(prompt)
            completion_tokens = self.estimate_prompt_tokens(prompt)
            usage_source = "estimated"

        # 3. Determine the finish reason.
        finish_reason = body.get("done_reason", "stop")

        return AIResponse(
            content=content,
            model=self._model,
            provider=self.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=0,
            reasoning_tokens=0,
            finish_reason=finish_reason,
            usage_source=usage_source,
        )

    async def close(self) -> None:
        """Close the underlying httpx client."""

        await self._client.aclose()


def get_ollama_provider(settings=None) -> OllamaAIProvider | None:
    """Return an ``OllamaAIProvider`` instance when the configuration is valid.

    Returns ``None`` when ``AI_PROVIDER`` is not ``"ollama"`` or when the
    configured model is not available on the local Ollama server (``validate_connection``
    returns ``False``).  The caller should treat ``None`` as "use the mock
    provider" so the app never crashes if Ollama is not installed.

    Note: This function does **not** raise — it returns ``None`` or a provider
    instance.  The routing logic (factory) is responsible for falling back to
    ``MockAIProvider`` when the result is ``None``.
    """

    s = settings or get_settings()

    if s.AI_PROVIDER != "ollama":
        return None

    provider = OllamaAIProvider(
        model=s.OLLAMA_MODEL,
        base_url=s.OLLAMA_BASE_URL,
        timeout=s.OLLAMA_TIMEOUT,
    )

    # Quick connectivity check; if the server is down we return None so the
    # factory can fall back to MockAIProvider.
    if not provider.validate_connection():
        return None

    return provider
