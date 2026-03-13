
import asyncio
import json
import logging
import os
from typing import AsyncGenerator, Dict, Any, List, Optional

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletion
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.openai_client = None
        self.gemini_client = None # Placeholder for Gemini client
        self._initialize_clients()

    def _initialize_clients(self):
        if os.environ.get("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI()
        # if os.environ.get("GEMINI_API_KEY"):
        #     self.gemini_client = some_gemini_client_init()

    async def complete(self, messages: List[Dict[str, str]], model: str = "gpt-4o", **kwargs) -> AsyncGenerator[str, None]:
        """
        Completes a chat interaction with the specified LLM, supporting streaming.
        Yields string chunks of the response.
        """
        logger.info(f"Attempting LLM completion with model: {model}")

        if model.startswith("gpt") and self.openai_client:
            async for chunk in self._openai_stream_complete(messages, model, **kwargs):
                yield chunk
        # elif model.startswith("gemini") and self.gemini_client:
        #     async for chunk in self._gemini_stream_complete(messages, model, **kwargs):
        #         yield chunk
        else:
            # Fallback for non-streaming or unsupported models/clients
            logger.warning(f"Streaming not supported for model {model} or client not initialized. Falling back to non-streaming.")
            full_response = await self._non_streaming_complete(messages, model, **kwargs)
            yield full_response


    async def _openai_stream_complete(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AsyncGenerator[str, None]:
        try:
            stream = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    # Placeholder for Gemini streaming
    # async def _gemini_stream_complete(self, messages: List[Dict[str, str]], model: str, **kwargs) -> AsyncGenerator[str, None]:
    #     try:
    #         # Assuming Gemini client has a similar streaming interface
    #         stream = await self.gemini_client.generate_content_async(
    #             contents=[{'role': m['role'], 'parts': [{'text': m['content']}]} for m in messages],
    #             stream=True,
    #             model=model,
    #             **kwargs
    #         )
    #         async for chunk in stream:
    #             if chunk.text:
    #                 yield chunk.text
    #     except Exception as e:
    #         logger.error(f"Gemini streaming error: {e}")
    #         raise

    async def _non_streaming_complete(self, messages: List[Dict[str, str]], model: str, **kwargs) -> str:
        """Handles non-streaming completion for models without explicit streaming support or as a fallback."""
        if model.startswith("gpt") and self.openai_client:
            response: ChatCompletion = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content if response.choices else ""
        # Add other non-streaming clients here if needed
        else:
            raise ValueError(f"No client available for model: {model}")

