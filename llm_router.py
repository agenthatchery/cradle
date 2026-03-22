import os

import asyncio
import httpx
import json
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, Any, Optional
from cradle.config import Config


logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    content: str
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    provider: str = ""


class LLMRouter:
    # Cradle AI: Streaming support marker - To be replaced with actual streaming logic.

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient()

    def get_provider_for_model(self, model_name: str) -> str:
        """Infers the provider (openai/gemini) from the model name."""
        if not model_name:
             return "gemini"
        m = model_name.lower()
        if "gpt" in m or "o1" in m:
            return "openai"
        if "gemini" in m:
            return "gemini"
        if "minimax" in m:
            return "minimax"
        return "minimax" # Default to Minimax per user request


    async def complete(self, messages, model: Optional[str] = None, max_tokens=None, temperature=0.7, top_p=1.0, stop_sequences=None, system: str = None) -> LLMResponse:
        """Get a single (non-streaming) completion from the LLM."""
        if not model:
            model = self.config.llm_providers[0].model if self.config.llm_providers else "gemini-2.0-flash"

        if isinstance(messages, str):
            prompt = messages
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
        else:
             prompt = messages[-1]["content"] if messages else ""

        provider = self.get_provider_for_model(model)
        api_key = self.config.minimax_api_key if provider == "minimax" else (self.config.openai_api_key if provider == "openai" else self.config.gemini_api_key)
        base_url = self.config.minimax_base_url if provider == "minimax" else (self.config.openai_base_url if provider == "openai" else None)


        content = await self._get_non_streaming_completion(
            messages[0]["content"] if len(messages) == 1 else json.dumps(messages), 
            model, 
            api_key, 
            base_url, 
            provider, 
            max_tokens=max_tokens, 
            temperature=temperature, 
            top_p=top_p, 
            stop=stop_sequences
        )
        return LLMResponse(content=content, model=model, provider=provider)

    async def stream(self, messages, model, max_tokens=None, temperature=0.7, top_p=1.0, stop_sequences=None) -> AsyncGenerator[str, None]:
        """Get a streaming completion from the LLM."""
        provider = self.get_provider_for_model(model)
        api_key = self.config.minimax_api_key if provider == "minimax" else (self.config.openai_api_key if provider == "openai" else self.config.gemini_api_key)
        base_url = self.config.minimax_base_url if provider == "minimax" else (self.config.openai_base_url if provider == "openai" else None)


        if provider == "openai":
            async for chunk in self._stream_openai_completion(messages, model, api_key, base_url, max_tokens=max_tokens, temperature=temperature, top_p=top_p, stop_sequences=stop_sequences):
                yield chunk
        elif provider == "gemini":
            async for chunk in self._stream_gemini_completion(messages, model, api_key, base_url, max_tokens=max_tokens, temperature=temperature, top_p=top_p, stop_sequences=stop_sequences):
                yield chunk
        else:
            response = await self.complete(messages, model, max_tokens, temperature, top_p, stop_sequences)
            yield response.content


        # (Original line commented out: # Determine provider based on model or configuration)
        # (Original line commented out: provider = self.get_provider_for_model(model) # Assuming such a method exists or can be inferred)
# (Original line commented out: )
        # (Original line commented out: if provider == "openai":)
            # (Original line commented out: from openai import AsyncOpenAI)
            # (Original line commented out: client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY")))
            # (Original line commented out: stream = await client.chat.completions.create()
                # (Original line commented out: model=model,)
                # (Original line commented out: messages=[{"role": m["role"], "content": m["content"]} for m in messages],)
                # (Original line commented out: max_tokens=max_tokens,)
                # (Original line commented out: temperature=temperature,)
                # (Original line commented out: top_p=top_p,)
                # (Original line commented out: stop=stop_sequences,)
                # (Original line commented out: stream=True,)
            # (Original line commented out: ))
            # (Original line commented out: async for chunk in stream:)
                # (Original line commented out: if chunk.choices and chunk.choices[0].delta.content:)
                    # (Original line commented out: yield chunk.choices[0].delta.content)
        # (Original line commented out: elif provider == "gemini":)
            # (Original line commented out: # Example for Gemini, assuming a similar streaming API)
            # (Original line commented out: # This part needs actual Gemini API integration)
            # (Original line commented out: from google.generativeai.types import GenerateContentResponse)
            # (Original line commented out: # Example placeholder, replace with actual Gemini streaming logic)
            # (Original line commented out: # Assuming a gemini_client is initialized elsewhere)
            # (Original line commented out: # stream = await self.gemini_client.generate_content_async()
            # (Original line commented out: #     contents=[{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages],)
            # (Original line commented out: #     stream=True,)
            # (Original line commented out: # ))
            # (Original line commented out: # For demonstration, we'll yield a simple response)
            # (Original line commented out: yield "Gemini streaming is not fully implemented yet, but this is a stream...")
        # (Original line commented out: else:)
            # (Original line commented out: # Fallback for non-streaming providers or if streaming is not supported/implemented)
            # (Original line commented out: # This would be the existing non-streaming logic)
            # (Original line commented out: # For now, we'll yield the full response as a single chunk)
            # (Original line commented out: response_text = "Non-streaming response simulation.")
            # (Original line commented out: yield response_text)
