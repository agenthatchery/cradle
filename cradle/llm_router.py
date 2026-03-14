
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

    async def complete(self, 
                       model: str, 
                       messages: List[Dict[str, str]], 
                       stream: bool = False,
                       **kwargs) -> Union[AsyncGenerator[str, None], str]:
        
        if model.startswith("gpt") and self.openai_client:
            return await self._openai_complete(model, messages, stream, **kwargs)
        elif model.startswith("gemini") and self.gemini_config:
            return await self._gemini_complete(model, messages, stream, **kwargs)
        else:
            raise ValueError(f"Unsupported model or provider: {model}")

    async def _openai_complete(self,
                               model: str,
                               messages: List[Dict[str, str]],
                               stream: bool,
                               **kwargs) -> Union[AsyncGenerator[str, None], str]:
        try:
            if stream:
                response_stream = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                async def generator():
                    async for chunk in response_stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generator()
            else:
                response = await self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                    **kwargs
                )
                return response.choices[0].message.content
        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {e}")
            raise

    async def _gemini_complete(self,
                              model: str,
                              messages: List[Dict[str, str]],
                              stream: bool,
                              **kwargs) -> Union[AsyncGenerator[str, None], str]:
        try:
            # Gemini expects messages in a specific format for chat models
            formatted_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_messages.append({"role": role, "parts": [msg["content"]]})

            model_client = genai.GenerativeModel(model_name=model)
            
            if stream:
                response_stream = await model_client.generate_content_async(
                    contents=formatted_messages,
                    stream=True,
                    **kwargs
                )
                async def generator():
                    async for chunk in response_stream:
                        yield chunk.text
                return generator()
            else:
                response = await model_client.generate_content_async(
                    contents=formatted_messages,
                    stream=False,
                    **kwargs
                )
                return response.text
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            raise

