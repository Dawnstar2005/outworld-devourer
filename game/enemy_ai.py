"""1–4-р давхрын (мөн 5-р давхрын эхний үеүдийн) дайсны AI — pygame-гүй.

Боссын суралцдаг AI (`ai.BossAI`) нь 5-р давхрын Demon Lord-ийн тулаанд ажиллана. Бусад
тулаанд энэ тактикийн AI дайсан бүрийн engine-ийн хууль ёсны нүүдлийг (`unit_actions`)
`next_state()`-ээр үнэлж, хамгийн ашигтайг сонгоно — дүрэм давтаж бичихгүй.

Үнэлгээ (дайсны талаас):
  + баатарт учруулсан хохирол × баатрын аюулын түвшин (профайлын target_priority)
  + баатар унагах урамшуулал, + дуудсан дагуул, + өөрийгөө эдгээсэн (drain)
  − өөрсдийн алдсан HP
  + байрлал: ойрын тулаанч баатар руу дөхнө, холын зайн довтолгоочид зайгаа барина
Профайл өгвөл тоглогчийн найддаг баатрыг илүү онилно — 1–4-р давхарт ч «суралцана».
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Optional

from engine import DEMONS, HEROES, SKILLS, Action, GameState, apply, dist, next_state, unit_actions

from .labels import action_label

DEFAULT_PRIORITY = {"knight": 1.0, "mage": 1.3, "healer": 1.4}
KILL_BONUS = 45.0
SUMMON_VALUE = 18.0
OWN_HP_WEIGHT = 0.7
APPROACH_WEIGHT = 2.5


@dataclass
class TacticalDecision:
    actions: list
    options: list = field(default_factory=list)   # [(label, score, chosen)]
    habits: list = field(default_factory=list)
    enraged: bool = False
    random_pick: bool = False
    elapsed: float = 0.0

    def to_panel(self) -> dict:
        """«Боссын бодол» самбарын өгөгдөл (ai.Decision.to_panel()-тай ижил хэлбэр)."""
        return {"habits": list(self.habits),
                "options": [{"label": lbl, "score": round(sc, 2), "chosen": ch}
                            for lbl, sc, ch in self.options],
                "enraged": self.enraged, "random_pick": self.random_pick,
                "ms": round(self.elapsed * 1000), "mode": "tactic", "iterations": 0}


def _side_hp(state: GameState, side: str) -> float:
    return sum(u.hp for u in state.units.values() if u.side == side and u.alive)


class TacticalAI:
    def __init__(self, profile: Optional[dict] = None, seed: Optional[int] = None,
                 epsilon: float = 0.08):
        self.profile = profile or {}
        self.priority = dict(DEFAULT_PRIORITY)
        self.priority.update(self.profile.get("target_priority", {}))
        self.rng = random.Random(seed)
        self.epsilon = epsilon

    # ------------------------------------------------------------------ үнэлгээ
    def score(self, state: GameState, unit, action: Action) -> float:
        after = next_state(state, action)
        if after.winner == DEMONS:
            return 1e6
        if after.winner == HEROES:
            return -1e6
        value = 0.0
        for uid, h in state.units.items():
            if h.side != HEROES or not h.alive:
                continue
            h2 = after.units[uid]
            w = self.priority.get(h.kind, 1.0)
            value += w * (h.hp - h2.hp)
            if not h2.alive:
                value += w * KILL_BONUS
        value -= OWN_HP_WEIGHT * (_side_hp(state, DEMONS) - _side_hp(after, DEMONS))
        alive_before = sum(1 for u in state.alive_units(DEMONS))
        alive_after = sum(1 for u in after.alive_units(DEMONS))
        if action.skill and SKILLS[action.skill].kind == "summon":
            value += SUMMON_VALUE * max(0, alive_after - alive_before)
        heroes = [h.pos for h in after.alive_units(HEROES)]
        if heroes:
            d = min(dist(action.dest, p) for p in heroes)
            reach = max((SKILLS[s].range for s in unit.type.skills
                         if SKILLS[s].kind in ("damage", "drain", "area_damage")), default=1)
            want = 1 if reach <= 1 else max(2, reach - 1)
            value -= APPROACH_WEIGHT * abs(d - want)
        return value

    # ------------------------------------------------------------------ шийдвэр
    def decide(self, state: GameState) -> TacticalDecision:
        t0 = time.perf_counter()
        s = state.clone()
        side = s.side_to_act
        boss = s.boss
        actions, options, random_pick = [], [], False
        while not s.is_over and s.side_to_act == side:
            pending = [u for u in s.alive_units(side) if not u.acted]
            if not pending:
                break
            pending.sort(key=lambda u: (boss is None or u.uid != boss.uid, u.uid))
            u = pending[0]
            scored = sorted(((self.score(s, u, a), i, a) for i, a in enumerate(unit_actions(s, u))),
                            key=lambda t: (-t[0], t[1]))
            pick = 0
            if len(scored) > 1 and self.rng.random() < self.epsilon:
                pick = self.rng.randrange(1, min(3, len(scored)))
                if not actions:
                    random_pick = True
            if not actions:                       # самбарт эхний (боссын) дүрийн 3 сонголт
                options = self._panel_options(s, scored, pick)
            a = scored[pick][2]
            actions.append(a)
            apply(s, a)
        return TacticalDecision(actions=actions, options=options,
                                habits=list(self.profile.get("habits", [])),
                                enraged=state.boss_enraged, random_pick=random_pick,
                                elapsed=time.perf_counter() - t0)

    @staticmethod
    def _panel_options(s: GameState, scored: list, pick: int) -> list:
        seen, out = set(), []
        top = scored[0][0] if scored else 0.0
        for idx, (sc, _, a) in enumerate(scored):
            key = (a.skill, a.target_uid)
            if key in seen and idx != pick:
                continue
            seen.add(key)
            norm = 0.5 + 0.5 * max(-1.0, min(1.0, sc / (abs(top) + 30.0)))
            out.append((action_label(a, s), norm, idx == pick))
            if len(out) == 3:
                break
        if not any(ch for _, _, ch in out):          # санамсаргүй сонголт 3-т ороогүй бол
            sc, _, a = scored[pick]
            out[-1] = (action_label(a, s), 0.5 + 0.5 * max(-1.0, min(1.0, sc / (abs(top) + 30.0))),
                       True)
        return out
