import json
import random
import time

import pytest

from engine import (DEMONS, END_TURN, HEROES, SKILLS, UNIT_TYPES, Action, GameState, apply,
                    is_legal, legal_actions, next_state, reachable)
from engine.constants import ENRAGE_THRESHOLD

# Тэнцвэрийн утгыг constants.py-аас уншина — утга өөрчлөгдөхөд тест эвдрэхгүй.
BOSS_HP = UNIT_TYPES["demon_lord"].hp
KNIGHT_HP = UNIT_TYPES["knight"].hp
MAGE_HP = UNIT_TYPES["mage"].hp
IMP_HP = UNIT_TYPES["imp"].hp


def place(s, **pos):
    for uid, p in pos.items():
        s.units[uid].x, s.units[uid].y = p


def kill(s, *uids):
    for uid in uids:
        s.units[uid].alive = False
        s.units[uid].hp = 0


def acts_of(s, uid, skill=None):
    return [a for a in legal_actions(s) if a.unit == uid and (skill is None or a.skill == skill)]


# ---------------------------------------------------------------- эхлэл, хөдөлгөөн

def test_new_game():
    s = GameState.new_game()
    assert s.side_to_act == HEROES and s.round == 1 and s.winner is None
    assert len(s.alive_units(HEROES)) == 3 and len(s.alive_units(DEMONS)) == 3
    assert s.boss.hp == BOSS_HP


def test_heroes_only_on_hero_turn():
    s = GameState.new_game()
    assert {a.unit for a in legal_actions(s) if not a.is_end_turn} == {"knight", "mage", "healer"}


def test_movement_range_and_blocking():
    s = GameState.new_game()
    k = s.units["knight"]
    r = reachable(s, k)
    assert all(abs(c[0] - 3) + abs(c[1] - 6) <= 3 for c in r)
    assert (2, 7) not in r  # Mage-ийн нүд
    s.walls[(3, 5)] = 2
    assert (3, 5) not in reachable(s, k)


def test_wait_action_exists():
    s = GameState.new_game()
    assert Action("knight", (3, 6)) in legal_actions(s)


# ---------------------------------------------------------------- хохирол, бамбай

def test_sword_damage_and_shield():
    s = GameState.new_game()
    place(s, knight=(4, 2))
    s.boss.shield = 0
    a = Action("knight", (4, 2), "sword", (4, 1), "demon_lord")
    assert is_legal(s, a)
    apply(s, a)
    assert s.boss.hp == BOSS_HP - SKILLS["sword"].power


def test_shield_absorbs():
    s = GameState.new_game()
    s.units["knight"].shield = 20
    s.side_to_act = DEMONS
    place(s, demon_lord=(3, 3))
    apply(s, Action("demon_lord", (3, 3), "dark_flame", (3, 6), "knight"))
    k = s.units["knight"]
    assert k.shield == 0 and k.hp == KNIGHT_HP - (SKILLS["dark_flame"].power - 20)  # 20 шингээсэн


def test_fireball_area_hits_only_enemies():
    s = GameState.new_game()
    place(s, mage=(4, 4))
    apply(s, Action("mage", (4, 4), "fireball", (3, 1)))  # 3×3: (2..4, 0..2)
    fb = SKILLS["fireball"].power
    assert s.boss.hp == BOSS_HP - fb and s.units["imp1"].hp == max(0, IMP_HP - fb)
    assert s.units["imp2"].hp == IMP_HP
    assert s.units["knight"].hp == KNIGHT_HP


def test_area_targets_only_useful_cells():
    s = GameState.new_game()
    for a in acts_of(s, "mage", "fireball"):
        cx, cy = a.target
        assert any(abs(e.x - cx) <= 1 and abs(e.y - cy) <= 1 for e in s.alive_units(DEMONS))


# ---------------------------------------------------------------- хараал, эдгэрэл

