
import logging
from typing import AsyncIterator, Any, Dict
import openai
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)

    async def complete(self, messages: list[dict], model: str, stream: bool = False, **kwargs):
        if stream:
            # Placeholder for actual streaming logic
            yield 'Streaming chunk example.'
            return
            provider = self._get_provider(model)
            if stream and provider.supports_streaming:
                async for chunk in provider.stream_complete(messages, model, **kwargs):
                    yield chunk
            else:
                response = await provider.complete(messages, model, **kwargs)
                yield response

        Args:
            model: The name of the LLM model to use (e.g., 'gpt-4o', 'gemini-pro').
            messages: A list of message dictionaries for the conversation history.
            **kwargs: Additional keyword arguments to pass to the LLM API.

        Yields:
            Chunks of the streaming response as strings.
        """
        logger.info(f"Requesting streaming completion from model: {model}")
        try:
            if model.startswith("gpt"):
                async for chunk in await self._openai_stream_complete(model, messages, **kwargs):
                    yield chunk
            elif model.startswith("gemini"):
                async for chunk in await self._gemini_stream_complete(model, messages, **kwargs):
                    yield chunk
            else:
                raise ValueError(f"Unsupported model: {model}")
        except Exception as e:
            logger.error(f"Error during LLM streaming completion for {model}: {e}")
            raise

    async def _openai_stream_complete(self, model: str, messages: list[Dict[str, str]], **kwargs) -> AsyncIterator[str]:
        """Handles streaming completion for OpenAI models."""
        stream = await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _gemini_stream_complete(self, model: str, messages: list[Dict[str, str]], **kwargs) -> AsyncIterator[str]:
        """Handles streaming completion for Gemini models."""
        if not self.gemini_api_key:
            raise ValueError("Gemini API key not configured.")

        # Gemini expects roles 'user' and 'model', convert OpenAI-style messages
        gemini_messages = []
        for msg in messages:
            role = 'user' if msg['role'] == 'user' else 'model'
            gemini_messages.append({'role': role, 'parts': [msg['content']]})

        model_instance = genai.GenerativeModel(model)
        response_stream = await model_instance.generate_content_async(
            gemini_messages,
            stream=True,
            **kwargs
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text