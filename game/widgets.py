"""Цэсний товч, slider, toggle — dark fantasy загвартай, хөдөлгөөнтэй (pygame).

Товч хулгана/сонголтод ороход зөөлөн «асна»: дулаан градиент, алтан хүрээ, гадна талын
галын туяа, гэрлийн зурвас гүйх, хоёр талд алмаазан тэмдэг, бага зэрэг дээш өргөгдөнө.
Hover-ийн явц товч бүрийн key-ээр хадгалагдана (зурах үед бодит цагаар шинэчлэгдэнэ).
"""

from __future__ import annotations

import math
import time

import pygame

from . import theme as T

HOVER_SPEED = 7.0           # 1/сек — hover бүрэн асах ~0.14 сек
GLOW = (255, 120, 45)
GOLD = (255, 205, 110)
TEXT_HOT = (255, 238, 200)

STYLES = {
    "normal": {"top": (50, 44, 62), "bottom": (24, 21, 32), "hot_top": (104, 52, 36),
               "hot_bottom": (46, 20, 18), "border": (98, 80, 70), "hot_border": GOLD},
    "primary": {"top": (118, 46, 30), "bottom": (60, 18, 14), "hot_top": (172, 70, 36),
                "hot_bottom": (92, 28, 16), "border": (190, 120, 64), "hot_border": (255, 222, 130)},
    "disabled": {"top": (44, 44, 52), "bottom": (32, 32, 38), "hot_top": (44, 44, 52),
                 "hot_bottom": (32, 32, 38), "border": (62, 62, 72), "hot_border": (62, 62, 72)},
}


