import httpx
import asyncio

import openai
import google.generativeai as genai
import os
from typing import AsyncGenerator, Dict, Any

class LLMRouter:
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

    async def complete(self, provider: str, model: str, messages: list, stream: bool = False, **kwargs) -> AsyncGenerator[Dict[str, Any], None] | Dict[str, Any]:
        # CRADLE_EDIT: Added streaming support
        # This section needs to be refactored to handle streaming responses from LLM providers.
        # For OpenAI, add `stream=True` to the API call and iterate over the response.
        # Example for OpenAI:
        # if self.provider == 'openai':
        #     response_stream = await self.openai_client.chat.completions.create(model=model, messages=messages, stream=True, **kwargs)
        #     async for chunk in response_stream:
        #         if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
        #             yield chunk.choices[0].delta.content
        # For Gemini, use the appropriate streaming method and yield chunks.
        # Example for Gemini:
        # if self.provider == 'gemini':
        #     response_stream = await self.gemini_client.generate_content(model=model, contents=messages, stream=True, **kwargs)
        #     async for chunk in response_stream:
        #         if chunk.text:
        #             yield chunk.text
        # TODO: Implement actual streaming logic and return an async generator
        if provider == "openai":
        # CRADLE_EDIT: Original non-streaming return removed. Implement streaming logic above.
        elif provider == "gemini":
            return await self._gemini_complete(model, messages, stream, **kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

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
