"""VFX тест: симуляци pygame-гүй, ур чадвар бүр эффект үүсгэнэ, cap баригдана, App smoke."""

import subprocess
import sys
import time

import pytest

from engine import SKILLS, GameState
from engine.constants import Skill
from game import layout
from game import vfx as V


def test_vfx_core_does_not_import_pygame():
    code = "import sys; import game.vfx; print('pygame' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def state():
    s = GameState.new_game()
    s.units["knight"].x, s.units["knight"].y = (4, 3)
    return s


def skill_ev(sid, target=(4, 2), uid="knight", target_uid=None):
    return {"type": "skill", "unit": uid, "skill": sid, "target": target, "target_uid": target_uid}


def run(v, secs=1.5, dt=1 / 60):
    for _ in range(int(secs / dt)):
        v.update(dt)


@pytest.mark.parametrize("sid", sorted(SKILLS))
def test_every_skill_makes_effect(sid):
    s = state()
    v = V.Vfx()
    v.push([skill_ev(sid, target=(4, 2) if SKILLS[sid].range else None)], s)
    assert v.count > 0
    run(v)
    assert v.count == 0                      # бүгд дуусна (≤ ~1 сек)


def test_drain_and_unknown_kind(monkeypatch):
    monkeypatch.setitem(SKILLS, "life_drain", Skill("life_drain", "Drain", "drain", range=3))
    monkeypatch.setitem(SKILLS, "weird", Skill("weird", "Weird", "no_such_kind", range=3))
    for sid in ("life_drain", "weird"):
        v = V.Vfx()
        v.push([skill_ev(sid)], state())
        assert v.count > 0
        run(v)
        assert v.count == 0
    v = V.Vfx()
    v.push([skill_ev("life_drain")], state())
    v.update(0.1)
    assert any(isinstance(e, V.Beam) for e in v.effects)


def test_leap_summon_wall_death_damage_events():
    s = state()
    for ev in ({"type": "move", "unit": "demon_lord", "from": (4, 1), "to": (4, 4), "leap": True},
               {"type": "wall", "src": "mage", "cells": [(1, 1), (2, 1)], "turns": 2},
               {"type": "summon", "src": "demon_lord", "spawned": [{"unit": "imp1", "pos": (3, 1)}]},
               {"type": "death", "unit": "knight"},
               {"type": "damage", "src": "mage", "dst": "knight", "amount": 5, "absorbed": 0,
                "hp": 1}):
        v = V.Vfx()
        v.push([ev], s)
        assert v.count > 0, ev
        run(v)
        assert v.count == 0, ev
    v = V.Vfx()
    v.push([{"type": "move", "unit": "knight", "from": (4, 3), "to": (4, 2), "leap": False}], s)
    assert v.count == 0


def test_projectile_reaches_target():
    s = state()
    v = V.Vfx()
    v.push([skill_ev("dark_flame", target=(4, 6))], s)
    proj = next(e for e in v.effects if isinstance(e, V.Projectile))
    run(v, V.PROJECTILE_TIME * 0.5)
    mid = proj.pos
    assert mid != proj.src and mid != proj.dst
    run(v, V.PROJECTILE_TIME)
    assert proj.arrived and proj.pos == pytest.approx(proj.dst)
    assert v.particles                         # цохилтын оч үлдсэн


def test_sparks_not_duplicated_when_skill_covers_target():
    s = state()
    v = V.Vfx()
    v.push([skill_ev("sword"), {"type": "damage", "src": "knight", "dst": "demon_lord",
                                "amount": 20, "absorbed": 0, "hp": 1}], s)
    n = len(v.effects)
    s.units["demon_lord"].x, s.units["demon_lord"].y = (4, 2)
    v2 = V.Vfx()
    v2.push([skill_ev("sword"), {"type": "damage", "src": "knight", "dst": "demon_lord",
                                 "amount": 20, "absorbed": 0, "hp": 1}], s)
    assert len(v2.effects) <= n


def test_particles_expire_and_cap_holds_in_burst():
    s = state()
    v = V.Vfx()
    sids = sorted(SKILLS)
    evs = [skill_ev(sids[i % len(sids)], target=(i % 8, (i * 3) % 8)) for i in range(50)]
    peak = 0
    v.push(evs, s)
    for _ in range(120):
        v.update(1 / 60)
        peak = max(peak, len(v.particles))
        assert len(v.particles) <= V.MAX_PARTICLES
        assert len(v.effects) <= V.MAX_EFFECTS
    assert peak > 100
    run(v, 2.0)
    assert v.count == 0


# ---------------------------------------------------------------- App smoke
pygame = pytest.importorskip("pygame")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    from game.boss_driver import PlaceholderBoss
    a = App(start_screen="game", sound=False, boss=PlaceholderBoss(seed=0), boss_step_delay=0.0)
    yield a
    pygame.quit()


def test_app_plays_skills_with_vfx(app):
    from engine import Action
    s = app.state
    s.units["knight"].x, s.units["knight"].y = (4, 2)
    s.units["mage"].x, s.units["mage"].y = (4, 5)
    app.play(Action("knight", (4, 2), skill="sword", target=(4, 1), target_uid="demon_lord"))
    assert app.vfx.count > 0
    app.play(Action("mage", (4, 5), skill="fireball", target=(4, 1)))
    for _ in range(60):
        app.step(1 / 60)
    assert app.vfx.count < 400


def test_app_heavy_burst_frame_time(app):
    s = app.state
    sids = sorted(SKILLS)
    evs = [skill_ev(sids[i % len(sids)], target=(i % 8, (i * 3) % 8), uid="knight")
           for i in range(30)]
    app.vfx.push(evs, s)
    for _ in range(5):
        app.draw()
    t0 = time.perf_counter()
    n = 60
    for _ in range(n):
        app.step(1 / 60)
    per = (time.perf_counter() - t0) / n
    print(f"burst frame: {per * 1000:.2f} ms")
    assert per < 1 / 60
