
import asyncio
import httpx
import json
import os
import logging

logger = logging.getLogger(__name__)

class LLMRouter:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.active_provider = "openai" # Default provider

    def set_provider(self, provider: str):
        if provider not in ["openai", "gemini"]:
            raise ValueError("Invalid LLM provider. Choose 'openai' or 'gemini'.")
        self.active_provider = provider
        logger.info(f"LLM provider set to {self.active_provider}")

async def complete(self, model_name: str, messages: list, max_tokens: int, temperature: float, provider: str):
        if provider == "openai":
            import openai
            client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            stream = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            async for chunk in stream:
                yield chunk.choices[0].delta.content or ""
        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
            model = genai.GenerativeModel(model_name)
            response_stream = await model.generate_content(
                contents=messages,
                generation_config={'max_output_tokens': max_tokens, 'temperature': temperature},
                stream=True
            )
            async for chunk in response_stream:
                yield chunk.text
        else:
            # Fallback for non-streaming providers or error
            # For now, I'll just raise an error, but a non-streaming fallback could be implemented
            raise NotImplementedError(f"Streaming not supported for provider: {provider}")

        
        


'
                        # We need to parse each line. A chunk might contain multiple lines.
                        for line in chunk.decode('utf-8').splitlines():
                            if line.strip().startswith("data:"):
                                json_str = line.strip()[len("data:"):].strip()
                                if json_str == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(json_str)
                                    yield data
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to decode JSON from OpenAI stream: {json_str}")
                                    continue
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI API HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"OpenAI API request error: {e}")
                raise

    async def _gemini_complete(self, messages: list, model: str = None, **kwargs):
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        
        # Gemini expects 'parts' within 'contents'
        formatted_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model" # Gemini uses 'user'/'model'
            formatted_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": formatted_messages,
            "generationConfig": {
                "temperature": kwargs.get("temperature", 0.7),
                "topP": kwargs.get("top_p", 0.95),
                "topK": kwargs.get("top_k", 60),
                "maxOutputTokens": kwargs.get("max_tokens", 8192),
            }
        }

        gemini_model = model or "gemini-1.5-pro-latest"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:streamGenerateContent?key={self.gemini_api_key}"

        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=None) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        # Gemini streams data as newline-delimited JSON objects
                        # A chunk might contain multiple lines or partial lines.
                        # We need to buffer and process complete JSON objects.
                        buffer = b''
                        buffer += chunk
                        while b'
' in buffer:
                            line, buffer = buffer.split(b'
', 1)
                            try:
                                data = json.loads(line.decode('utf-8'))
                                yield data
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to decode JSON from Gemini stream: {line.decode('utf-8')}")
                                continue
            except httpx.HTTPStatusError as e:
                logger.error(f"Gemini API HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Gemini API request error: {e}")
                raise