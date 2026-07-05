import requests

from app.config import GROQ_API_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def summarize_and_tag(text: str) -> str | None:
    """Runs command text through Groq's free LLM API to produce a one-line
    summary/tag. Returns None if AI is not configured or the call fails —
    the app must keep working without it."""
    if not GROQ_API_KEY or not text:
        return None
    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Summarize this in under 12 words and add one "
                            f"category tag in brackets. Text: {text}"
                        ),
                    }
                ],
                "max_tokens": 60,
            },
            timeout=5,
        )
        if resp.status_code < 300:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError):
        pass
    return None
