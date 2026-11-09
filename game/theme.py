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

FLOAT_COLORS = {"damage": (255, 90, 90), "heal": (110, 240, 140), "shield": (130, 200, 255),
                "skill": (255, 235, 150)}

# Ур чадварын бай: "harm" — дайсанд, "help" — холбоотонд, "wall" — Мөсөн хана
TARGET_FILL = {"harm": (255, 80, 80, 60), "help": (90, 230, 130, 60), "wall": (150, 220, 250, 60)}
TARGET_HOVER = {"harm": (255, 90, 90, 150), "help": (100, 240, 140, 150),
                "wall": (150, 220, 250, 150)}
AREA_PREVIEW = (255, 120, 60, 110)
FLASH_COLORS = {"harm": (255, 110, 60), "help": (110, 240, 140), "wall": (150, 220, 250)}

BADGE_SHIELD = (70, 150, 255)
BADGE_CURSE = (160, 70, 220)
BADGE_TAUNT = (235, 180, 40)
PREVIEW_HARM = (255, 110, 110)
PREVIEW_HELP = (130, 245, 160)
PREVIEW_STATUS = (250, 220, 120)

UNIT_COLORS = {
    "knight": (66, 135, 245),
    "mage": (160, 95, 235),
    "healer": (46, 184, 114),
    "demon_lord": (200, 40, 55),
    "imp": (225, 115, 45),
    "slime": (90, 200, 80),
    "slime_king": (210, 190, 60),
    "goblin": (130, 160, 60),
    "goblin_king": (170, 120, 40),
    "low_vampire": (150, 60, 110),
    "vampire_lord": (120, 40, 150),
    "demon": (210, 80, 70),
    "legion_commander": (190, 50, 40),
    "hell_demon": (240, 100, 30),
}
UNIT_LETTERS = {"knight": "K", "mage": "M", "healer": "H", "demon_lord": "D", "imp": "i",
                "slime": "s", "slime_king": "S", "goblin": "g", "goblin_king": "G",
                "low_vampire": "v", "vampire_lord": "V", "demon": "d", "legion_commander": "L",
                "hell_demon": "h"}

SIDE_RING_HERO = (90, 150, 255)       # баатрын суурийн цагираг
SIDE_RING_ENEMY = (235, 80, 80)       # дайсны суурийн цагираг
BOSS_RING = (255, 210, 80)            # босс — алтан цагираг
_FALLBACK_HERO = (66, 135, 245)
_FALLBACK_ENEMY = (200, 60, 60)


def _is_hero(kind) -> bool:
    from engine.constants import HEROES, UNIT_TYPES
    t = UNIT_TYPES.get(kind)
    return t is None or t.side == HEROES


def is_boss(kind) -> bool:
    from engine.constants import UNIT_TYPES
    t = UNIT_TYPES.get(kind)
    return bool(t is not None and t.boss)


def unit_color(kind):
    """Дүрийн үндсэн өнгө; үл мэдэгдэх kind-д талын өнгө."""
    c = UNIT_COLORS.get(kind)
    if c is not None:
        return c
    return _FALLBACK_HERO if _is_hero(kind) else _FALLBACK_ENEMY


def unit_letter(kind) -> str:
    return UNIT_LETTERS.get(kind) or (str(kind)[:1].upper() if kind else "?")


def side_ring_color(kind):
    if is_boss(kind):
        return BOSS_RING
    return SIDE_RING_HERO if _is_hero(kind) else SIDE_RING_ENEMY


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

    def wrap(self, text: str, size: int, width: int, bold: bool = False) -> list:
        """Текстийг `width` px-д багтаахаар үгээр нь мөр болгон хуваана."""
        font = self.font(size, bold)
        lines, line = [], ""
        for word in text.split():
            candidate = f"{line} {word}" if line else word
            if line and font.size(candidate)[0] > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        return lines

    def draw(self, target, text, pos, size=20, color=TEXT, bold=False, anchor="topleft"):
        surf = self.render(text, size, color, bold)
        rect = surf.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        target.blit(surf, rect)
        return rect
