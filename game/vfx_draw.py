"""VFX зурах хэсэг (pygame): `Vfx`-ийн симуляцийг дэлгэц дээр зурна.

Гэрэлтэх (additive) бүх зүйлийг талбайн хэмжээтэй нэг хар гадаргуу дээр түүвэрлэж,
нэг удаа BLEND_ADD-аар дэлгэцэнд нэмнэ — тоосонцор олон ч FPS буурахгүй.
Гэрлийн толбыг (glow) өнгө/радиус/тод байдлаар cache-лэнэ.
"""

from __future__ import annotations

import pygame

from . import layout as L

LEVELS = 10
_CACHE: dict = {}


def _glow(color, r: int, level: int, additive: bool) -> pygame.Surface:
    key = (color, r, level, additive)
    s = _CACHE.get(key)
    if s is not None:
        return s
    if len(_CACHE) > 3000:
        _CACHE.clear()
    k = level / LEVELS
    size = 2 * r + 1
    if additive:
        s = pygame.Surface((size, size))
        s.fill((0, 0, 0))
    else:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
    steps = max(3, min(r, 10))
    for i in range(steps):
        rr = max(1, int(r * (1 - i / steps)))
        f = ((i + 1) / steps) ** 1.4
        if additive:
            col = tuple(int(c * f * k) for c in color)
        else:
            col = (*color, int(255 * f * k))
        pygame.draw.circle(s, col, (r, r), rr)
    _CACHE[key] = s
    return s


def _q_radius(r: float) -> int:
    r = max(1, int(r))
    return r if r <= 12 else (r // 2) * 2


def _scaled(color, a: float) -> tuple:
    return (int(color[0] * a), int(color[1] * a), int(color[2] * a))


class VfxView:
    """Нэг давхарга зурна: draw(screen, vfx, "under" | "over")."""

    def __init__(self):
        self._fx = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H))
        self._clip = pygame.Rect(L.BOARD_X, L.BOARD_Y, L.BOARD_PX_W, L.BOARD_PX_H)

    def draw(self, screen, vfx, layer: str) -> None:
        shapes = vfx.shapes(layer)
        parts = [p for p in vfx.particles if p.layer == layer]
        if not shapes and not parts:
            return
        fx = self._fx
        fx.fill((0, 0, 0))
        ox, oy = L.BOARD_X, L.BOARD_Y
        normal = []                                  # гэрэлтдэггүй (утаа) — дэлгэц рүү шууд

        for s in shapes:
            kind = s[0]
            if kind == "glow":
                _, _, x, y, r, color, a, additive = s
                self._glow(fx, normal, x - ox, y - oy, r, color, a, additive)
            elif kind == "ring":
                _, _, x, y, r, w, color, a = s
                if a > 0.02 and r > 1:
                    pygame.draw.circle(fx, _scaled(color, a), (int(x - ox), int(y - oy)),
                                       int(r), max(1, int(w)))
            elif kind == "line":
                _, _, x0, y0, x1, y1, w, color, a = s
                if a > 0.02:
                    pygame.draw.line(fx, _scaled(color, a), (x0 - ox, y0 - oy), (x1 - ox, y1 - oy),
                                     max(1, int(w)))
        for p in parts:
            a = p.alpha
            if p.streak:
                pygame.draw.line(fx, _scaled(p.color, a), (p.x - ox, p.y - oy),
                                 (p.x - ox - p.vx * 0.035, p.y - oy - p.vy * 0.035),
                                 max(1, int(p.size * 0.7)))
            else:
                self._glow(fx, normal, p.x - ox, p.y - oy, p.size, p.color, a, p.additive)

        for surf, pos in normal:
            screen.blit(surf, pos)
        screen.blit(fx, (ox, oy), special_flags=pygame.BLEND_ADD)

    @staticmethod
    def _glow(fx, normal, x, y, r, color, a, additive):
        lvl = int(a * LEVELS + 0.5)
        if lvl <= 0 or r < 1:
            return
        r = _q_radius(r)
        surf = _glow(color, r, min(LEVELS, lvl), additive)
        if additive:
            fx.blit(surf, (int(x) - r, int(y) - r), special_flags=pygame.BLEND_ADD)
        else:
            normal.append((surf, (int(x) - r + L.BOARD_X, int(y) - r + L.BOARD_Y)))
