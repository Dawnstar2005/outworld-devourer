"""Тоглогчийн загвар (opponent model): «би ингэвэл тоглогч юу хийх вэ».

Босс өөрийн нэр дэвшигч төлөвлөгөө бүрийн дараа баатруудын БҮТЭН хариу ээлжийг энэ
загвараар тоглуулж үзээд, үр дүнг нь үнэлнэ (boss.py, mode="lookahead").

`GreedyHeroModel` — default загвар. Баатар бүр боломжит БҮХ нүүдлээс боссын оноог
хамгийн их бууруулах нүүдлийг сонгоно (дүрийн дарааллыг ч өөрөө сонгоно).

`PredictorHeroModel` — DQ-ийн таамаглагчаар (predictor) тоглогчийн өмнөх тулаануудын
хэв маягийг дуурайна: таамаглагчийн жинг шунахай оноотой хольж хамгийн өндрийг авна.

Тоглогчийн загвар нь тоглогчийн ЖИНХЭНЭ дараагийн нүүдлийг харахгүй — зөвхөн одоогийн
төлөв болон өмнөх log-оос сурсан зүйлийг ашиглана.
"""

from __future__ import annotations

from engine import END_TURN, HEROES, GameState, apply, next_state, unit_actions

from .evaluate import evaluate


class GreedyHeroModel:
    def __init__(self, evaluate_fn=None):
        self.evaluate = evaluate_fn or evaluate

    def choose(self, state: GameState):
        best, best_v = END_TURN, None
        blocked = state.blocked_cells()
        for u in state.alive_units(HEROES):
            if u.acted:
                continue
            for a in unit_actions(state, u, blocked):
                v = self.evaluate(next_state(state, a))
                if best_v is None or v < best_v:
                    best, best_v = a, v
        return best

    def play_turn(self, state: GameState) -> GameState:
        """Баатруудын бүтэн ээлжийг хуулбар дээр тоглуулж, шинэ төлөв буцаана."""
        s = state.clone()
        while not s.is_over and s.side_to_act == HEROES:
            apply(s, self.choose(s))
        return s


class PredictorHeroModel(GreedyHeroModel):
    """predictor(state, unit_uid, actions) -> жин. mix — таамаглагчийн хувь (0..1)."""

    def __init__(self, predictor, mix: float = 0.7, evaluate_fn=None):
        super().__init__(evaluate_fn)
        self.predictor = predictor
        self.mix = mix

    def choose(self, state: GameState):
        best, best_v = END_TURN, None
        blocked = state.blocked_cells()
        for u in state.alive_units(HEROES):
            if u.acted:
                continue
            acts = unit_actions(state, u, blocked)
            probs = self.predictor(state, u.uid, acts) or [1.0] * len(acts)
            top = max(probs) or 1.0
            for a, p in zip(acts, probs):
                greedy = 1.0 - self.evaluate(next_state(state, a))
                v = self.mix * (p / top) + (1.0 - self.mix) * greedy
                if best_v is None or v > best_v:
                    best, best_v = a, v
        return best
