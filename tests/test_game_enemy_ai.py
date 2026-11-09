"""game/enemy_ai.py: 1–4-р давхрын тактикийн дайсны AI (pygame-гүй)."""

from engine import DEMONS, HEROES, apply, is_legal
from engine.dungeon import FLOORS, get_stage, new_stage_state
from game.enemy_ai import TacticalAI
from game.labels import action_label


def _demon_turn(stage_key):
    f, i = map(int, stage_key.split("-"))
    s = new_stage_state(get_stage(f, i))
    s.side_to_act = DEMONS
    return s


def test_decide_returns_legal_sequence_for_every_stage():
    for floor in FLOORS:
        for st in floor.stages:
            s = new_stage_state(st)
            s.side_to_act = DEMONS
            d = TacticalAI(seed=0).decide(s)
            assert d.actions, st.key
            sim = s.clone()
            for a in d.actions:
                assert is_legal(sim, a), (st.key, a)
                apply(sim, a)
            assert sim.is_over or sim.side_to_act == HEROES


def test_decide_does_not_mutate_state():
    s = _demon_turn("2-4")
    before = s.to_dict()
    TacticalAI(seed=1).decide(s)
    assert s.to_dict() == before


def test_prefers_finishing_low_hp_hero():
    s = _demon_turn("1-1")
    slime = s.units["slime1"]
    mage = s.units["mage"]
    knight = s.units["knight"]
    mage.x, mage.y = slime.x, slime.y + 1
    knight.x, knight.y = slime.x + 1, slime.y
    mage.hp = 5
    d = TacticalAI(seed=0, epsilon=0.0).decide(s)
    first = next(a for a in d.actions if a.unit == "slime1")
    assert first.target_uid == "mage"


def test_profile_priority_overrides_default():
    ai = TacticalAI(profile={"target_priority": {"knight": 3.0}, "habits": ["Knight-д найддаг"]})
    assert ai.priority["knight"] == 3.0 and ai.priority["mage"] > 1.0
    d = ai.decide(_demon_turn("3-1"))
    assert d.habits == ["Knight-д найддаг"]


def test_panel_format_matches_boss_panel():
    s = _demon_turn("4-4")
    panel = TacticalAI(seed=2).decide(s).to_panel()
    assert set(panel) >= {"habits", "options", "enraged", "random_pick", "ms", "mode"}
    assert panel["mode"] == "tactic"
    assert 1 <= len(panel["options"]) <= 3
    assert sum(1 for o in panel["options"] if o["chosen"]) == 1
    for o in panel["options"]:
        assert isinstance(o["label"], str) and 0.0 <= o["score"] <= 1.0


def test_seed_is_deterministic():
    s = _demon_turn("2-2")
    a = TacticalAI(seed=7).decide(s).actions
    b = TacticalAI(seed=7).decide(s).actions
    assert [x.to_dict() for x in a] == [x.to_dict() for x in b]


def test_action_label_is_mongolian_text():
    s = _demon_turn("3-4")
    d = TacticalAI(seed=0).decide(s)
    for a in d.actions:
        text = action_label(a, s)
        assert text and "None" not in text
