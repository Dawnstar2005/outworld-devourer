"""game/prediction.py: тоглогчийн нүүдлийн таамаг, зөв таасан тоо, арын thread-ийн сургалт."""

import os
import time

import pytest

from engine import END_TURN, HEROES, Action, GameState
from game.prediction import LearnedModels, PredictionTracker, class_label
from learning.predictor import MovePredictor


class FixedPredictor:
    """Бүх баатарт «хөдлөх/хүлээх»-ийг 0.9, бусдыг бага гэж таамаглана."""

    def class_probs(self, state, uid, actions=None):
        return [((None, None), 0.9), (("sword", "imp1"), 0.05), (("heal", "mage"), 0.05)]


def test_class_label():
    s = GameState.new_game()
    assert class_label((None, None)) == "Хөдлөх / хүлээх"
    assert "Imp 1" in class_label(("sword", "imp1"), s)
    assert class_label(("taunt", None)) and "-т" not in class_label(("taunt", None))


def test_refresh_only_on_human_turn_and_pending_heroes():
    s = GameState.new_game()
    t = PredictionTracker(FixedPredictor())
    t.refresh(s)
    assert [g.uid for g in t.guesses] == [u.uid for u in s.alive_units(HEROES)]
    assert all(g.p == 0.9 for g in t.guesses)
    s.units["knight"].acted = True
    t.refresh(s)
    assert "knight" not in [g.uid for g in t.guesses]
    s.side_to_act = "demons"
    t.refresh(s)
    assert t.guesses == []


def test_hit_counting():
    s = GameState.new_game()
    t = PredictionTracker(FixedPredictor())
    knight = s.units["knight"]
    t.on_action(s, Action("knight", knight.pos), [])                 # хүлээх — top-1 зөв
    assert (t.hits, t.hits3, t.total) == (1, 1, 1) and t.last[3]
    t.on_action(s, Action("knight", knight.pos, "sword", (0, 0), "imp1"), [])   # top-3 дотор
    assert (t.hits, t.hits3, t.total) == (1, 2, 2) and not t.last[3]
    t.on_action(s, END_TURN, [])                                      # тоологдохгүй
    s.side_to_act = "demons"
    t.on_action(s, Action("imp1", s.units["imp1"].pos), [])           # боссын нүүдэл тоологдохгүй
    assert t.total == 2
    p = t.panel()
    assert p["hits"] == 1 and p["total"] == 2 and p["last"][0] == "knight"
    t.reset()
    assert t.total == 0 and t.last is None


def test_real_predictor_works_with_tracker():
    s = GameState.new_game()
    t = PredictionTracker(MovePredictor())
    t.refresh(s)
    assert len(t.guesses) == 3 and all(0 < g.p <= 1 for g in t.guesses)


def test_learned_models_background_and_signature(tmp_path):
    calls = []

    def build():
        calls.append(1)
        time.sleep(0.05)
        m = MovePredictor()
        m.n_samples = 5
        return m

    lm = LearnedModels(tmp_path, build=build)
    assert not lm.refresh() and lm.predictor is None          # log байхгүй
    (tmp_path / "a.jsonl").write_text("{}", encoding="utf-8")
    assert lm.refresh()
    lm.wait()
    assert lm.predictor is not None and len(calls) == 1
    assert not lm.refresh()                                     # log өөрчлөгдөөгүй
    (tmp_path / "b.jsonl").write_text("{}", encoding="utf-8")
    assert lm.refresh()
    lm.wait()
    assert len(calls) == 2


def test_learned_models_survive_bad_logs(tmp_path):
    (tmp_path / "x.jsonl").write_text("not json\n", encoding="utf-8")

    def broken():
        raise ValueError("эвдэрсэн")

    lm = LearnedModels(tmp_path, build=broken)
    lm.refresh()
    lm.wait()
    assert lm.predictor is None and "эвдэрсэн" in lm.error


def test_learned_models_from_real_logs(tmp_path):
    from bots import HERO_BOTS, play_match
    from game.boss_driver import PlaceholderBoss
    from learning import GameLogger
    lg = GameLogger(tmp_path, human_side=HEROES)
    play_match(HERO_BOTS["greedy"](seed=0), PlaceholderBoss(seed=0), logger=lg)
    lm = LearnedModels(tmp_path)
    assert lm.refresh()
    lm.wait(30)
    assert lm.predictor is not None and lm.predictor.n_samples > 0


@pytest.fixture
def app(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    from game.boss_driver import PlaceholderBoss
    from game.campaign import Campaign
    from game.session import GameSession
    from game.settings import Settings

    class Ready:
        predictor = FixedPredictor()

        def refresh(self):
            self.refreshed = True

    a = App(GameSession(), boss=PlaceholderBoss(seed=0), boss_step_delay=0.0,
            start_screen="menu", campaign=Campaign(), settings=Settings(), learned=Ready())
    yield a
    pygame.quit()


def test_app_shows_prediction_and_counts(app):
    app.start_game()
    assert app.tracker is not None and len(app.tracker.guesses) == 3
    knight = app.state.units["knight"]
    app.play(Action("knight", knight.pos))                       # хүлээх = таамагтай таарна
    assert app.tracker.total == 1 and app.tracker.hits == 1
    assert "knight" not in [g.uid for g in app.tracker.guesses]
    app.draw()
    app.go_menu()
    assert app.learned.refreshed


def test_app_without_learned_has_no_tracker(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    from game.boss_driver import PlaceholderBoss
    from game.campaign import Campaign
    from game.settings import Settings
    a = App(boss=PlaceholderBoss(seed=0), start_screen="game", campaign=Campaign(),
            settings=Settings())
    a.start_game()
    assert a.tracker is None
    a.draw()
    pygame.quit()
