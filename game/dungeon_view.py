"""Dungeon-ий газрын зураг ба шагналын дэлгэц зурах (pygame).

Байршил, сонголтын логик game/dungeon_map.py-д (pygame-гүй), ахиц game/campaign.py-д.
"""

from __future__ import annotations

import math

import pygame

from engine import ITEMS, UNIT_TYPES
from engine.constants import BOSS_DROPS, ITEM_DROP_CHANCE, MAX_ITEMS_PER_HERO
from engine.dungeon import FLOORS, HERO_UIDS, STAGES_PER_FLOOR, get_stage, new_stage_state
from engine.progression import level_progress, stage_xp

from . import dungeon_map as M
from . import layout as L
from . import theme as T
from .campaign import STAGE_KEYS, parse_key
from .labels import RARITY_NAMES, item_effect, item_name, power_text, unit_name

# Давхар бүрийн сэдвийн өнгө (зангилаа, хүрээ)
FLOOR_COLORS = {"slime": (95, 205, 110), "goblin": (205, 160, 70), "vampire": (190, 50, 85),
                "demon": (230, 95, 45), "hell": (255, 70, 30)}
RARITY_COLORS = {"common": (200, 200, 210), "rare": (110, 170, 255), "boss": (255, 200, 70)}
CLEARED = (250, 200, 70)
LOCKED = (52, 52, 62)
PATH_DIM = (70, 70, 84)
REWARD_CARD_Y = 112           # шагналын дэлгэц: XP-ийн карт
REWARD_CARD_H = 150
DROP_GAP = 14                 # XP-ийн карт ба олзны картын зай
DROP_BUTTONS_DY = 70          # олзны картын дээд ирмэгээс «хэнд өгөх» товч хүртэл


def reward_drop_top() -> int:
    """Шагналын дэлгэц дээрх олзыг хуваарилах товчны дээд y (App-ийн дарах шалгалтад)."""
    return REWARD_CARD_Y + REWARD_CARD_H + DROP_GAP + DROP_BUTTONS_DY


def _floor_color(floor) -> tuple:
    return FLOOR_COLORS.get(floor.theme, (180, 180, 190))


