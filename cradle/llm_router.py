import os

import asyncio
import httpx
import json
import logging
from typing import AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)

class LLMRouter:
    # Cradle AI: Streaming support marker - To be replaced with actual streaming logic.

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = httpx.AsyncClient()


    async def complete(self, messages, model, max_tokens=None, temperature=0.7, top_p=1.0, stop_sequences=None):
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
                    # OpenAI sends data in 'data: {json_object}

' format
                    # And 'data: [DONE]

' for the end
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

    async def _stream_gemini_completion(self, prompt: str, model_name: str, api_key: str, base_url: str, **kwargs) -> AsyncGenerator[str, None]:
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
        # Gemini uses 'v1beta' or 'v1' and specific endpoints
        url = f"{base_url or 'https://generativelanguage.googleapis.com/v1beta'}/models/{model_name}:streamGenerateContent?key={api_key}"

        async with self.client.stream("POST", url, headers=headers, json=payload, timeout=None) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                try:
                    # Gemini sends a single JSON object per chunk or multiple concatenated
                    # Need to handle potential partial JSONs or multiple JSONs in one chunk
                    text_chunk = chunk.decode('utf-8')
                    # Simple split by `}
{` to handle multiple JSONs, then re-add braces
                    json_strings = [s for s in text_chunk.split('}
{') if s]
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

        else:
            raise NotImplementedError(f"Non-streaming completion not implemented for provider type: {provider_type}")

