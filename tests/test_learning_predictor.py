"""learning/predictor.py — тоглогчийн дараагийн нүүдэл таамаглагч."""

import json
import random
import statistics
import subprocess
import sys
import time

import pytest

from bots import HERO_BOTS, play_match
from engine import END_TURN, Action, GameState, apply, unit_actions
from game.boss_driver import PlaceholderBoss
from learning import GameLogger, iter_logs
from learning.predictor import (HEUR_PRIOR, MovePredictor, class_key, evaluate_accuracy, main,
                                load_predictor, predictor_from_logs, save_predictor)


def place(s, **pos):
    for uid, p in pos.items():
        s.units[uid].x, s.units[uid].y = p


@pytest.fixture(scope="module")
def bot_games(tmp_path_factory):
    """healer_reliant ба aggressive bot-ын 8 тулааны log (түр босстой)."""
    out = {}
    for name in ("healer_reliant", "aggressive"):
        folder = tmp_path_factory.mktemp(name)
        logger = GameLogger(folder)
        for k in range(8):
            play_match(HERO_BOTS[name](seed=k), PlaceholderBoss(seed=k), logger=logger)
        out[name] = [r for _, r in iter_logs(folder)]
    return out


def test_predict_shape_sum_and_equal_split():
    s = GameState.new_game()
    acts = unit_actions(s, s.units["mage"])
    p = MovePredictor().predict(s, "mage", acts)
    assert len(p) == len(acts) and all(x >= 0 for x in p)
    assert abs(sum(p) - 1.0) < 1e-9
    by_class = {}
    for a, x in zip(acts, p):
        by_class.setdefault(class_key(a), set()).add(round(x, 12))
    assert all(len(v) == 1 for v in by_class.values())      # нэг ангид тэнцүү хуваана
    assert MovePredictor().predict(s, "mage", []) == []
    assert MovePredictor()(s, "mage", acts) == p              # BossAI-д дуудагдахуйц


def test_untrained_model_prefers_killing_blow():
    s = GameState.new_game()
    place(s, knight=(2, 3))
    s.units["imp1"].hp = 5
    top = MovePredictor().top_k(s, "knight", 3)
    assert top[0] == ("sword", "imp1")
    assert len(top) == len(set(top)) <= 3


def test_heal_targets_hurt_ally_and_skips_cursed():
    s = GameState.new_game()
    s.units["mage"].hp = 20
    probs = dict(MovePredictor().class_probs(s, "healer"))
    assert max(probs, key=probs.get) == ("heal", "mage")
    s.units["mage"].cursed = 2
    assert ("heal", "mage") not in dict(MovePredictor().class_probs(s, "healer"))


def test_trained_model_beats_chance_and_meets_top3(bot_games):
    for name, games in bot_games.items():
        train, test = games[:6], games[6:]
        model = MovePredictor().fit(train)
        acc = evaluate_accuracy(model, test)
        base = evaluate_accuracy(MovePredictor(), test)
        assert acc["n"] > 20
        assert acc["top3"] >= 0.6, name                       # PDF-ийн шалгуур
        assert acc["top1"] > acc["chance1"] + 0.15, name      # санамсаргүйгээс илт сайн
        assert acc["top1"] >= base["top1"] - 0.05, name       # heuristic-ээс муудахгүй
        assert model.n_samples > 50


def test_little_data_stays_close_to_heuristic(bot_games):
    games = bot_games["aggressive"]
    one = [[r for r in games[0] if r.get("type") != "action"]
           + [r for r in games[0] if r.get("actor") == "human"][:1]]
    model = MovePredictor().fit(one)
    assert model.n_samples == 1
    assert abs(model.heur_w - HEUR_PRIOR) < 0.5
    assert all(abs(v) < 0.5 for v in model.w.values())
    test = games[1:3]
    fresh = MovePredictor()
    agree = total = 0
    for state, uid, _ in MovePredictor.decisions(test):
        total += 1
        agree += model.top_k(state, uid, 1) == fresh.top_k(state, uid, 1)
    assert agree / total >= 0.9


def test_roundtrip_json_and_cli(bot_games, tmp_path):
    model = MovePredictor().fit(bot_games["healer_reliant"][:4])
    d = model.to_dict()
    json.dumps(d)
    again = MovePredictor.from_dict(json.loads(json.dumps(d)))
    s = GameState.new_game()
    s.units["knight"].hp = 30
    acts = unit_actions(s, s.units["healer"])
    assert again.predict(s, "healer", acts) == pytest.approx(model.predict(s, "healer", acts),
                                                               abs=1e-6)
    path = save_predictor(model, tmp_path / "p.json")
    assert load_predictor(path).n_samples == model.n_samples
    assert load_predictor(tmp_path / "missing.json") is None
    folder = tmp_path / "logs"
    logger = GameLogger(folder)
    play_match(HERO_BOTS["greedy"](seed=1), PlaceholderBoss(seed=1), logger=logger)
    play_match(HERO_BOTS["greedy"](seed=2), PlaceholderBoss(seed=2), logger=logger)
    assert predictor_from_logs(folder).n_samples > 0
    assert main([str(folder)]) == 0 and (folder / "predictor.json").is_file()


def test_predict_is_fast_enough(bot_games):
    """MCTS rollout-д: нэг дуудлага ≤ 0.2 мс (6 нүдний түүвэр, median)."""
    model = MovePredictor().fit(bot_games["aggressive"][:4])
    rng = random.Random(0)
    cases = []
    for state, uid, _ in MovePredictor.decisions(bot_games["aggressive"][4:]):
        acts = unit_actions(state, state.units[uid])
        dests = sorted({a.dest for a in acts})
        keep = set(rng.sample(dests, min(6, len(dests))))
        cases.append((state, uid, [a for a in acts if a.dest in keep]))
    times = []
    for i in range(2000):
        state, uid, cands = cases[i % len(cases)]
        t0 = time.perf_counter()
        model.predict(state, uid, cands)
        times.append(time.perf_counter() - t0)
    assert statistics.median(times) <= 0.0002


def test_decisions_skip_end_turn_and_boss():
    s = GameState.new_game()
    recs = [{"type": "action", "actor": "human", "state": s.to_dict(),
             "action": END_TURN.to_dict(), "events": []},
            {"type": "action", "actor": "boss", "state": s.to_dict(),
             "action": Action("knight", (3, 6)).to_dict(), "events": []},
            {"type": "action", "actor": "human", "state": s.to_dict(),
             "action": Action("knight", (3, 5)).to_dict(), "events": []}]
    got = list(MovePredictor.decisions([recs]))
    assert len(got) == 1 and got[0][1:] == ("knight", (None, None))


def test_predictor_does_not_import_pygame():
    code = "import sys, learning.predictor, experiments.predictor_eval; print('pygame' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_boss_ai_uses_predictor_in_mcts():
    ai = pytest.importorskip("ai")                             # ai/ main-д орсны дараа ажиллана
    calls = []
    model = MovePredictor()

    def counting(state, uid, actions):
        calls.append(len(actions))
        return model(state, uid, actions)

    s = GameState.new_game()
    apply(s, END_TURN)
    boss = ai.BossAI(mode="mcts", seed=0, max_iters=40, predictor=counting)
    d = boss.decide(s)
    assert d.actions and calls and all(n > 0 for n in calls)
