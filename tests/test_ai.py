import random

from engine import DEMONS, HEROES, Action, GameState, apply, END_TURN
from ai import BossAI, action_label, evaluate
from ai.sparring import random_heroes_turn


def boss_turn_state():
    s = GameState.new_game()
    apply(s, END_TURN)
    return s


def test_evaluate_range_and_terminal():
    s = GameState.new_game()
    assert abs(evaluate(s) - 0.5) < 0.02
    s.winner = DEMONS
    assert evaluate(s) == 1.0
    s.winner = HEROES
    assert evaluate(s) == 0.0


def test_evaluate_prefers_hurt_heroes_and_healthy_boss():
    s = GameState.new_game()
    hurt = s.clone(); hurt.units["healer"].hp = 20
    boss_hurt = s.clone(); boss_hurt.boss.hp = 200
    assert evaluate(hurt) > evaluate(s) > evaluate(boss_hurt)


def test_priority_changes_preference():
    s = GameState.new_game()
    a = s.clone(); a.units["healer"].hp -= 30
    b = s.clone(); b.units["knight"].hp -= 30
    pr = {"healer": 2.0, "knight": 0.5, "mage": 1.0}
    assert evaluate(a, priority=pr) > evaluate(b, priority=pr)


def test_decide_does_not_mutate_and_returns_panel():
    s = boss_turn_state()
    before = s.to_dict()
    d = BossAI(seed=1, epsilon=0).decide(s)
    assert s.to_dict() == before
    assert d.actions and d.actions[0].unit == "demon_lord"
    panel = d.to_panel()
    assert 1 <= len(panel["options"]) <= 3
    assert sum(o["chosen"] for o in panel["options"]) == 1
    labels = [o["label"] for o in panel["options"]]
    assert len(set(labels)) == len(labels)  # давхардсан санаа байхгүй


def test_decision_under_2_seconds():
    s = boss_turn_state()
    d = BossAI(seed=0).decide(s)
    assert d.elapsed < 2.0


def test_profile_makes_boss_target_healer():
    """Healer-т их найддаг профайлтай бол босс Healer-ийг онилно."""
    s = boss_turn_state()
    prof = {"target_priority": {"healer": 3.0, "knight": 0.5, "mage": 0.8},
            "habits": ["Healer-т их найддаг"]}
    d = BossAI(profile=prof, seed=0, epsilon=0).decide(s)
    first = d.actions[0]
    assert first.target_uid == "healer" or (first.skill and "Healer" in action_label(first, s))
    assert d.to_panel()["habits"] == ["Healer-т их найддаг"]


def test_epsilon_random_pick_happens():
    s = boss_turn_state()
    boss = BossAI(seed=3, epsilon=1.0)
    assert boss.decide(s).random_pick
    assert not BossAI(seed=3, epsilon=0.0).decide(s).random_pick


def test_play_turn_hands_back_to_heroes():
    s = boss_turn_state()
    BossAI(seed=0).play_turn(s)
    assert s.side_to_act == HEROES or s.is_over


def test_full_games_vs_random_heroes():
    rng = random.Random(7)
    for g in range(5):
        s = GameState.new_game()
        boss = BossAI(seed=g)
        while not s.is_over:
            if s.side_to_act == HEROES:
                random_heroes_turn(s, rng)
            else:
                boss.play_turn(s)
        assert s.winner in (HEROES, DEMONS, "draw")


def test_action_label_mongolian():
    s = boss_turn_state()
    a = Action("demon_lord", (4, 1), "dark_flame", (3, 6), "knight")
    assert action_label(a, s) == "Хар дөл Knight-т"
