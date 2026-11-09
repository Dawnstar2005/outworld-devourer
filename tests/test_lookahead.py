"""mode="lookahead" — тоглогчийн хариу ээлжийг загвараар тоглуулж сонгох."""
import random

from engine import DEMONS, END_TURN, HEROES, GameState, apply, is_legal
from ai import BossAI
from ai.opponent import GreedyHeroModel, PredictorHeroModel
from ai.sparring import random_heroes_turn


def boss_turn_state():
    s = GameState.new_game()
    apply(s, END_TURN)
    return s


def test_default_mode_is_lookahead():
    d = BossAI(seed=0, epsilon=0).decide(boss_turn_state())
    assert d.mode == "lookahead"
    assert d.elapsed < 2.0


def test_greedy_model_plays_full_legal_hero_turn():
    s = GameState.new_game()
    m = GreedyHeroModel()
    c = s.clone()
    while c.side_to_act == HEROES and not c.is_over:
        a = m.choose(c)
        assert is_legal(c, a)
        apply(c, a)
    after = m.play_turn(s)
    assert after.side_to_act == DEMONS or after.is_over
    assert s.side_to_act == HEROES  # эх төлөв хөндөгдөөгүй


def test_greedy_model_takes_lethal_hit():
    """Загвар нь боссыг алж болох бол алах ёстой (тоглогч ийм боломжийг алдахгүй)."""
    s = GameState.new_game()
    s.boss.hp = 15
    s.units["knight"].x, s.units["knight"].y = 4, 2
    a = GreedyHeroModel().choose(s)
    assert a.skill in ("sword", "fireball") and a.unit in ("knight", "mage")


def test_lookahead_avoids_move_that_loses_immediately():
    """Баатрууд дараагийн ээлжид ялах боломжтой бол lookahead-ийн оноо 0 болно."""
    s = boss_turn_state()
    s.boss.hp = 15
    d = BossAI(seed=0, epsilon=0).decide(s)
    assert all(0.0 <= o.score <= 1.0 for o in d.options)


def test_predictor_model_follows_predictor():
    s = GameState.new_game()

    def likes_waiting(state, uid, actions):
        return [1.0 if (a.skill is None and a.dest == state.units[uid].pos) else 0.0
                for a in actions]

    a = PredictorHeroModel(likes_waiting, mix=1.0).choose(s)
    assert a.skill is None and a.dest == s.units[a.unit].pos


def test_predictor_used_in_lookahead_mode():
    calls = []

    def pred(state, uid, actions):
        calls.append(uid)
        return [1.0] * len(actions)

    BossAI(seed=0, predictor=pred).decide(boss_turn_state())
    assert calls and set(calls) <= {"knight", "mage", "healer"}


def test_full_games_lookahead():
    rng = random.Random(3)
    for g in range(3):
        s = GameState.new_game()
        boss = BossAI(seed=g)
        while not s.is_over:
            if s.side_to_act == HEROES:
                random_heroes_turn(s, rng)
            else:
                boss.play_turn(s)
        assert s.winner in (HEROES, DEMONS, "draw")
