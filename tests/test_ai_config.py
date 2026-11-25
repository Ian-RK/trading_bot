import dataclasses
from datetime import datetime, timezone

import pytest

from utils.ai_budget import RequestBudget, ScoreCache
from utils.ai_client import get_daily_score
from utils.ai_config import DEFAULT_CONFIG, cache_version, system_prompt

NOW = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)


def test_prompt_names_the_target_and_has_no_placeholder_left():
    p = system_prompt(DEFAULT_CONFIG, "SPY")
    assert "S&P 500" in p and "{target}" not in p
    assert "Nasdaq-100" in system_prompt(DEFAULT_CONFIG, "QQQ")


def test_unsupported_symbol_raises():
    with pytest.raises(ValueError):
        system_prompt(DEFAULT_CONFIG, "ZZZZ")
    with pytest.raises(ValueError):
        cache_version(DEFAULT_CONFIG, "ZZZZ")


def test_cache_version_separates_symbols():
    assert cache_version(DEFAULT_CONFIG, "SPY") != cache_version(DEFAULT_CONFIG, "QQQ")


def test_editing_the_prompt_changes_the_cache_version():
    edited = dataclasses.replace(
        DEFAULT_CONFIG, system_prompt_template=DEFAULT_CONFIG.system_prompt_template + " ")
    assert cache_version(edited, "SPY") != cache_version(DEFAULT_CONFIG, "SPY")


def test_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_CONFIG.model = "other"


def test_unsupported_symbol_gives_neutral_without_call_or_budget(tmp_path):
    calls = []

    def post(*a):
        calls.append(a)

    budget = RequestBudget(tmp_path / "b.json")
    cache = ScoreCache(tmp_path / "c.json")
    r = get_daily_score("2026-11-25", [{"headline": "x"}], NOW, budget, cache,
                        symbol="ZZZZ", post=post, api_key="k")
    assert r["ok"] is False and "unsupported" in r["reason"]
    assert calls == []
    assert not (tmp_path / "b.json").exists()