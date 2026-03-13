import httpx
import asyncio
import typing

import openai
import google.generativeai as genai
import os
from typing import AsyncGenerator, Dict, Any

class LLMRouter:
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))


    async def complete(self, messages: list[dict], model: str = None, **kwargs) -> typing.AsyncGenerator[str, None]:
        # Determine the provider based on the model or configuration
        provider_name = self._determine_provider(model)
        provider = self.providers.get(provider_name)

        if not provider:
            raise ValueError(f"No provider found for model: {model}")

        # Assuming provider has a streaming_complete method
        # This will need to be implemented for each provider (OpenAI, Gemini, etc.)
        if hasattr(provider, 'streaming_complete') and callable(provider.streaming_complete):
            async for chunk in provider.streaming_complete(messages, model, **kwargs):
                yield chunk
        else:
            # Fallback to non-streaming if streaming is not supported by the provider
            # or if it's explicitly not requested.
            response = await provider.complete(messages, model, **kwargs)
            yield response

    async def _openai_complete(self, model: str, messages: list, stream: bool, **kwargs) -> AsyncGenerator[Dict[str, Any], None] | Dict[str, Any]:
        if stream:
            response_stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            )
            async def generator():

    async def stream_complete(self, messages, functions=None, function_call=None, provider=None, model=None, temperature=0, max_tokens=None, **kwargs):
        # Placeholder for streaming logic
        # This method should yield chunks of response as they arrive.
        # Example for OpenAI:
        # client = self._get_client(provider)
        # stream = await client.chat.completions.create(
        #     messages=messages,
        #     model=model,
        #     stream=True,
        #     **kwargs
        # )
        # async for chunk in stream:
        #     yield chunk.choices[0].delta.content or ""
        
        # For now, simulate a streaming response
        yield "This "
        await asyncio.sleep(0.1)
        yield "is "
        await asyncio.sleep(0.1)
        yield "a "
        await asyncio.sleep(0.1)
        yield "streaming "
        await asyncio.sleep(0.1)
        yield "response."

                async for chunk in response_stream:
                    yield chunk.dict()
            return generator()
        else:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                **kwargs
            )
            return response.dict()

    async def _gemini_complete(self, model: str, messages: list, stream: bool, **kwargs) -> AsyncGenerator[Dict[str, Any], None] | Dict[str, Any]:
        gemini_model = genai.GenerativeModel(model)
        formatted_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            formatted_messages.append({"role": role, "parts": [msg["content"]]})

        if stream:
            response_stream = await gemini_model.generate_content_async(
                formatted_messages,
                stream=True,
                **kwargs
            )
            async def generator():
                async for chunk in response_stream:
                    yield {"choices": [{"delta": {"content": part.text for part in chunk.parts}}]} # Simplified for streaming content
            return generator()
        else:
            response = await gemini_model.generate_content_async(
                formatted_messages,
                stream=False,
                **kwargs
            )
            return {"choices": [{"message": {"content": part.text for part in response.parts}}]} # Simplified for non-streaming content

# TODO: Implement streaming support for complete method
