"""«Тохиргоо» дэлгэцийн мөрүүд, байршил, гар/хулганы логик (pygame-гүй).

Мөр бүр Settings-ийн нэг талбарыг өөрчилнө: slider (дуу 0–100), choice (дайсны хурд),
toggle (самбар, бүтэн дэлгэц). Доод талд «Анхны утга», «Буцах» товч.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import layout as L
from .settings import ENEMY_SPEED_NAMES, ENEMY_SPEEDS, VOLUME_STEP, Settings


@dataclass(frozen=True)
class OptionRow:
    key: str
    label: str
    kind: str          # slider | choice | toggle | button
    hint: str = ""


ROWS = (
    OptionRow("master", "Ерөнхий дуу", "slider", "Бүх дуу, хөгжмийн түвшин"),
    OptionRow("music", "Хөгжим", "slider", "Цэс, тулааны арын хөгжим"),
    OptionRow("sfx", "Дууны эффект", "slider", "Цохилт, ур чадвар, товчны дуу"),
    OptionRow("enemy_speed", "Дайсны нүүдлийн хурд", "choice",
              "Дайсан нэг нүүдэл хийх бүрийн хоорондох хүлээлт"),
    OptionRow("boss_panel", "«Боссын бодол» самбар", "toggle",
              "Тулааны үед AI-ийн бодлыг харуулах (Tab-аар ч солино)"),
    OptionRow("fullscreen", "Бүтэн дэлгэц", "toggle", "Цонхыг дэлгэц дүүрэн томруулна"),
    OptionRow("defaults", "Анхны утга", "button", "Бүх тохиргоог анхны утгад нь буцаана"),
    OptionRow("back", "Буцах", "button", ""),
)
SETTING_ROWS = tuple(r for r in ROWS if r.kind != "button")

CARD_W = 660
TOP = 128
ROW_H = 52
SLIDER_W = 220
BUTTON_W = 210
BUTTON_H = 46


def card_x(screen_w: int) -> int:
    return (screen_w - CARD_W) // 2


def row_rect(index: int, screen_w: int) -> tuple:
    """Тохиргооны мөр (index < len(SETTING_ROWS)) эсвэл доод товч."""
    row = ROWS[index]
    if row.kind == "button":
        k = index - len(SETTING_ROWS)
        n = len(ROWS) - len(SETTING_ROWS)
        total = n * BUTTON_W + (n - 1) * 16
        x = (screen_w - total) // 2 + k * (BUTTON_W + 16)
        return (x, TOP + len(SETTING_ROWS) * ROW_H + 26, BUTTON_W, BUTTON_H)
    return (card_x(screen_w), TOP + index * ROW_H, CARD_W, ROW_H - 6)


def control_rect(index: int, screen_w: int) -> tuple:
    x, y, w, h = row_rect(index, screen_w)
    return (x + w - SLIDER_W - 96, y + 6, SLIDER_W + 80, h - 12)


def slider_bar(index: int, screen_w: int) -> tuple:
    x, y, w, h = control_rect(index, screen_w)
    return (x, y + h // 2 - 5, SLIDER_W, 10)


def hint_y() -> int:
    return TOP + len(SETTING_ROWS) * ROW_H + 26 + BUTTON_H + 22


class OptionsMenu:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.index = 0
        self.dragging: Optional[int] = None

    @property
    def row(self) -> OptionRow:
        return ROWS[self.index]

    def move(self, delta: int) -> None:
        self.index = (self.index + delta) % len(ROWS)

    def value(self, row: OptionRow):
        return getattr(self.settings, row.key) if row.kind != "button" else None

    def value_text(self, row: OptionRow) -> str:
        v = self.value(row)
        if row.kind == "slider":
            return f"{v}%"
        if row.kind == "choice":
            return ENEMY_SPEED_NAMES.get(v, str(v))
        if row.kind == "toggle":
            return "Асаалттай" if v else "Унтраалттай"
        return ""

    def adjust(self, delta: int, index: Optional[int] = None) -> Optional[str]:
        """←/→: slider ±10, choice дараагийн/өмнөх, toggle солих. Өөрчлөгдсөн key эсвэл None."""
        row = ROWS[self.index if index is None else index]
        if row.kind == "slider":
            before = getattr(self.settings, row.key)
            self.settings.update(**{row.key: before + delta * VOLUME_STEP})
            return row.key if getattr(self.settings, row.key) != before else None
        if row.kind == "choice":
            i = ENEMY_SPEEDS.index(self.settings.enemy_speed)
            self.settings.update(enemy_speed=ENEMY_SPEEDS[(i + delta) % len(ENEMY_SPEEDS)])
            return row.key
        if row.kind == "toggle":
            setattr(self.settings, row.key, not getattr(self.settings, row.key))
            return row.key
        return None

    def activate(self, index: Optional[int] = None) -> Optional[str]:
        """Enter / дарах: товч бол түүний key ("defaults", "back"), бусад нь adjust(+1)."""
        i = self.index if index is None else index
        row = ROWS[i]
        if row.kind == "button":
            if row.key == "defaults":
                self.settings.reset()
            return row.key
        if row.kind == "slider":
            return None
        return self.adjust(1, i)

    def set_slider_from_x(self, index: int, x: float, screen_w: int) -> Optional[str]:
        bx, _, bw, _ = slider_bar(index, screen_w)
        row = ROWS[index]
        before = getattr(self.settings, row.key)
        frac = max(0.0, min(1.0, (x - bx) / bw))
        self.settings.update(**{row.key: frac * 100})
        return row.key if getattr(self.settings, row.key) != before else None

    def hit(self, pos, screen_w: int):
        """("slider", i) — зурвас дээр, ("row", i) — мөр дээр, эсвэл None."""
        for i, row in enumerate(ROWS):
            if row.kind == "slider":
                bx, by, bw, bh = slider_bar(i, screen_w)
                if L.point_in((bx - 8, by - 12, bw + 16, bh + 24), pos):
                    return ("slider", i)
            if L.point_in(row_rect(i, screen_w), pos):
                return ("row", i)
        return None
