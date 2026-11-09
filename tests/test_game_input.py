"""game/-ийн pygame-гүй хэсгийн тест: сонголт, session hook, боссын thread, layout, анимаци."""

import json
import subprocess
import sys
import threading
import time

import pytest

from engine import (DEMONS, END_TURN, HEROES, Action, GameState, apply, is_legal,
                    unit_actions)
from game import layout
from game.anim import Animator
from game.boss_driver import BossDriver, PlaceholderBoss, PlaceholderDecision, make_boss
from game.input import Selection
from game.labels import event_text, unit_name
from game.session import GameSession


def place(s, **pos):
    for uid, p in pos.items():
        s.units[uid].x, s.units[uid].y = p


def fresh():
    session = GameSession()
    return session, Selection(session)


# ---------------------------------------------------------------- pygame-гүй

def test_logic_modules_do_not_import_pygame():
    code = ("import sys; import game.input, game.session, game.boss_driver, game.anim, "
            "game.labels, game.layout; print('pygame' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# ---------------------------------------------------------------- layout

def test_layout_cell_roundtrip_and_outside():
    for x in range(8):
        for y in range(8):
            assert layout.cell_at(layout.cell_center((x, y))) == (x, y)
            rx, ry, w, h = layout.cell_rect((x, y))
            assert layout.cell_at((rx, ry)) == (x, y)
            assert layout.cell_at((rx + w - 1, ry + h - 1)) == (x, y)
    assert layout.cell_at((layout.BOARD_X - 1, layout.BOARD_Y)) is None
    assert layout.cell_at((layout.BOARD_X + layout.BOARD_PX_W, layout.BOARD_Y)) is None
    assert layout.cell_at((layout.BOARD_X, layout.BOARD_Y + layout.BOARD_PX_H)) is None


def test_buttons_inside_screen_and_hit_test():
    for name, (x, y, w, h) in layout.BUTTONS.items():
        assert 0 <= x and x + w <= layout.SCREEN_W and 0 <= y and y + h <= layout.SCREEN_H
        assert layout.button_at((x + w // 2, y + h // 2)) == name
        assert layout.cell_at((x + w // 2, y + h // 2)) is None
    assert layout.button_at(layout.cell_center((0, 0))) is None


# ---------------------------------------------------------------- сонголт

def test_select_hero_uses_engine_moves():
    session, sel = fresh()
    knight = session.state.units["knight"]
    assert sel.click(knight.pos) is None
    assert sel.unit_uid == "knight"
    assert sel.move_cells == {a.dest for a in unit_actions(session.state, knight)}
    assert knight.pos in sel.move_cells


def test_cannot_select_demons_or_on_demon_turn():
    session, sel = fresh()
    assert sel.click(session.state.units["demon_lord"].pos) is None
    assert sel.unit_uid is None
    session.play(END_TURN)
    assert session.state.side_to_act == DEMONS
    assert sel.click(session.state.units["knight"].pos) is None
    assert sel.unit_uid is None
    assert sel.end_turn() is None


def test_click_reachable_cell_moves_hero():
    session, sel = fresh()
    s = session.state
    start = s.units["knight"].pos
    sel.click(start)
    dest = (start[0], start[1] - 2)
    assert dest in sel.move_cells
    a = sel.click(dest)
    assert a == Action("knight", dest)
    assert is_legal(s, a)
    assert sel.unit_uid is None
    events = session.play(a)
    assert s.units["knight"].pos == dest and s.units["knight"].acted
    assert events[0] == {"type": "move", "unit": "knight", "from": start, "to": dest,
                         "leap": False}


def test_click_unreachable_or_self_cancels():
    session, sel = fresh()
    knight = session.state.units["knight"]
    sel.click(knight.pos)
    assert (0, 0) not in sel.move_cells
    assert sel.click((0, 0)) is None and sel.unit_uid is None
    sel.click(knight.pos)
    assert sel.click(knight.pos) is None and sel.unit_uid is None


def test_click_other_hero_switches_selection():
    session, sel = fresh()
    sel.click(session.state.units["knight"].pos)
    assert sel.click(session.state.units["mage"].pos) is None
    assert sel.unit_uid == "mage"


def test_acted_hero_not_selectable():
    session, sel = fresh()
    sel.select("knight")
    session.play(sel.wait())
    assert session.state.units["knight"].acted
    assert not sel.select("knight")
    sel.click(session.state.units["knight"].pos)
    assert sel.unit_uid is None


def test_wait_keeps_position():
    session, sel = fresh()
    pos = session.state.units["healer"].pos
    assert sel.wait() is None            # сонгоогүй үед юу ч болохгүй
    sel.select("healer")
    a = sel.wait()
    assert a == Action("healer", pos)
    events = session.play(a)
    assert session.state.units["healer"].pos == pos
    assert not any(e["type"] == "move" for e in events)


def test_all_heroes_act_then_turn_passes_to_boss():
    session, sel = fresh()
    for uid in ("knight", "mage", "healer"):
        assert sel.select(uid)
        session.play(sel.wait())
    assert session.state.side_to_act == DEMONS
    assert not session.human_to_act


def test_end_turn_button():
    session, sel = fresh()
    sel.select("knight")
    a = sel.end_turn()
    assert a == END_TURN and sel.unit_uid is None
    session.play(a)
    assert session.state.side_to_act == DEMONS


def test_skill_actions_at_destination():
    session, sel = fresh()
    s = session.state
    place(s, knight=(4, 3))               # demon_lord (4,1)-ээс 2 алхам
    sel.select("knight")
    skills = sel.skill_actions_at((4, 2))
    assert skills and all(a.dest == (4, 2) for a in skills)
    assert any(a.skill == "sword" and a.target_uid == "demon_lord" for a in skills)
    assert all(a.dest == (4, 2) for a in sel.actions_at((4, 2)))
    assert sel.move_action((4, 2)) == Action("knight", (4, 2))


def test_refresh_clears_dead_or_acted_selection():
    session, sel = fresh()
    sel.select("mage")
    session.play(Action("mage", session.state.units["mage"].pos))
    sel.refresh()
    assert sel.unit_uid is None


def test_selection_follows_session_reset():
    session, sel = fresh()
    sel.select("knight")
    session.play(sel.wait())
    session.reset()
    assert sel.select("knight")


# ---------------------------------------------------------------- on_action hook

def test_on_action_hook_gets_state_before_action_events():
    calls = []
    session = GameSession(on_action=lambda before, a, ev: calls.append((before, a, ev)))
    start = session.state.units["knight"].pos
    dest = (start[0] + 1, start[1])
    events = session.play(Action("knight", dest))
    assert len(calls) == 1
    before, a, ev = calls[0]
    assert before.units["knight"].pos == start and not before.units["knight"].acted
    assert session.state.units["knight"].pos == dest
    assert a == Action("knight", dest) and ev is events
    json.dumps({"state": before.to_dict(), "action": a.to_dict()})   # DQ log-д бичигдэнэ
    session.play(END_TURN)
    assert calls[-1][1] == END_TURN


def test_illegal_action_does_not_call_hook():
    calls = []
    session = GameSession(on_action=lambda *args: calls.append(args))
    with pytest.raises(ValueError):
        session.play(Action("knight", (0, 0)))
    with pytest.raises(ValueError):
        session.play(Action("demon_lord", session.state.units["demon_lord"].pos))
    assert calls == []


def test_hook_error_does_not_break_game(capsys):
    def bad(*_):
        raise RuntimeError("log эвдэрсэн")
    session = GameSession(on_action=bad)
    session.play(END_TURN)
    assert session.state.side_to_act == DEMONS
    assert "log эвдэрсэн" in capsys.readouterr().err


# ---------------------------------------------------------------- босс

def test_placeholder_boss_plays_legal_full_turn():
    session = GameSession()
    seen = []
    session.add_hook(lambda before, a, ev: seen.append(a))
    session.play(END_TURN)
    boss = PlaceholderBoss(seed=1)
    for _ in range(10):                   # 10 round тоглуулна
        if session.state.is_over:
            break
        assert session.state.side_to_act == DEMONS
        d = boss.decide(session.state)
        assert d.to_panel() is None
        units = [a.unit for a in d.actions]
        assert len(units) == len(set(units))
        for a in d.actions:
            session.play(a)              # validate=True — хууль бус бол ValueError
        if not session.state.is_over and session.state.side_to_act == DEMONS:
            session.play(END_TURN)
        if not session.state.is_over:
            session.play(END_TURN)       # баатрууд алгасна
    assert any(a.unit == "demon_lord" for a in seen)


def test_placeholder_boss_does_not_touch_real_state():
    s = GameState.new_game()
    apply(s, END_TURN)
    snapshot = json.dumps(s.to_dict())
    PlaceholderBoss(seed=0).decide(s)
    assert json.dumps(s.to_dict()) == snapshot


def test_make_boss_falls_back_without_ai(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai", None)   # `import ai` → ModuleNotFoundError
    assert isinstance(make_boss(), PlaceholderBoss)


class SlowBoss:
    def __init__(self, delay):
        self.delay = delay
        self.release = threading.Event()

    def decide(self, state):
        self.release.wait(self.delay)
        return PlaceholderDecision([END_TURN])


def test_boss_driver_runs_in_background_thread():
    boss = SlowBoss(delay=5)
    driver = BossDriver(boss)
    s = GameState.new_game()
    t0 = time.perf_counter()
    driver.start(s)
    assert time.perf_counter() - t0 < 0.2      # UI thread хүлээхгүй
    assert driver.thinking and driver.poll() is None
    boss.release.set()
    for _ in range(200):
        d = driver.poll()
        if d is not None:
            break
        time.sleep(0.01)
    assert d is not None and d.actions == [END_TURN]
    assert not driver.thinking and driver.poll() is None


def test_boss_driver_cancel_discards_stale_result():
    boss = SlowBoss(delay=5)
    driver = BossDriver(boss)
    driver.start(GameState.new_game())
    driver.cancel()
    boss.release.set()
    time.sleep(0.1)
    assert driver.poll() is None and not driver.thinking


def test_boss_driver_reraises_errors():
    class Broken:
        def decide(self, state):
            raise RuntimeError("boom")
    driver = BossDriver(Broken())
    driver.start(GameState.new_game())
    with pytest.raises(RuntimeError):
        for _ in range(200):
            driver.poll()
            time.sleep(0.01)


# ---------------------------------------------------------------- анимаци, нэр

def test_animator_move_tween():
    anim = Animator()
    s = GameState.new_game()
    ev = {"type": "move", "unit": "knight", "from": (3, 6), "to": (3, 4), "leap": False}
    anim.push([ev], s)
    assert anim.busy
    assert anim.unit_center("knight", (3, 4)) == layout.cell_center((3, 6))
    anim.update(0.05)
    mid = anim.unit_center("knight", (3, 4))
    assert layout.cell_center((3, 4))[1] < mid[1] < layout.cell_center((3, 6))[1]
    anim.update(5)
    assert not anim.busy
    assert anim.unit_center("knight", (3, 4)) == layout.cell_center((3, 4))


def test_animator_floats_and_fades():
    anim = Animator()
    s = GameState.new_game()
    anim.push([{"type": "damage", "src": "knight", "dst": "imp1", "amount": 10, "absorbed": 0,
                "hp": 0}, {"type": "death", "unit": "imp1"}], s)
    assert [f.text for f in anim.floats] == ["-10"] and len(anim.fades) == 1
    assert not anim.busy                      # хөвөх тоо оролтыг хаахгүй
    anim.update(5)
    assert anim.floats == [] and anim.fades == []


def test_labels():
    s = GameState.new_game()
    assert unit_name("imp2", s) == "Imp 2" and unit_name("demon_lord", s) == "Demon Lord"
    text = event_text({"type": "damage", "src": "knight", "dst": "demon_lord", "amount": 20,
                       "absorbed": 0, "hp": 380}, s)
    assert "Demon Lord" in text and "-20" in text
    assert event_text({"type": "turn_end", "side": HEROES, "round": 1}, s) is None
    # бүх event төрөл алдаагүй текст болно
    s2 = GameState.new_game()
    apply(s2, END_TURN)
    for a in unit_actions(s2, s2.units["demon_lord"])[:40]:
        for ev in apply(s2.clone(), a):
            event_text(ev, s2)
