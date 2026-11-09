"""Pygame App-ийн smoke тест: дэлгэцгүй (SDL dummy driver) ажиллана."""

import time

import pytest

pygame = pytest.importorskip("pygame")

from engine import DEMONS, HEROES  # noqa: E402
from game import layout  # noqa: E402


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    from game.boss_driver import PlaceholderBoss
    from game.session import GameSession
    calls = []
    session = GameSession(on_action=lambda before, a, ev: calls.append(a))
    a = App(session, boss=PlaceholderBoss(seed=0), boss_step_delay=0.0, start_screen="game")
    a.hook_calls = calls
    yield a
    pygame.quit()


def click(app, pos, button=1):
    pos = (int(pos[0]), int(pos[1]))
    app.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
    app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button))


def run_until(app, cond, limit=600, dt=0.05):
    for _ in range(limit):
        app.step(dt)
        if cond():
            return True
        time.sleep(0.001)   # боссын thread-д цаг өгнө
    return False


def test_move_hero_with_mouse(app):
    knight = app.state.units["knight"]
    start = knight.pos
    dest = (start[0], start[1] - 3)
    click(app, layout.cell_center(start))
    assert app.selection.unit_uid == "knight"
    app.step(0.016)
    click(app, layout.cell_center(dest))
    assert knight.pos == start and app.selection.dest == dest   # очих нүд сонгогдсон
    app.step(0.016)
    click(app, layout.cell_center(dest))
    assert knight.pos == dest and knight.acted
    assert app.anim.busy                              # гулсаж байна
    assert run_until(app, lambda: not app.anim.busy)
    assert app.hook_calls[-1].unit == "knight"


def test_input_ignored_while_animating(app):
    knight = app.state.units["knight"]
    dest = (knight.x, knight.y - 3)
    click(app, layout.cell_center(knight.pos))
    click(app, layout.cell_center(dest))
    click(app, layout.cell_center(dest))
    assert app.anim.busy
    mage = app.state.units["mage"]
    click(app, layout.cell_center(mage.pos))
    assert app.selection.unit_uid is None


def test_end_turn_button_then_boss_plays_in_thread(app):
    x, y, w, h = layout.BUTTONS["end_turn"]
    click(app, (x + w / 2, y + h / 2))
    assert app.state.side_to_act == DEMONS
    app.step(0.016)
    assert app.boss_phase == "thinking" and app.status_text().startswith("Босс бодож")
    assert run_until(app, lambda: app.state.side_to_act == HEROES or app.state.is_over)
    assert app.state.round == 2
    assert {a.unit for a in app.hook_calls} >= {"demon_lord"}   # боссын нүүдэл ч hook-оор
    assert run_until(app, lambda: not app.anim.busy)


def test_end_turn_right_after_boss_turn_still_lets_boss_think(app):
    """Регресс: боссын сүүлийн нүүдлийн дараах кадрт ээлж дуусгавал босс алгасагдаж байсан."""
    x, y, w, h = layout.BUTTONS["end_turn"]
    for _ in range(3):
        click(app, (x + w / 2, y + h / 2))
        assert app.state.side_to_act == DEMONS
        app.step(0.016)
        assert app.boss_phase == "thinking"
        assert run_until(app, lambda: app.state.side_to_act == HEROES or app.state.is_over)
        if app.state.is_over:
            break
        app.anim.clear()                    # анимаци дуусахыг хүлээлгүй шууд дарна


def test_wait_key_and_right_click_cancel(app):
    healer = app.state.units["healer"]
    click(app, layout.cell_center(healer.pos))
    click(app, layout.cell_center(healer.pos), button=3)
    assert app.selection.unit_uid is None
    click(app, layout.cell_center(healer.pos))
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w, mod=0, unicode="w",
                                        scancode=0))
    assert healer.acted and healer.pos == (5, 7)


def test_game_over_screen_and_restart(app):
    app.state.winner = HEROES
    app.draw()
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, mod=0, unicode="r",
                                        scancode=0))
    assert not app.state.is_over and app.state.round == 1


def test_frame_time_fits_60_fps(app):
    click(app, layout.cell_center(app.state.units["knight"].pos))   # тодруулгатай үед
    for _ in range(10):
        app.draw()
    t0 = time.perf_counter()
    n = 120
    for _ in range(n):
        app.step(1 / 60)
    per_frame = (time.perf_counter() - t0) / n
    assert per_frame < 1 / 60, f"{per_frame * 1000:.1f} ms/кадр"


def key(app, k):
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0))


def test_use_skill_with_hotkey_and_click(app):
    s = app.state
    s.units["knight"].x, s.units["knight"].y = (4, 3)
    click(app, layout.cell_center((4, 3)))
    click(app, layout.cell_center((4, 2)))
    key(app, pygame.K_1)                                  # Сэлэм
    assert app.selection.skill == "sword"
    app.hover = (4, 1)
    app.draw()                                            # урьдчилсан харагдац зурагдана
    click(app, layout.cell_center((4, 1)))
    assert s.units["demon_lord"].hp == 380
    assert any(f.kind == "skill" for f in app.anim.floats)
    assert app.anim.flashes
    assert app.hook_calls[-1].skill == "sword"


