"""Glue for shadow mode: news fetch, lazy AI scorer, never-raising tick.

Log-only. No order path. Scorer objects are built on first use, so a bad
budget/cache file shows up as a logged failed score, not a startup crash.
"""
from datetime import datetime, timezone

from alpaca.data.requests import NewsRequest

from utils.ai_budget import RequestBudget, ScoreCache
from utils.ai_client import get_daily_score


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def fetch_news_items(client, limit=50):
    """Latest `limit` unfiltered news items as plain dicts."""
    res = client.get_news(NewsRequest(limit=limit, sort="desc"))
    data = getattr(res, "data", None)
    if isinstance(data, dict):
        res = data.get("news", [])
    return [{"id": _get(n, "id"), "headline": _get(n, "headline"),
             "created_at": _get(n, "created_at"), "source": _get(n, "source")}
            for n in (res or [])]


def make_scorer(budget_path, cache_path, symbol="SPY", post=None, api_key=None):
    state = {}

    def score(day, headlines):
        if not state:
            state["budget"] = RequestBudget(budget_path)
            state["cache"] = ScoreCache(cache_path)
        return get_daily_score(day, headlines, datetime.now(timezone.utc),
                               state["budget"], state["cache"], symbol=symbol,
                               post=post, api_key=api_key)
    return score


def shadow_tick(shadow, now, fetch, score, audit):
    """One shadow pass. Audits only when something happened. Never raises."""
    try:
        out = shadow.step(now, fetch, score)
        if out["new"] or out["scored_day"] or out["errors"]:
            audit("shadow", new=out["new"], scored_day=out["scored_day"],
                  errors=out["errors"])
        return out
    except Exception:
        return None