def test_heal_capped_and_curse_blocks():
    s2 = GameState.new_game()
    s2.units["mage"].hp = MAGE_HP - 10
    place(s2, healer=(3, 7))
    apply(s2, Action("healer", (3, 7), "heal", (2, 7), "mage"))
    assert s2.units["mage"].hp == MAGE_HP  # дээд HP-гаас хэтрэхгүй

    s3 = GameState.new_game()
    s3.units["mage"].hp = 30
    s3.units["mage"].cursed = 2
    assert not [a for a in acts_of(s3, "healer", "heal") if a.target_uid == "mage"]


def test_curse_lasts_two_hero_turns():
    s = GameState.new_game()
    s.side_to_act = DEMONS
    place(s, demon_lord=(3, 3))
    apply(s, Action("demon_lord", (3, 3), "curse", (5, 7), "healer"))
    apply(s, END_TURN)                     # боссын ээлж дуусна
    assert s.units["healer"].cursed == 2
    apply(s, END_TURN)                     # heroes 1
    assert s.units["healer"].cursed == 1
    apply(s, END_TURN); apply(s, END_TURN)  # demons, heroes 2
    assert s.units["healer"].cursed == 0


# ---------------------------------------------------------------- taunt

def test_taunt_forces_single_target():
    s = GameState.new_game()
    place(s, knight=(4, 4), demon_lord=(4, 2))
    apply(s, Action("knight", (4, 4), "taunt"))
    assert s.boss.taunted_by == "knight"
    apply(s, END_TURN)
    targets = {a.target_uid for a in acts_of(s, "demon_lord", "dark_flame")}
    # Knight хүрэх зайд байгаа нүднээс зөвхөн Knight руу
    for a in acts_of(s, "demon_lord", "dark_flame"):
        if abs(a.dest[0] - 4) + abs(a.dest[1] - 4) <= SKILLS["dark_flame"].range:
            assert a.target_uid == "knight"
    assert "knight" in targets


def test_taunt_expires_after_two_demon_turns():
    s = GameState.new_game()
    place(s, knight=(4, 4))
    apply(s, Action("knight", (4, 4), "taunt"))
    for _ in range(4):
        apply(s, END_TURN)
    assert s.boss.taunted_by is None


# ---------------------------------------------------------------- мөсөн хана

def test_ice_wall_blocks_and_expires():
    s = GameState.new_game()
    apply(s, Action("mage", (2, 7), "ice_wall", (2, 4), None, 0))
    assert set(s.walls) == {(2, 4), (3, 4)}
    apply(s, END_TURN)  # heroes дууслаа
    assert (3, 4) not in reachable(s, s.units["imp1"])
    apply(s, END_TURN); apply(s, END_TURN)  # demons 1, heroes
    assert s.walls
    apply(s, END_TURN)  # demons 2
    assert not s.walls


# ---------------------------------------------------------------- cooldown

def test_cooldown():
    s = GameState.new_game()
    place(s, mage=(4, 4))
    apply(s, Action("mage", (4, 4), "fireball", (4, 1)))
    apply(s, END_TURN); apply(s, END_TURN)
    assert not acts_of(s, "mage", "fireball")      # cooldown 2: дараагийн ээлжид болохгүй
    apply(s, END_TURN); apply(s, END_TURN)
    assert acts_of(s, "mage", "fireball")


# ---------------------------------------------------------------- босс: үсрэлт, дуудлага

def test_shadow_leap_then_skill():
    s = GameState.new_game()
    s.side_to_act = DEMONS
    leaps = [a for a in acts_of(s, "demon_lord") if a.leap]
    assert leaps
    a = next(a for a in leaps if a.skill == "curse" and a.target_uid == "healer")
    apply(s, a)
    assert s.boss.pos == a.dest and s.units["healer"].cursed == 2
    assert s.boss.cooldowns["shadow_leap"] == SKILLS["shadow_leap"].cooldown


