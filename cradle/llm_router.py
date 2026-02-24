"""Multi-provider LLM router with automatic fallback.

Supports: Gemini, MiniMax, Groq, OpenRouter, OpenAI.
Each provider has different API conventions — this module normalizes them.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from cradle.config import Config, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


@dataclass
class UsageStats:
    """Track cumulative usage across all providers."""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls_by_provider: dict[str, int] = field(default_factory=dict)
    errors_by_provider: dict[str, int] = field(default_factory=dict)


class LLMRouter:
    """Routes LLM calls through prioritized providers with auto-fallback."""

    def __init__(self, config: Config):
        self.providers = config.llm_providers
        self.stats = UsageStats()
        self._client = httpx.AsyncClient(timeout=120.0)

    async def close(self):
        await self._client.aclose()

    async def complete(
        self,
        prompt: str,
        system: str = "",
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a completion request, falling through providers on failure."""
        providers = list(self.providers)

        # If a specific provider is preferred, try it first
        if preferred_provider:
            providers.sort(key=lambda p: (0 if p.name == preferred_provider else p.priority))

        last_error = None
        for provider in providers:
            try:
                t0 = time.monotonic()
                response = await self._call_provider(
                    provider, prompt, system, temperature, max_tokens
                )
                response.latency_ms = int((time.monotonic() - t0) * 1000)
                response.cost_usd = (
                    (response.input_tokens + response.output_tokens)
                    / 1000
                    * provider.cost_per_1k_tokens
                )

                # Update stats
                self.stats.total_calls += 1
                self.stats.total_input_tokens += response.input_tokens
                self.stats.total_output_tokens += response.output_tokens
                self.stats.total_cost_usd += response.cost_usd
                self.stats.calls_by_provider[provider.name] = (
                    self.stats.calls_by_provider.get(provider.name, 0) + 1
                )

                logger.info(
                    f"LLM call: provider={provider.name} model={provider.model} "
                    f"tokens={response.input_tokens}+{response.output_tokens} "
                    f"latency={response.latency_ms}ms cost=${response.cost_usd:.4f}"
                )
                return response

            except Exception as e:
                last_error = e
                self.stats.errors_by_provider[provider.name] = (
                    self.stats.errors_by_provider.get(provider.name, 0) + 1
                )
                logger.warning(f"Provider {provider.name} failed: {e}, trying next...")
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    async def _call_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Provider-specific API calls."""
        if provider.name == "gemini":
            return await self._call_gemini(provider, prompt, system, temperature, max_tokens)
        else:
            # OpenAI-compatible API (MiniMax, Groq, OpenRouter, OpenAI)
            return await self._call_openai_compatible(
                provider, prompt, system, temperature, max_tokens
            )

    async def _call_gemini(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Call Gemini API (Google's native format)."""
        url = (
            f"{provider.base_url}/models/{provider.model}:generateContent"
            f"?key={provider.api_key}"
        )

        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        resp = await self._client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

        # Extract text from response
        text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)

        # Extract usage
        usage = data.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount", 0)
        output_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            content=text,
            provider=provider.name,
            model=provider.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def _call_openai_compatible(
        self,
        provider: LLMProvider,
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Call OpenAI-compatible API (works for MiniMax, Groq, OpenRouter, OpenAI)."""
        url = f"{provider.base_url}/chat/completions"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": provider.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        # OpenRouter requires extra headers
        if provider.name == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/agenthatchery/cradle"
            headers["X-Title"] = "Cradle Agent"

        resp = await self._client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        # Extract text
        text = ""
        choices = data.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "") or ""

        # Extract usage
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=text,
            provider=provider.name,
            model=provider.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def get_stats_summary(self) -> str:
        """Return a human-readable stats summary."""
        s = self.stats
        lines = [
            f"📊 LLM Usage Stats:",
            f"  Total calls: {s.total_calls}",
            f"  Total tokens: {s.total_input_tokens} in + {s.total_output_tokens} out",
            f"  Total cost: ${s.total_cost_usd:.4f}",
            f"  By provider: {s.calls_by_provider}",
        ]
        if s.errors_by_provider:
            lines.append(f"  Errors: {s.errors_by_provider}")
        return "\n".join(lines)
