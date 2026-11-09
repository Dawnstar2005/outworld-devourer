"""apply()-ийн events → энгийн анимаци (pygame-гүй).

Төлөв (GameState) нүүдэл хиймэгц шинэчлэгддэг. Animator зөвхөн дүрслэлийг хоцроож
харуулна: хөдөлсөн дүрийг хуучин нүднээс шинэ рүү гулсуулж, хохирол/эдгэрлийн тоог хөвүүлнэ,
үхсэн дүрийг бүдгэрүүлнэ. Хөдөлгөөн дуустал (`busy`) тоглогчийн оролтыг хүлээлгэнэ.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine import dist

from .layout import cell_center

STEP_TIME = 0.09        # нэг нүд алхах хугацаа (сек)
MIN_MOVE_TIME = 0.12
LEAP_TIME = 0.35
FLOAT_TIME = 0.9
FLOAT_RISE = 28         # px
FADE_TIME = 0.5


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
    kind: str          # "damage" | "heal" | "shield"
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


class Animator:
    def __init__(self):
        self.clear()

    def clear(self) -> None:
        self.moves: dict[str, Tween] = {}
        self.floats: list[FloatText] = []
        self.fades: list[Fade] = []

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
        self.floats = [f for f in self.floats if not f.done]
        self.fades = [f for f in self.fades if not f.done]

    def unit_center(self, uid: str, cell) -> tuple:
        """Дүрийг зурах төв (px): хөдөлж байвал завсрын байрлал."""
        tw = self.moves.get(uid)
        return tw.pos() if tw is not None else cell_center(cell)
