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
    named = dict(layout.BUTTONS)
    named.update({f"skill:{i}": r for i, r in enumerate(layout.SKILL_BUTTONS)})
    for name, (x, y, w, h) in named.items():
        assert 0 <= x and x + w <= layout.SCREEN_W and 0 <= y and y + h <= layout.SCREEN_H
        assert layout.button_at((x + w // 2, y + h // 2)) == name
        assert layout.cell_at((x + w // 2, y + h // 2)) is None
    assert layout.button_at(layout.cell_center((0, 0))) is None
    last = layout.SKILL_BUTTONS[-1]
    assert last[1] + last[3] < layout.LOG_Y < layout.BUTTONS["wait"][1]


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
    assert sel.click(dest) is None and sel.dest == dest      # эхний дарлт: очих нүд
    assert s.units["knight"].pos == start                    # төлөв өөрчлөгдөөгүй
    assert sel.hover_action(dest) == Action("knight", dest)
    a = sel.click(dest)                                      # дахин дарлт: хөдлөх
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
    session.play(sel.confirm_move())
    assert session.state.units["knight"].acted
    assert not sel.select("knight")
    sel.click(session.state.units["knight"].pos)
    assert sel.unit_uid is None


def test_wait_keeps_position():
    session, sel = fresh()
    pos = session.state.units["healer"].pos
    assert sel.confirm_move() is None    # сонгоогүй үед юу ч болохгүй
    sel.select("healer")
    a = sel.confirm_move()
    assert a == Action("healer", pos)
    events = session.play(a)
    assert session.state.units["healer"].pos == pos
    assert not any(e["type"] == "move" for e in events)


def test_all_heroes_act_then_turn_passes_to_boss():
    session, sel = fresh()
    for uid in ("knight", "mage", "healer"):
        assert sel.select(uid)
        session.play(sel.confirm_move())
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
    session.play(sel.confirm_move())
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


def test_animator_skill_flashes():
    anim = Animator()
    s = GameState.new_game()
    anim.push([{"type": "skill", "unit": "mage", "skill": "fireball", "target": (3, 1),
                "target_uid": None},
               {"type": "wall", "src": "mage", "cells": [(0, 4), (1, 4)], "turns": 2}], s)
    assert len(anim.flashes[0].cells) == 9 and anim.flashes[0].kind == "harm"
    assert anim.flashes[1].kind == "wall"
    assert [f.kind for f in anim.floats] == ["skill"]
    anim.update(5)
    assert anim.flashes == [] and anim.floats == []


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


# ---------------------------------------------------------------- ур чадвар (11/20)

def knight_next_to_boss():
    """Knight (4,3), очих нүд (4,2) — Demon Lord (4,1)-тэй зэрэгцэнэ."""
    session, sel = fresh()
    place(session.state, knight=(4, 3))
    sel.select("knight")
    sel.stage((4, 2))
    return session, sel


def test_stage_then_confirm_with_button():
    session, sel = fresh()
    start = session.state.units["mage"].pos
    sel.select("mage")
    assert sel.stage((start[0], start[1] - 1))
    assert not sel.stage((0, 0))                     # хүрэхгүй нүд
    a = sel.confirm_move()
    assert a == Action("mage", (start[0], start[1] - 1)) and sel.unit_uid is None


def test_back_goes_one_step_at_a_time():
    session, sel = knight_next_to_boss()
    sel.arm("sword")
    sel.back()
    assert sel.skill is None and sel.dest == (4, 2)
    sel.back()
    assert sel.dest == (4, 3) and sel.unit_uid == "knight"
    sel.back()
    assert sel.unit_uid is None


def test_single_target_skill_from_destination():
    session, sel = knight_next_to_boss()
    assert sel.skill_status("sword") == "ready"
    assert sel.arm("sword") is None and sel.skill == "sword"
    assert sel.needs_target
    assert sel.target_cells == {(4, 1)}
    a = sel.click((4, 1))
    assert a == Action("knight", (4, 2), "sword", (4, 1), "demon_lord")
    events = session.play(a)
    assert any(e["type"] == "damage" and e["dst"] == "demon_lord" for e in events)


def test_skill_status_no_target_and_cooldown():
    session, sel = fresh()
    sel.select("knight")
    assert sel.skill_status("sword") == "no_target"    # эхлэх байрлалаас дайсан хол
    assert sel.arm("sword") is None and sel.skill is None
    session.state.units["knight"].cooldowns["taunt"] = 2
    assert sel.skill_status("taunt") == "cooldown"
    assert sel.arm("taunt") is None and sel.skill is None
    assert sel.arm("fireball") is None                 # өөр дүрийн ур чадвар


def test_no_target_skill_commits_on_second_press_or_dest_click():
    session, sel = knight_next_to_boss()
    assert sel.arm("taunt") is None
    assert not sel.needs_target and sel.target_cells == set()
    assert sel.armed_action() == Action("knight", (4, 2), "taunt")
    assert sel.preview(sel.armed_action())["demon_lord"].get("taunted")
    a = sel.arm("taunt")
    assert a == Action("knight", (4, 2), "taunt") and sel.unit_uid is None
    # дүрийн нүдэн дээр дарж баталгаажуулах
    session2, sel2 = knight_next_to_boss()
    sel2.arm_index(1)
    assert sel2.click((4, 2)) == Action("knight", (4, 2), "taunt")


def test_area_damage_targets_and_preview_use_engine():
    session, sel = fresh()
    s = session.state
    place(s, mage=(4, 4))
    sel.select("mage")
    sel.arm("fireball")
    assert (3, 1) in sel.target_cells
    a = sel.action_for_target((3, 1))
    fx = sel.preview(a)
    from engine import SKILLS
    power = SKILLS["fireball"].power                       # тэнцвэрийн утгаас хамааралгүй
    imp = s.units["imp1"]
    assert fx["demon_lord"]["hp"] == -power and fx["imp1"]["hp"] == -min(power, imp.hp)
    assert "imp2" not in fx and bool(fx["imp1"].get("dies")) == (power >= imp.hp)
    assert s.units["demon_lord"].hp == s.units["demon_lord"].max_hp   # жинхэнэ төлөв хөндөгдөөгүй
    assert sel.preview(a) is fx                             # cache


def test_preview_marks_deaths():
    session, sel = fresh()
    s = session.state
    place(s, knight=(2, 3))
    s.units["imp1"].hp = 15
    sel.select("knight")
    sel.stage((2, 2))
    sel.arm("sword")
    fx = sel.preview(sel.action_for_target((2, 1)))
    assert fx["imp1"] == {"hp": -15, "dies": True}


def test_ice_wall_variant_and_rotate():
    session, sel = fresh()
    place(session.state, mage=(4, 4))
    sel.select("mage")
    sel.arm("ice_wall")
    assert sel.action_for_target((4, 5)).variant == 0
    sel.rotate()
    assert sel.action_for_target((4, 5)).variant == 1
    sel.rotate()
    a = sel.action_for_target((7, 4))                       # хэвтээ бол талбайгаас гарна
    assert a is not None and a.variant == 1


def test_heal_self_at_destination():
    session, sel = fresh()
    s = session.state
    s.units["healer"].hp = 40
    sel.select("healer")
    sel.stage((5, 6))
    sel.arm("heal")
    assert (5, 6) in sel.target_cells
    a = sel.click((5, 6))
    assert a == Action("healer", (5, 6), "heal", (5, 6), "healer")
    session.play(a)
    assert s.units["healer"].hp == 75 and s.units["healer"].pos == (5, 6)


def test_restage_while_armed_keeps_or_drops_skill():
    session, sel = knight_next_to_boss()
    sel.arm("taunt")
    assert sel.click((4, 3)) is None                  # өөр нүд — taunt тэндээс ч хүрнэ
    assert sel.dest == (4, 3) and sel.skill == "taunt"
    sel.stage((4, 2))
    sel.arm_index(0)                                  # sword
    assert sel.click((4, 5)) is None                  # тэндээс сэлэм хүрэхгүй
    assert sel.dest == (4, 5) and sel.skill is None


def test_click_non_target_while_armed_only_disarms():
    session, sel = knight_next_to_boss()
    sel.arm("sword")
    assert sel.click((0, 0)) is None
    assert sel.skill is None and sel.unit_uid == "knight" and sel.dest == (4, 2)


def test_every_hero_skill_action_reachable_through_selection():
    """UI-аар engine-ийн бүх ур чадварын нүүдлийг хийж болохыг шалгана."""
    session, sel = fresh()
    s = session.state
    place(s, knight=(4, 3), mage=(3, 4), healer=(5, 4))
    s.units["mage"].hp = 30
    for uid in ("knight", "mage", "healer"):
        sel.select(uid)
        wanted = {a for a in unit_actions(s, s.units[uid]) if a.skill}
        got = set()
        for dest in sel.move_cells:
            sel.stage(dest)
            for sid in sel.skills:
                if sel.skill_status(sid) != "ready":
                    continue
                for variant in (0, 1):
                    sel.skill = None
                    sel.variant = variant
                    sel.arm(sid)
                    if sel.needs_target:
                        got.update(sel.action_for_target(c) for c in sel.target_cells)
                    else:
                        got.add(sel.armed_action())
        assert got == wanted, uid
        sel.clear()
