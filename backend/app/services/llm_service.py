import json
import hashlib
import redis as redis_lib
from google import genai
from google.genai import types
from app.core.settings import settings

# Redis cache client for LLM response caching
_cache = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
_CACHE_TTL = 60 * 60 * 24  # 24 hours

# Gemini client (single instance — DRY)
_client = genai.Client(api_key=settings.GOOGLE_API_KEY)


def _cache_key(prompt: str) -> str:
    return f"llm:cache:{hashlib.sha256(prompt.encode()).hexdigest()}"


def _get_cached(prompt: str) -> dict | None:
    raw = _cache.get(_cache_key(prompt))
    return json.loads(raw) if raw else None


def _set_cached(prompt: str, response: dict) -> None:
    _cache.setex(_cache_key(prompt), _CACHE_TTL, json.dumps(response))


def call_llm(prompt: str, use_cache: bool = True) -> str:
    """
    Call Gemini LLM with optional Redis caching.
    Cache hit = zero LLM cost for repeated identical prompts.
    """
    if use_cache:
        cached = _get_cached(prompt)
        if cached:
            return cached["text"]

    response = _client.models.generate_content(
        model=settings.GOOGLE_API_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )
    text = response.text

    if use_cache:
        _set_cached(prompt, {"text": text})

    return text


def call_llm_json(prompt: str, use_cache: bool = True) -> dict:
    """
    Call LLM and parse JSON response. Raises ValueError if not valid JSON.
    """
    raw = call_llm(prompt, use_cache=use_cache)
    # Strip markdown code fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    return json.loads(cleaned.strip())
