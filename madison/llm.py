"""One place that talks to the AI service and turns its failures into plain English."""
import json
import os
import threading

import openai

from .errors import FriendlyError

_client = None
_lock = threading.Lock()


def has_key():
    return bool(os.getenv("OPENAI_API_KEY"))


def _get_client():
    global _client
    if not has_key():
        raise FriendlyError(
            "The AI service isn't connected",
            "This copy of the tool has no AI key, so it can't write a new brief.",
            "Press “See an example brief” to see a finished one. If you run this tool, add OPENAI_API_KEY in the app's settings.")
    with _lock:
        if _client is None:
            _client = openai.OpenAI(timeout=90, max_retries=2)
    return _client


def chat_json(model, system, user, temperature=0.0):
    """Ask for a JSON object. Returns (parsed dict or None, raw text, (prompt_tokens, completion_tokens))."""
    try:
        r = _get_client().chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
    except openai.AuthenticationError:
        raise FriendlyError(
            "The AI service rejected this tool's key",
            "The key that lets this tool use the AI service is missing or expired. This is on our side, not yours.",
            "Please tell the person who shared this link. “See an example brief” still works in the meantime.")
    except openai.RateLimitError as e:
        if "insufficient_quota" in str(e):
            raise FriendlyError(
                "This demo's AI budget is used up",
                "The tool has reached the spending limit its owner set for the AI service.",
                "Please tell the person who shared this link. “See an example brief” still works in the meantime.")
        raise FriendlyError("The AI service is busy right now",
                            "Too many requests reached the AI service at the same time.",
                            "Wait about 30 seconds, then press “Build my brief” again.", kind="warn")
    except (openai.APITimeoutError, openai.APIConnectionError):
        raise FriendlyError("The AI service didn't answer in time",
                            "The connection to the AI service dropped or timed out. Nothing was published.",
                            "Press “Build my brief” again. Picking fewer competitors also makes it faster.", kind="warn")
    except openai.APIStatusError as e:
        raise FriendlyError("The AI service returned an error",
                            f"It answered with an error (code {e.status_code}). Nothing was published.",
                            "Try again in a minute.", kind="warn")
    text = r.choices[0].message.content or ""
    usage = (r.usage.prompt_tokens, r.usage.completion_tokens) if r.usage else (0, 0)
    try:
        data = json.loads(text.strip().removeprefix("```json").removeprefix("```").removesuffix("```"))
    except json.JSONDecodeError:
        data = None
    return (data if isinstance(data, dict) else None), text, usage
