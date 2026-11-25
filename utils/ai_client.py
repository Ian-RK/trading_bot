"""OpenRouter client for the advisory AI score. It never trades.

The HTTP call is injected (`post`) so tests never touch the network. The API
key is read from the environment and is never printed, logged or returned.
Every failure gives a neutral score. There are no retries.
Settings live in utils/ai_config.py.
"""
import os

from utils.ai_config import DEFAULT_CONFIG, cache_version, system_prompt
from utils.ai_sentiment import parse_sentiment


def _neutral(reason):
    return {"score": 0.0, "confidence": 0.0, "ok": False,
            "reason": reason, "source": "none"}


def _clean(headlines, max_chars):
    lines = []
    for h in headlines:
        text = " ".join(str(h.get("headline", "")).split())[:max_chars]
        if text:
            lines.append(text)
    return lines


def build_messages(system, lines):
    body = "Headlines:\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(lines, 1))
    return [{"role": "system", "content": system},
            {"role": "user", "content": body}]


def _default_post(url, headers, payload, timeout):
    import requests
    return requests.post(url, headers=headers, json=payload, timeout=timeout)


def _content(body):
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    return text if isinstance(text, str) else None


def get_daily_score(day, headlines, now, budget, cache, symbol="SPY",
                    config=DEFAULT_CONFIG, post=None, api_key=None):
    """Score one trading day's headlines. `day` is a YYYY-MM-DD string."""
    try:
        version = cache_version(config, symbol)
        system = system_prompt(config, symbol)
    except ValueError:
        return _neutral(f"unsupported symbol {symbol!r}")

    cached = cache.get(config.model, version, day)
    if cached is not None:
        return {**cached, "source": "cache"}

    lines = _clean(headlines, config.max_headline_chars)
    if not lines:
        return _neutral("no headlines")

    key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return _neutral("no API key configured")

    if not budget.try_consume(now):
        return _neutral("request budget exhausted")

    payload = {"model": config.model, "messages": build_messages(system, lines),
               "temperature": 0, "max_tokens": config.max_tokens}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        resp = (post or _default_post)(config.url, headers, payload,
                                       config.timeout_seconds)
    except Exception as e:
        return _neutral(f"request failed ({type(e).__name__})")

    status = getattr(resp, "status_code", None)
    if status != 200:
        return _neutral(f"HTTP status {status}")
    try:
        body = resp.json()
    except ValueError:
        return _neutral("response is not JSON")

    text = _content(body)
    if text is None:
        return _neutral("response has no message content")
    result = parse_sentiment(text)
    if not result["ok"]:
        return {**result, "source": "api"}

    try:
        cache.put(config.model, version, day, result,
                  meta={"n_headlines": len(lines), "symbol": symbol})
    except (OSError, ValueError):
        pass          # a cache problem must never block or alter the score
    return {**result, "source": "api"}