import random

from engine import DEMONS, END_TURN, HEROES, GameState, apply, is_legal
from ai import BossAI, evaluate
from ai.mcts import MCTSPlanner, finish_turn


def boss_turn_state():
    s = GameState.new_game()
    apply(s, END_TURN)
    return s


def test_sampled_turn_is_legal_for_both_sides():
    rng = random.Random(0)
    p = MCTSPlanner(evaluate, rng)
    for start in (GameState.new_game(), boss_turn_state()):
        s = start.clone()
        for a in p.sample_turn(s):
            assert is_legal(s, a), a
            apply(s, a)


def test_finish_turn_hands_over():
    s = boss_turn_state()
    p = MCTSPlanner(evaluate, random.Random(0))
    nxt = finish_turn(s, p.sample_turn(s))
    assert nxt.side_to_act == HEROES or nxt.is_over
    assert s.side_to_act == DEMONS  # эх төлөв өөрчлөгдөөгүй


def test_mcts_decision_with_iterations():
    s = boss_turn_state()
    before = s.to_dict()
    d = BossAI(seed=0, epsilon=0, max_iters=200, mode="mcts").decide(s)
    assert s.to_dict() == before
    assert d.mode == "mcts" and d.iterations == 200
    assert d.options[0].visits >= d.options[-1].visits
    assert 0.0 <= d.score <= 1.0


def test_mcts_respects_time_limit():
    s = boss_turn_state()
    d = BossAI(seed=0, time_limit=0.3, mode="mcts").decide(s)
    assert d.elapsed < 2.0
    assert d.iterations > 0


def test_eval_mode_still_available():
    d = BossAI(seed=0, mode="eval").decide(boss_turn_state())
    assert d.mode == "eval" and d.iterations == 0


def test_predictor_is_used_for_heroes():
    calls = []

    def predictor(state, uid, actions):
        calls.append(uid)
        return [1.0] * len(actions)

    BossAI(seed=0, max_iters=30, predictor=predictor, mode="mcts").decide(boss_turn_state())
    assert calls and set(calls) <= {"knight", "mage", "healer"}


def test_full_game_with_mcts():
    rng = random.Random(1)
    s = GameState.new_game()
    boss = BossAI(seed=1, max_iters=60, mode="mcts")
    from ai.sparring import random_heroes_turn
    while not s.is_over:
        if s.side_to_act == HEROES:
            random_heroes_turn(s, rng)
        else:
            boss.play_turn(s)
    assert s.winner in (HEROES, DEMONS, "draw")
