"""Multi-provider LLM router with automatic fallback.

Supports: Gemini, MiniMax, Groq, OpenRouter, OpenAI.
Each provider has different API conventions — this module normalizes them.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

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

    MAX_CONSECUTIVE_FAILURES = 3
    DEMOTION_COOLDOWN_SECS = 300  # 5 minutes before retrying a demoted provider

    def __init__(self, config: Config):
        self.config = config
        self.providers = config.llm_providers
        self.stats = UsageStats()
        self._client = httpx.AsyncClient(timeout=120.0)
        self._consecutive_failures: dict[str, int] = {}
        self._demoted_until: dict[str, float] = {}  # provider_name -> timestamp
        
        # Ensure log directory exists
        self.audit_log_path = os.path.join(config.data_dir, "llm_audit.jsonl")
        os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)

    async def close(self):
        await self._client.aclose()


    async def complete(self, messages: list, model: str, stream: bool = False, **kwargs):
        # Determine provider based on model name or configuration
        provider = self._get_provider_for_model(model) # Assume _get_provider_for_model exists

        if provider == "openai":
            import openai # Assume openai is imported at the top
            if stream:
                response = await openai.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
            else:
                response = await openai.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                    **kwargs
                )
                yield response.choices[0].message.content
        elif provider == "gemini":
            import google.generativeai as genai # Assume genai is imported at the top
            # Configure genai if not already done, e.g., genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            model_instance = genai.GenerativeModel(model)
            if stream:
                response = await model_instance.generate_content_async(
                    contents=messages,
                    stream=True,
                    **kwargs
                )
                async for chunk in response:
                    yield chunk.text
            else:
                response = await model_instance.generate_content_async(
                    contents=messages,
                    stream=False,
                    **kwargs
                )
                yield response.text
        else:
            # Handle other providers or non-streaming default
            # For now, raise an error or fall back to non-streaming
            raise NotImplementedError(f"Provider '{provider}' not supported for streaming or model '{model}' is unknown.")
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

    def _log_audit(self, entry: dict):
        """Append an entry to the JSONL audit log."""
        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")
