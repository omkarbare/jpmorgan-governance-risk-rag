from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from typing import Any

import litellm
from litellm import completion

litellm.set_verbose = False

PRIMARY_MODEL = os.getenv(
    "LLM_PRIMARY_MODEL",
    "groq/qwen/qwen3-32b",
)
FALLBACK_MODEL = os.getenv(
    "LLM_FALLBACK_MODEL",
    "openai/gpt-4o-mini",
)

LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_CACHE_TTL_SEC = int(os.getenv("LLM_CACHE_TTL_SEC", "300"))
LLM_CACHE_SIZE = int(os.getenv("LLM_CACHE_SIZE", "256"))

_cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
) -> str:
    # API keys are deliberately not part of messages or cache keys.
    payload = repr(
        {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_cached(key: str) -> str | None:
    now = time.time()

    with _cache_lock:
        item = _cache.get(key)
        if item is None:
            return None

        created_at, value = item
        if now - created_at > LLM_CACHE_TTL_SEC:
            del _cache[key]
            return None

        _cache.move_to_end(key)
        return value


def _set_cached(key: str, value: str) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), value)
        _cache.move_to_end(key)

        while len(_cache) > LLM_CACHE_SIZE:
            _cache.popitem(last=False)


def _call_model(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
    groq_api_key: str | None,
) -> str:
    call_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": LLM_TIMEOUT_SEC,
        "num_retries": LLM_MAX_RETRIES,
    }

    # The session key is used only for a Groq request. It is not logged,
    # persisted, included in cache keys, returned, or sent to the fallback.
    if model.startswith("groq/") and groq_api_key:
        call_kwargs["api_key"] = groq_api_key

    response = completion(**call_kwargs)

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError(f"Model returned an empty response: {model}")

    return str(content)


def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    groq_api_key: str | None = None,
) -> str:
    """
    Generate an LLM response with:
    - primary Groq/Qwen model;
    - OpenAI fallback;
    - LiteLLM retries and timeout;
    - in-memory exact-response cache;
    - optional request-scoped Groq key that is never persisted.
    """
    key = _cache_key(messages, temperature, max_tokens)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    selected_model = model or PRIMARY_MODEL

    try:
        answer = _call_model(
            model=selected_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            groq_api_key=groq_api_key,
        )
    except Exception as primary_error:
        if selected_model == FALLBACK_MODEL:
            raise

        try:
            answer = _call_model(
                model=FALLBACK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                groq_api_key=None,
            )
        except Exception as fallback_error:
            raise RuntimeError(
                "Both primary and fallback LLM calls failed. "
                f"Primary: {primary_error}; Fallback: {fallback_error}"
            ) from fallback_error

    _set_cached(key, answer)
    return answer
