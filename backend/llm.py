"""LLM orchestration stub. Both Groq and Ollama expose an OpenAI-compatible
API, so one client covers either backend via env vars.

ponytail: no tools registered yet — wire in rule-function tools per PRD feature list once scope is confirmed.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("LLM_API_KEY", "ollama"),
    timeout=5.0,
    max_retries=0,
)
MODEL = os.getenv("LLM_MODEL", "llama3.1")


def chat(messages: list[dict], tools: list[dict] | None = None):
    return client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
