"""Өнгө, фонт, текстийн cache (pygame).

Фонт: pygame-ийн default freesansbold нь «ү»-г «v» шиг, «→»-г хоосон дөрвөлжин болгодог.
Тиймээс системийн фонтыг (Windows: Tahoma) эхэлж хайна. Фонт файлыг repo-д оруулахгүй
(лиценз нь CC0 биш). Олдохгүй бол default фонт руу буцна.
Текстийг кадр бүр дахин render хийхгүйн тулд cache-лэнэ (60 FPS).
"""

import pygame

FONT_NAMES = ("tahoma", "dejavusans", "notosans", "liberationsans", "freesans")
SYSFONT_SCALE = 0.7      # default фонтын хэмжээтэй ойролцоо харагдуулах коэффициент


def find_font(bold: bool = False):
    """Монгол кирилл бүрэн харуулдаг системийн фонтын зам, олдохгүй бол None."""
    for name in FONT_NAMES:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return path
    return None

BG = (22, 22, 30)
PANEL_BG = (32, 32, 44)
PANEL_LINE = (60, 60, 80)
TEXT = (230, 230, 240)
TEXT_DIM = (140, 140, 160)
ACCENT = (250, 200, 70)

CELL_LIGHT = (58, 62, 74)
CELL_DARK = (48, 52, 63)
GRID_LINE = (36, 38, 48)
MOVE_FILL = (80, 160, 255, 70)
MOVE_HOVER = (120, 200, 255, 140)
HOVER_LINE = (200, 200, 220)
SELECT_LINE = ACCENT
WALL = (150, 220, 250)

HP_BG = (25, 25, 30)
HP_HERO = (80, 210, 120)
HP_DEMON = (230, 70, 70)
HP_LOW = (240, 170, 50)

BUTTON = (70, 90, 140)
BUTTON_HOVER = (90, 115, 175)
BUTTON_OFF = (55, 55, 68)

FLOAT_COLORS = {"damage": (255, 90, 90), "heal": (110, 240, 140), "shield": (130, 200, 255)}

UNIT_COLORS = {
    "knight": (66, 135, 245),
    "mage": (160, 95, 235),
    "healer": (46, 184, 114),
    "demon_lord": (200, 40, 55),
    "imp": (225, 115, 45),
}
UNIT_LETTERS = {"knight": "K", "mage": "M", "healer": "H", "demon_lord": "D", "imp": "i"}


def dim(color, k=0.45):
    return tuple(int(c * k) for c in color[:3])


class Text:
    """Текстийн surface-ийг (text, size, color, bold) түлхүүрээр cache-лэнэ."""

    def __init__(self):
        self._fonts = {}
        self._cache = {}
        self._paths = {False: find_font(False), True: find_font(True)}

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            path = self._paths[bold] or self._paths[False]
            if path:
                f = pygame.font.Font(path, max(8, round(size * SYSFONT_SCALE)))
                if bold and not self._paths[True]:
                    f.bold = True
            else:
                f = pygame.font.Font(None, size)   # freesansbold
                f.bold = bold
            self._fonts[key] = f
        return f

    def render(self, text: str, size: int = 20, color=TEXT, bold: bool = False) -> pygame.Surface:
        key = (text, size, color, bold)
        surf = self._cache.get(key)
        if surf is None:
            if len(self._cache) > 600:
                self._cache.clear()
            surf = self.font(size, bold).render(text, True, color)
            self._cache[key] = surf
        return surf

    def draw(self, target, text, pos, size=20, color=TEXT, bold=False, anchor="topleft"):
        surf = self.render(text, size, color, bold)
        rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        target.blit(surf, rect)
        return rect
