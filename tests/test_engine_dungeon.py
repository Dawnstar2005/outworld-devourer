"""engine: dungeon (давхар, үе, саад, шинэ мангас/босс) ба ахиц (level, item)."""

import random
from collections import deque

import pytest

from engine import (DEMONS, END_TURN, HEROES, ITEMS, SKILLS, UNIT_TYPES, Action, GameState, apply,
                    is_legal, legal_actions, reachable, unit_actions)
from engine.constants import (BOARD_H, BOARD_W, BOSS_EXTRA_SCALE, FLOOR_ENEMY_SCALE, LEVEL_XP,
                              LOSS_XP_FRACTION,
                              MAX_SUMMONS, START_POSITIONS)
from engine.dungeon import (FLOORS, HERO_UIDS, STAGES_PER_FLOOR, get_stage, new_stage_state,
                            stage_encounter)
from engine.progression import hero_stats, level_for_xp, level_progress, roll_drop, stage_xp

ALL_STAGES = [st for f in FLOORS for st in f.stages]


def place(s, **pos):
    for uid, p in pos.items():
        s.units[uid].x, s.units[uid].y = p


# ---------------------------------------------------------------- хуучин тулаан хэвээр

def test_default_new_game_unchanged():
    s = GameState.new_game()
    assert set(s.units) == set(START_POSITIONS) and s.obstacles == set()
    assert s.boss.uid == "demon_lord" and s.boss.type.boss
    assert all(u.power_mult == 1.0 and u.level == 1 for u in s.units.values())


# ---------------------------------------------------------------- давхар, үе

def test_floor_structure_matches_design():
    assert [f.theme for f in FLOORS] == ["slime", "goblin", "vampire", "demon", "hell"]
    assert [f.boss for f in FLOORS] == ["slime_king", "goblin_king", "vampire_lord",
                                        "legion_commander", "demon_lord"]
    for f in FLOORS:
        assert len(f.stages) == STAGES_PER_FLOOR
        for st in f.stages:
            kinds = [k for _, k, _ in st.enemies]
            if st.is_boss:
                assert kinds[0] == f.boss and len(kinds) == 3        # босс + 2 дагуул
                assert all(not UNIT_TYPES[k].boss for k in kinds[1:])
            else:
                assert len(kinds) == 3 and set(kinds) <= set(f.mobs)
                assert not any(UNIT_TYPES[k].boss for k in kinds)
    final = get_stage(5, 4)
    assert {uid: (k, p) for uid, k, p in final.enemies} == \
        {uid: v for uid, v in START_POSITIONS.items() if uid not in HERO_UIDS}


@pytest.mark.parametrize("stage", ALL_STAGES, ids=lambda st: st.key)
def test_stage_layout_valid_and_connected(stage):
    enc = stage_encounter(stage)
    cells = [tuple(p) for _, p in enc["units"].values()] + [tuple(c) for c in enc["obstacles"]]
    assert len(cells) == len(set(cells))                             # давхцалгүй
    assert all(0 <= x < BOARD_W and 0 <= y < BOARD_H for x, y in cells)
    blocked = set(map(tuple, enc["obstacles"]))
    enemies = {tuple(p) for uid, (k, p) in enc["units"].items() if uid not in HERO_UIDS}
    for hero in HERO_UIDS:                                           # саад замыг бүрэн хаахгүй
        start = tuple(enc["units"][hero][1])
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n not in seen and n not in blocked and 0 <= n[0] < BOARD_W and 0 <= n[1] < BOARD_H:
                    seen.add(n)
                    q.append(n)
        assert enemies <= seen, (stage.key, hero)


def test_new_stage_state_scales_enemies_and_applies_heroes():
    st = get_stage(3, 4)
    stats = {"knight": hero_stats("knight", 4, ["life_heart"]),
             "mage": hero_stats("mage", 2, []), "healer": hero_stats("healer", 1, [])}
    s = new_stage_state(st, stats)
    hp_m, pw_m = FLOOR_ENEMY_SCALE[3]
    lord = s.units["vampire_lord"]
    assert lord.max_hp == lord.hp == round(UNIT_TYPES["vampire_lord"].hp * hp_m)
    assert lord.power_mult == pw_m and s.boss is lord
    k = s.units["knight"]
    assert (k.max_hp, k.power_mult, k.level) == (stats["knight"]["max_hp"],
                                                 stats["knight"]["power_mult"], 4)
    assert s.obstacles == set(st.obstacles)


# ---------------------------------------------------------------- саад

