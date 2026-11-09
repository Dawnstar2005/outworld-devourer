"""game/campaign.py: dungeon-ий ахиц, байнгын хадгалалт (pygame-гүй)."""

import json
import random

import pytest

from engine import HEROES, ITEMS
from engine.constants import BOSS_DROPS, LEVEL_XP, MAX_ITEMS_PER_HERO
from engine.progression import stage_xp
from game.campaign import (FINAL_STAGE, SAVE_ENV, STAGE_KEYS, Campaign, default_save_path,
                           fresh_data)


@pytest.fixture
def camp(tmp_path):
    return Campaign.load(tmp_path / "save.json", rng=random.Random(0))


def clear_until(c, key):
    for k in STAGE_KEYS:
        if k == key:
            return
        c.finish_stage(k, True, 5)


def test_fresh_campaign_only_first_stage_unlocked(camp):
    assert camp.level == 1 and camp.xp == 0
    assert camp.is_unlocked("1-1")
    assert not any(camp.is_unlocked(k) for k in STAGE_KEYS[1:])
    assert camp.next_stage() == "1-1"
    with pytest.raises(ValueError):
        camp.new_state("1-2")


def test_win_unlocks_next_stage_and_floor(camp):
    r = camp.finish_stage("1-1", True, 7)
    assert r.won and r.first_clear and r.unlocked == "1-2"
    assert r.xp_gained == stage_xp(1, False, True)
    assert camp.is_unlocked("1-2") and not camp.is_unlocked("1-3")
    clear_until(camp, "2-1")
    assert camp.floor_cleared(1) and camp.floor_unlocked(2) and camp.next_stage() == "2-1"


def test_loss_gives_partial_xp_and_no_unlock(camp):
    r = camp.finish_stage("1-1", False, 12)
    assert not r.won and r.unlocked is None and r.drop is None
    assert 0 < r.xp_gained < stage_xp(1, False, True)
    assert not camp.is_cleared("1-1") and camp.data["losses"] == 1


def test_boss_drop_guaranteed_only_on_first_clear(camp):
    clear_until(camp, "1-4")
    bag_before = len(camp.bag)
    r = camp.finish_stage("1-4", True, 10)
    assert r.drop == BOSS_DROPS[1] and len(camp.bag) == bag_before + 1
    camp.rng = random.Random(1)
    drops = {camp.finish_stage("1-4", True, 9).drop for _ in range(20)}
    assert BOSS_DROPS[1] not in drops            # дахин тоглоход энгийн олз л унана
    assert not any(camp.finish_stage("1-4", True, 9).first_clear for _ in range(2))


def test_level_up_reported(camp):
    camp.data["xp"] = LEVEL_XP[1] - 1
    r = camp.finish_stage("1-1", True, 5)
    assert r.leveled_up and r.level_before == 1 and r.level_after == 2 == camp.level


def test_new_state_applies_level_and_items(camp):
    camp.data["xp"] = LEVEL_XP[4]
    camp.data["bag"] = ["life_heart", "sharp_edge"]
    assert camp.equip("life_heart", "knight") and camp.equip("sharp_edge", "mage")
    s = camp.new_state("1-1")
    st = camp.hero_stats()
    knight, mage = s.units["knight"], s.units["mage"]
    assert knight.level == 5 and knight.max_hp == st["knight"]["max_hp"] == knight.hp
    assert mage.power_mult == st["mage"]["power_mult"] > st["healer"]["power_mult"]
    assert s.side_to_act == HEROES


def test_equip_limits_and_unequip(camp):
    camp.data["bag"] = ["life_heart"] * (MAX_ITEMS_PER_HERO + 1)
    for _ in range(MAX_ITEMS_PER_HERO):
        assert camp.equip("life_heart", "healer")
    assert not camp.can_equip("healer") and not camp.equip("life_heart", "healer")
    assert not camp.equip("rune_stone", "knight")        # цүнхэнд байхгүй
    assert camp.unequip("healer", 0) and len(camp.bag) == 2
    assert not camp.unequip("healer", 9)


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "sub" / "save.json"
    c = Campaign.load(path, rng=random.Random(5))
    clear_until(c, "1-4")
    c.data["bag"].append("rune_stone")
    c.equip("rune_stone", "mage")
    c2 = Campaign.load(path)
    assert c2.data == c.data
    assert c2.next_stage() == "1-4" and c2.items("mage") == ["rune_stone"]


def test_corrupt_save_is_backed_up(tmp_path):
    path = tmp_path / "save.json"
    path.write_text("{not json", encoding="utf-8")
    c = Campaign.load(path)
    assert c.load_error and c.data == fresh_data()
    assert path.with_suffix(".bak").exists()


def test_unknown_values_are_dropped(tmp_path):
    path = tmp_path / "save.json"
    path.write_text(json.dumps({"xp": -5, "items": {"knight": ["life_heart", "nope"]},
                                "bag": ["nope", "sharp_edge"], "cleared": ["1-1", "9-9"],
                                "best_rounds": {"1-1": 4, "x": 1}}), encoding="utf-8")
    c = Campaign.load(path)
    assert c.xp == 0 and c.items("knight") == ["life_heart"] and c.bag == ["sharp_edge"]
    assert c.data["cleared"] == ["1-1"] and c.data["best_rounds"] == {"1-1": 4}


def test_final_stage_completes_campaign(camp):
    clear_until(camp, FINAL_STAGE)
    r = camp.finish_stage(FINAL_STAGE, True, 18)
    assert r.campaign_complete and camp.complete and r.unlocked is None
    assert camp.next_stage() == FINAL_STAGE


def test_reset_clears_progress(camp):
    clear_until(camp, "2-1")
    camp.reset()
    assert camp.data == fresh_data() and Campaign.load(camp.path).data == fresh_data()


def test_default_save_path_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(SAVE_ENV, str(tmp_path / "x.json"))
    assert default_save_path() == tmp_path / "x.json"
    monkeypatch.delenv(SAVE_ENV)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_save_path() == tmp_path / "OutworldDevourer" / "save.json"


def test_all_item_ids_are_known():
    assert set(BOSS_DROPS.values()) <= set(ITEMS)