def test_skill_button_click_and_wall_rotate_with_wheel(app):
    s = app.state
    s.units["mage"].x, s.units["mage"].y = (4, 4)
    click(app, layout.cell_center((4, 4)))
    x, y, w, h = layout.SKILL_BUTTONS[1]                  # Мөсөн хана
    click(app, (x + w / 2, y + h / 2))
    assert app.selection.skill == "ice_wall"
    v = app.selection.variant
    app.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=False))
    assert app.selection.variant == 1 - v
    app.hover = (4, 5)
    app.draw()
    click(app, layout.cell_center((4, 5)))
    expected = {(4, 5), (4, 6)} if v == 0 else {(4, 5), (5, 5)}   # эргүүлсний дараах чиглэл
    assert set(s.walls) == expected


def test_right_click_steps_back(app):
    s = app.state
    s.units["knight"].x, s.units["knight"].y = (4, 3)
    click(app, layout.cell_center((4, 3)))
    click(app, layout.cell_center((4, 2)))
    key(app, pygame.K_2)
    for expected in ("taunt", None):
        assert app.selection.skill == expected
        click(app, layout.cell_center((0, 0)), button=3)
    assert app.selection.dest == (4, 3)
    click(app, layout.cell_center((0, 0)), button=3)
    assert app.selection.unit_uid is None


def test_status_badges_draw(app):
    s = app.state
    s.units["knight"].shield = 20
    s.units["mage"].cursed = 2
    s.units["demon_lord"].taunted_by, s.units["demon_lord"].taunt_turns = "knight", 2
    s.walls[(0, 4)] = 2
    app.hover = s.units["demon_lord"].pos
    app.draw()


# ---------------------------------------------------------------- цэс, самбар, үр дүн (11/29)

class FakeDecision:
    def __init__(self, actions, panel):
        self.actions = actions
        self._panel = panel

    def to_panel(self):
        return self._panel


class FakeAIBoss:
    """ai.BossAI-тай ижил интерфейс: decide() → actions + to_panel()."""
    panel = {"habits": ["Healer-т их найддаг (эдгээлт 8/тулаан)"],
             "options": [{"label": "Сүүдрийн үсрэлт → Хар дөл Mage-т", "score": 0.57,
                          "chosen": True},
                         {"label": "Тамын гал (Knight + Healer)", "score": 0.54, "chosen": False},
                         {"label": "Хар дөл Mage-т", "score": 0.53, "chosen": False}],
             "enraged": True, "random_pick": False, "ms": 1003, "mode": "mcts",
             "iterations": 4800}

    def decide(self, state):
        from game.boss_driver import PlaceholderBoss
        return FakeDecision(PlaceholderBoss(seed=0).decide(state).actions, dict(self.panel))


def make_app(monkeypatch, **kw):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from game.app import App
    kw.setdefault("boss_step_delay", 0.0)
    return App(**kw)


def test_menu_play_pause_and_back_to_menu(monkeypatch):
    from game.boss_driver import PlaceholderBoss
    app = make_app(monkeypatch, boss=PlaceholderBoss(seed=0))
    assert app.screen_name == "menu"
    app.draw()
    key(app, pygame.K_RETURN)                         # «Тоглох»
    assert app.screen_name == "game" and not app.paused
    key(app, pygame.K_ESCAPE)                         # сонголтгүй үед түр зогсоно
    assert app.paused
    app.draw()
    knight = app.state.units["knight"]
    click(app, layout.cell_center(knight.pos))
    assert app.selection.unit_uid is None             # түр зогссон үед талбар хаалттай
    for _ in range(3):
        key(app, pygame.K_DOWN)
    assert app.pause_menu.selected == "menu"
    key(app, pygame.K_RETURN)
    assert app.screen_name == "menu" and not app.paused
    pygame.quit()


def test_help_from_pause_returns_to_pause(monkeypatch):
    from game.boss_driver import PlaceholderBoss
    app = make_app(monkeypatch, boss=PlaceholderBoss(seed=0), start_screen="game")
    key(app, pygame.K_ESCAPE)
    app.pause_menu.index = 2                          # «Удирдлага»
    key(app, pygame.K_RETURN)
    assert app.screen_name == "help"
    app.draw()
    key(app, pygame.K_ESCAPE)
    assert app.screen_name == "game" and app.paused
    key(app, pygame.K_ESCAPE)
    assert not app.paused
    pygame.quit()


def test_tab_toggles_boss_panel_and_window_width(monkeypatch):
    from game.boss_driver import PlaceholderBoss
    app = make_app(monkeypatch, boss=PlaceholderBoss(seed=0), start_screen="game")
    assert app.show_boss_panel and app.screen.get_width() == layout.SCREEN_W_WIDE
    app.draw()
    key(app, pygame.K_TAB)
    assert not app.show_boss_panel and app.screen.get_width() == layout.SCREEN_W
    app.draw()
    key(app, pygame.K_TAB)
    assert app.screen.get_width() == layout.SCREEN_W_WIDE
    assert not app.ai_connected                       # түр босс → тайлбар харагдана
    pygame.quit()


