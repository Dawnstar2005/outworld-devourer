"""Боссын горимын default (lookahead) ба хуучин ai/-тай нийцэл."""

import importlib.util

import pytest

from game import boss_driver
from game.boss_panel import ITERATION_UNITS, MODE_NAMES
from learning.profile import DEFAULT_PRIORITY

HAS_AI = importlib.util.find_spec("ai") is not None


def test_app_default_mode_is_lookahead():
    from game.app import BOSS_MODE_LABELS, BOSS_MODES, DEFAULT_BOSS_MODE
    assert DEFAULT_BOSS_MODE == "lookahead" == BOSS_MODES[0]
    assert set(BOSS_MODE_LABELS) == set(BOSS_MODES)


def test_panel_knows_lookahead():
    assert MODE_NAMES["lookahead"] and ITERATION_UNITS["lookahead"] != "симуляци"


def test_make_boss_without_ai_is_placeholder(monkeypatch):
    if HAS_AI:
        pytest.skip("ai/ суусан")
    assert isinstance(boss_driver.make_boss(seed=0), boss_driver.PlaceholderBoss)
    assert not boss_driver.lookahead_available()


@pytest.mark.skipif(not HAS_AI, reason="ai/ суугаагүй")
def test_make_boss_default_and_old_ai_fallback(monkeypatch):
    expected = "lookahead" if boss_driver.lookahead_available() else "eval"
    assert boss_driver.make_boss(seed=0).mode == expected
    monkeypatch.setattr(boss_driver, "lookahead_available", lambda: False)   # хуучин ai/
    assert boss_driver.make_boss(seed=0).mode == "eval"
    assert boss_driver.make_boss(mode="mcts", seed=0).mode == "mcts"


@pytest.mark.skipif(not HAS_AI, reason="ai/ суугаагүй")
def test_experiments_refuse_lookahead_on_old_ai(monkeypatch):
    from experiments.runner import make_boss_factory
    monkeypatch.setattr(boss_driver, "lookahead_available", lambda: False)
    with pytest.raises(ValueError):
        make_boss_factory("lookahead")
    assert make_boss_factory("eval")(None, 0).mode == "eval"


def test_profile_default_priority_is_equal_or_from_ai():
    """ai/ байхгүй үед тэнцүү эрэмбэ (PR #12); байвал ai.evaluate-ийнхтэй яг ижил."""
    if HAS_AI:
        from ai.evaluate import DEFAULT_PRIORITY as AI_PRIORITY
        assert DEFAULT_PRIORITY == AI_PRIORITY
    else:
        assert set(DEFAULT_PRIORITY.values()) == {1.0}
