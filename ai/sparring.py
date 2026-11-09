"""AI-г хөгжүүлэхэд хэрэглэх энгийн баатрын бодлого (AI Engineer-ийн дотоод хэрэгсэл).

Албан ёсны bot-ууд (санамсаргүй, шунахай, тогтмол зуршилтай) болон 100 тулааны
туршилт нь DQ-ийн ажил (`bots/`, `experiments/`). Энэ файл зөвхөн боссыг тааруулах
явцад хурдан шалгахад зориулагдсан.
"""
from __future__ import annotations

import random

from engine import END_TURN, HEROES, GameState, apply, next_state, unit_actions

from .evaluate import evaluate


def random_heroes_turn(state: GameState, rng: random.Random):
    while not state.is_over and state.side_to_act == HEROES:
        pending = [u for u in state.alive_units(HEROES) if not u.acted]
        if not pending:
            apply(state, END_TURN)
            break
        u = rng.choice(pending)
        apply(state, rng.choice(unit_actions(state, u)))


def greedy_heroes_turn(state: GameState, rng: random.Random):
    """Баатар бүр (Knight → Mage → Healer) боссын оноог хамгийн бага болгох нүүдэл хийнэ."""
    while not state.is_over and state.side_to_act == HEROES:
        pending = [u for u in state.alive_units(HEROES) if not u.acted]
        if not pending:
            apply(state, END_TURN)
            break
        u = pending[0]
        acts = unit_actions(state, u)
        rng.shuffle(acts)
        apply(state, min(acts, key=lambda a: evaluate(next_state(state, a))))
