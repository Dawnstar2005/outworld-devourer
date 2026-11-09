"""Энгийн босоо цэсийн логик: сонголт, гар/хулганаар шилжих (pygame-гүй).

Үндсэн цэс, түр зогсоох цэс, үр дүнгийн дэлгэцийн товчнууд бүгд үүнийг ашиглана.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import layout as L


@dataclass
class MenuItem:
    key: str
    label: str
    enabled: bool = True
    hint: str = ""             # сонгогдсон үед товчны доор харагдах тайлбар
    primary: bool = False      # гол үйлдэл — галт өнгөтэй товч


class Menu:
    def __init__(self, items: list, top: int, width: int = 320, height: int = 50, gap: int = 12):
        self.items = items
        self.top = top
        self.width = width
        self.height = height
        self.gap = gap
        self.index = 0
        self._skip_disabled(1)

    def rects(self, screen_w: int) -> list:
        return L.menu_buttons(len(self.items), screen_w, self.top, self.width, self.height,
                              self.gap)

    def item_at(self, pos, screen_w: int):
        """Хулганы байрлал дээрх идэвхтэй товчны индекс эсвэл None."""
        for i, r in enumerate(self.rects(screen_w)):
            if L.point_in(r, pos) and self.items[i].enabled:
                return i
        return None

    def move(self, delta: int) -> None:
        if not any(it.enabled for it in self.items):
            return
        self.index = (self.index + delta) % len(self.items)
        self._skip_disabled(delta)

    def _skip_disabled(self, delta: int) -> None:
        for _ in range(len(self.items)):
            if self.items[self.index].enabled:
                return
            self.index = (self.index + (1 if delta >= 0 else -1)) % len(self.items)

    @property
    def selected(self) -> str:
        return self.items[self.index].key

    def hover(self, pos, screen_w: int) -> None:
        i = self.item_at(pos, screen_w)
        if i is not None:
            self.index = i

    def click(self, pos, screen_w: int):
        """Дарсан товчны key эсвэл None."""
        i = self.item_at(pos, screen_w)
        if i is None:
            return None
        self.index = i
        return self.items[i].key
