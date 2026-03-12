
import openai
import google.generativeai as genai
import asyncio

class LLMRouter:
    def __init__(self, openai_api_key=None, gemini_api_key=None):
        if openai_api_key:
            openai.api_key = openai_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    async async def complete(self, provider: str, model: str, messages: list, stream: bool = False):
        # TODO: Implement actual streaming logic here using `yield`
        # Example: `async for chunk in provider.stream_completion(...): yield chunk`
        if provider == "openai":
            if stream:
                async def openai_stream_generator():
                    response = await openai.ChatCompletion.acreate(
                        model=model,
                        messages=messages,
                        stream=True
                    )
                    async for chunk in response:
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content
                return openai_stream_generator()
            else:
                response = await openai.ChatCompletion.acreate(
                    model=model,
                    messages=messages,
                    stream=False
                )
                return response.choices[0].message.content
        elif provider == "gemini":
            if stream:
                async def gemini_stream_generator():
                    model_instance = genai.GenerativeModel(model_name=model)
                    # Gemini API expects messages in a specific format for content
                    # This example assumes messages are already in the correct format
                    # e.g., [{'role': 'user', 'parts': ['text']}]
                    response = await model_instance.generate_content_async(
                        contents=messages,
                        stream=True
                    )
                    async for chunk in response:
                        yield chunk.text
                return gemini_stream_generator()
            else:
                model_instance = genai.GenerativeModel(model_name=model)
                response = await model_instance.generate_content_async(
                    contents=messages,
                    stream=False
                )
                return response.text
        else:
            raise ValueError(f"Unsupported provider: {provider}")
