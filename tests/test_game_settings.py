"""game/settings.py ба game/options.py: тохиргоо, «Тохиргоо» дэлгэцийн логик (pygame-гүй)."""

import json

import pytest

from game import layout as L
from game import options as O
from game.settings import ENEMY_STEP_DELAY, SETTINGS_ENV, Settings, default_settings_path


def test_defaults_and_gains():
    s = Settings()
    assert (s.master, s.music, s.sfx, s.enemy_speed) == (80, 70, 80, "normal")
    assert s.music_gain == pytest.approx(0.56) and s.sfx_gain == pytest.approx(0.64)
    assert s.enemy_step_delay == ENEMY_STEP_DELAY["normal"]


def test_update_clamps_and_ignores_bad_values():
    s = Settings()
    s.update(master=137, music=-5, sfx=44, enemy_speed="warp", boss_panel="yes", nope=1)
    assert (s.master, s.music, s.sfx) == (100, 0, 40)
    assert s.enemy_speed == "normal" and s.boss_panel is True


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "a" / "settings.json"
    s = Settings.load(path)
    s.update(master=50, enemy_speed="fast", fullscreen=True)
    s.save()
    t = Settings.load(path)
    assert t.to_dict() == s.to_dict() and t.path == path
    assert json.loads(path.read_text(encoding="utf-8"))["master"] == 50


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2", encoding="utf-8")
    assert Settings.load(path).to_dict() == Settings().to_dict()


def test_path_none_never_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings()
    s.update(master=10)
    s.save()
    assert list(tmp_path.iterdir()) == []


def test_settings_path_env_and_default(monkeypatch, tmp_path):
    monkeypatch.setenv(SETTINGS_ENV, str(tmp_path / "x.json"))
    assert default_settings_path() == tmp_path / "x.json"
    monkeypatch.delenv(SETTINGS_ENV)
    monkeypatch.delenv("OUTWORLD_SAVE", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_settings_path() == tmp_path / "OutworldDevourer" / "settings.json"


def test_options_keyboard_adjust():
    s = Settings()
    m = O.OptionsMenu(s)
    assert m.row.key == "master"
    assert m.adjust(1) == "master" and s.master == 90
    assert m.adjust(1) == "master" and s.master == 100
    assert m.adjust(1) is None                       # дээд хязгаар
    m.move(3)
    assert m.row.key == "enemy_speed"
    assert m.adjust(1) == "enemy_speed" and s.enemy_speed == "fast"
    assert m.adjust(1) and s.enemy_speed == "slow"   # эргэлдэнэ
    m.move(1)
    assert m.activate() == "boss_panel" and s.boss_panel is False
    assert m.value_text(m.row) == "Унтраалттай"


def test_options_buttons():
    s = Settings()
    s.update(master=10, fullscreen=True)
    m = O.OptionsMenu(s)
    i_def = [r.key for r in O.ROWS].index("defaults")
    assert m.activate(i_def) == "defaults" and s.to_dict() == Settings().to_dict()
    assert m.activate([r.key for r in O.ROWS].index("back")) == "back"
    m.move(-1)
    assert m.row.key == "back"                        # эхнээс дээш → сүүлийнх


@pytest.mark.parametrize("w", [L.SCREEN_W, L.SCREEN_W_WIDE])
def test_options_layout_and_hit(w):
    s = Settings()
    m = O.OptionsMenu(s)
    for i, row in enumerate(O.ROWS):
        x, y, rw, rh = O.row_rect(i, w)
        assert 0 <= x and x + rw <= w and y + rh <= L.SCREEN_H - 40
        if row.kind == "slider":
            bx, by, bw, bh = O.slider_bar(i, w)
            assert m.hit((bx + 2, by + 2), w) == ("slider", i)
            assert m.set_slider_from_x(i, bx + bw, w) in (row.key, None)
            assert getattr(s, row.key) == 100
            m.set_slider_from_x(i, bx + bw * 0.31, w)
            assert getattr(s, row.key) == 30
            m.set_slider_from_x(i, bx - 50, w)
            assert getattr(s, row.key) == 0
        else:
            assert m.hit((x + 5, y + 5), w) == ("row", i)
    assert O.hint_y() < L.SCREEN_H - 40
