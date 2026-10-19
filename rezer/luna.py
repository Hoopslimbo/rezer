"""Luna — the built-in AI assistant. Powered by the Pollinations text API
(https://text.pollinations.ai), which is free and needs no API key."""

from urllib.parse import quote

import requests

API_BASE = "https://text.pollinations.ai/"
TIMEOUT = 60
MAX_PAGE_CHARS = 4000

SYSTEM = (
    "You are Luna, a helpful AI assistant built into the Rezer web browser. "
    "Answer concisely and in plain language."
)


def ask(prompt: str, context: str = "") -> str:
    """Ask Luna anything. `context` is optional page text for grounding."""
    full = SYSTEM + "\n\n"
    if context:
        full += "Page content for reference:\n" + context[:MAX_PAGE_CHARS] + "\n\n"
    full += "User: " + prompt
    try:
        r = requests.get(API_BASE + quote(full), timeout=TIMEOUT)
        r.raise_for_status()
        text = r.text.strip()
        return text or "Luna didn't get a response. Try again?"
    except requests.RequestException:
        return "Luna couldn't reach the AI service right now. Check your connection and try again."


def summarize_page(page_text: str) -> str:
    return ask("Summarize this webpage in a few short bullet points.", context=page_text)


def explain_selection(selected_text: str) -> str:
    return ask("Explain this in simple terms: " + selected_text[:2000])