def _mix(a, b, k: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


class DungeonView:
    def __init__(self, text: T.Text, sprites=None):
        self.text = text
        self.sprites = sprites
        self._row_bg = {}          # (floor, w, h) → бүдэг tile-тай дэвсгэр
        self._enemy_info = {}      # key → [(kind, count, max_hp, power_mult)]

    # ------------------------------------------------------------------ туслах
    def _unit_img(self, kind: str, size: int, dim: bool = False):
        if self.sprites is None:
            return None
        img = self.sprites.dungeon_unit(kind, dim)
        return pygame.transform.scale(img, (size, size)) if img is not None else None

    def _icon(self, name: str, size: int):
        if self.sprites is None:
            return None
        return self.sprites.dungeon.icon(name, size)

    def _unit_badge(self, surf, kind, center, size, dim=False):
        img = self._unit_img(kind, size, dim)
        if img is not None:
            surf.blit(img, img.get_rect(center=center))
        else:
            r = pygame.Rect(0, 0, size - 8, size - 8)
            r.center = center
            pygame.draw.rect(surf, T.dim(T.unit_color(kind), 0.6) if dim else T.unit_color(kind), r,
                             border_radius=6)
            self.text.draw(surf, T.unit_letter(kind), center, size // 2, (255, 255, 255),
                           bold=True, anchor="center")

    def _item_slot(self, surf, rect, iid, highlight=False):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, (24, 24, 32), r, border_radius=5)
        if iid is not None:
            rar = ITEMS[iid].rarity if iid in ITEMS else "common"
            icon = self._icon(iid, r.w - 2)
            if icon is not None:
                surf.blit(icon, icon.get_rect(center=r.center))
            else:
                self.text.draw(surf, item_name(iid)[:2], r.center, 13, T.TEXT, anchor="center")
            pygame.draw.rect(surf, RARITY_COLORS.get(rar, T.TEXT), r, 1, border_radius=5)
        else:
            pygame.draw.rect(surf, T.PANEL_LINE, r, 1, border_radius=5)
        if highlight:
            pygame.draw.rect(surf, T.ACCENT, r.inflate(4, 4), 2, border_radius=6)

    def _button(self, surf, rect, label, enabled=True, hot=False, accent=False):
        r = pygame.Rect(rect)
        color = (T.BUTTON_HOVER if hot else T.BUTTON) if enabled else T.BUTTON_OFF
        if accent and enabled:
            color = (150, 60, 40) if not hot else (185, 80, 50)
        pygame.draw.rect(surf, color, r, border_radius=8)
        if hot and enabled:
            pygame.draw.rect(surf, T.ACCENT, r, 2, border_radius=8)
        size = 18 if r.h >= 40 else 15
        self.text.draw(surf, label, r.center, size, T.TEXT if enabled else T.TEXT_DIM,
                       anchor="center")

    def enemy_info(self, key: str) -> list:
        """Үеийн дайснууд төрлөөр: [(kind, тоо, max_hp, power_mult)] — давхрын хүчийг тооцсон."""
        if key not in self._enemy_info:
            st = get_stage(*parse_key(key))
            s = new_stage_state(st)
            groups = {}
            for uid, kind, _ in st.enemies:
                u = s.units[uid]
                g = groups.setdefault(kind, [kind, 0, u.max_hp, u.power_mult])
                g[1] += 1
            info = sorted(groups.values(), key=lambda g: (not UNIT_TYPES[g[0]].boss, g[0]))
            self._enemy_info[key] = [tuple(g) for g in info]
        return self._enemy_info[key]

    def _row_background(self, floor, rect):
        x, y, w, h = rect
        cache_key = (floor.index, w, h)
        if cache_key not in self._row_bg:
            bg = pygame.Surface((w, h), pygame.SRCALPHA)
            theme = self.sprites.theme(floor.theme) if self.sprites is not None else None
            if theme is not None:
                tile = theme.floors[0]
                for tx in range(0, w, tile.get_width()):
                    for ty in range(0, h, tile.get_height()):
                        bg.blit(tile, (tx, ty))
                bg.fill((120, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
            else:
                bg.fill(T.dim(_floor_color(floor), 0.25) + (255,))
            mask = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=12)
            bg.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
            self._row_bg[cache_key] = bg
        return self._row_bg[cache_key]

    # ------------------------------------------------------------------ газрын зураг
    def draw_map(self, surf, dmap, mouse_pos, t: float):
        w, h = surf.get_size()
        c = dmap.campaign
        surf.fill((14, 12, 18))
        hot = dmap.hit(mouse_pos, w) if mouse_pos is not None else None

        # толгой
        self.text.draw(surf, "Dungeon", (L.MARGIN, 10), 34, T.ACCENT, bold=True)
        floors_done = sum(1 for f in FLOORS if c.floor_cleared(f.index))
        sub = f"{floors_done}/{len(FLOORS)} давхар давсан · {len(c.data['cleared'])}/{len(STAGE_KEYS)} үе"
        if c.complete:
            sub += " · Demon Lord ялагдсан!"
        self.text.draw(surf, sub, (L.MARGIN + 150, 24), 17, T.TEXT_DIM)
        reset_label = "Дахин дарж батал" if dmap.reset_armed > 0 else "Ахицыг арилгах"
        self._button(surf, M.map_buttons(w)["reset"], reset_label,
                     hot=hot == ("button", "reset"), accent=dmap.reset_armed > 0)

        self._draw_floors(surf, dmap, hot, t)
        self._draw_party(surf, dmap, hot)
        self._draw_stage_info(surf, dmap)

        buttons = M.map_buttons(w)
        if dmap.message:
            self.text.draw(surf, dmap.message, (M.side_x(w) + M.SIDE_W // 2, buttons["start"][1] - 16),
                           15, T.ACCENT, anchor="center")
        self._button(surf, buttons["back"], "Цэс (Esc)", hot=hot == ("button", "back"))
        self._button(surf, buttons["start"], "Тулаан эхлэх",
                     enabled=c.is_unlocked(dmap.selected), hot=hot == ("button", "start"),
                     accent=True)

    def _draw_floors(self, surf, dmap, hot, t):
        w = surf.get_width()
        c = dmap.campaign
        for floor in FLOORS:
            rect = M.floor_rect(floor.index, w)
            r = pygame.Rect(rect)
            open_ = c.floor_unlocked(floor.index)
            color = _floor_color(floor)
            bg = self._row_background(floor, rect)
            if not open_:
                bg = bg.copy()
                bg.fill((70, 70, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(bg, r)
            shade = pygame.Surface(r.size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, 120))
            surf.blit(shade, r)
            pygame.draw.rect(surf, color if open_ else LOCKED, r, 2, border_radius=12)
            title = f"{floor.index}-р давхар · {floor.name}"
            self.text.draw(surf, title, (r.x + 14, r.y + 8), 18, T.TEXT if open_ else T.TEXT_DIM,
                           bold=True)
            if c.floor_cleared(floor.index):
                status, scol = "Давсан", CLEARED
            elif open_:
                status, scol = f"Босс: {UNIT_TYPES[floor.boss].name}", color
            else:
                status, scol = "Түгжээтэй", T.TEXT_DIM
            self.text.draw(surf, status, (r.right - 14, r.y + 10), 15, scol, anchor="topright")

        # зам (үе хооронд)
        for a, b in zip(STAGE_KEYS, STAGE_KEYS[1:]):
            pa, pb = M.node_center(a, w), M.node_center(b, w)
            col = CLEARED if c.is_cleared(a) else PATH_DIM
            if parse_key(a)[0] != parse_key(b)[0]:     # давхар хооронд: доош буух шат
                mid = (pa[0], pb[1])
                pygame.draw.line(surf, col, pa, mid, 4)
                pygame.draw.line(surf, col, mid, pb, 4)
            else:
                pygame.draw.line(surf, col, pa, pb, 4)

        for key in STAGE_KEYS:
            self._draw_node(surf, dmap, key, hot == ("node", key), t)

    def _draw_node(self, surf, dmap, key, is_hot, t):
        w = surf.get_width()
        c = dmap.campaign
        f, i = parse_key(key)
        floor = FLOORS[f - 1]
        center = M.node_center(key, w)
        rad = M.node_radius(key)
        unlocked, cleared = c.is_unlocked(key), c.is_cleared(key)
        color = _floor_color(floor)
        selected = key == dmap.selected
        if unlocked and not cleared:            # дараагийн зорилт — лугшина
            glow = 6 + 3 * math.sin(t * 4)
            g = pygame.Surface((2 * (rad + 12), 2 * (rad + 12)), pygame.SRCALPHA)
            pygame.draw.circle(g, color + (70,), g.get_rect().center, int(rad + glow))
            surf.blit(g, g.get_rect(center=center))
        fill = (30, 30, 38) if not unlocked else _mix((20, 20, 26), color, 0.35)
        pygame.draw.circle(surf, fill, center, rad)
        ring = CLEARED if cleared else (color if unlocked else LOCKED)
        pygame.draw.circle(surf, ring, center, rad, 3)
        kind = floor.boss if i == STAGES_PER_FLOOR else floor.mobs[0]
        size = 2 * rad - (4 if i == STAGES_PER_FLOOR else 8)
        if unlocked:
            self._unit_badge(surf, kind, center, size, dim=cleared and not selected)
        else:
            self._draw_lock(surf, center)
        if cleared:
            pygame.draw.circle(surf, CLEARED, (center[0] + rad - 5, center[1] - rad + 5), 7)
            pygame.draw.lines(surf, (40, 30, 10), False,
                              [(center[0] + rad - 9, center[1] - rad + 5),
                               (center[0] + rad - 6, center[1] - rad + 8),
                               (center[0] + rad - 1, center[1] - rad + 1)], 2)
        if selected:
            pygame.draw.circle(surf, (255, 255, 255), center, rad + 5, 2)
            bob = int(3 * math.sin(t * 5))
            tip = (center[0], center[1] - rad - 8 + bob)
            pygame.draw.polygon(surf, T.ACCENT, [tip, (tip[0] - 7, tip[1] - 10),
                                                 (tip[0] + 7, tip[1] - 10)])
        elif is_hot and unlocked:
            pygame.draw.circle(surf, T.HOVER_LINE, center, rad + 4, 1)
        if i != STAGES_PER_FLOOR:                # боссын зангилаа том тул шошгогүй
            self.text.draw(surf, key, (center[0], center[1] + rad + 4), 13,
                           T.TEXT if unlocked else T.TEXT_DIM, anchor="midtop")

    def _draw_lock(self, surf, center):
        x, y = center
        pygame.draw.arc(surf, T.TEXT_DIM, (x - 7, y - 13, 14, 16), 0, math.pi, 3)
        body = pygame.Rect(0, 0, 20, 14)
        body.midtop = (x, y - 4)
        pygame.draw.rect(surf, T.TEXT_DIM, body, border_radius=3)
        pygame.draw.circle(surf, (30, 30, 38), (x, y + 2), 2)

    def _draw_party(self, surf, dmap, hot):
        w = surf.get_width()
        c = dmap.campaign
        x = M.side_x(w)
        level, start, nxt = c.progress()
        self.text.draw(surf, f"Баг · Lv {level}", (x, M.HEADER_H - 2), 22, T.ACCENT, bold=True)
        bar = pygame.Rect(x, M.HEADER_H + 28, M.SIDE_W, 12)
        pygame.draw.rect(surf, T.HP_BG, bar, border_radius=6)
        if nxt is None:
            frac, label = 1.0, "MAX"
        else:
            frac = (c.xp - start) / max(1, nxt - start)
            label = f"{c.xp - start}/{nxt - start} XP"
        fill = bar.copy()
        fill.w = max(0, int(bar.w * frac))
        pygame.draw.rect(surf, (120, 90, 230), fill, border_radius=6)
        self.text.draw(surf, label, (bar.right, M.HEADER_H + 4), 14, T.TEXT_DIM, anchor="topright")

        stats = c.hero_stats()
        for hi, hero in enumerate(HERO_UIDS):
            r = pygame.Rect(M.hero_row_rect(hi, w))
            st = stats[hero]
            row_hot = hot is not None and hot[0] in ("hero", "item") and hot[1] == hero
            pygame.draw.rect(surf, (40, 40, 56) if row_hot and dmap.bag_pick is not None
                             else T.PANEL_BG, r, border_radius=8)
            self._unit_badge(surf, hero, (r.x + 30, r.y + r.h // 2), 52)
            self.text.draw(surf, f"{unit_name(hero)}", (r.x + 64, r.y + 5), 17, T.TEXT, bold=True)
            line = f"HP {st['max_hp']} · хүч {power_text(st['power_mult'])} · нүүдэл {st['move']}"
            self.text.draw(surf, line, (r.x + 150, r.y + 8), 13, T.TEXT_DIM)
            items = c.items(hero)
            for slot in range(MAX_ITEMS_PER_HERO):
                iid = items[slot] if slot < len(items) else None
                self._item_slot(surf, M.hero_item_rect(hi, slot, w), iid,
                                highlight=hot == ("item", hero, slot) and iid is not None)

        by = M.bag_y()
        self.text.draw(surf, "Цүнх", (x, by + 6), 16, T.TEXT_DIM, bold=True)
        bag = c.bag
        if not bag:
            self.text.draw(surf, "хоосон — олз энд орно", (x + 70, by + 6), 14, T.TEXT_DIM)
        for slot in range(min(len(bag), M.BAG_SLOTS)):
            self._item_slot(surf, M.bag_rect(slot, w), bag[slot],
                            highlight=dmap.bag_pick == slot or hot == ("bag", slot))
        if len(bag) > M.BAG_SLOTS:
            self.text.draw(surf, f"+{len(bag) - M.BAG_SLOTS}", (x + M.SIDE_W - 4, by + 8), 14,
                           T.TEXT_DIM, anchor="topright")
        tip = None
        if hot is not None and hot[0] == "bag" and hot[1] < len(bag):
            tip = bag[hot[1]]
        elif hot is not None and hot[0] == "item":
            its = c.items(hot[1])
            tip = its[hot[2]] if hot[2] < len(its) else None
        if tip is not None:
            self._tooltip(surf, tip, (x, by + M.BAG_ICON + 2))

    def _tooltip(self, surf, iid, pos):
        it = ITEMS[iid]
        text = f"{it.name} ({RARITY_NAMES.get(it.rarity, it.rarity)}): {item_effect(iid)}"
        lbl = self.text.render(text, 14, RARITY_COLORS.get(it.rarity, T.TEXT))
        box = lbl.get_rect(topleft=(pos[0], pos[1] + 2)).inflate(10, 6)
        pygame.draw.rect(surf, (12, 12, 18), box, border_radius=5)
        pygame.draw.rect(surf, T.PANEL_LINE, box, 1, border_radius=5)
        surf.blit(lbl, lbl.get_rect(center=box.center))

    def _draw_stage_info(self, surf, dmap):
        w = surf.get_width()
        c = dmap.campaign
        key = dmap.selected
        f, i = parse_key(key)
        floor = FLOORS[f - 1]
        st = get_stage(f, i)
        x, y = M.side_x(w), M.stage_info_y() + 22
        bottom = M.map_buttons(w)["start"][1] - 30
        card = pygame.Rect(x, y, M.SIDE_W, bottom - y)
        pygame.draw.rect(surf, T.PANEL_BG, card, border_radius=8)
        pygame.draw.rect(surf, _floor_color(floor), card, 1, border_radius=8)
        kind_text = "Боссын тулаан" if st.is_boss else f"Мангасын үе {i}/{STAGES_PER_FLOOR - 1}"
        self.text.draw(surf, f"{key} · {kind_text}", (x + 12, y + 8), 18, T.TEXT, bold=True)
        if c.is_cleared(key):
            best = c.data["best_rounds"].get(key)
            status = "Давсан" + (f" · шилдэг {best} round" if best else "")
            scol = CLEARED
        elif c.is_unlocked(key):
            status, scol = "Шинэ — давж дараагийн үеийг нээнэ", T.HP_HERO
        else:
            status, scol = "Түгжээтэй", T.TEXT_DIM
        self.text.draw(surf, status, (x + 12, y + 32), 14, scol)
        ey = y + 56
        for kind, count, max_hp, pm in self.enemy_info(key):
            self._unit_badge(surf, kind, (x + 26, ey + 15), 32)
            name = UNIT_TYPES[kind].name + (f" ×{count}" if count > 1 else "")
            color = T.BOSS_RING if UNIT_TYPES[kind].boss else T.TEXT
            self.text.draw(surf, name, (x + 48, ey + 2), 15, color, bold=UNIT_TYPES[kind].boss)
            self.text.draw(surf, f"HP {max_hp} · хүч {power_text(pm)}", (x + 48, ey + 19), 13,
                           T.TEXT_DIM)
            ey += 36
        xp = stage_xp(f, st.is_boss, True)
        if st.is_boss and not c.is_cleared(key) and f in BOSS_DROPS:
            loot = f"Олз: {item_name(BOSS_DROPS[f])}"
        else:
            loot = f"Олз: {round(ITEM_DROP_CHANCE * 100)}% магадлалтай"
        self.text.draw(surf, f"+{xp} XP · {loot}", (x + 12, card.bottom - 24), 14, T.ACCENT)

    # ------------------------------------------------------------------ шагнал
    def draw_reward(self, surf, reward, campaign, state, stats, menu, mouse_pos, t: float,
                    draw_buttons: bool = True):
        """Үеийн дараах дэлгэц: ялалт/ялагдал, XP, level ахилт, олз, нээгдсэн үе."""
        w, h = surf.get_size()
        cx = w // 2
        surf.fill((16, 14, 20))
        f, i = parse_key(reward.key)
        floor = FLOORS[f - 1]
        won = reward.won
        title = "Ялалт!" if won else "Ялагдал"
        color = T.HP_HERO if won else T.HP_DEMON
        if reward.campaign_complete:
            title, color = "Demon Lord ялагдлаа!", T.ACCENT
        self.text.draw(surf, title, (cx, 46), 50, color, bold=True, anchor="center")
        sub = f"{reward.key} · {floor.name} · {state.round} round"
        mvp = stats.mvp("heroes", state) if stats is not None else None
        if mvp:
            sub += f" · Шилдэг баатар: {unit_name(mvp, state)}"
        self.text.draw(surf, sub, (cx, 88), 19, T.TEXT_DIM, anchor="center")

        # XP ба level
        card = pygame.Rect(0, 0, min(660, w - 40), REWARD_CARD_H)
        card.midtop = (cx, REWARD_CARD_Y)
        pygame.draw.rect(surf, T.PANEL_BG, card, border_radius=10)
        k = min(1.0, t / M.REWARD_XP_ANIM)
        k = 1 - (1 - k) ** 3
        xp_now = int(reward.xp_before + (reward.xp_after - reward.xp_before) * k)
        lv, start, nxt = level_progress(xp_now)
        self.text.draw(surf, f"+{reward.xp_gained} XP", (card.x + 20, card.y + 14), 24, (170, 140, 255),
                       bold=True)
        self.text.draw(surf, f"Lv {lv}", (card.right - 20, card.y + 14), 24, T.ACCENT, bold=True,
                       anchor="topright")
        bar = pygame.Rect(card.x + 20, card.y + 50, card.w - 40, 14)
        pygame.draw.rect(surf, T.HP_BG, bar, border_radius=7)
        frac = 1.0 if nxt is None else (xp_now - start) / max(1, nxt - start)
        fill = bar.copy()
        fill.w = int(bar.w * frac)
        pygame.draw.rect(surf, (120, 90, 230), fill, border_radius=7)
        if reward.leveled_up and k >= 1.0:
            pulse = 0.75 + 0.25 * math.sin(t * 6)
            lc = tuple(int(v * pulse) for v in T.ACCENT)
            self.text.draw(surf, f"LEVEL UP!  Lv {reward.level_before} → Lv {reward.level_after}",
                           (cx, card.y + 76), 20, lc, bold=True, anchor="midtop")
            before = campaign.hero_stats(reward.level_before)
            after = campaign.hero_stats(reward.level_after)
            parts = [f"{unit_name(u)} HP {before[u]['max_hp']}→{after[u]['max_hp']}"
                     for u in HERO_UIDS]
            hero0 = HERO_UIDS[0]
            gain = f"+{round((after[hero0]['power_mult'] - before[hero0]['power_mult']) * 100)}%"
            self.text.draw(surf, " · ".join(parts) + f" · хүч {gain}", (cx, card.y + 106), 15,
                           T.TEXT, anchor="midtop")
        elif not won:
            self.text.draw(surf, "Ялагдсан ч туршлага олов — хүчээ авч дахин оролдоорой",
                           (cx, card.y + 84), 16, T.TEXT_DIM, anchor="midtop")
        else:
            self.text.draw(surf, "Дараагийн level хүртэл: "
                           + ("MAX" if nxt is None else f"{nxt - xp_now} XP"),
                           (cx, card.y + 84), 16, T.TEXT_DIM, anchor="midtop")

        # олз
        dy = card.bottom + DROP_GAP
        drop_card = pygame.Rect(0, 0, card.w, 116)
        drop_card.midtop = (cx, dy)
        if reward.drop is not None:
            it = ITEMS[reward.drop]
            pygame.draw.rect(surf, T.PANEL_BG, drop_card, border_radius=10)
            pygame.draw.rect(surf, RARITY_COLORS.get(it.rarity, T.TEXT), drop_card, 1,
                             border_radius=10)
            chest = self._icon("chest", 44)
            if chest is not None:
                surf.blit(chest, (drop_card.x + 14, drop_card.y + 12))
            self._item_slot(surf, (drop_card.x + 66, drop_card.y + 10, 48, 48), reward.drop)
            self.text.draw(surf, f"Олз: {it.name}", (drop_card.x + 128, drop_card.y + 12), 20,
                           RARITY_COLORS.get(it.rarity, T.TEXT), bold=True)
            self.text.draw(surf, f"{RARITY_NAMES.get(it.rarity, it.rarity)} · {item_effect(reward.drop)}",
                           (drop_card.x + 128, drop_card.y + 40), 15, T.TEXT_DIM)
            if reward.assigned_to is None:
                self._drop_buttons(surf, campaign, drop_card.y + DROP_BUTTONS_DY, mouse_pos,
                                   draw_buttons)
            else:
                who = "Цүнхэнд хадгалагдлаа" if reward.assigned_to == "bag" else \
                    f"{unit_name(reward.assigned_to)} зүүлээ"
                self.text.draw(surf, who, (cx, drop_card.y + 80), 18, T.HP_HERO, anchor="midtop")
        elif won:
            self.text.draw(surf, "Энэ удаа олз унасангүй", (cx, dy + 20), 17, T.TEXT_DIM,
                           anchor="midtop")

        # нээгдсэн үе
        y = drop_card.bottom + 8
        if reward.unlocked:
            nf, ni = parse_key(reward.unlocked)
            text = (f"Шинэ давхар нээгдлээ: {FLOORS[nf - 1].name}" if ni == 1
                    else f"Шинэ үе нээгдлээ: {reward.unlocked}")
            self.text.draw(surf, text, (cx, y), 18, T.ACCENT, bold=True, anchor="midtop")
        if stats is not None:
            self._hero_stats_row(surf, state, stats, (cx, y + 34), card.w)
        self._menu_buttons(surf, menu, mouse_pos)

    def _hero_stats_row(self, surf, state, stats, top_center, width):
        """Баатар бүрийн тулааны дүн: хохирол, эдгээлт, алсан, үлдсэн HP."""
        rows = [r for r in stats.rows(state) if r["side"] == "heroes"]
        if not rows:
            return
        col = width // len(rows)
        x0 = top_center[0] - width // 2
        for k, row in enumerate(rows):
            x = x0 + k * col
            kind = state.units[row["uid"]].kind
            self._unit_badge(surf, kind, (x + 24, top_center[1] + 20), 40, dim=not row["alive"])
            hp = f"{row['hp']}/{row['max_hp']} HP" if row["alive"] else "унасан"
            self.text.draw(surf, f"{unit_name(row['uid'], state)} · {hp}",
                           (x + 50, top_center[1] + 2), 15, T.TEXT if row["alive"] else T.TEXT_DIM)
            self.text.draw(surf, f"хохирол {row['damage']} · эдгээлт {row['heal']} · алсан {row['kills']}",
                           (x + 50, top_center[1] + 22), 13, T.TEXT_DIM)

    def _drop_buttons(self, surf, campaign, top, mouse_pos, enabled):
        w = surf.get_width()
        for name, rect in M.reward_drop_buttons(w, top).items():
            if name == "bag":
                label, ok = "Цүнхэнд (4)", True
            else:
                n = HERO_UIDS.index(name) + 1
                ok = campaign.can_equip(name)
                label = f"{unit_name(name)} ({n})" if ok else f"{unit_name(name)}: дүүрсэн"
            hot = mouse_pos is not None and L.point_in(rect, mouse_pos)
            self._button(surf, rect, label, enabled=ok and enabled, hot=hot)

    def _menu_buttons(self, surf, menu, mouse_pos):
        w = surf.get_width()
        for k, (item, rect) in enumerate(zip(menu.items, menu.rects(w))):
            selected = k == menu.index and item.enabled
            self._button(surf, rect, item.label, enabled=item.enabled, hot=selected,
                         accent=k == 0)
