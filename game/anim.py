"""apply()-ийн events → энгийн анимаци (pygame-гүй).

Төлөв (GameState) нүүдэл хиймэгц шинэчлэгддэг. Animator зөвхөн дүрслэлийг хоцроож
харуулна: хөдөлсөн дүрийг хуучин нүднээс шинэ рүү гулсуулж, хохирол/эдгэрлийн тоог хөвүүлнэ,
үхсэн дүрийг бүдгэрүүлнэ. Хөдөлгөөн дуустал (`busy`) тоглогчийн оролтыг хүлээлгэнэ.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine import SKILLS, area_cells, dist

from .labels import skill_name
from .layout import cell_center

STEP_TIME = 0.09        # нэг нүд алхах хугацаа (сек)
MIN_MOVE_TIME = 0.12
LEAP_TIME = 0.35
FLOAT_TIME = 0.9
FLOAT_RISE = 28         # px
FADE_TIME = 0.5
FLASH_TIME = 0.5


@dataclass
class Tween:
    start: tuple
    end: tuple
    duration: float
    t: float = 0.0

    @property
    def done(self) -> bool:
        return self.t >= self.duration

    @property
    def progress(self) -> float:
        return 1.0 if self.duration <= 0 else min(1.0, self.t / self.duration)

    def pos(self):
        p = self.progress
        p = p * p * (3 - 2 * p)   # smoothstep
        return (self.start[0] + (self.end[0] - self.start[0]) * p,
                self.start[1] + (self.end[1] - self.start[1]) * p)


@dataclass
class FloatText:
    text: str
    kind: str          # "damage" | "heal" | "shield" | "skill"
    origin: tuple      # px
    t: float = 0.0

    @property
    def done(self) -> bool:
        return self.t >= FLOAT_TIME

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - self.t / FLOAT_TIME)

    def pos(self):
        return (self.origin[0], self.origin[1] - FLOAT_RISE * min(1.0, self.t / FLOAT_TIME))


@dataclass
class Fade:
    uid: str
    kind: str
    cell: tuple
    t: float = 0.0

    @property
    def done(self) -> bool:
        return self.t >= FADE_TIME

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - self.t / FADE_TIME)


@dataclass
class Flash:
    """Ур чадвар онох үед нүднүүдийг түр гэрэлтүүлэх."""
    cells: list
    kind: str          # "harm" | "help" | "wall"
    t: float = 0.0

    @property
    def done(self) -> bool:
        return self.t >= FLASH_TIME

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - self.t / FLASH_TIME)


HARM_KINDS = ("damage", "area_damage", "curse")


class Animator:
    def __init__(self):
        self.clear()

    def clear(self) -> None:
        self.moves: dict[str, Tween] = {}
        self.floats: list[FloatText] = []
        self.fades: list[Fade] = []
        self.flashes: list[Flash] = []

    @property
    def busy(self) -> bool:
        """Хөдөлгөөн явагдаж байна (хөвөх тоо, бүдгэрэлт оролтыг хаахгүй)."""
        return bool(self.moves)

    def push(self, events: list, state) -> None:
        for ev in events:
            t = ev["type"]
            if t == "move":
                if ev.get("leap"):
                    dur = LEAP_TIME
                else:
                    dur = max(MIN_MOVE_TIME, STEP_TIME * dist(ev["from"], ev["to"]))
                self.moves[ev["unit"]] = Tween(cell_center(ev["from"]), cell_center(ev["to"]), dur)
            elif t == "damage":
                pos = self._unit_center(ev["dst"], state)
                if ev.get("absorbed"):
                    self.floats.append(FloatText(f"-{ev['absorbed']}", "shield",
                                                 (pos[0], pos[1] - 14)))
                self.floats.append(FloatText(f"-{ev['amount']}", "damage", pos))
            elif t == "heal":
                self.floats.append(FloatText(f"+{ev['amount']}", "heal",
                                             self._unit_center(ev["dst"], state)))
            elif t == "skill":
                caster = state.units[ev["unit"]]
                cx, cy = cell_center(caster.pos)
                self.floats.append(FloatText(skill_name(ev["skill"]), "skill", (cx, cy - 20)))
                kind = SKILLS[ev["skill"]].kind
                if kind == "area_damage":
                    self.flashes.append(Flash(area_cells(ev["target"]), "harm"))
                elif ev.get("target") is not None and kind != "wall":
                    self.flashes.append(Flash([ev["target"]],
                                              "harm" if kind in HARM_KINDS else "help"))
            elif t == "wall":
                self.flashes.append(Flash(list(ev["cells"]), "wall"))
            elif t == "taunt":
                cells = [state.units[u].pos for u in ev["targets"] if state.units[u].alive]
                if cells:
                    self.flashes.append(Flash(cells, "harm"))
            elif t == "death":
                u = state.units[ev["unit"]]
                self.fades.append(Fade(u.uid, u.kind, u.pos))

    @staticmethod
    def _unit_center(uid, state):
        return cell_center(state.units[uid].pos)

    def update(self, dt: float) -> None:
        for uid in list(self.moves):
            tw = self.moves[uid]
            tw.t += dt
            if tw.done:
                del self.moves[uid]
        for f in self.floats:
            f.t += dt
        for f in self.fades:
            f.t += dt
        for f in self.flashes:
            f.t += dt
        self.floats = [f for f in self.floats if not f.done]
        self.fades = [f for f in self.fades if not f.done]
        self.flashes = [f for f in self.flashes if not f.done]

    def unit_center(self, uid: str, cell) -> tuple:
        """Дүрийг зурах төв (px): хөдөлж байвал завсрын байрлал."""
        tw = self.moves.get(uid)
        return tw.pos() if tw is not None else cell_center(cell)
