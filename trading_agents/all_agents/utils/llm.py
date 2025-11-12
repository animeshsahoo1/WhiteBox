from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os

load_dotenv()

# Use LiteLLM with OpenRouter for better model availability
chat_model = llms.LiteLLMChat(
    model="openrouter/openai/gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
)