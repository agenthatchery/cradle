
import asyncio
from typing import AsyncGenerator
import os

import logging
from typing import AsyncGenerator, Dict, Any, List, Optional, Union

import openai
from openai import AsyncOpenAI
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_client = None
        self.gemini_config = None
        self._initialize_clients()

    def _initialize_clients(self):
        if "openai" in self.config:
            openai_api_key = self.config["openai"].get("api_key")
            if not openai_api_key:
                openai_api_key = os.environ.get("OPENAI_API_KEY")
            if openai_api_key:
                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
            else:
                logger.warning("OpenAI API key not found in config or environment.")

        if "gemini" in self.config:
            gemini_api_key = self.config["gemini"].get("api_key")
            if not gemini_api_key:
                gemini_api_key = os.environ.get("GEMINI_API_KEY")
            if gemini_api_key:
                genai.configure(api_key=gemini_api_key)
                self.gemini_config = self.config["gemini"]
            else:
                logger.warning("Gemini API key not found in config or environment.")

    
    
    
        async def complete(self, messages: list[dict], model_name: str, temperature: float, max_tokens: int, **kwargs) -> AsyncGenerator[str, None]:
            client = self._get_client(model_name)
            if model_name.startswith("gpt"):
                stream = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    **kwargs
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        yield chunk.choices[0].delta.content
            elif model_name.startswith("gemini"):
                # Assuming Gemini client is already set up and supports streaming
                # This part needs to be adapted based on the actual Gemini client usage
                # Example for google.generativeai client (needs 'packages': ['google-generativeai'])
                model = client.get_model(model_name)
                response_stream = model.generate_content(
                    messages, 
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                    stream=True,
                    **kwargs
                )
                async for chunk in response_stream:
                    yield chunk.text
            else:
                # Fallback for non-streaming models or other providers
                # This might need to be a separate non-streaming 'complete_non_streaming' method
                # or handled by calling the non-streaming API and yielding the full result once.
                # For now, let's assume direct call and yield once.
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                if hasattr(response, 'choices') and response.choices:
                    yield response.choices[0].message.content
                elif hasattr(response, 'text'): # For Gemini non-streaming fallback
                    yield response.text
                else:
                    yield str(response) # Generic fallback
    