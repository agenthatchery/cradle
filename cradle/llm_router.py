
import openai
import google.generativeai as genai
import asyncio

class LLMRouter:

    async def complete(self, messages, model_name, stream: bool = False, **kwargs):
        if model_name.startswith("gpt"):
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized.")
            if stream:
                async for chunk in await self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=True,
                    **kwargs
                ):
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                response = await self.openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    stream=False,
                    **kwargs
                )
                yield response.choices[0].message.content
        elif model_name.startswith("gemini"):
            if not self.gemini_client:
                raise ValueError("Gemini client not initialized.")
            if stream:
                response = await self.gemini_client.generate_content(
                    contents=messages,
                    stream=True,
                    **kwargs
                )
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
            else:
                response = await self.gemini_client.generate_content(
                    contents=messages,
                    stream=False,
                    **kwargs
                )
                yield response.text
        else:
            raise ValueError(f"Unsupported model provider: {model_name}")
    def __init__(self, openai_api_key=None, gemini_api_key=None):
        if openai_api_key:
            openai.api_key = openai_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)

    async async async def complete_stream(self, provider: str, model: str, messages: list, stream: bool = False):
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
                # Placeholder for streaming logic
        # Example for OpenAI:
        # async for chunk in client.chat.completions.create(..., stream=True):
        #     if chunk.choices[0].delta.content:
        #         yield chunk.choices[0].delta.content
        yield openai_stream_generator()
            else:
                response = await openai.ChatCompletion.acreate(
                    model=model,
                    messages=messages,
                    stream=False
                )
                # Placeholder for streaming logic
        # Example for OpenAI:
        # async for chunk in client.chat.completions.create(..., stream=True):
        #     if chunk.choices[0].delta.content:
        #         yield chunk.choices[0].delta.content
        yield response.choices[0].message.content
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
                # Placeholder for streaming logic
        # Example for OpenAI:
        # async for chunk in client.chat.completions.create(..., stream=True):
        #     if chunk.choices[0].delta.content:
        #         yield chunk.choices[0].delta.content
        yield gemini_stream_generator()
            else:
                model_instance = genai.GenerativeModel(model_name=model)
                response = await model_instance.generate_content_async(
                    contents=messages,
                    stream=False
                )
                # Placeholder for streaming logic
        # Example for OpenAI:
        # async for chunk in client.chat.completions.create(..., stream=True):
        #     if chunk.choices[0].delta.content:
        #         yield chunk.choices[0].delta.content
        yield response.text
        else:
            raise ValueError(f"Unsupported provider: {provider}")
