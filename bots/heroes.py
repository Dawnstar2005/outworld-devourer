"""Баатруудыг удирдах скриптэй bot-ууд — тус бүр өөр «зуршилтай» тоглогчийг дуурайна.

Зуршлын профайл (learning/profile.py) болон 100 тулааны туршилтад (experiments/) ашиглана.
`choose(state)` нь баатруудын ээлжинд нэг Action буцаана. Сонголт бүр
engine.legal_actions()-аас, оноог engine.next_state()-ээр тооцоолно.
"""

from __future__ import annotations

import random

from engine import END_TURN, HEROES, SKILLS, Action, GameState, dist, legal_actions, next_state


def _hero_hp(state: GameState) -> float:
    return sum(u.hp for u in state.units.values() if u.side == HEROES and u.alive)


def _demon_hp(state: GameState) -> float:
    return sum(u.hp for u in state.units.values() if u.side != HEROES and u.alive)


class HeroBot:
    """Үндсэн bot: нүүдэл бүрийг `score()`-оор үнэлж хамгийн өндрийг сонгоно."""

    name = "base"

    def __init__(self, seed: int | None = None, noise: float = 0.05):
        self.rng = random.Random(seed)
        self.noise = noise

    def choose(self, state: GameState) -> Action:
        acts = [a for a in legal_actions(state) if not a.is_end_turn]
        if not acts:
            return END_TURN
        return max(acts, key=lambda a: self.score(state, a) + self.rng.random() * self.noise)

    def score(self, state: GameState, action: Action) -> float:
        after = next_state(state, action)
        if after.winner == HEROES:
            return 1e6
        return (_demon_hp(state) - _demon_hp(after)) + 0.8 * (_hero_hp(after) - _hero_hp(state))


class RandomBot(HeroBot):
    name = "random"

    def choose(self, state):
        acts = [a for a in legal_actions(state) if not a.is_end_turn]
        return self.rng.choice(acts) if acts else END_TURN


class GreedyBot(HeroBot):
    """Хохирол + эдгээлтийг шууд нэмэгдүүлнэ (тэнцвэртэй тоглогч)."""
    name = "greedy"


class HealerReliantBot(HeroBot):
    """Healer-ийг байнга ашигладаг, Healer Knight-ийн ард нуугддаг тоглогч."""
    name = "healer_reliant"

    def score(self, state, action):
        s = super().score(state, action)
        if action.unit == "healer":
            if action.skill in ("heal", "shield"):
                s += 25
            knight = state.units["knight"]
            boss = state.boss.pos
            if knight.alive and dist(action.dest, knight.pos) <= 2 and \
                    dist(action.dest, boss) > dist(knight.pos, boss):
                s += 8
        return s


class MageReliantBot(HeroBot):
    """Mage-ийн бүсийн довтолгоонд найддаг, алсаас довтолдог тоглогч."""
    name = "mage_reliant"

    def score(self, state, action):
        s = super().score(state, action)
        if action.unit == "mage":
            if action.skill == "fireball":
                s += 20
            s += 2 * min(dist(action.dest, state.boss.pos), 5)
        return s


class AggressiveBot(HeroBot):
    """Боссыг шууд дайрдаг, Knight урд талд түрдэг тоглогч."""
    name = "aggressive"

    def score(self, state, action):
        s = super().score(state, action)
        if action.target_uid == "demon_lord":
            s += 10
        if action.unit == "knight":
            s += 6 - 2 * dist(action.dest, state.boss.pos)
        return s


class CautiousBot(HeroBot):
    """Боссоос хол байж, хамгаалалт (бамбай, мөсөн хана, taunt) их ашигладаг тоглогч."""
    name = "cautious"

    def score(self, state, action):
        s = super().score(state, action)
        if action.skill and SKILLS[action.skill].kind in ("shield", "wall", "taunt"):
            s += 12
        s += 1.5 * min(dist(action.dest, state.boss.pos), 6)
        return s


HERO_BOTS = {cls.name: cls for cls in (RandomBot, GreedyBot, HealerReliantBot, MageReliantBot,
                                        AggressiveBot, CautiousBot)}