def test_obstacles_block_movement_and_walls_and_roundtrip():
    s = GameState.new_game()
    s.obstacles = {(3, 5), (4, 6)}
    r = reachable(s, s.units["knight"])
    assert (3, 5) not in r and (4, 6) not in r
    place(s, mage=(3, 4))
    walls = [a for a in unit_actions(s, s.units["mage"]) if a.skill == "ice_wall"]
    from engine import wall_cells
    assert walls and all(not (set(wall_cells(a.target, a.variant)) & s.obstacles) for a in walls)
    d = s.to_dict()
    again = GameState.from_dict(d)
    assert again.obstacles == s.obstacles and again.clone().obstacles == s.obstacles
    d.pop("obstacles")
    assert GameState.from_dict(d).obstacles == set()                 # хуучин log
    for u in d["units"]:
        u.pop("power_mult")
        u.pop("level")
    old = GameState.from_dict(d)
    assert old.units["knight"].power_mult == 1.0 and old.units["knight"].level == 1


# ---------------------------------------------------------------- хүчний үржвэр, drain, summon

def test_power_mult_scales_damage_heal_and_shield():
    s = GameState.new_game()
    place(s, knight=(4, 2))
    s.units["knight"].power_mult = 1.5
    apply(s, Action("knight", (4, 2), "sword", (4, 1), "demon_lord"))
    assert s.boss.hp == s.boss.max_hp - round(SKILLS["sword"].power * 1.5)
    s2 = GameState.new_game()
    s2.units["mage"].hp = 10
    s2.units["healer"].power_mult = 1.2
    place(s2, healer=(3, 7))
    apply(s2, Action("healer", (3, 7), "heal", (2, 7), "mage"))
    assert s2.units["mage"].hp == 10 + round(SKILLS["heal"].power * 1.2)
    s3 = GameState.new_game()
    s3.units["healer"].power_mult = 1.5
    apply(s3, Action("healer", (5, 7), "shield", (3, 6), "knight"))
    assert s3.units["knight"].shield == round(SKILLS["shield"].power * 1.5)


def test_drain_damages_and_heals_caster():
    s = new_stage_state(get_stage(3, 1))
    s.side_to_act = DEMONS
    v = s.units["low_vampire1"]
    v.hp = 10
    place(s, low_vampire1=(3, 5))
    knight_hp = s.units["knight"].hp
    a = Action("low_vampire1", (3, 5), "bite", (3, 6), "knight")
    assert is_legal(s, a)
    events = apply(s, a)
    dealt = knight_hp - s.units["knight"].hp
    assert dealt == round(SKILLS["bite"].power * v.power_mult)
    assert v.hp == 10 + round(dealt * SKILLS["bite"].drain)
    assert any(e["type"] == "heal" and e["dst"] == "low_vampire1" for e in events)
    s2 = new_stage_state(get_stage(3, 1))
    s2.side_to_act = DEMONS
    place(s2, low_vampire1=(3, 5))
    s2.units["low_vampire1"].hp = 10
    s2.units["low_vampire1"].cursed = 2                              # хараалтай бол эдгэрэхгүй
    apply(s2, Action("low_vampire1", (3, 5), "bite", (3, 6), "knight"))
    assert s2.units["low_vampire1"].hp == 10


def test_generalized_summon_revives_floor_minions():
    s = new_stage_state(get_stage(1, 4))
    s.side_to_act = DEMONS
    for uid in ("slime1", "slime2"):
        s.units[uid].alive = False
        s.units[uid].hp = 0
    king = s.units["slime_king"]
    acts = [a for a in unit_actions(s, king) if a.skill == "split"]
    assert acts
    events = apply(s, Action("slime_king", king.pos, "split"))
    spawned = next(e for e in events if e["type"] == "summon")["spawned"]
    assert {x["unit"] for x in spawned} == {"slime1", "slime2"}
    hp_m, pw_m = FLOOR_ENEMY_SCALE[1]
    assert s.side_to_act == HEROES          # дуудагдсан slime нүүгээгүй тул ээлж шилжсэн
    for uid in ("slime1", "slime2"):
        u = s.units[uid]
        assert u.alive and u.max_hp == round(UNIT_TYPES["slime"].hp * hp_m)
        assert u.power_mult == pw_m
    assert sum(1 for u in s.alive_units(DEMONS) if u.kind == "slime") <= MAX_SUMMONS


