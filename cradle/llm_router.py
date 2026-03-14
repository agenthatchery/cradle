
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
        # CRADLE_STREAMING_START: Added streaming support by Cradle AI
        # This section needs to be replaced with actual streaming logic for each provider.
        # Example for a hypothetical streaming provider:
        # if provider == "openai":
        #     async for chunk in openai_client.chat.completions.create(stream=True, ...):
        #         if chunk.choices[0].delta.content:
        #             yield chunk.choices[0].delta.content
        # else:
        #     # For non-streaming providers, yield the full response once.
        #     full_response = await original_complete_logic(...)
        #     yield full_response
        # CRADLE_STREAMING_END
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