
import openai
import google.generativeai as genai
import asyncio
from typing import AsyncGenerator, Dict, Any, List

class LLMRouter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.openai_client = None
        self.gemini_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        if 'openai' in self.config:
            self.openai_client = openai.AsyncOpenAI(api_key=self.config['openai'].get('api_key'))
        if 'gemini' in self.config:
            genai.configure(api_key=self.config['gemini'].get('api_key'))
            self.gemini_client = genai

    async def complete(self, provider: str, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Completes a chat interaction with the specified LLM provider, supporting streaming responses.
        """
        if provider == 'openai':
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized. Check configuration.")
            try:
                stream = await self.openai_client.chat.completions.create(
                    model=kwargs.get('model', 'gpt-4o'),
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                print(f"OpenAI API error: {e}")
                raise
        elif provider == 'gemini':
            if not self.gemini_client:
                raise ValueError("Gemini client not initialized. Check configuration.")
            try:
                model = self.gemini_client.GenerativeModel(model_name=kwargs.get('model', 'gemini-pro'))
                # Gemini expects history in a specific format
                gemini_history = []
                for msg in messages:
                    role = 'user' if msg['role'] == 'user' else 'model'
                    gemini_history.append({'role': role, 'parts': [msg['content']]})

                # The last message is the prompt
                prompt = gemini_history.pop() if gemini_history else {'role': 'user', 'parts': ['']}

                stream = await model.generate_content_async(
                    contents=prompt['parts'][0],
                    generation_config=genai.types.GenerationConfig(
                        temperature=kwargs.get('temperature', 0.7),
                        max_output_tokens=kwargs.get('max_tokens', 2048)
                    ),
                    safety_settings=kwargs.get('safety_settings', None),
                    stream=True
                )

                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
            except Exception as e:
                print(f"Gemini API error: {e}")
                raise
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

# Example usage (for testing purposes, not part of the class)
async def main():
    # This part would typically be in your task_engine or similar, calling the router
    # For demonstration, assume a config is available
    config = {
        'openai': {'api_key': os.environ.get('OPENAI_API_KEY')},
        'gemini': {'api_key': os.environ.get('GEMINI_API_KEY')}
    }
    router = LLMRouter(config)

    print("
--- OpenAI Streaming ---")
    openai_messages = [{
        "role": "user",
        "content": "Tell me a very short story about a robot and a cat."
    }]
    try:
        async for chunk in router.complete('openai', openai_messages, model='gpt-3.5-turbo'):
            print(chunk, end='')
        print('
')
    except ValueError as e:
        print(f"Error with OpenAI: {e}")

    print("
--- Gemini Streaming ---")
    gemini_messages = [{
        "role": "user",
        "content": "Write a haiku about autonomous agents."
    }]
    try:
        async for chunk in router.complete('gemini', gemini_messages, model='gemini-pro'):
            print(chunk, end='')
        print('
')
    except ValueError as e:
        print(f"Error with Gemini: {e}")

if __name__ == '__main__':
    # Only run main if API keys are available for testing purposes
    if os.environ.get('OPENAI_API_KEY') or os.environ.get('GEMINI_API_KEY'):
        asyncio.run(main())
    else:
        print("Set OPENAI_API_KEY or GEMINI_API_KEY environment variables to run example usage.")
