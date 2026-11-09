"""Дэлгэцийн байршил: нүд ↔ пиксел хөрвүүлэлт, товчны байрлал (pygame-гүй).

Тэгш өнцөгтийг (x, y, w, h) tuple-аар илэрхийлнэ — pygame.Rect(*rect)-д шууд өгч болно.
"""

from engine.constants import BOARD_H, BOARD_W

CELL = 72                     # нэг нүдний хэмжээ (px)
MARGIN = 20
TOP_BAR_H = 40                # талбарын дээрх ээлжийн мөр

BOARD_X = MARGIN
BOARD_Y = TOP_BAR_H + MARGIN
BOARD_PX_W = CELL * BOARD_W
BOARD_PX_H = CELL * BOARD_H

PANEL_X = BOARD_X + BOARD_PX_W + MARGIN
PANEL_Y = BOARD_Y
PANEL_W = 320
PANEL_H = BOARD_PX_H

SCREEN_W = PANEL_X + PANEL_W + MARGIN
SCREEN_H = BOARD_Y + BOARD_PX_H + MARGIN

BUTTON_H = 44
BUTTON_GAP = 8
_half = (PANEL_W - BUTTON_GAP) // 2
BUTTONS = {
    "wait": (PANEL_X, PANEL_Y + PANEL_H - BUTTON_H, _half, BUTTON_H),
    "end_turn": (PANEL_X + _half + BUTTON_GAP, PANEL_Y + PANEL_H - BUTTON_H, _half, BUTTON_H),
}

# Самбарын хэсгүүд (дээрээс доош): дүрүүд → сонгосон дүр + ур чадварын товч → log → товч
UNITS_Y = PANEL_Y + 10
INFO_Y = PANEL_Y + 190
SKILL_BTN_Y = INFO_Y + 56
SKILL_BTN_H = 30
SKILL_BTN_STEP = SKILL_BTN_H + 4
MAX_SKILLS = 4
SKILL_BUTTONS = [(PANEL_X + 8, SKILL_BTN_Y + i * SKILL_BTN_STEP, PANEL_W - 16, SKILL_BTN_H)
                 for i in range(MAX_SKILLS)]
LOG_Y = SKILL_BTN_Y + MAX_SKILLS * SKILL_BTN_STEP + 6


def point_in(rect, pos) -> bool:
    x, y, w, h = rect
    return x <= pos[0] < x + w and y <= pos[1] < y + h


def cell_at(pos):
    """Пикселийн байрлал → нүд (x, y). Талбараас гадуур бол None."""
    px, py = pos[0] - BOARD_X, pos[1] - BOARD_Y
    if px < 0 or py < 0:
        return None
    cx, cy = int(px // CELL), int(py // CELL)
    if cx >= BOARD_W or cy >= BOARD_H:
        return None
    return (cx, cy)


def cell_rect(cell):
    return (BOARD_X + cell[0] * CELL, BOARD_Y + cell[1] * CELL, CELL, CELL)


def cell_center(cell):
    return (BOARD_X + cell[0] * CELL + CELL / 2, BOARD_Y + cell[1] * CELL + CELL / 2)


def button_at(pos):
    """Пикселийн байрлал дээрх товчны нэр ("wait", "end_turn", "skill:0".."skill:3") эсвэл None."""
    for name, rect in BUTTONS.items():
        if point_in(rect, pos):
            return name
    for i, rect in enumerate(SKILL_BUTTONS):
        if point_in(rect, pos):
            return f"skill:{i}"
    return None
