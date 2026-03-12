
import openai
import google.generativeai as genai
import asyncio

class LLMRouter:


    async def complete(self, prompt: str, provider: str = "openai", **kwargs):
        if provider == "openai":
            # Assuming self.openai_client is an async OpenAI client
            # and supports .stream attribute for chat completions
            stream = await self.openai_client.chat.completions.create(
                model=kwargs.get("model", "gpt-4"),
                messages=[{"role": "user", "content": prompt}],
                stream=True, # Enable streaming
                **kwargs
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        elif provider == "gemini":
            # Assuming self.gemini_client is an async Gemini client
            # and supports .generate_content with stream=True
            model = self.gemini_client.GenerativeModel(kwargs.get("model", "gemini-pro"))
            response_stream = model.generate_content(
                prompt,
                stream=True,
                **kwargs
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        elif provider == "mock": # A simple mock provider for testing or local development
            for char in f"Mock streaming response for: {prompt}":
                yield char
                await asyncio.sleep(0.01) # Simulate delay
        else:
            # Fallback for non-streaming providers or if streaming is not implemented
            # This part would typically call a non-streaming version or raise an error.
            # For now, we'll just yield a single non-streaming response.
            # In a real scenario, you'd likely have a separate non-streaming path
            # or ensure all paths return an async generator.
            print(f"Warning: Provider {provider} does not support streaming or is not implemented. Returning full response.")
            # This part needs actual implementation based on other providers.
            # For now, we'll just return a placeholder string if no streaming path is found.
            yield f"[NON-STREAMING] Full response for {provider}: {prompt}"

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