def test_boss_extra_scale_only_on_boss():
    """Эцсийн босст нэмэлт үржвэр, дагуул Imp-үүдэд зөвхөн давхрын үржвэр."""
    s = new_stage_state(get_stage(5, 4))
    hp_m, pw_m = FLOOR_ENEMY_SCALE[5]
    bh, bp = BOSS_EXTRA_SCALE.get(5, (1.0, 1.0))
    lord = s.units["demon_lord"]
    assert lord.max_hp == round(UNIT_TYPES["demon_lord"].hp * hp_m * bh)
    assert lord.power_mult == pytest.approx(pw_m * bp)
    imp = s.units["imp1"]
    assert imp.max_hp == round(UNIT_TYPES["imp"].hp * hp_m) and imp.power_mult == pw_m


def test_vampire_lord_can_mist_step():
    s = new_stage_state(get_stage(3, 4))
    s.side_to_act = DEMONS
    assert any(a.leap for a in unit_actions(s, s.units["vampire_lord"]))


# ---------------------------------------------------------------- ялалтын нөхцөл

def test_mob_stage_win_needs_all_enemies_dead():
    s = new_stage_state(get_stage(2, 1))
    assert s.boss is None and not s.boss_enraged
    for uid in ("goblin1", "goblin2"):
        s.units[uid].alive = False
        s.units[uid].hp = 0
    g = s.units["goblin3"]
    g.hp = 1
    place(s, knight=(g.x, g.y + 1))
    assert s.winner is None
    events = apply(s, Action("knight", s.units["knight"].pos, "sword", g.pos, "goblin3"))
    assert s.winner == HEROES and events[-1]["type"] == "game_over"


def test_boss_stage_win_when_boss_falls_even_with_minions():
    s = new_stage_state(get_stage(2, 4))
    king = s.units["goblin_king"]
    king.hp = 1
    place(s, knight=(king.x, king.y + 1))
    apply(s, Action("knight", s.units["knight"].pos, "sword", king.pos, "goblin_king"))
    assert s.winner == HEROES and s.units["goblin1"].alive


@pytest.mark.parametrize("stage", ALL_STAGES, ids=lambda st: st.key)
def test_random_playout_every_stage(stage):
    rng = random.Random(hash(stage.key) % 1000)
    s = new_stage_state(stage)
    for _ in range(4000):
        if s.is_over:
            break
        acts = legal_actions(s)
        apply(s, rng.choice(acts), validate=True)
        for u in s.units.values():
            assert 0 <= u.hp <= u.max_hp
    assert s.is_over and s.winner in (HEROES, DEMONS, "draw")


# ---------------------------------------------------------------- ахиц

def test_levels_xp_and_stats():
    assert level_for_xp(0) == 1 and level_for_xp(LEVEL_XP[1] - 1) == 1
    assert level_for_xp(LEVEL_XP[1]) == 2 and level_for_xp(10 ** 9) == len(LEVEL_XP)
    lvl, start, nxt = level_progress(LEVEL_XP[2] + 5)
    assert (lvl, start, nxt) == (3, LEVEL_XP[2], LEVEL_XP[3])
    assert level_progress(10 ** 9)[2] is None
    base = hero_stats("mage", 1)
    assert base == {"max_hp": UNIT_TYPES["mage"].hp, "power_mult": 1.0,
                    "move": UNIT_TYPES["mage"].move, "level": 1}
    up = hero_stats("mage", 5, ["life_heart", "sharp_edge", "swift_boots"])
    assert up["max_hp"] > base["max_hp"] + ITEMS["life_heart"].hp
    assert up["power_mult"] > 1.0 + ITEMS["sharp_edge"].power
    assert up["move"] == base["move"] + 1
    assert stage_xp(2, False, True) * LOSS_XP_FRACTION // 1 == stage_xp(2, False, False)
    assert stage_xp(1, True, True) > stage_xp(1, False, True)


def test_drops():
    rng = random.Random(0)
    assert roll_drop(1, True, rng) == "slime_core"                   # боссын баталгаатай олз
    drops = [roll_drop(2, False, random.Random(i)) for i in range(300)]
    got = [d for d in drops if d]
    assert 0.25 < len(got) / len(drops) < 0.65
    assert set(got) <= set(ITEMS) and not any(ITEMS[d].rarity == "boss" for d in got)
    assert roll_drop(3, False, random.Random(7)) == roll_drop(3, False, random.Random(7))


def test_end_turn_still_works_without_boss():
    s = new_stage_state(get_stage(1, 1))
    apply(s, END_TURN)
    assert s.side_to_act == DEMONS and not s.is_over
