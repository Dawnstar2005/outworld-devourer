"""game/dungeon_map.py: газрын зургийн байршил, сонголт (pygame-гүй)."""

import random

import pytest

from engine.dungeon import FLOORS, HERO_UIDS
from game import dungeon_map as M
from game import layout as L
from game.campaign import STAGE_KEYS, Campaign

WIDTHS = [L.SCREEN_W, L.SCREEN_W_WIDE]


@pytest.fixture
def dm(tmp_path):
    return M.DungeonMap(Campaign.load(tmp_path / "s.json", rng=random.Random(0)))


@pytest.mark.parametrize("w", WIDTHS)
def test_nodes_inside_their_floor_and_hit_testable(w):
    centers = set()
    for key in STAGE_KEYS:
        c = M.node_center(key, w)
        x, y, fw, fh = M.floor_rect(int(key.split("-")[0]), w)
        assert x < c[0] < x + fw and y < c[1] < y + fh
        assert M.node_at(c, w) == key
        centers.add(c)
    assert len(centers) == len(STAGE_KEYS)
    side = M.side_x(w)
    assert all(M.node_center(k, w)[0] + M.BOSS_R < side for k in STAGE_KEYS)


@pytest.mark.parametrize("w", WIDTHS)
def test_side_panel_fits_window(w):
    for name, (x, y, bw, bh) in M.map_buttons(w).items():
        assert 0 <= x and x + bw <= w and y + bh <= L.SCREEN_H, name
    assert M.stage_info_y() < M.map_buttons(w)["start"][1] - 120
    for hi in range(len(HERO_UIDS)):
        assert M.hero_row_rect(hi, w)[1] + M.HERO_ROW_H <= M.bag_y() + 6


def test_snake_path_alternates_direction():
    w = L.SCREEN_W
    for f in FLOORS:
        xs = [M.node_center(f"{f.index}-{i}", w)[0] for i in range(1, 5)]
        assert xs == sorted(xs, reverse=f.index % 2 == 0)


def test_locked_stage_cannot_be_selected(dm):
    assert dm.selected == "1-1"
    assert not dm.select("1-3") and dm.selected == "1-1" and dm.message


def test_arrow_moves_only_to_unlocked(dm):
    w = L.SCREEN_W
    assert not dm.move(1, 0, w)                  # 1-2 түгжээтэй
    for k in STAGE_KEYS[:3]:
        dm.campaign.finish_stage(k, True, 5)
    assert dm.move(1, 0, w) and dm.selected == "1-2"
    assert dm.move(1, 0, w) and dm.selected == "1-3"
    assert dm.move(1, 0, w) and dm.selected == "1-4"
    assert dm.move(-1, 0, w) and dm.selected == "1-3"


def test_bag_to_hero_equip_flow(dm):
    dm.campaign.data["bag"] = ["sharp_edge", "life_heart"]
    assert not dm.click_hero("mage")             # цүнхнээс юу ч сонгоогүй
    dm.click_bag(1)
    assert dm.bag_pick == 1
    assert dm.click_hero("mage") and dm.campaign.items("mage") == ["life_heart"]
    assert dm.bag_pick is None and dm.campaign.bag == ["sharp_edge"]
    assert dm.click_item("mage", 0) and dm.campaign.bag == ["sharp_edge", "life_heart"]


def test_hit_identifies_regions(dm):
    w = L.SCREEN_W_WIDE
    x, y, bw, bh = M.map_buttons(w)["start"]
    assert dm.hit((x + 5, y + 5), w) == ("button", "start")
    assert dm.hit(M.node_center("2-3", w), w) == ("node", "2-3")
    bx, by, _, _ = M.bag_rect(0, w)
    assert dm.hit((bx + 3, by + 3), w) == ("bag", 0)
    ix, iy, _, _ = M.hero_item_rect(1, 2, w)
    assert dm.hit((ix + 3, iy + 3), w) == ("item", "mage", 2)
    hx, hy, _, _ = M.hero_row_rect(2, w)
    assert dm.hit((hx + 3, hy + 3), w) == ("hero", "healer")


def test_reset_needs_two_presses(dm):
    dm.campaign.finish_stage("1-1", True, 5)
    assert not dm.press_reset() and dm.campaign.is_cleared("1-1")
    dm.update(M.RESET_CONFIRM_SECS + 0.1)
    assert not dm.press_reset()                  # хугацаа дууссан тул дахин асууна
    assert dm.press_reset() and not dm.campaign.is_cleared("1-1")


def test_reward_drop_buttons_fit():
    for w in WIDTHS:
        rects = M.reward_drop_buttons(w, 300)
        assert set(rects) == set(HERO_UIDS) | {"bag"}
        assert all(0 <= r[0] and r[0] + r[2] <= w for r in rects.values())
