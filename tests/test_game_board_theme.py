"""Сэдэвт талбар, Dungeon sprite-ийн тест: дэлгэцгүй (SDL dummy driver) ажиллана."""

import pytest

pygame = pytest.importorskip("pygame")

from engine import dungeon  # noqa: E402
from engine.constants import UNIT_TYPES  # noqa: E402
from game import layout as L  # noqa: E402
from game import theme as T  # noqa: E402


@pytest.fixture
def gfx(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((L.SCREEN_W, L.SCREEN_H))
    yield screen
    pygame.quit()


@pytest.fixture
def sprites(gfx):
    from game.sprites import Sprites
    return Sprites(56, L.CELL)


def test_manifest_loads(sprites):
    d = sprites.dungeon
    assert d.ok
    assert set(UNIT_TYPES) <= set(d.units)
    assert d.units["knight"].get_size() == (64, 64)


def test_every_unit_kind_has_sprite_or_fallback(sprites):
    for kind in UNIT_TYPES:
        assert sprites.dungeon_unit(kind) is not None or sprites.dungeon_unit(kind, dim=True) is None
        assert isinstance(T.unit_color(kind), tuple)
        assert T.unit_letter(kind)
    assert T.unit_color("nonexistent") and T.unit_letter("nonexistent") == "N"


def test_every_theme_loads(sprites):
    for floor in dungeon.FLOORS:
        tiles = sprites.theme(floor.theme)
        assert tiles is not None, floor.theme
        assert tiles.floors and tiles.wall is not None and tiles.obstacles and tiles.torch is not None
        assert tiles.floors[0].get_size() == (L.CELL, L.CELL)
    assert sprites.theme("nope") is None and sprites.theme(None) is None


def test_slime_tinted_green(sprites):
    img = sprites.dungeon.unit("slime")
    n = g = b = 0
    for x in range(img.get_width()):
        for y in range(img.get_height()):
            r_, g_, b_, a = img.get_at((x, y))
            if a > 200:
                n += 1
                g += g_
                b += b_
    assert n > 0 and g > b       # ногоон өнгө давамгайлна (анхны желе цэнхэр)


def test_missing_folder_fallback(gfx, tmp_path):
    from game.board_view import BoardView
    from game.sprites import Sprites
    sp = Sprites(56, L.CELL, folder=tmp_path / "a", dungeon_folder=tmp_path / "b")
    assert not sp.ok and not sp.dungeon.ok
    assert sp.dungeon_unit("knight") is None and sp.theme("slime") is None
    view = BoardView(T.Text(), sp)
    view.set_theme("slime")              # сэдэв олдохгүй → хуучин харагдац, унахгүй
    assert view._theme_name is None


def test_board_draws_every_floor(gfx, sprites):
    from game.anim import Animator
    from game.board_view import BoardView
    from game.input import Selection
    from game.session import GameSession
    view = BoardView(T.Text(), sprites)
    for fi, floor in enumerate(dungeon.FLOORS, 1):
        view.set_theme(floor.theme)
        for idx in range(1, len(floor.stages) + 1):
            session = GameSession()
            session.state = dungeon.new_stage_state(dungeon.get_stage(fi, idx))
            sel = Selection(session, side=session.human_side)
            sel.select("knight")
            view.draw(gfx, session.state, sel, Animator(), (3, 3), True, t=1.25)
    view.set_theme(None)
    view.draw(gfx, session.state, sel, Animator(), None, True)


def test_unknown_unit_kind_draws(gfx, sprites):
    from game.board_view import BoardView
    view = BoardView(T.Text(), sprites)
    view._draw_unit_box(gfx, "mystery", "mystery1", (100, 100), 0.5, acted=False)
    view._draw_unit_box(gfx, "mystery", "mystery1", (100, 100), 0.5, acted=True, alpha=0.5)
