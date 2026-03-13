
import logging
import openai
from openai import AsyncOpenAI
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import os
import asyncio

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
            logger.info("OpenAI client initialized.")
        else:
            logger.warning("OPENAI_API_KEY not found. OpenAI client not initialized.")

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.gemini_client = genai
            logger.info("Gemini client initialized.")
        else:
            logger.warning("GEMINI_API_KEY not found. Gemini client not initialized.")

    # Streaming support placeholder
async def complete(self, prompt: str, model: str = "gpt-4o", max_tokens: int = 1000, temperature: float = 0.7, stream: bool = False):
        """
        Generates a completion from an LLM. Supports streaming responses.
        """
        if model.startswith("gpt"):
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized.")
            return await self._openai_complete(prompt, model, max_tokens, temperature, stream)
        elif model.startswith("gemini"):
            if not self.gemini_client:
                raise ValueError("Gemini client not initialized.")
            return await self._gemini_complete(prompt, model, max_tokens, temperature, stream)
        else:
            raise ValueError(f"Unsupported model: {model}")

    async def _openai_complete(self, prompt: str, model: str, max_tokens: int, temperature: float, stream: bool):
        messages = [{"role": "user", "content": prompt}]
        try:
            if stream:
                async def generator():
                    async for chunk in await self.openai_client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True,
                    ):
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generator()
            else:
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )
                return response.choices[0].message.content
        except openai.APIStatusError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _gemini_complete(self, prompt: str, model: str, max_tokens: int, temperature: float, stream: bool):
        generation_config = GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            if stream:
                async def generator():
                    response_stream = await self.gemini_client.get_model(model).generate_content(
                        prompt,
                        generation_config=generation_config,
                        stream=True,
                    )
                    async for chunk in response_stream:
                        if chunk.text:
                            yield chunk.text
                return generator()
            else:
                response = await self.gemini_client.get_model(model).generate_content(
                    prompt,
                    generation_config=generation_config,
                    stream=False,
                )
                return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

