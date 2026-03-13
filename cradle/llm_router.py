
import httpx
import json
import os
import asyncio
from typing import AsyncGenerator, Dict, Any

class LLMRouter:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.client = httpx.AsyncClient()

    async def _stream_openai(self, model: str, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "stream": True, **kwargs}
        async with self.client.stream("POST", "https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=None) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                # OpenAI's streaming format is line-delimited JSON, starting with 'data: '
                for line in chunk.decode().splitlines():
                    if line.startswith("data: "):
                        json_data = line[len("data: "):]
                        if json_data == "[DONE]":
                            break
                        try:
                            data = json.loads(json_data)
                            if data.get("choices") and data["choices"][0].get("delta") and data["choices"][0]["delta"].get("content"):
                                yield data["choices"][0]["delta"]["content"]
                        except json.JSONDecodeError:
                            # Handle incomplete JSON lines or other non-JSON data
                            pass

    async def _stream_gemini(self, model: str, messages: list, **kwargs) -> AsyncGenerator[str, None]:
        # Gemini API expects a specific message format
        formatted_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            formatted_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        headers = {"Content-Type": "application/json"}
        payload = {"contents": formatted_messages, **kwargs}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={self.gemini_api_key}"

        async with self.client.stream("POST", url, headers=headers, json=payload, timeout=None) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                # Gemini's streaming format is similar to OpenAI's but can be more complex
                # It often returns multiple JSON objects in a single chunk, not always line-delimited
                # This parser is simplified and might need robust error handling for real-world use
                try:
                    # Attempt to parse the chunk as a series of JSON objects
                    # This is a basic attempt and might need a more sophisticated JSON stream parser
                    data_str = chunk.decode()
                    # Simple heuristic for splitting multiple JSON objects in a stream
                    for part in data_str.split('}
{'):
                        if part.strip():
                            # Reconstruct potential incomplete JSON objects
                            if not part.startswith('{'):
                                part = '{' + part
                            if not part.endswith('}'):
                                part = part + '}'
                            try:
                                data = json.loads(part)
                                if data.get("candidates") and data["candidates"][0].get("content") and data["candidates"][0]["content"].get("parts"):
                                    for part_obj in data["candidates"][0]["content"]["parts"]:
                                        if part_obj.get("text"):
                                            yield part_obj["text"]
                            except json.JSONDecodeError:
                                # Handle incomplete JSON objects or non-JSON data
                                pass
                except UnicodeDecodeError:
                    # Handle cases where chunk is not fully decodable as UTF-8
                    pass

    async def complete(self, provider: str, model: str, messages: list, stream: bool = False, **kwargs) -> AsyncGenerator[str, None] | Dict[str, Any]:
        if provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not set.")
            if stream:
                return self._stream_openai(model, messages, **kwargs)
            else:
                headers = {"Authorization": f"Bearer {self.openai_api_key}", "Content-Type": "application/json"}
                payload = {"model": model, "messages": messages, **kwargs}
                response = await self.client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        elif provider == "gemini":
            if not self.gemini_api_key:
                raise ValueError("Gemini API key not set.")

            formatted_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                formatted_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

            if stream:
                return self._stream_gemini(model, messages, **kwargs)
            else:
                headers = {"Content-Type": "application/json"}
                payload = {"contents": formatted_messages, **kwargs}
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
                response = await self.client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

# Example usage (for testing purposes, not part of the class itself)
async def main():
    router = LLMRouter()
    messages = [{"role": "user", "content": "What is the capital of France?"}]

    print("
--- OpenAI Streaming ---")
    try:
        async for chunk in router.complete(provider="openai", model="gpt-3.5-turbo", messages=messages, stream=True):
            print(chunk, end='')
        print()
    except Exception as e:
        print(f"OpenAI streaming error: {e}")

    print("
--- Gemini Streaming ---")
    try:
        async for chunk in router.complete(provider="gemini", model="gemini-pro", messages=messages, stream=True):
            print(chunk, end='')
        print()
    except Exception as e:
        print(f"Gemini streaming error: {e}")

    print("
--- OpenAI Non-Streaming ---")
    try:
        response = await router.complete(provider="openai", model="gpt-3.5-turbo", messages=messages, stream=False)
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"OpenAI non-streaming error: {e}")

    print("
--- Gemini Non-Streaming ---")
    try:
        response = await router.complete(provider="gemini", model="gemini-pro", messages=messages, stream=False)
        print(json.dumps(response, indent=2))
    except Exception as e:
        print(f"Gemini non-streaming error: {e}")

if __name__ == '__main__':
    # Set dummy API keys for local testing if needed
    # os.environ["OPENAI_API_KEY"] = "sk-..."
    # os.environ["GEMINI_API_KEY"] = "AIza..."
    asyncio.run(main())
