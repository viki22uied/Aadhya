"""LLM orchestration stub. Both Groq and Ollama expose an OpenAI-compatible
API, so one client covers either backend via env vars.
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
    # tool_choice="auto" is the OpenAI-spec default when tools are passed, but
    # some OpenAI-compatible backends (small Groq models especially) skip real
    # tool-calling and instead write fake tool-call syntax into plain text
    # unless this is explicit.
    kwargs = {"tool_choice": "auto"} if tools else {}
    return client.chat.completions.create(model=MODEL, messages=messages, tools=tools, **kwargs)