def test_summon_imp():
    s = GameState.new_game()
    kill(s, "imp1", "imp2")
    s.side_to_act = DEMONS
    assert acts_of(s, "demon_lord", "summon_imp")
    apply(s, Action("demon_lord", (4, 1), "summon_imp"))
    imps = [u for u in s.alive_units(DEMONS) if u.kind == "imp"]
    assert len(imps) == 2 and all(u.hp == 30 for u in imps)
    assert s.side_to_act == HEROES  # дуудагдсан imp энэ ээлжид нүүхгүй


def test_no_summon_when_imps_alive():
    s = GameState.new_game()
    s.side_to_act = DEMONS
    assert not acts_of(s, "demon_lord", "summon_imp")


# ---------------------------------------------------------------- ялагч, ээлж

def test_boss_death_heroes_win():
    s = GameState.new_game()
    s.boss.hp = 10
    place(s, knight=(4, 2))
    ev = apply(s, Action("knight", (4, 2), "sword", (4, 1), "demon_lord"))
    assert s.winner == HEROES and ev[-1]["type"] == "game_over"
    assert legal_actions(s) == []


def test_turn_switches_after_all_units_act():
    s = GameState.new_game()
    for uid in ("knight", "mage", "healer"):
        apply(s, Action(uid, s.units[uid].pos))
    assert s.side_to_act == DEMONS


def test_enrage_flag():
    s = GameState.new_game()
    edge = int(BOSS_HP * ENRAGE_THRESHOLD)          # HP < 30% бол уур хилэн
    s.boss.hp = edge - 1
    assert s.boss_enraged
    s.boss.hp = edge if edge >= BOSS_HP * ENRAGE_THRESHOLD else edge + 1
    assert not s.boss_enraged


def test_illegal_action_rejected():
    s = GameState.new_game()
    with pytest.raises(ValueError):
        apply(s, Action("demon_lord", (4, 2)), validate=True)


# ---------------------------------------------------------------- хуулбар, JSON

def test_clone_is_independent():
    s = GameState.new_game()
    c = s.clone()
    c.units["knight"].hp = 1
    c.units["knight"].cooldowns["sword"] = 5
    c.walls[(0, 0)] = 1
    assert s.units["knight"].hp == KNIGHT_HP and s.units["knight"].cooldowns["sword"] == 0
    assert not s.walls


def test_json_roundtrip():
    s = GameState.new_game()
    rng = random.Random(1)
    for _ in range(15):
        apply(s, rng.choice(legal_actions(s, include_end_turn=False)))
    s2 = GameState.from_dict(json.loads(json.dumps(s.to_dict())))
    assert s2.to_dict() == json.loads(json.dumps(s.to_dict()))
    assert len(legal_actions(s2)) == len(legal_actions(s))
    a = legal_actions(s)[0]
    assert Action.from_dict(json.loads(json.dumps(a.to_dict()))) == a


# ---------------------------------------------------------------- санамсаргүй тоглолт

def test_random_games_finish_without_crash():
    rng = random.Random(42)
    results = {}
    for _ in range(200):
        s = GameState.new_game()
        steps = 0
        while not s.is_over:
            acts = legal_actions(s, include_end_turn=False)
            assert acts, "дүрүүд нүүх нүүдэлгүй үлдэж болохгүй"
            a = rng.choice(acts)
            assert is_legal(s, a)
            apply(s, a, validate=False)
            for u in s.units.values():
                assert 0 <= u.hp <= u.max_hp
            steps += 1
            assert steps < 2000
        results[s.winner] = results.get(s.winner, 0) + 1
    assert sum(results.values()) == 200


def test_simulation_speed():
    """MCTS-д хангалттай хурдан эсэх: clone + legal_actions + apply."""
    rng = random.Random(0)
    s = GameState.new_game()
    t = time.perf_counter()
    n = 0
    while n < 2000:
        if s.is_over:
            s = GameState.new_game()
        c = s.clone()
        apply(c, rng.choice(legal_actions(c, include_end_turn=False)))
        s = c
        n += 1
    per = (time.perf_counter() - t) / n
    print(f"\n  {per * 1e6:.0f} µs / (clone + legal_actions + apply)")
    assert per < 0.005