# (Original line commented out: )
# (Original line commented out: )
    async def _stream_openai_completion(self, prompt: str, model_name: str, api_key: str, base_url: str, **kwargs) -> AsyncGenerator[str, None]:
        # Determine provider based on model or configuration
        provider = self.get_provider_for_model(model) # Assuming such a method exists or can be inferred

        if provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            stream = await client.chat.completions.create(
                model=model,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop_sequences,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        elif provider == "gemini":
            # Example for Gemini, assuming a similar streaming API
            # This part needs actual Gemini API integration
            from google.generativeai.types import GenerateContentResponse
            # Example placeholder, replace with actual Gemini streaming logic
            # Assuming a gemini_client is initialized elsewhere
            # stream = await self.gemini_client.generate_content_async(
            #     contents=[{"role": m["role"], "parts": [{"text": m["content"]}]} for m in messages],
            #     stream=True,
            # ) 
            # For demonstration, we'll yield a simple response
            yield "Gemini streaming is not fully implemented yet, but this is a stream..."
        else:
            # Fallback for non-streaming providers or if streaming is not supported/implemented
            # This would be the existing non-streaming logic
            # For now, we'll yield the full response as a single chunk
            response_text = "Non-streaming response simulation."
            yield response_text


    async def _stream_openai_completion(self, prompt: str, model_name: str, api_key: str, base_url: str, **kwargs) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            **kwargs
        }
        url = f"{base_url or 'https://api.openai.com/v1'}/chat/completions"

        async with self.client.stream("POST", url, headers=headers, json=payload, timeout=None) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                try:
                    # OpenAI sends data in 'data: {json_object}\n\n' format
                    # And 'data: [DONE]\n\n' for the end
                    lines = chunk.decode('utf-8').splitlines()
                    for line in lines:
                        if line.startswith("data: ") and line != "data: [DONE]":
                            json_data = line[len("data: "):]
                            data = json.loads(json_data)
                            if "choices" in data and data["choices"] and "delta" in data["choices"][0]:
                                content = data["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode JSON from chunk: {chunk.decode('utf-8')}")
                except Exception as e:
                    logger.error(f"Error processing OpenAI stream chunk: {e}")
                    raise

    async def _stream_gemini_completion(self, messages: list[Dict[str, str]], model_name: str, api_key: str, base_url: str, **kwargs) -> AsyncGenerator[str, None]:
        headers = {
            "Content-Type": "application/json",
        }
        # Convert messages to Gemini format
        gemini_contents = []
        for msg in messages:
            if msg["role"] == "user":
                gemini_contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
            elif msg["role"] == "assistant":
                gemini_contents.append({"role": "model", "parts": [{"text": msg["content"]}]})
            # Add other roles if necessary

        payload = {
            "contents": gemini_contents,
            "generationConfig": {
                **kwargs
            }
        }
        # Gemini uses 'v1beta' or 'v1' and specific endpoints
        url = f"{base_url or 'https://generativelanguage.googleapis.com/v1beta'}/models/{model_name}:streamGenerateContent?key={api_key}"

        async with self.client.stream("POST", url, headers=headers, json=payload, timeout=None) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                try:
                    # Gemini sends a single JSON object per chunk or multiple concatenated
                    # Need to handle potential partial JSONs or multiple JSONs in one chunk
                    text_chunk = chunk.decode('utf-8')
                    # Simple split by `}\n{` to handle multiple JSONs, then re-add braces
                    json_strings = [s for s in text_chunk.split('}\n{') if s]
                    processed_json_strings = []
                    if len(json_strings) > 1:
                        processed_json_strings.append(json_strings[0] + '}')
                        for s in json_strings[1:-1]:
                            processed_json_strings.append('{' + s + '}')
                        processed_json_strings.append('{' + json_strings[-1])
                    else:
                        processed_json_strings = json_strings

                    for json_str in processed_json_strings:
                        data = json.loads(json_str)
                        if "candidates" in data and data["candidates"] and "content" in data["candidates"][0]:
                            for part in data["candidates"][0]["content"].get("parts", []):
                                if "text" in part:
                                    yield part["text"]
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode JSON from chunk: {chunk.decode('utf-8')}")
                except Exception as e:
                    logger.error(f"Error processing Gemini stream chunk: {e}")
                    raise

    async def _get_non_streaming_completion(self, prompt: str, model_name: str, api_key: str, base_url: str, provider_type: str, **kwargs) -> str:
        # This method will be called for providers that don't support streaming
        # or when streaming is explicitly not requested/available.
        # Implement specific logic for each non-streaming provider type if needed.
        # For now, it's a placeholder for direct completion.
        logger.info(f"Falling back to non-streaming completion for {provider_type} model: {model_name}")

        if provider_type == "openai": # Non-streaming OpenAI call
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                **kwargs
            }
            url = f"{base_url or 'https://api.openai.com/v1'}/chat/completions"
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        elif provider_type == "gemini": # Non-streaming Gemini call
            headers = {
                "Content-Type": "application/json",
            }
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    **kwargs
                }
            }
            url = f"{base_url or 'https://generativelanguage.googleapis.com/v1beta'}/models/{model_name}:generateContent?key={api_key}"
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        elif provider_type == "minimax": # Non-streaming Minimax (OpenAI-compatible) call
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                **kwargs
            }
            url = f"{base_url or 'https://api.minimax.chat/v1'}/chat/completions"
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        else:
            raise NotImplementedError(f"Non-streaming completion not implemented for provider type: {provider_type}")

