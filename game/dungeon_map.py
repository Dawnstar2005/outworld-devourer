"""Dungeon-ий газрын зураг ба шагналын дэлгэцийн байршил, сонголтын логик (pygame-гүй).

Газрын зураг: зүүн талд 5 давхар (дээрээс доош гүнзгийрнэ), давхар бүрт 4 үеийн зангилаа.
Зам «могой» хэлбэртэй: сондгой давхар зүүнээс баруун, тэгш давхар баруунаас зүүн.
Баруун талд багийн самбар (level, XP, баатар бүрийн HP/хүч/item, цүнх) ба сонгосон үеийн мэдээлэл.

Тэгш өнцөгт бүр (x, y, w, h) tuple — pygame.Rect(*rect)-д шууд өгнө.
"""

from __future__ import annotations

import math
from typing import Optional

from engine.dungeon import FLOORS, HERO_UIDS, STAGES_PER_FLOOR

from . import layout as L
from .campaign import STAGE_KEYS, Campaign, parse_key

HEADER_H = 64
SIDE_W = 330                  # баруун самбарын өргөн
NODE_R = 23
BOSS_R = 30
ROW_GAP = 10
ITEM_ICON = 26                # баатрын мөрөн дэх item-ийн дүрс
BAG_ICON = 30
HERO_ROW_H = 74
BUTTON_H = 44
RESET_CONFIRM_SECS = 3.0

# ---------------------------------------------------------------------- байршил


def side_x(screen_w: int) -> int:
    return screen_w - SIDE_W - L.MARGIN


def map_rect(screen_w: int, screen_h: int = L.SCREEN_H) -> tuple:
    x = L.MARGIN
    return (x, HEADER_H, side_x(screen_w) - L.MARGIN - x, screen_h - HEADER_H - L.MARGIN)


def floor_rect(floor: int, screen_w: int, screen_h: int = L.SCREEN_H) -> tuple:
    x, y, w, h = map_rect(screen_w, screen_h)
    row_h = (h + ROW_GAP) / len(FLOORS)
    return (x, int(y + (floor - 1) * row_h), w, int(row_h - ROW_GAP))


def node_center(key: str, screen_w: int, screen_h: int = L.SCREEN_H) -> tuple:
    f, i = parse_key(key)
    x, y, w, h = floor_rect(f, screen_w, screen_h)
    pad = 64
    step = (w - 2 * pad) / (STAGES_PER_FLOOR - 1)
    k = i - 1 if f % 2 == 1 else STAGES_PER_FLOOR - i      # могой зам
    return (int(x + pad + k * step), int(y + h * 0.62))


def node_radius(key: str) -> int:
    return BOSS_R if parse_key(key)[1] == STAGES_PER_FLOOR else NODE_R


def node_at(pos, screen_w: int, screen_h: int = L.SCREEN_H) -> Optional[str]:
    for key in STAGE_KEYS:
        cx, cy = node_center(key, screen_w, screen_h)
        if math.hypot(pos[0] - cx, pos[1] - cy) <= node_radius(key) + 4:
            return key
    return None


def hero_row_rect(index: int, screen_w: int) -> tuple:
    return (side_x(screen_w), HEADER_H + 58 + index * HERO_ROW_H, SIDE_W, HERO_ROW_H - 6)


def hero_item_rect(hero_index: int, slot: int, screen_w: int) -> tuple:
    x, y, w, h = hero_row_rect(hero_index, screen_w)
    return (x + 64 + slot * (ITEM_ICON + 6), y + h - ITEM_ICON - 6, ITEM_ICON, ITEM_ICON)


def bag_y() -> int:
    return HEADER_H + 58 + len(HERO_UIDS) * HERO_ROW_H + 4


def bag_rect(slot: int, screen_w: int) -> tuple:
    return (side_x(screen_w) + 70 + slot * (BAG_ICON + 6), bag_y(), BAG_ICON, BAG_ICON)


BAG_SLOTS = 7


def map_buttons(screen_w: int, screen_h: int = L.SCREEN_H) -> dict:
    x = side_x(screen_w)
    y = screen_h - L.MARGIN - BUTTON_H
    half = (SIDE_W - 8) // 2
    return {"back": (x, y, half, BUTTON_H),
            "start": (x + half + 8, y, SIDE_W - half - 8, BUTTON_H),
            "reset": (screen_w - L.MARGIN - 150, 16, 150, 30)}


def stage_info_y() -> int:
    return bag_y() + BAG_ICON + 14


# ---------------------------------------------------------------------- газрын зургийн логик