def test_boss_panel_shows_ai_decision(monkeypatch):
    app = make_app(monkeypatch, boss=FakeAIBoss(), start_screen="game")
    assert app.ai_connected
    x, y, w, h = layout.BUTTONS["end_turn"]
    click(app, (x + w / 2, y + h / 2))
    app.step(0.016)
    assert app.boss_phase == "thinking"
    assert run_until(app, lambda: app.boss_panel is not None)
    assert app.boss_panel["options"][0]["chosen"] and app.boss_panel_round == 1
    app.draw()
    assert run_until(app, lambda: app.state.side_to_act == HEROES or app.state.is_over)
    pygame.quit()


def test_result_screen_after_game_over_and_play_again(monkeypatch):
    from engine import Action
    from game.boss_driver import PlaceholderBoss
    app = make_app(monkeypatch, boss=PlaceholderBoss(seed=0), start_screen="game")
    s = app.state
    s.units["knight"].x, s.units["knight"].y = (4, 2)
    s.units["demon_lord"].hp = 15
    app.play(Action("knight", (4, 2), "sword", (4, 1), "demon_lord"))
    assert app.state.winner == HEROES and app.stats.kills["knight"] == 1
    assert run_until(app, lambda: app.screen_name == "result")
    app.draw()
    key(app, pygame.K_RETURN)                         # «Дахин тоглох»
    assert app.screen_name == "game" and not app.state.is_over
    assert app.stats.kills["knight"] == 0
    pygame.quit()


def test_boss_mode_toggle_creates_boss_with_mode(monkeypatch):
    import game.app as app_mod
    from game.boss_driver import PlaceholderBoss
    monkeypatch.setattr(app_mod, "ai_available", lambda: True)
    modes = []

    def factory(mode):
        modes.append(mode)
        return PlaceholderBoss(seed=0)

    app = make_app(monkeypatch, boss_factory=factory)
    assert app.main_menu.items[1].enabled
    key(app, pygame.K_DOWN)
    key(app, pygame.K_RETURN)                         # «Босс: ...» → mcts
    assert app.boss_mode == "mcts" and "MCTS" in app.main_menu.items[1].label
    app.main_menu.index = 0
    key(app, pygame.K_RETURN)
    assert modes == ["eval", "mcts"]                  # эхлэхэд + шинэ тоглолтод
    pygame.quit()


def test_boss_mode_disabled_without_ai(monkeypatch):
    import game.app as app_mod
    from game.boss_driver import PlaceholderBoss
    monkeypatch.setattr(app_mod, "ai_available", lambda: False)
    app = make_app(monkeypatch, boss_factory=lambda mode: PlaceholderBoss(seed=0))
    assert not app.main_menu.items[1].enabled
    key(app, pygame.K_DOWN)
    assert app.main_menu.selected == "help"
    app.draw()
    pygame.quit()


# ---------------------------------------------------------------- sprite, дуу (11/29)

def test_sprites_load_and_fallback(app, tmp_path):
    from game.sprites import Sprites
    sp = app.sprites
    assert sp.ok and sp.unit("knight").get_size() == (48, 48)
    assert sp.unit("imp", dim=True) is not None and sp.wall is not None
    assert sp.floor(0, 0).get_size() == (layout.CELL, layout.CELL)
    missing = Sprites(48, layout.CELL, folder=tmp_path)          # хоосон хавтас
    assert not missing.ok and missing.unit("knight") is None and missing.floor(1, 1) is None
    from game.board_view import BoardView
    BoardView(app.text, missing).draw(app.screen, app.state, app.selection, app.anim, None, True)


def test_asset_dir_inside_pyinstaller_bundle(monkeypatch, tmp_path):
    import sys
    from game.sprites import asset_dir
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert asset_dir() == tmp_path / "game" / "assets"


def test_sound_player_safe_and_mute_key(app, tmp_path):
    from game.sound import SoundPlayer
    assert SoundPlayer(enabled=False).ok is False
    broken = SoundPlayer(folder=tmp_path)                          # файлгүй — алдаагүй чимээгүй
    assert not broken.ok
    broken.play("slash")
    assert app.sound.ok                                            # dummy audio driver дээр ачаална
    key(app, pygame.K_m)
    assert app.sound.muted and "Дуу унтраалттай" in app.status_text()
    app.sound.play("slash")                                        # muted — юу ч болохгүй
    key(app, pygame.K_m)
    assert not app.sound.muted


def test_ui_sounds_follow_selection(app, monkeypatch):
    played = []
    monkeypatch.setattr(app.sound, "play", played.append)
    s = app.state
    s.units["knight"].x, s.units["knight"].y = (4, 3)
    s.units["knight"].cooldowns["taunt"] = 2
    click(app, layout.cell_center((4, 3)))
    click(app, layout.cell_center((4, 2)))
    key(app, pygame.K_2)                                           # cooldown
    key(app, pygame.K_1)
    click(app, layout.cell_center((4, 1)))                         # Сэлэм
    assert played[:4] == ["select", "tick", "error", "tick"]
    assert "slash" in played and "step" in played
