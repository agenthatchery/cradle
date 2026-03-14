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

    
    async def complete(self, messages: list[dict], provider: str, model: str, temperature: float) -> AsyncGenerator[str, None]:
        """Completes a chat interaction, supporting streaming responses."""
        if provider == "openai":
            from openai import AsyncOpenAI # Import inside to avoid global dependency if not used
            client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        elif provider == "gemini":
            from google.generativeai.client import get_default_retriever_async_client
            from google.generativeai.types import content_types
            from google.generativeai.generative_models import GenerativeModel, ChatSession
            
            # Ensure GEMINI_API_KEY is set in environment
            gemini_api_key = os.environ.get("GEMINI_API_KEY")
            if not gemini_api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set for Gemini provider.")
            
            model_client = GenerativeModel(model_name=model, generation_config={'temperature': temperature})
            
            # Convert messages to Gemini format
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append(content_types.to_content(role=role, parts=[msg["content"]]))
            
            # Start a chat session (if applicable for streaming, otherwise call generate_content directly)
            # For simple streaming, direct generate_content is often easier.
            # Assuming `generate_content` supports streaming directly.
            
            stream = await model_client.generate_content_async(
                contents=gemini_messages,
                stream=True
            )
            
            async for chunk in stream:
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        yield part.text
        else:
            # Fallback for non-streaming providers or other providers
            # This part needs to call the non-streaming API and yield the full response.
            # For now, I'll raise an error or provide a basic non-streaming implementation.
            # A proper implementation would integrate existing non-streaming logic here.
            raise NotImplementedError(f"Streaming not yet implemented for provider: {provider}")
