"""Боссын (чөтгөрүүдийн) ээлжийг UI царцаахгүйгээр тооцоолох (pygame-гүй).

Хянагч (controller) нь `decide(state) -> decision` интерфейстэй:
    decision.actions    — ээлжийн нүүдлүүд дарааллаар [боссын, imp1, imp2, ...]
    decision.to_panel() — «Боссын бодол» самбарын dict (байхгүй бол None)
`ai.BossAI` яг ийм интерфейстэй. `ai/` main-д ороогүй үед `PlaceholderBoss` ажиллана.

`BossDriver` нь `decide()`-г тусдаа thread-д ажиллуулж, үндсэн давталт `poll()`-оор
үр дүнг шалгана. Тооцоолол төлөвийн хуулбар дээр явагдах тул UI-тай зөрчилдөхгүй.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from engine import Action, GameState, apply, dist, unit_actions


@dataclass
class PlaceholderDecision:
    actions: list = field(default_factory=list)

    def to_panel(self):
        return None


class PlaceholderBoss:
    """Түр босс: `ai/` main-д merge хийгдэх хүртэл тоглоомыг туршихад.

    Ур чадвар хэрэглэж болох бол санамсаргүй нэгийг, үгүй бол хамгийн ойрын баатар руу
    дөхөх нүүдлийг сонгоно. Бүх нүүдэл engine.unit_actions()-аас ирнэ.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def decide(self, state: GameState) -> PlaceholderDecision:
        s = state.clone()
        side = s.side_to_act
        actions = []
        while not s.is_over and s.side_to_act == side:
            pending = [u for u in s.alive_units(side) if not u.acted]
            if not pending:
                break
            a = self._choose(s, pending[0])
            actions.append(a)
            apply(s, a)
        return PlaceholderDecision(actions)

    def _choose(self, s: GameState, unit) -> Action:
        acts = unit_actions(s, unit)
        with_skill = [a for a in acts if a.skill is not None]
        if with_skill:
            return self.rng.choice(with_skill)
        enemies = [u.pos for u in s.alive_units() if u.side != unit.side]
        if not enemies:
            return acts[0]
        return min(acts, key=lambda a: (min(dist(a.dest, e) for e in enemies), self.rng.random()))


def make_boss(mode: str = "eval", profile: Optional[dict] = None, seed: Optional[int] = None):
    """`ai.BossAI` байвал түүнийг, үгүй бол PlaceholderBoss буцаана."""
    try:
        from ai import BossAI
    except ModuleNotFoundError as e:
        if e.name != "ai":
            raise
        return PlaceholderBoss(seed=seed)
    return BossAI(profile=profile, mode=mode, seed=seed)


class BossDriver:
    """`controller.decide(state)`-г тусдаа thread-д ажиллуулна."""

    def __init__(self, controller):
        self.controller = controller
        self._lock = threading.Lock()
        self._gen = 0              # cancel/шинэ start хийхэд хуучин үр дүнг хаяна
        self._out = None           # (gen, decision, error)
        self._started_at: Optional[float] = None

    @property
    def thinking(self) -> bool:
        return self._started_at is not None

    @property
    def elapsed(self) -> float:
        return 0.0 if self._started_at is None else time.perf_counter() - self._started_at

    def start(self, state: GameState) -> None:
        with self._lock:
            self._gen += 1
            gen = self._gen
            self._out = None
            self._started_at = time.perf_counter()
        t = threading.Thread(target=self._run, args=(gen, state.clone()), daemon=True,
                             name="boss-think")
        t.start()

    def _run(self, gen: int, state: GameState) -> None:
        try:
            out = (gen, self.controller.decide(state), None)
        except Exception as e:  # алдааг үндсэн thread poll()-оор хүлээж авна
            out = (gen, None, e)
        with self._lock:
            if gen == self._gen:
                self._out = out

    def poll(self):
        """Шийдвэр бэлэн бол буцаана (нэг л удаа), бэлэн биш бол None. Алдааг дахин шиднэ."""
        with self._lock:
            if self._out is None:
                return None
            _, decision, error = self._out
            self._out = None
            self._started_at = None
        if error is not None:
            raise error
        return decision

    def cancel(self) -> None:
        """Тооцоолж буй шийдвэрийг хаяна (жишээ нь шинэ тоглолт эхлэхэд)."""
        with self._lock:
            self._gen += 1
            self._out = None
            self._started_at = None
