from pathway.xpacks.llm import llms
from dotenv import load_dotenv
import os

load_dotenv()

chat_model = llms.OpenAIChat(
    model="gpt-4o-mini",
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY"),
)
