import os
import requests
from typing import Optional

_PROMPT = (
    "You are a code documentation assistant. "
    "Write a brief technical passage (2-4 sentences) that would answer this question "
    "about a software codebase. Use specific technical terminology.\n\n"
    "Question: {query}\n\nAnswer:"
)


def generate_hyde(query: str) -> Optional[str]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    model = os.getenv("COEUS_LLM_MODEL", "anthropic/claude-3.5-haiku")
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": _PROMPT.format(query=query)}],
                "max_tokens": 150,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
