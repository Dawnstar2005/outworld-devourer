"""learning/log.py — тоглолтын log бичих, унших, дахин тоглуулах."""

import json
import random

import pytest

from engine import END_TURN, HEROES, legal_actions
from game.boss_driver import PlaceholderBoss
from game.session import GameSession
from learning import GameLogger, iter_logs, read_log, replay_check


def play_full_game(session, seed=0, max_steps=2000):
    """Баатрууд санамсаргүй (engine-ийн хууль ёсны нүүдлээс), босс PlaceholderBoss."""
    rng = random.Random(seed)
    boss = PlaceholderBoss(seed=seed)
    for _ in range(max_steps):
        s = session.state
        if s.is_over:
            return
        if s.side_to_act == HEROES:
            acts = [a for a in legal_actions(s) if not a.is_end_turn]
            session.play(rng.choice(acts) if acts else END_TURN)
        else:
            for a in boss.decide(s).actions:
                session.play(a)
            if not s.is_over and s.side_to_act != HEROES:
                session.play(END_TURN)
    raise AssertionError("тоглолт дуусаагүй")


def test_full_game_log_is_replayable(tmp_path):
    logger = GameLogger(tmp_path, meta={"boss": "placeholder"})
    session = GameSession(on_action=logger.on_action)
    logger.start(session.state)
    play_full_game(session, seed=3)
    assert not logger.active                          # game_over-оор өөрөө хаагдсан
    recs = read_log(logger.path)
    assert recs[0]["type"] == "start" and recs[0]["version"] == 1
    assert recs[0]["meta"] == {"boss": "placeholder"} and recs[0]["human_side"] == HEROES
    acts = [r for r in recs if r["type"] == "action"]
    assert [r["i"] for r in acts] == list(range(len(acts)))
    assert {r["actor"] for r in acts} == {"human", "boss"}
    assert all((r["actor"] == "human") == (r["side"] == HEROES) for r in acts)
    end = recs[-1]
    assert end["type"] == "end" and end["reason"] == "game_over"
    assert end["winner"] == session.state.winner and end["actions"] == len(acts)
    assert replay_check(recs)


def test_replay_check_detects_tampering(tmp_path):
    logger = GameLogger(tmp_path)
    session = GameSession(on_action=logger.on_action)
    play_full_game(session, seed=5)                    # start() дуудаагүй — автоматаар нээнэ
    recs = read_log(logger.path)
    hit = next(r for r in recs if r["type"] == "action" and
               any(e["type"] == "damage" for e in r["events"]))
    next(e for e in hit["events"] if e["type"] == "damage")["amount"] += 1
    assert not replay_check(recs)


def test_close_reasons_and_restart(tmp_path):
    logger = GameLogger(tmp_path)
    session = GameSession(on_action=logger.on_action)
    first = logger.start(session.state)
    session.play(END_TURN)
    second = logger.start(session.state)               # дуусаагүй тоглолт → "restart"
    assert first != second
    end = read_log(first)[-1]
    assert end == {"type": "end", "winner": None, "rounds": 1, "actions": 1,
                   "reason": "restart"}
    logger.close("menu")
    assert read_log(second)[-1]["reason"] == "menu" and not logger.active
    logger.close("quit")                               # дахин хаахад юу ч болохгүй
    assert read_log(second)[-1]["reason"] == "menu"


def test_read_log_skips_truncated_line_and_iter_filters(tmp_path):
    logger = GameLogger(tmp_path)
    session = GameSession(on_action=logger.on_action)
    play_full_game(session, seed=1)
    finished = logger.path
    logger.start(session.__class__().state)
    logger.on_action(GameSession().state, END_TURN, [{"type": "turn_end"}])
    unfinished = logger.path
    with open(unfinished, "a", encoding="utf-8") as f:
        f.write('{"type": "action", "i": 9')         # гэнэт хаагдсан мэт дутуу мөр
    recs = read_log(unfinished)
    assert recs[-1]["type"] == "action" and len(recs) == 2
    all_logs = [p for p, _ in iter_logs(tmp_path)]
    done = [p for p, _ in iter_logs(tmp_path, finished_only=True)]
    assert set(all_logs) == {finished, unfinished} and done == [finished]
    assert list(iter_logs(tmp_path / "missing")) == []


def test_log_lines_are_plain_json(tmp_path):
    logger = GameLogger(tmp_path)
    session = GameSession(on_action=logger.on_action)
    play_full_game(session, seed=2)
    with open(logger.path, encoding="utf-8") as f:
        for line in f:
            json.loads(line)                           # мөр бүр бие даасан JSON
    move = next(r for r in read_log(logger.path) if r["type"] == "action"
                for e in r["events"] if e["type"] == "move")
    ev = next(e for e in move["events"] if e["type"] == "move")
    assert isinstance(ev["from"], list) and isinstance(ev["to"], list)


def test_app_writes_one_log_per_game(monkeypatch, tmp_path):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from engine import Action
    from game.app import App
    logger = GameLogger(tmp_path)
    app = App(boss=PlaceholderBoss(seed=0), boss_step_delay=0.0, logger=logger, sound=False)
    app.start_game()
    knight = app.state.units["knight"]
    app.play(Action("knight", (knight.x, knight.y - 1)))
    app.start_game()                                   # Шинээр эхлэх → өмнөх нь "restart"
    app.go_menu()                                      # цэс → "menu"
    logs = list(iter_logs(tmp_path))
    assert len(logs) == 2
    (p1, r1), (p2, r2) = logs
    assert r1[0]["meta"] == {"boss": "placeholder"}
    assert [r["type"] for r in r1] == ["start", "action", "end"] and r1[-1]["reason"] == "restart"
    assert r2[-1]["reason"] == "menu"
    pygame.quit()


def test_learning_does_not_import_pygame():
    import subprocess
    import sys
    code = "import sys, learning; print('pygame' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_skip_menu_start_writes_boss_meta(monkeypatch, tmp_path):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    logger = GameLogger(tmp_path)
    app = App(boss=PlaceholderBoss(seed=0), logger=logger, sound=False, start_screen="game")
    assert logger.active and read_log(logger.path)[0]["meta"] == {"boss": "placeholder"}
    app.go_menu()
    pygame.quit()
