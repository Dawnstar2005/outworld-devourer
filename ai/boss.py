"""Боссын шийдвэр (WBS 3.2) — анхны хувилбар: нөхцөл үнэлэх функцээр.

Ээлж бүрт:
1. Demon Lord-ийн боломжит БҮХ нүүдлийг (хөдлөх/үсрэх × ур чадвар × бай) үнэлнэ.
2. Шилдэг `top_k` (5) нүүдлийг сонгоно. Тус бүрийн дараа Imp-үүд шунахайгаар нүүнэ,
   тэгээд ээлжийн эцсийн төлөвийг дахин үнэлнэ. (11/25: энэ алхмыг MCTS орлоно.)
3. Хамгийн өндөр оноотойг сонгоно. `epsilon` (10%) магадлалаар шилдэг 5-аас
   санамсаргүйг сонгоно — тоглогч ялах боломжтой байх шударга байдлын дүрэм.
4. «Боссын бодол» самбарт зориулж эхний 3 сонголт, оноо, танисан зуршлыг буцаана.

Босс тоглогчийн нүүдлийг урьдчилж харахгүй: зөвхөн одоогийн төлөв болон
профайлыг (өмнөх тулаануудаас) ашиглана.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from engine import (DEMONS, END_TURN, SKILLS, UNIT_TYPES, Action, GameState, apply,
                    area_cells, legal_actions, next_state, unit_actions)

from .evaluate import DEFAULT_PRIORITY, evaluate


@dataclass
class Option:
    action: Action
    label: str
    score: float


@dataclass
class Decision:
    actions: list                       # ээлжийн бүх нүүдэл: [боссын, imp1, imp2, ...]
    score: float
    options: list = field(default_factory=list)   # эхний 3 Option (самбарт)
    chosen: int = 0                     # options доторх сонгосон индекс
    habits: list = field(default_factory=list)    # танисан зуршил (профайлаас)
    enraged: bool = False
    random_pick: bool = False
    elapsed: float = 0.0                # секунд

    def to_panel(self) -> dict:
        """«Боссын бодол» самбарын өгөгдөл (GD үүнийг зурна)."""
        return {
            "habits": self.habits,
            "options": [{"label": o.label, "score": round(o.score, 2), "chosen": i == self.chosen}
                        for i, o in enumerate(self.options)],
            "enraged": self.enraged,
            "random_pick": self.random_pick,
            "ms": round(self.elapsed * 1000),
        }

    def to_text(self) -> str:
        lines = []
        if self.habits:
            lines.append("Тоглогчийн зуршил: " + self.habits[0])
            lines += ["                   " + h for h in self.habits[1:]]
        if self.enraged:
            lines.append("УУР ХИЛЭН: HP 30%-иас доош")
        lines.append("Сонголтууд:")
        for i, o in enumerate(self.options):
            mark = "  ← сонгосон" + (" (санамсаргүй)" if self.random_pick else "") \
                if i == self.chosen else ""
            lines.append(f"  {i + 1}. {o.label:<36} оноо {o.score:.2f}{mark}")
        return "\n".join(lines)


def _name(uid_or_kind: str, state: GameState) -> str:
    u = state.units.get(uid_or_kind)
    kind = u.kind if u else uid_or_kind
    return UNIT_TYPES[kind].name


def action_label(action: Action, state: GameState) -> str:
    """Нүүдлийг монголоор: «Сүүдрийн үсрэлт → Хараал Healer-т»."""
    if action.is_end_turn:
        return "Ээлж дуусгах"
    parts = []
    if action.leap:
        parts.append(SKILLS["shadow_leap"].name + " →")
    if action.skill is None:
        u = state.units[action.unit]
        parts.append("Хүлээх" if action.dest == u.pos and not action.leap
                     else f"Хөдлөх {action.dest}")
        return " ".join(parts)
    sk = SKILLS[action.skill]
    if action.target_uid:
        parts.append(f"{sk.name} {_name(action.target_uid, state)}-т")
    elif sk.kind == "area_damage":
        cells = set(area_cells(action.target))
        hit = [_name(e.uid, state) for e in state.alive_units()
               if e.side != state.units[action.unit].side and e.pos in cells]
        parts.append(f"{sk.name} ({' + '.join(hit)})")
    else:
        parts.append(sk.name)
    return " ".join(parts)


def _idea_key(a: Action, state: GameState):
    """Нүүдлийн «санаа»: ур чадвар + хэнд нөлөөлөх. Байрлал, бүсийн төв нүдийг үл тооно."""
    if a.skill and SKILLS[a.skill].kind == "area_damage":
        cells = set(area_cells(a.target))
        side = state.units[a.unit].side
        hit = frozenset(e.uid for e in state.alive_units() if e.side != side and e.pos in cells)
        return (a.skill, hit, a.leap)
    if a.skill is None:
        return (None, a.dest == state.units[a.unit].pos and not a.leap, a.leap)
    return (a.skill, a.target_uid, a.variant if a.skill == "ice_wall" else 0, a.leap)


class BossAI:
    """Demon Lord болон Imp-үүдийн ээлжийг шийднэ.

    profile — DQ-ийн зуршлын профайл (dict). Ашигладаг талбарууд:
        "target_priority": {"knight": 1.0, "mage": 1.2, "healer": 1.8}
        "habits": ["Healer-т их найддаг (эдгээлт 8/тулаан)", ...]   # самбарт
    profile=None бол суралцдаггүй босс (A/B туршилтын B бүлэг).
    """

    def __init__(self, profile: dict | None = None, epsilon: float = 0.1, top_k: int = 5,
                 seed: int | None = None, weights: dict | None = None):
        self.profile = profile or {}
        self.epsilon = epsilon
        self.top_k = top_k
        self.rng = random.Random(seed)
        self.weights = weights
        self.priority = dict(DEFAULT_PRIORITY)
        self.priority.update(self.profile.get("target_priority", {}))

    def evaluate(self, state: GameState) -> float:
        return evaluate(state, self.weights, self.priority)

    # ------------------------------------------------------------------ гол функц
    def decide(self, state: GameState) -> Decision:
        """Боссын талын бүтэн ээлжийг шийднэ. `state`-ийг өөрчлөхгүй."""
        if state.side_to_act != DEMONS or state.is_over:
            raise ValueError("decide() зөвхөн боссын ээлжинд")
        t0 = time.perf_counter()
        boss = state.boss
        enraged = state.boss_enraged

        # 1. Боссын бүх нүүдлийг үнэлэх
        if boss.alive and not boss.acted:
            first = unit_actions(state, boss)
        else:
            first = [None]
        scored = []
        for a in first:
            s = next_state(state, a) if a is not None else state.clone()
            scored.append((self.evaluate(s), a, s))
        scored.sort(key=lambda t: t[0], reverse=True)
        # Ижил санаатай (ур чадвар + бай) нүүдлээс зөвхөн хамгийн сайн байрлалыг үлдээнэ
        seen, distinct = set(), []
        for item in scored:
            a = item[1]
            key = None if a is None else _idea_key(a, state)
            if key in seen:
                continue
            seen.add(key)
            distinct.append(item)
        scored = distinct

        # 2. Шилдэг top_k-г Imp-үүдийн нүүдлээр гүйцээж дахин үнэлэх
        finals = []
        for _, a, s in scored[:self.top_k]:
            seq = [a] if a is not None else []
            seq += self._greedy_rest(s)
            end = state.clone()
            for x in seq:
                if end.is_over or end.side_to_act != DEMONS:
                    break
                apply(end, x)
            finals.append((self.evaluate(end), seq, a))
        finals.sort(key=lambda t: t[0], reverse=True)

        # 3. Сонгох (10% санамсаргүй — шилдэг 5-аас)
        chosen_i = 0
        random_pick = False
        if len(finals) > 1 and self.rng.random() < self.epsilon:
            chosen_i = self.rng.randrange(1, len(finals))
            random_pick = True
        score, seq, _ = finals[chosen_i]

        # 4. Самбарын өгөгдөл: эхний 3, сонгосон нь заавал орно
        shown = list(range(min(3, len(finals))))
        if chosen_i not in shown:
            shown[-1] = chosen_i
        options = [Option(finals[i][2] or END_TURN,
                          action_label(finals[i][2], state) if finals[i][2] else "—",
                          finals[i][0]) for i in shown]
        return Decision(actions=seq, score=score, options=options,
                        chosen=shown.index(chosen_i),
                        habits=list(self.profile.get("habits", [])),
                        enraged=enraged, random_pick=random_pick,
                        elapsed=time.perf_counter() - t0)

    def play_turn(self, state: GameState):
        """decide() + нүүдлүүдийг state дээр хийнэ. (Decision, events) буцаана."""
        d = self.decide(state)
        events = []
        for a in d.actions:
            if state.is_over or state.side_to_act != DEMONS:
                break
            events += apply(state, a)
        if not state.is_over and state.side_to_act == DEMONS:
            events += apply(state, END_TURN)
        return d, events

    # ------------------------------------------------------------------ Imp-үүд
    def _greedy_rest(self, state: GameState) -> list:
        """Үлдсэн Imp-үүд дараалан хамгийн сайн нүүдлээ хийнэ."""
        s = state.clone()
        seq = []
        while not s.is_over and s.side_to_act == DEMONS:
            pending = [u for u in s.alive_units(DEMONS) if not u.acted]
            if not pending:
                break
            u = pending[0]
            best = max(unit_actions(s, u), key=lambda a: self.evaluate(next_state(s, a)))
            seq.append(best)
            apply(s, best)
        return seq
