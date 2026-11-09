"""learning/profile.py — log-оос зуршлын профайл, bots/ — скриптэй тоглогчид."""

import argparse
import json
import subprocess
import sys

import pytest

from bots import HERO_BOTS, play_match
from engine import HEROES, GameState, is_legal
from game.boss_driver import PlaceholderBoss
from learning import GameLogger, iter_logs, read_log, replay_check
from learning.profile import (DEFAULT_PRIORITY, build_profile, load_profile, main,
                              profile_from_logs, save_profile)


def bot_logs(tmp_path, name, games=3):
    folder = tmp_path / name
    logger = GameLogger(folder)
    for seed in range(games):
        play_match(HERO_BOTS[name](seed=seed), PlaceholderBoss(seed=seed), logger=logger)
    return folder


# ---------------------------------------------------------------- bots

def test_bots_choose_legal_actions_and_finish():
    for name, cls in HERO_BOTS.items():
        bot = cls(seed=0)
        s = GameState.new_game()
        a = bot.choose(s)
        assert a.is_end_turn or is_legal(s, a), name
        r = play_match(bot, PlaceholderBoss(seed=0))
        assert r.winner in ("heroes", "demons", "draw") and r.actions > 0, name


def test_play_match_is_deterministic_and_logs_replay(tmp_path):
    r1 = play_match(HERO_BOTS["greedy"](seed=4), PlaceholderBoss(seed=4))
    logger = GameLogger(tmp_path)
    r2 = play_match(HERO_BOTS["greedy"](seed=4), PlaceholderBoss(seed=4), logger=logger,
                    meta={"exp": "test"})
    assert (r1.winner, r1.rounds, r1.boss_hp, r1.actions) == \
        (r2.winner, r2.rounds, r2.boss_hp, r2.actions)
    recs = read_log(r2.log_path)
    assert recs[0]["meta"] == {"bot": "greedy", "exp": "test"}
    assert recs[-1]["reason"] == "game_over" and replay_check(recs)


def test_bots_and_learning_do_not_import_pygame():
    code = "import sys, bots, learning.profile; print('pygame' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# ---------------------------------------------------------------- профайл

def test_empty_logs_give_default_profile(tmp_path):
    prof = profile_from_logs(tmp_path / "none")
    assert prof["target_priority"] == DEFAULT_PRIORITY and prof["habits"] == []
    assert prof["stats"]["games"] == 0 and prof["version"] == 1
    json.dumps(prof)


def test_profiles_differ_by_play_style(tmp_path):
    mage = profile_from_logs(bot_logs(tmp_path, "mage_reliant"))
    healer = profile_from_logs(bot_logs(tmp_path, "healer_reliant"))
    cautious = profile_from_logs(bot_logs(tmp_path, "cautious"))
    assert mage["stats"]["games"] == 3
    assert mage["target_priority"]["mage"] > DEFAULT_PRIORITY["mage"]
    assert any(h.startswith("Mage алсаас довтолдог") for h in mage["habits"])
    assert "Healer Knight-ийн ард нуугддаг" in healer["habits"]
    assert "Healer Knight-ийн ард нуугддаг" not in mage["habits"]
    assert any(h.startswith("Taunt-ийг байнга") for h in cautious["habits"])
    for prof in (mage, healer, cautious):
        assert set(prof["target_priority"]) == {"knight", "mage", "healer"}
        assert all(0.5 <= v <= 2.5 for v in prof["target_priority"].values())
        assert len(prof["habits"]) <= 4


def test_little_data_stays_near_default(tmp_path):
    folder = bot_logs(tmp_path, "random", games=1)
    _, recs = next(iter_logs(folder))
    head = [r for r in recs if r["type"] != "action"][:1]
    humans = [r for r in recs if r["type"] == "action" and r["actor"] == "human"][:8]
    prof = build_profile([head + humans])
    for k, base in DEFAULT_PRIORITY.items():
        assert abs(prof["target_priority"][k] - base) <= 0.2 * base
    too_short = build_profile([head + humans[:3]])                  # MIN_HUMAN_ACTIONS-аас цөөн
    assert too_short["stats"]["games"] == 0 and too_short["habits"] == []


def test_shield_counts_absorbed_damage_from_boss_turn():
    state = GameState.new_game().to_dict()
    act = {"unit": "healer", "dest": [5, 7], "skill": "shield", "target": [3, 6],
           "target_uid": "knight", "variant": 0, "leap": False}
    wait = {"unit": "mage", "dest": [2, 7], "skill": None, "target": None, "target_uid": None,
            "variant": 0, "leap": False}
    recs = [{"type": "start", "human_side": HEROES}]
    recs += [{"type": "action", "actor": "human", "state": state, "action": act,
              "events": [{"type": "shield", "src": "healer", "dst": "knight", "amount": 20}]}]
    recs += [{"type": "action", "actor": "human", "state": state, "action": wait, "events": []}] * 5
    recs += [{"type": "action", "actor": "boss", "state": state, "action": wait,
              "events": [{"type": "damage", "src": "demon_lord", "dst": "knight", "amount": 10,
                          "absorbed": 20, "hp": 110}]}]
    prof = build_profile([recs])
    assert prof["stats"]["contribution"]["healer"] == 1.0           # зөвхөн шингээсэн 20
    assert prof["target_priority"]["healer"] > DEFAULT_PRIORITY["healer"]


def test_save_load_and_cli(tmp_path, capsys):
    folder = bot_logs(tmp_path, "aggressive", games=2)
    prof = profile_from_logs(folder)
    path = save_profile(prof, tmp_path / "out" / "p.json")
    assert load_profile(path) == prof
    assert load_profile(tmp_path / "missing.json") is None
    assert main([str(folder)]) == 0
    assert load_profile(folder / "profile.json")["target_priority"] == prof["target_priority"]
    assert "тулаан" in capsys.readouterr().out


def test_game_current_profile_modes(tmp_path):
    pytest.importorskip("pygame")
    from game.app import current_profile
    ns = lambda profile, log_dir: argparse.Namespace(profile=profile, log_dir=str(log_dir))  # noqa
    assert current_profile(ns("none", tmp_path)) is None
    assert current_profile(ns("auto", tmp_path / "empty")) is None    # log байхгүй — суралцаагүй
    folder = bot_logs(tmp_path, "cautious", games=2)
    prof = current_profile(ns("auto", folder))
    assert prof["stats"]["games"] == 2 and (folder / "profile.json").is_file()
    assert current_profile(ns(str(folder / "profile.json"), tmp_path)) == prof


def test_boss_ai_accepts_profile():
    ai = pytest.importorskip("ai")                                   # ai/ main-д орсны дараа
    prof = {"target_priority": {"knight": 0.8, "mage": 1.2, "healer": 2.0},
            "habits": ["Healer-т их найддаг"]}
    boss = ai.BossAI(profile=prof, mode="eval", seed=0)
    s = GameState.new_game()
    from engine import END_TURN, apply
    apply(s, END_TURN)
    panel = boss.decide(s).to_panel()
    assert panel["habits"] == ["Healer-т их найддаг"]
    assert boss.priority["healer"] == 2.0
