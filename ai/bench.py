"""Боссыг хурдан хэмжих: python -m ai.bench --games 20 --heroes greedy"""
from __future__ import annotations

import argparse
import random
import statistics
import time

from engine import DEMONS, HEROES, GameState

from .boss import BossAI
from .sparring import greedy_heroes_turn, random_heroes_turn

POLICIES = {"random": random_heroes_turn, "greedy": greedy_heroes_turn}


def run(games: int, heroes: str, seed: int = 0, epsilon: float = 0.1, verbose=False,
        mode: str = "mcts", iters: int | None = 300, boss_hp: int | None = None):
    rng = random.Random(seed)
    hero_turn = POLICIES[heroes]
    wins = {HEROES: 0, DEMONS: 0, "draw": 0}
    times, rounds = [], []
    for g in range(games):
        boss = BossAI(epsilon=epsilon, seed=seed * 1000 + g, mode=mode, max_iters=iters)
        s = GameState.new_game()
        if boss_hp:  # тэнцвэрийн туршилтад зориулсан хөнгөлөлт (constants-ыг өөрчлөхгүй)
            s.boss.hp = s.boss.max_hp = boss_hp
        while not s.is_over:
            if s.side_to_act == HEROES:
                hero_turn(s, rng)
            else:
                r = s.round
                d, _ = boss.play_turn(s)
                times.append(d.elapsed)
                if verbose:
                    print(f"round {r}\n{d.to_text()}\n")
        wins[s.winner] += 1
        rounds.append(s.round)
    return {
        "games": games, "heroes": heroes, "mode": mode, "iters": iters, "boss_hp": boss_hp,
        "boss_win_rate": wins[DEMONS] / games, "hero_win_rate": wins[HEROES] / games,
        "draws": wins["draw"], "avg_rounds": statistics.mean(rounds),
        "decision_ms_avg": 1000 * statistics.mean(times),
        "decision_ms_max": 1000 * max(times),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=20)
    p.add_argument("--heroes", choices=list(POLICIES), default="greedy")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--epsilon", type=float, default=0.1)
    p.add_argument("--mode", choices=["mcts", "eval"], default="mcts")
    p.add_argument("--iters", type=int, default=300, help="MCTS давталт (0 = хугацаагаар)")
    p.add_argument("--boss-hp", type=int, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args()
    t = time.perf_counter()
    r = run(a.games, a.heroes, a.seed, a.epsilon, a.verbose, a.mode, a.iters or None, a.boss_hp)
    for k, v in r.items():
        print(f"{k:>16}: {v:.3f}" if isinstance(v, float) else f"{k:>16}: {v}")
    print(f"{'total_s':>16}: {time.perf_counter() - t:.1f}")
