"""Ур чадварын VFX (визуал эффект): тоосонцор + өндөр түвшний эффект (pygame-гүй симуляци).

Энд зөвхөн симуляци бий — байрлал, хурд, амьдрах хугацаа. Зурах хэсэг `vfx_draw.py`-д (pygame).
`Vfx.push(events, state)` нь `engine.apply()`-ийн events-ийг эффект болгоно. Эффектийг
**ур чадварын төрлөөр (kind)** сонгоно, өнгийг ур чадвар бүрээр (PALETTES) тохируулна —
тиймээс шинэ ур чадвар нэмэхэд kind нь таарвал эффект өөрөө гарна, үл мэдэгдэх kind бол
ерөнхий ид шидийн дэлбэрэлт болно.

Оролтыг хаахгүй: `Animator.busy` зөвхөн хөдөлгөөнөөс хамаарна, VFX зөвхөн гоёл.
FPS-ийг хамгаалах тул тоосонцор MAX_PARTICLES, эффект MAX_EFFECTS-ээр хязгаарлагдана.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

from engine import SKILLS, area_cells

from .layout import cell_center

MAX_PARTICLES = 800
MAX_EFFECTS = 400
PROJECTILE_TIME = 0.25     # сумны нислэгийн хугацаа (сек)
LEAP_VFX_TIME = 0.35       # anim.LEAP_TIME-тай нийцнэ
TAU = math.tau

Color = tuple


# ----------------------------------------------------------------------- палитр
@dataclass(frozen=True)
class Pal:
    main: Color
    accent: Color = (255, 255, 255)
    dark: Optional[Color] = None      # бүдүүн утаа (хар/бараан) — гэрэлтдэггүй
    style: str = ""                   # kind доторх дэд хэв маяг: "claw", "hell", ...


DEFAULT_PAL = Pal((190, 120, 255), (255, 235, 255), (40, 20, 60))

PALETTES = {
    "sword": Pal((190, 215, 255), (255, 255, 255)),
    "claw": Pal((255, 80, 70), (255, 200, 170), style="claw"),
    "dark_flame": Pal((150, 60, 230), (230, 170, 255), (25, 8, 40)),
    "fireball": Pal((255, 140, 40), (255, 225, 120), (60, 40, 30)),
    "hellfire": Pal((255, 50, 30), (255, 150, 90), (12, 6, 8), style="hell"),
    "heal": Pal((80, 255, 140), (220, 255, 230)),
    "shield": Pal((80, 160, 255), (200, 230, 255)),
    "curse": Pal((170, 70, 230), (230, 160, 255), (35, 10, 50)),
    "taunt": Pal((255, 195, 70), (255, 245, 200)),
    "ice_wall": Pal((150, 225, 255), (240, 255, 255)),
    "summon_imp": Pal((230, 70, 40), (255, 190, 80), (30, 10, 10)),
    "shadow_leap": Pal((110, 60, 160), (190, 150, 230), (20, 10, 30)),
}

KIND_PALETTES = {                 # шинэ ур чадварын өгөгдмөл өнгө
    "damage": Pal((255, 170, 90), (255, 240, 200)),
    "area_damage": Pal((255, 130, 50), (255, 220, 120), (50, 30, 20)),
    "drain": Pal((235, 30, 55), (255, 150, 160), (40, 5, 10)),
    "heal": PALETTES["heal"], "shield": PALETTES["shield"], "curse": PALETTES["curse"],
    "taunt": PALETTES["taunt"], "wall": PALETTES["ice_wall"], "summon": PALETTES["summon_imp"],
    "leap": PALETTES["shadow_leap"],
}


def palette(skill_id: str, kind: str) -> Pal:
    return PALETTES.get(skill_id) or KIND_PALETTES.get(kind) or DEFAULT_PAL


# ----------------------------------------------------------------------- тоосонцор
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "gravity", "drag", "life", "age", "size0", "size1",
                 "color", "additive", "streak", "layer")

    def __init__(self, x, y, vx, vy, life, size0, size1, color, gravity, drag, additive,
                 streak, layer):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life, self.age = life, 0.0
        self.size0, self.size1 = size0, size1
        self.color, self.gravity, self.drag = color, gravity, drag
        self.additive, self.streak, self.layer = additive, streak, layer

    @property
    def t(self) -> float:
        return min(1.0, self.age / self.life)

    @property
    def alpha(self) -> float:
        return max(0.0, 1.0 - self.t) ** 0.8

    @property
    def size(self) -> float:
        return self.size0 + (self.size1 - self.size0) * self.t

    def step(self, dt: float) -> None:
        self.age += dt
        k = max(0.0, 1.0 - self.drag * dt)
        self.vx *= k
        self.vy = self.vy * k + self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def dead(self) -> bool:
        return self.age >= self.life


# ----------------------------------------------------------------------- эффектүүд
class Effect:
    """Хоцролт (delay) + амьдрах хугацаа. `shapes()` нь зурах примитивүүдийг буцаана:
    ("glow", layer, x, y, r, color, alpha, additive), ("ring", layer, x, y, r, w, color, alpha),
    ("line", layer, x0, y0, x1, y1, w, color, alpha)."""

    def __init__(self, life: float, delay: float = 0.0, layer: str = "over"):
        self.life, self.delay, self.layer = life, delay, layer
        self.age = 0.0

    @property
    def t(self) -> float:               # хоцролтыг хасч тоосон хугацаа
        return self.age - self.delay

    @property
    def active(self) -> bool:
        return self.age >= self.delay

    @property
    def done(self) -> bool:
        return self.age >= self.delay + self.life

    @property
    def p(self) -> float:               # 0..1
        return min(1.0, max(0.0, self.t / self.life)) if self.life > 0 else 1.0

    def env(self, fade_in: float = 0.12, fade_out: float = 0.35) -> float:
        """Гарч ирээд бүдгэрэх дугтуй (0..1)."""
        p = self.p
        return min(1.0, p / fade_in if fade_in else 1.0, (1 - p) / fade_out if fade_out else 1.0)

    def update(self, dt: float, vfx: "Vfx") -> None:
        self.age += dt
        if self.active:
            self.tick(dt, vfx)

    def tick(self, dt: float, vfx: "Vfx") -> None:
        pass

    def shapes(self) -> list:
        return []


class Later(Effect):
    """Хоцорч нэг удаа функц дуудна."""

    def __init__(self, delay: float, fn: Callable[["Vfx"], None]):
        super().__init__(0.0, delay)
        self.fn = fn
        self.fired = False

    def tick(self, dt, vfx):
        if not self.fired:
            self.fired = True
            self.fn(vfx)

    @property
    def done(self) -> bool:
        return self.fired


class Projectile(Effect):
    def __init__(self, src, dst, pal: Pal, dur: float = PROJECTILE_TIME, delay: float = 0.0,
                 on_arrive: Optional[Callable[["Vfx"], None]] = None, size: float = 11.0):
        super().__init__(dur, delay)
        self.src, self.dst, self.pal, self.on_arrive, self.size = src, dst, pal, on_arrive, size
        self.arrived = False

    @property
    def pos(self) -> tuple:
        p = self.p
        return (self.src[0] + (self.dst[0] - self.src[0]) * p,
                self.src[1] + (self.dst[1] - self.src[1]) * p)

    def tick(self, dt, vfx):
        x, y = self.pos
        vfx.emit(x, y, 2, speed=(10, 50), life=(0.18, 0.35), size=(5, 1), color=self.pal.main)
        if self.pal.dark:
            vfx.emit(x, y, 1, speed=(5, 30), life=(0.25, 0.45), size=(6, 2),
                     color=self.pal.dark, additive=False)
        if self.t >= self.life and not self.arrived:
            self.arrived = True
            if self.on_arrive:
                self.on_arrive(vfx)

    def shapes(self):
        if not self.active or self.arrived:
            return []
        x, y = self.pos
        return [("glow", "over", x, y, self.size * 2.2, self.pal.main, 0.8, True),
                ("glow", "over", x, y, self.size, self.pal.accent, 1.0, True)]


class Ring(Effect):
    def __init__(self, center, r0, r1, life, pal_color, width=4, delay=0.0, layer="under",
                 alpha=0.9):
        super().__init__(life, delay, layer)
        self.c, self.r0, self.r1, self.color, self.width, self.alpha = \
            center, r0, r1, pal_color, width, alpha

    def shapes(self):
        if not self.active:
            return []
        p = self.p
        e = 1 - (1 - p) ** 2          # easeOut
        r = self.r0 + (self.r1 - self.r0) * e
        return [("ring", self.layer, self.c[0], self.c[1], r, max(1, int(self.width * (1 - p))),
                 self.color, self.alpha * (1 - p))]


class Flash(Effect):
    """Кадр дахь гэрлийн толбо."""

    def __init__(self, center, r, color, life=0.25, delay=0.0, layer="over"):
        super().__init__(life, delay, layer)
        self.c, self.r, self.color = center, r, color

    def shapes(self):
        if not self.active:
            return []
        p = self.p
        return [("glow", self.layer, self.c[0], self.c[1], self.r * (0.6 + 0.6 * p),
                 self.color, 1 - p, True)]


class Slash(Effect):
    """Хүчтэй сэлмийн нум."""

    def __init__(self, center, radius, angle, sweep, pal: Pal, life=0.3, delay=0.0):
        super().__init__(life, delay)
        self.c, self.radius, self.angle, self.sweep, self.pal = center, radius, angle, sweep, pal

    def shapes(self):
        if not self.active:
            return []
        p = self.p
        head = min(1.0, p / 0.4)
        fade = 1.0 if p < 0.4 else max(0.0, 1 - (p - 0.4) / 0.6)
        a0 = self.angle - self.sweep
        n = 10
        out = []
        for i in range(n):
            u0, u1 = i / n, (i + 1) / n
            if u0 > head:
                break
            u1 = min(u1, head)
            pts = []
            for u in (u0, u1):
                a = a0 + 2 * self.sweep * u
                pts.append((self.c[0] + math.cos(a) * self.radius,
                            self.c[1] + math.sin(a) * self.radius))
            w = 1 + 7 * math.sin(math.pi * (u0 + u1) / 2)
            out.append(("line", "over", pts[0][0], pts[0][1], pts[1][0], pts[1][1],
                        int(w) + 2, self.pal.main, 0.6 * fade))
            out.append(("line", "over", pts[0][0], pts[0][1], pts[1][0], pts[1][1],
                        max(1, int(w * 0.5)), self.pal.accent, fade))
        return out


class Scratch(Effect):
    """Сарвуунаас гарсан гурван зураас."""

    def __init__(self, center, angle, pal: Pal, life=0.32, delay=0.0):
        super().__init__(life, delay)
        self.c, self.angle, self.pal = center, angle, pal

    def shapes(self):
        if not self.active:
            return []
        p = self.p
        grow = min(1.0, p / 0.3)
        fade = 1.0 if p < 0.4 else max(0.0, 1 - (p - 0.4) / 0.6)
        ux, uy = math.cos(self.angle), math.sin(self.angle)
        px, py = -uy, ux
        out = []
        for k in (-1, 0, 1):
            ox, oy = self.c[0] + px * k * 11, self.c[1] + py * k * 11
            L = 26 * (1.2 if k == 0 else 1.0)
            x0, y0 = ox - ux * L, oy - uy * L
            x1, y1 = x0 + ux * 2 * L * grow, y0 + uy * 2 * L * grow
            out.append(("line", "over", x0, y0, x1, y1, 5, self.pal.main, 0.6 * fade))
            out.append(("line", "over", x0, y0, x1, y1, 2, self.pal.accent, fade))
        return out


class Beam(Effect):
    """Урсдаг цус сорох туяа: src → dst, туяан дээр тоосонцор урсана."""

    def __init__(self, src, dst, pal: Pal, life=0.6, delay=0.0):
        super().__init__(life, delay)
        self.src, self.dst, self.pal = src, dst, pal

    def tick(self, dt, vfx):
        e = self.env()
        n = 3 if e > 0.3 else 1
        d = math.dist(self.src, self.dst) or 1.0
        for _ in range(n):
            u = random.random() * 0.3
            x = self.src[0] + (self.dst[0] - self.src[0]) * u
            y = self.src[1] + (self.dst[1] - self.src[1]) * u
            sp = d / 0.28
            vfx.emit_one(x + random.uniform(-8, 8), y + random.uniform(-8, 8),
                         (self.dst[0] - x) / d * sp, (self.dst[1] - y) / d * sp,
                         life=0.3, size=(5, 2), color=self.pal.main, drag=0.0)

    def shapes(self):
        if not self.active:
            return []
        e = self.env()
        n = 14
        pts = []
        for i in range(n + 1):
            u = i / n
            off = math.sin(self.t * 22 + u * 9) * 7 * math.sin(math.pi * u)
            dx, dy = self.dst[0] - self.src[0], self.dst[1] - self.src[1]
            d = math.hypot(dx, dy) or 1.0
            pts.append((self.src[0] + dx * u - dy / d * off, self.src[1] + dy * u + dx / d * off))
        out = []
        for a, b in zip(pts, pts[1:]):
            out.append(("line", "over", a[0], a[1], b[0], b[1], 7, self.pal.main, 0.45 * e))
            out.append(("line", "over", a[0], a[1], b[0], b[1], 2, self.pal.accent, 0.9 * e))
        out.append(("glow", "over", self.dst[0], self.dst[1], 26, self.pal.main, 0.7 * e, True))
        return out


class Bubble(Effect):
    """Бамбайн хөөс: нэг цохилж байгаа цагираг."""

    def __init__(self, center, pal: Pal, life=0.8, delay=0.0):
        super().__init__(life, delay)
        self.c, self.pal = center, pal

    def shapes(self):
        if not self.active:
            return []
        e = self.env(0.15, 0.3)
        pulse = math.sin(self.t * 16)
        x, y = self.c
        return [("glow", "over", x, y, 36, self.pal.main, 0.35 * e, True),
                ("ring", "over", x, y, 31 + 3 * pulse, 3, self.pal.accent, 0.95 * e),
                ("ring", "over", x, y, 27 - 2 * pulse, 2, self.pal.main, 0.7 * e)]


class Runes(Effect):
    """Хараалын дүрс үсэг эргэлдэнэ + утаа."""

    def __init__(self, center, pal: Pal, life=0.5, delay=0.0):
        super().__init__(life, delay)
        self.c, self.pal = center, pal

    def tick(self, dt, vfx):
        x, y = self.c
        vfx.emit(x + random.uniform(-20, 20), y + 18, 1, speed=(0, 10), life=(0.4, 0.6),
                 size=(7, 13), color=self.pal.dark or self.pal.main, additive=False, gravity=-70,
                 angle=(-math.pi / 2 - 0.4, -math.pi / 2 + 0.4))
        if random.random() < 0.6:
            vfx.emit(x, y, 1, speed=(20, 40), life=(0.4, 0.7), size=(4, 1), color=self.pal.main,
                     gravity=-40)

    def shapes(self):
        if not self.active:
            return []
        e = self.env(0.2, 0.3)
        out = [("glow", "over", self.c[0], self.c[1], 34, self.pal.main, 0.25 * e, True)]
        for i in range(4):
            a = self.t * 3.2 + i * TAU / 4
            r = 30 + 4 * math.sin(self.t * 6 + i)
            gx, gy = self.c[0] + math.cos(a) * r, self.c[1] + math.sin(a) * r * 0.9
            s = 7
            rot = a * 2
            for k in range(3):                    # үсэг: гурван зураас од
                aa = rot + k * math.pi / 3
                out.append(("line", "over", gx - math.cos(aa) * s, gy - math.sin(aa) * s,
                            gx + math.cos(aa) * s, gy + math.sin(aa) * s, 2,
                            self.pal.accent if k == 0 else self.pal.main, 0.95 * e))
            out.append(("glow", "over", gx, gy, 9, self.pal.main, 0.5 * e, True))
        return out


class Portal(Effect):
    """Дуудлагын ээрэх порталь."""

    def __init__(self, center, pal: Pal, life=0.8, delay=0.0):
        super().__init__(life, delay)
        self.c, self.pal = center, pal

    def tick(self, dt, vfx):
        if random.random() < 0.7:
            a = random.random() * TAU
            vfx.emit_one(self.c[0] + math.cos(a) * 34, self.c[1] + math.sin(a) * 34,
                         -math.cos(a) * 60, -math.sin(a) * 60 - 20, life=0.35, size=(4, 1),
                         color=self.pal.accent)

    def shapes(self):
        if not self.active:
            return []
        e = self.env(0.2, 0.3)
        x, y = self.c
        out = [("glow", "under", x, y, 38, self.pal.dark or self.pal.main, 0.5 * e, True),
               ("glow", "under", x, y, 30, self.pal.main, 0.5 * e, True)]
        for i in range(3):
            u = (self.t * 1.8 + i / 3) % 1.0
            out.append(("ring", "under", x, y, 34 * (1 - u) + 4, 2, self.pal.main, 0.9 * e * (1 - u)))
        for i in range(6):
            a = self.t * 9 + i * TAU / 6
            r = 30 * (1 - self.p * 0.5) * (0.6 + 0.4 * math.sin(self.t * 5 + i))
            out.append(("glow", "over", x + math.cos(a) * r, y + math.sin(a) * r * 0.8, 8,
                        self.pal.accent, 0.9 * e, True))
        return out


class Emitter(Effect):
    """Тогтмол хурдаар тоосонцор үүсгэгч: fn(vfx, t)."""

    def __init__(self, life, rate, fn, delay=0.0, layer="over"):
        super().__init__(life, delay, layer)
        self.rate, self.fn, self.acc = rate, fn, 0.0

    def tick(self, dt, vfx):
        self.acc += self.rate * dt
        while self.acc >= 1.0:
            self.acc -= 1.0
            self.fn(vfx, self.p)


# ----------------------------------------------------------------------- Vfx
class Vfx:
    def __init__(self, seed: int = 0):
        self.particles: list[Particle] = []
        self.effects: list[Effect] = []
        self.rng = random.Random(seed)
        self._covered: set = set()      # сүүлийн ур чадвар аль нүдэнд өөрийн цохилт үүсгэсэн

    # ---- амьдрал
    def clear(self) -> None:
        self.particles.clear()
        self.effects.clear()
        self._covered = set()

    @property
    def count(self) -> int:
        return len(self.effects) + len(self.particles)

    def add(self, fx: Effect) -> Optional[Effect]:
        if len(self.effects) >= MAX_EFFECTS:
            return None
        self.effects.append(fx)
        return fx

    def later(self, delay: float, fn: Callable[["Vfx"], None]) -> None:
        self.add(Later(delay, fn))

    def update(self, dt: float) -> None:
        dt = min(dt, 0.1)               # урт кадрт тэсрэлт болохоос сэргийлнэ
        for fx in list(self.effects):
            fx.update(dt, self)
        self.effects = [fx for fx in self.effects if not fx.done]
        for p in self.particles:
            p.step(dt)
        self.particles = [p for p in self.particles if not p.dead]

    # ---- тоосонцор
    def emit_one(self, x, y, vx, vy, life, size=(4, 0), color=(255, 255, 255), gravity=0.0,
                 drag=1.5, additive=True, streak=False, layer="over") -> None:
        if len(self.particles) >= MAX_PARTICLES:
            return
        self.particles.append(Particle(x, y, vx, vy, life, size[0], size[1], color, gravity,
                                       drag, additive, streak, layer))

    def emit(self, x, y, n, speed=(40, 160), life=(0.3, 0.6), size=(4, 0), color=(255, 255, 255),
             gravity=0.0, drag=2.0, additive=True, streak=False, layer="over",
             angle=(0.0, TAU)) -> None:
        """n тоосонцрыг тойрогт/сектор дотор тараана. Дүүрч байвал (>60%) тоог хасна."""
        if len(self.particles) > MAX_PARTICLES * 0.6:
            n = (n + 1) // 2
        r = self.rng
        for _ in range(n):
            a = r.uniform(*angle)
            s = r.uniform(*speed)
            self.emit_one(x, y, math.cos(a) * s, math.sin(a) * s, r.uniform(*life), size, color,
                          gravity, drag, additive, streak, layer)

    def shapes(self, layer: str) -> list:
        out = []
        for fx in self.effects:
            out.extend(s for s in fx.shapes() if s[1] == layer)
        return out

    # ---- events → эффект
    def push(self, events: list, state) -> None:
        for ev in events:
            h = _EVENT_HANDLERS.get(ev["type"])
            if h is not None:
                h(self, ev, state)


# ----------------------------------------------------------------------- туслах
def _unit_px(state, uid) -> tuple:
    return cell_center(state.units[uid].pos)


def _dir(a, b) -> tuple:
    d = math.dist(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d) if d > 1e-6 else (0.0, -1.0)


def hit_sparks(v: Vfx, c, pal: Pal, n: int = 12) -> None:
    v.emit(c[0], c[1], n, speed=(80, 230), life=(0.18, 0.4), size=(3, 0), color=pal.accent,
           drag=3.0, gravity=120, streak=True)
    v.emit(c[0], c[1], n // 2, speed=(30, 100), life=(0.2, 0.4), size=(5, 1), color=pal.main)
    v.add(Flash(c, 30, pal.main, 0.18))


def magic_burst(v: Vfx, c, pal: Pal, n: int = 22) -> None:
    v.add(Ring(c, 6, 46, 0.4, pal.main, 4))
    v.add(Flash(c, 40, pal.main, 0.3))
    v.emit(c[0], c[1], n, speed=(40, 180), life=(0.3, 0.6), size=(4, 0), color=pal.main, drag=2.5)
    v.emit(c[0], c[1], n // 3, speed=(20, 90), life=(0.3, 0.6), size=(3, 0), color=pal.accent)


def _target_px(v, ev, state) -> tuple:
    if ev.get("target") is not None:
        return cell_center(ev["target"])
    if ev.get("target_uid") in state.units:
        return _unit_px(state, ev["target_uid"])
    return _unit_px(state, ev["unit"])


# ----------------------------------------------------------------------- kind → эффект
def _fx_damage(v, ev, state, sk, pal, src, dst):
    v._covered = {ev["target"]} if ev.get("target") is not None else set()
    if sk.range <= 1:                               # ойрын байлдаа
        ang = math.atan2(*reversed(_dir(src, dst)))
        if pal.style == "claw":
            v.add(Scratch(dst, ang + math.pi / 5, pal))
        else:
            dx, dy = _dir(src, dst)
            v.add(Slash((dst[0] - dx * 36, dst[1] - dy * 36), 42, ang, 0.9, pal))
        v.later(0.08, lambda vv: hit_sparks(vv, dst, pal))
        return

    def impact(vv):                                 # холын дайралт: сум → цохилт
        hit_sparks(vv, dst, pal, 16)
        vv.add(Ring(dst, 6, 42, 0.35, pal.main, 4))
        if pal.dark:
            vv.emit(dst[0], dst[1], 8, speed=(20, 90), life=(0.35, 0.6), size=(8, 14),
                    color=pal.dark, additive=False, gravity=-40)
            vv.add(Emitter(0.3, 40, lambda v2, p: v2.emit(
                dst[0] + v2.rng.uniform(-18, 18), dst[1] + 10, 1, speed=(10, 40), life=(0.3, 0.5),
                size=(6, 1), color=pal.main, gravity=-120,
                angle=(-math.pi / 2 - 0.3, -math.pi / 2 + 0.3))))
    v.add(Projectile(src, dst, pal, on_arrive=impact))


def _fx_area(v, ev, state, sk, pal, src, dst):
    cells = area_cells(ev["target"]) if ev.get("target") is not None else []
    v._covered = set(cells)

    def explode(vv):
        vv.add(Ring(dst, 10, 125, 0.5, pal.main, 6))
        vv.add(Flash(dst, 100, pal.main, 0.4))
        vv.add(Flash(dst, 50, pal.accent, 0.25))
        for c in cells:
            cx, cy = cell_center(c)
            if pal.style == "hell":                 # тамын гал: дээш өргөгдөх улаан/хар дөл
                vv.add(Emitter(0.55, 34, lambda v2, p, cx=cx, cy=cy: (
                    v2.emit(cx + v2.rng.uniform(-24, 24), cy + 22, 1, speed=(5, 30),
                            life=(0.35, 0.6), size=(8, 2), color=pal.main, gravity=-170,
                            angle=(-math.pi / 2 - 0.2, -math.pi / 2 + 0.2)),
                    v2.rng.random() < 0.4 and v2.emit(
                        cx + v2.rng.uniform(-20, 20), cy, 1, speed=(5, 25), life=(0.4, 0.7),
                        size=(8, 14), color=pal.dark, additive=False, gravity=-90,
                        angle=(-math.pi / 2 - 0.3, -math.pi / 2 + 0.3)))))
                vv.add(Flash((cx, cy), 36, pal.main, 0.35))
            else:                                   # галт бөмбөг: тойрог тэсрэлт
                vv.emit(cx, cy, 9, speed=(50, 200), life=(0.25, 0.55), size=(6, 0),
                        color=pal.main, drag=2.5, gravity=60)
                vv.emit(cx, cy, 4, speed=(30, 120), life=(0.25, 0.5), size=(4, 0),
                        color=pal.accent)
        vv.emit(dst[0], dst[1], 8, speed=(100, 260), life=(0.3, 0.6), size=(3, 0), color=pal.accent,
                streak=True, gravity=150)
    v.add(Projectile(src, dst, pal, on_arrive=explode, size=13))


def _fx_drain(v, ev, state, sk, pal, src, dst):
    v._covered = {ev["target"]} if ev.get("target") is not None else set()
    hit_sparks(v, dst, pal, 10)
    v.add(Beam(dst, src, pal))
    v.later(0.3, lambda vv: (vv.emit(src[0], src[1], 10, speed=(20, 90), life=(0.3, 0.55),
                                     size=(4, 0), color=pal.accent, gravity=-60),
                             vv.add(Flash(src, 34, pal.main, 0.3))))


def _fx_heal(v, ev, state, sk, pal, src, dst):
    v.add(Ring(dst, 8, 38, 0.6, pal.main, 3))
    v.add(Flash(dst, 40, pal.main, 0.5))
    v.add(Emitter(0.75, 36, lambda vv, p: vv.emit_one(
        dst[0] + vv.rng.uniform(-26, 26), dst[1] + vv.rng.uniform(-6, 26), 0,
        -vv.rng.uniform(40, 90), life=vv.rng.uniform(0.4, 0.7), size=(4, 0),
        color=pal.main if vv.rng.random() < 0.7 else pal.accent, drag=0.3)))


def _fx_shield(v, ev, state, sk, pal, src, dst):
    v.add(Bubble(dst, pal))
    v.add(Ring(dst, 10, 44, 0.5, pal.main, 4))
    v.emit(dst[0], dst[1], 10, speed=(20, 70), life=(0.3, 0.6), size=(3, 0), color=pal.accent)


def _fx_curse(v, ev, state, sk, pal, src, dst):
    def land(vv):
        vv.add(Runes(dst, pal))
        vv.add(Ring(dst, 40, 8, 0.45, pal.main, 3))     # тойрог агшиж барина
    v.add(Projectile(src, dst, pal, dur=0.2, on_arrive=land, size=8))


def _fx_taunt(v, ev, state, sk, pal, src, dst):
    reach = max(2, sk.range) * 72 * 0.9
    v.add(Ring(src, 14, reach, 0.6, pal.main, 8))
    v.add(Ring(src, 8, reach * 0.7, 0.5, pal.accent, 4, delay=0.12))
    v.add(Flash(src, 60, pal.main, 0.35))
    v.emit(src[0], src[1], 20, speed=(160, 320), life=(0.2, 0.4), size=(3, 0), color=pal.accent,
           drag=2.0, streak=True)


def _fx_wall(v, ev, state, sk, pal, src, dst):
    # Хана босох нүднүүд дараагийн `wall` event-ээр ирнэ; энд мөсөн сум нисэнэ.
    v.add(Projectile(src, dst, pal, dur=0.2, size=9))


def _fx_summon(v, ev, state, sk, pal, src, dst):
    v.add(Ring(src, 50, 12, 0.5, pal.main, 4))                  # дуудагчийн дэргэд хураагдах цагираг
    v.emit(src[0], src[1], 12, speed=(20, 80), life=(0.4, 0.7), size=(4, 0), color=pal.dark or pal.main,
           additive=False, gravity=-30)


def _fx_leap(v, ev, state, sk, pal, src, dst):
    smoke_puff(v, src, pal)


def _fx_generic(v, ev, state, sk, pal, src, dst):
    magic_burst(v, dst if ev.get("target") is not None else src, pal)


def smoke_puff(v: Vfx, c, pal: Pal) -> None:
    v.emit(c[0], c[1], 14, speed=(20, 90), life=(0.4, 0.75), size=(10, 22),
           color=pal.dark or (60, 50, 70), additive=False, drag=2.5, gravity=-25)
    v.emit(c[0], c[1], 8, speed=(30, 100), life=(0.25, 0.5), size=(4, 0), color=pal.main)
    v.add(Ring(c, 8, 40, 0.4, pal.main, 3))


KIND_EFFECTS = {
    "damage": _fx_damage, "area_damage": _fx_area, "drain": _fx_drain, "heal": _fx_heal,
    "shield": _fx_shield, "curse": _fx_curse, "taunt": _fx_taunt, "wall": _fx_wall,
    "summon": _fx_summon, "leap": _fx_leap,
}


# ----------------------------------------------------------------------- event handlers
def _on_skill(v: Vfx, ev, state):
    sk = SKILLS.get(ev["skill"])
    kind = sk.kind if sk is not None else ""
    pal = palette(ev["skill"], kind)
    src = _unit_px(state, ev["unit"])
    dst = _target_px(v, ev, state)
    v._covered = set()
    if sk is None:      # Skill бүртгэлгүй: ерөнхий burst
        _fx_generic(v, ev, state, None, pal, src, dst)
        return
    KIND_EFFECTS.get(kind, _fx_generic)(v, ev, state, sk, pal, src, dst)


def _on_move(v: Vfx, ev, state):
    if not ev.get("leap"):
        return
    pal = PALETTES["shadow_leap"]
    a, b = cell_center(ev["from"]), cell_center(ev["to"])
    smoke_puff(v, a, pal)
    v.later(LEAP_VFX_TIME * 0.8, lambda vv: smoke_puff(vv, b, pal))


def _on_damage(v: Vfx, ev, state):
    u = state.units.get(ev["dst"])
    if u is None or u.pos in v._covered:
        return
    hit_sparks(v, cell_center(u.pos), KIND_PALETTES["damage"], 8)


def _on_death(v: Vfx, ev, state):
    u = state.units[ev["unit"]]
    c = cell_center(u.pos)
    pal = Pal((120, 220, 255), (255, 255, 255), (70, 80, 95)) if u.side == "heroes" else \
        Pal((255, 70, 50), (255, 190, 120), (25, 10, 15))

    def puff(vv):
        smoke_puff(vv, c, pal)
        vv.emit(c[0], c[1], 14, speed=(40, 150), life=(0.5, 0.8), size=(4, 0), color=pal.main,
                gravity=-60)
        vv.add(Flash(c, 50, pal.main, 0.35))
    v.later(0.1, puff)


def _on_wall(v: Vfx, ev, state):
    pal = PALETTES["ice_wall"]
    for c in ev["cells"]:
        x, y = cell_center(c)

        def frost(vv, x=x, y=y):
            vv.add(Ring((x, y), 6, 40, 0.4, pal.main, 4))
            vv.add(Flash((x, y), 42, pal.main, 0.4))
            vv.emit(x, y, 9, speed=(60, 190), life=(0.3, 0.6), size=(3, 0), color=pal.accent,
                    drag=2.5, gravity=220, streak=True)
            vv.emit(x, y, 6, speed=(20, 80), life=(0.3, 0.5), size=(5, 1), color=pal.main)
        v.later(0.2, frost)


def _on_summon(v: Vfx, ev, state):
    pal = PALETTES["summon_imp"]
    for sp in ev["spawned"]:
        c = cell_center(sp["pos"])
        v.add(Portal(c, pal, delay=0.1))
        v.later(0.6, lambda vv, c=c: (vv.emit(c[0], c[1], 14, speed=(40, 150), life=(0.3, 0.55),
                                              size=(4, 0), color=pal.accent, gravity=60),
                                      vv.add(Flash(c, 45, pal.main, 0.3))))


_EVENT_HANDLERS = {"skill": _on_skill, "move": _on_move, "damage": _on_damage,
                   "death": _on_death, "wall": _on_wall, "summon": _on_summon}