def _lerp(a, b, k: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def _ease(k: float) -> float:
    return 1 - (1 - k) ** 3


class ButtonRenderer:
    def __init__(self, text: T.Text):
        self.text = text
        self._progress = {}      # key → 0..1
        self._last = {}          # key → сүүлд зурсан цаг
        self._cache = {}

    # ---- hover-ийн явц ----
    def hover(self, key, hot: bool, now: float = None) -> float:
        now = time.perf_counter() if now is None else now
        dt = min(0.1, now - self._last.get(key, now))
        self._last[key] = now
        p = self._progress.get(key, 1.0 if hot else 0.0)
        p = min(1.0, p + dt * HOVER_SPEED) if hot else max(0.0, p - dt * HOVER_SPEED)
        self._progress[key] = p
        return _ease(p)

    # ---- кэштэй гадаргуу ----
    def _gradient(self, size, top, bottom, radius):
        key = ("g", size, top, bottom, radius)
        if key not in self._cache:
            w, h = size
            col = pygame.Surface((1, h), pygame.SRCALPHA)
            for y in range(h):
                col.set_at((0, y), _lerp(top, bottom, y / max(1, h - 1)) + (255,))
            surf = pygame.transform.scale(col, (w, h))
            surf.blit(self._mask(size, radius), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            self._cache[key] = surf
        return self._cache[key]

    def _mask(self, size, radius):
        key = ("m", size, radius)
        if key not in self._cache:
            m = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.rect(m, (255, 255, 255, 255), m.get_rect(), border_radius=radius)
            self._cache[key] = m
        return self._cache[key]

    def _glow(self, size, radius):
        key = ("glow", size, radius)
        if key not in self._cache:
            pad = 14
            w, h = size[0] + 2 * pad, size[1] + 2 * pad
            g = pygame.Surface((w, h), pygame.SRCALPHA)
            for i, a in enumerate((18, 26, 36, 50, 66)):
                grow = pad - i * 3
                r = pygame.Rect(pad - grow, pad - grow, size[0] + 2 * grow, size[1] + 2 * grow)
                pygame.draw.rect(g, GLOW + (a,), r, border_radius=radius + grow)
            self._cache[key] = g
        return self._cache[key]

    # ---- товч ----
    def draw(self, surf, rect, label: str, key=None, hot: bool = False, enabled: bool = True,
             style: str = "normal", size: int = 22, now: float = None, sublabel: str = ""):
        now = time.perf_counter() if now is None else now
        r = pygame.Rect(rect)
        k = self.hover(key if key is not None else (label, tuple(r)), hot and enabled, now)
        st = STYLES["disabled" if not enabled else style]
        radius = 10
        body = r.move(0, -int(round(2 * k)))

        shadow = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120), shadow.get_rect(), border_radius=radius)
        surf.blit(shadow, r.move(0, 4))
        if k > 0.01:
            glow = self._glow(r.size, radius).copy()
            pulse = 0.85 + 0.15 * math.sin(now * 4.0)
            glow.set_alpha(int(255 * k * pulse))
            surf.blit(glow, glow.get_rect(center=body.center))

        surf.blit(self._gradient(r.size, st["top"], st["bottom"], radius), body)
        if k > 0.01:
            hot_g = self._gradient(r.size, st["hot_top"], st["hot_bottom"], radius).copy()
            hot_g.set_alpha(int(255 * k))
            surf.blit(hot_g, body)
            self._shine(surf, body, radius, k, now)
        pygame.draw.line(surf, _lerp(st["top"], (255, 255, 255), 0.25),
                         (body.x + radius, body.y + 2), (body.right - radius, body.y + 2))
        pygame.draw.rect(surf, _lerp(st["border"], st["hot_border"], k), body, 2,
                         border_radius=radius)
        if k > 0.01 and enabled:
            self._diamonds(surf, body, k)

        color = _lerp(T.TEXT, TEXT_HOT, k) if enabled else T.TEXT_DIM
        bold = style == "primary"
        cy = body.centery - (7 if sublabel else 0)
        shade = self.text.render(label, size, (0, 0, 0), bold=bold).copy()
        shade.set_alpha(150)
        surf.blit(shade, shade.get_rect(center=(body.centerx + 1, cy + 2)))
        main = self.text.render(label, size, color, bold=bold)
        surf.blit(main, main.get_rect(center=(body.centerx, cy)))
        if sublabel:
            sub = self.text.render(sublabel, 13, _lerp(T.TEXT_DIM, GOLD, k * 0.6))
            surf.blit(sub, sub.get_rect(center=(body.centerx, body.centery + 13)))
        return body

    def _shine(self, surf, body, radius, k, now):
        """Товч дээгүүр ташуу гэрлийн зурвас гүйнэ (~2.2 сек тутам)."""
        w, h = body.size
        phase = (now % 2.2) / 2.2
        x = int(-h + phase * (w + 2 * h) * 1.4 - h)
        if x > w + h:
            return
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(band, (255, 240, 210, int(46 * k)),
                            [(x, h), (x + h // 2, 0), (x + h // 2 + 22, 0), (x + 22, h)])
        band.blit(self._mask((w, h), radius), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surf.blit(band, body)

    @staticmethod
    def _diamonds(surf, body, k):
        size = 5
        off = int(10 * (1 - k))
        color = _lerp((120, 80, 40), GOLD, k)
        for cx in (body.x + 16 - off, body.right - 16 + off):
            cy = body.centery
            pygame.draw.polygon(surf, color, [(cx, cy - size), (cx + size, cy), (cx, cy + size),
                                              (cx - size, cy)])

    # ---- тохиргооны элементүүд ----
    def slider(self, surf, bar_rect, value: int, hot: bool, key=None, now: float = None):
        """0–100 утгатай slider: галт дүүргэлт, алтан бариул."""
        k = self.hover(key if key is not None else ("slider", tuple(bar_rect)), hot, now)
        r = pygame.Rect(bar_rect)
        pygame.draw.rect(surf, (18, 16, 24), r.inflate(4, 4), border_radius=7)
        fill = r.copy()
        fill.w = int(r.w * value / 100)
        if fill.w > 0:
            grad = self._gradient((max(1, fill.w), r.h), (255, 150, 60), (170, 50, 30), 5)
            surf.blit(grad, fill)
        for i in range(1, 10):                                     # 10%-ийн зураас
            x = r.x + r.w * i // 10
            pygame.draw.line(surf, (60, 52, 70), (x, r.bottom + 4), (x, r.bottom + 6))
        knob = (r.x + fill.w, r.centery)
        rad = 9 + int(2 * k)
        if k > 0.01:
            g = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(g, GLOW + (int(90 * k),), (20, 20), 16)
            surf.blit(g, g.get_rect(center=knob))
        pygame.draw.circle(surf, (40, 30, 24), knob, rad + 2)
        pygame.draw.circle(surf, _lerp((210, 170, 100), GOLD, k), knob, rad)
        pygame.draw.circle(surf, (255, 245, 220), (knob[0] - 3, knob[1] - 3), 3)

    def toggle(self, surf, rect, on: bool, hot: bool, key=None, now: float = None):
        """Асаах/унтраах товч (pill хэлбэртэй)."""
        k = self.hover(key if key is not None else ("toggle", tuple(rect)), hot, now)
        r = pygame.Rect(rect)
        base = (150, 60, 34) if on else (48, 44, 58)
        pygame.draw.rect(surf, _lerp(base, (190, 80, 40) if on else (70, 64, 84), k * 0.5), r,
                         border_radius=r.h // 2)
        pygame.draw.rect(surf, _lerp((110, 90, 80), GOLD, k), r, 2, border_radius=r.h // 2)
        cx = r.right - r.h // 2 if on else r.x + r.h // 2
        pygame.draw.circle(surf, (245, 230, 200) if on else (150, 145, 160), (cx, r.centery),
                           r.h // 2 - 4)

    def choice(self, surf, rect, text: str, hot: bool, key=None, now: float = None):
        """‹ утга › — сумтай сонголт."""
        k = self.hover(key if key is not None else ("choice", tuple(rect)), hot, now)
        r = pygame.Rect(rect)
        color = _lerp((150, 130, 110), GOLD, k)
        cy = r.centery
        pygame.draw.polygon(surf, color, [(r.x + 12, cy - 7), (r.x + 3, cy), (r.x + 12, cy + 7)])
        pygame.draw.polygon(surf, color, [(r.right - 12, cy - 7), (r.right - 3, cy),
                                          (r.right - 12, cy + 7)])
        lbl = self.text.render(text, 18, _lerp(T.TEXT, TEXT_HOT, k), bold=True)
        surf.blit(lbl, lbl.get_rect(center=r.center))