class DungeonMap:
    """Сонгосон үе, цүнхний сонголт, ахиц арилгах баталгаажуулалт."""

    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self.selected = campaign.next_stage()
        self.bag_pick: Optional[int] = None     # цүнхний сонгосон item-ийн индекс
        self.reset_armed = 0.0                   # >0 бол дахин дарахад арилгана
        self.message = ""

    def update(self, dt: float) -> None:
        if self.reset_armed > 0:
            self.reset_armed = max(0.0, self.reset_armed - dt)

    def refresh(self) -> None:
        if not self.campaign.is_unlocked(self.selected):
            self.selected = self.campaign.next_stage()
        bag = self.campaign.bag
        if self.bag_pick is not None and self.bag_pick >= len(bag):
            self.bag_pick = None

    def select(self, key: Optional[str]) -> bool:
        if key is None or not self.campaign.is_unlocked(key):
            if key is not None:
                self.message = "Энэ үе түгжээтэй — өмнөх үеийг давна уу"
            return False
        self.selected = key
        self.message = ""
        return True

    def move(self, dx: int, dy: int, screen_w: int) -> bool:
        """Сумаар хамгийн ойр нээлттэй зангилаа руу шилжинэ (дэлгэцийн чиглэлээр)."""
        cx, cy = node_center(self.selected, screen_w)
        best, best_d = None, None
        for key in STAGE_KEYS:
            if key == self.selected or not self.campaign.is_unlocked(key):
                continue
            x, y = node_center(key, screen_w)
            vx, vy = x - cx, y - cy
            along = vx * dx + vy * dy
            if along <= 0:
                continue
            across = abs(vx * dy) + abs(vy * dx)
            d = along + 2.5 * across
            if best_d is None or d < best_d:
                best, best_d = key, d
        if best is None:
            return False
        self.selected = best
        return True

    def click_bag(self, slot: int) -> None:
        if slot < len(self.campaign.bag):
            self.bag_pick = None if self.bag_pick == slot else slot
            self.message = "Баатрын мөрөн дээр дарж зүүлгэнэ" if self.bag_pick is not None else ""

    def click_hero(self, hero: str) -> bool:
        if self.bag_pick is None:
            return False
        iid = self.campaign.bag[self.bag_pick]
        if self.campaign.equip(iid, hero):
            self.bag_pick = None
            self.message = ""
            return True
        self.message = "Item-ийн слот дүүрсэн (4)"
        return False

    def click_item(self, hero: str, slot: int) -> bool:
        ok = self.campaign.unequip(hero, slot)
        if ok:
            self.message = "Item цүнх рүү буцлаа"
        return ok

    def press_reset(self) -> bool:
        """Эхний дарахад баталгаа асууна, дахин дарахад ахицыг арилгана."""
        if self.reset_armed > 0:
            self.campaign.reset()
            self.reset_armed = 0.0
            self.selected = self.campaign.next_stage()
            self.bag_pick = None
            self.message = "Ахиц арилгагдлаа — 1-р давхраас эхэлнэ"
            return True
        self.reset_armed = RESET_CONFIRM_SECS
        return False

    def hit(self, pos, screen_w: int):
        """Хулганы байрлал дээрх зүйл: ("node", key) | ("button", name) | ("bag", slot) |
        ("item", hero, slot) | ("hero", hero) | None."""
        key = node_at(pos, screen_w)
        if key is not None:
            return ("node", key)
        for name, rect in map_buttons(screen_w).items():
            if L.point_in(rect, pos):
                return ("button", name)
        for slot in range(BAG_SLOTS):
            if L.point_in(bag_rect(slot, screen_w), pos):
                return ("bag", slot)
        for hi, hero in enumerate(HERO_UIDS):
            for slot in range(4):
                if L.point_in(hero_item_rect(hi, slot, screen_w), pos):
                    return ("item", hero, slot)
            if L.point_in(hero_row_rect(hi, screen_w), pos):
                return ("hero", hero)
        return None


# ---------------------------------------------------------------------- шагналын дэлгэц

REWARD_XP_ANIM = 1.4          # XP-ийн зурвас дүүрэх хугацаа (сек)


def reward_drop_buttons(screen_w: int, top: int) -> dict:
    """Олзыг хэнд өгөх товчнууд: баатар бүр + «Цүнхэнд»."""
    names = list(HERO_UIDS) + ["bag"]
    w, gap = 128, 10
    total = len(names) * w + (len(names) - 1) * gap
    x = (screen_w - total) // 2
    return {n: (x + k * (w + gap), top, w, 38) for k, n in enumerate(names)}
