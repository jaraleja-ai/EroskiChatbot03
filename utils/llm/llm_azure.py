# agent/utils/llm.py
from langchain_openai import AzureChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv()

llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_LLM_DEPLOYMENT"),
    azure_endpoint=os.getenv("AZURE_OPENAI_BASE"),
    openai_api_key=os.getenv("AZURE_OPENAI_KEY"),
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    temperature=0
)

