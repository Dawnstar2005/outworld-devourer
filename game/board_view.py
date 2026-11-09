"""8×8 талбар, дүр, тодруулга зурах (pygame).

Дүр, шал, мөсөн хана: Kenney CC0 sprite (game/sprites.py). Файл олдохгүй бол өнгөт
дөрвөлжин + үсгээр зурна.
Зурах дараалал: талбар → мөсөн хана → гэрэлтэлт → хөдлөх/бай нүд → урьдчилсан харагдац →
бүдгэрэх дүр → дүр (+ тэмдэг) → очих нүдний сүүдэр → үр нөлөөний тоо → хөвөх тоо.

Бай нүд, 3×3 бүс, Мөсөн ханын нүд бүгд engine-ээс (unit_actions, area_cells, wall_cells) ирнэ.
"""

import math
import re

import pygame

from engine import area_cells, wall_cells
from engine.constants import BOARD_H, BOARD_W

from . import layout as L
from . import theme as T

UNIT_INSET = 8
HP_BAR_H = 6
HELP_KINDS = ("heal", "shield")
SPRITE_PX = 64            # Dungeon sprite-ийн хэмжээ
BOSS_PX = 72              # босс арай том
FRAME = L.MARGIN          # талбарын эргэн тойрны хананы зурвасын өргөн
TORCH_PX = 34
GLOW_R = 64
GLOW_COLORS = {"slime": (120, 230, 90), "goblin": (255, 170, 60), "vampire": (200, 70, 120),
               "demon": (255, 110, 60), "hell": (255, 120, 40)}
FLOOR_ACCENT_EVERY = {"hell": 19}     # floor_1 тун ховор (хэт тод лав); бусад сэдэвт арай олон
FLOOR_ACCENT_DEFAULT = 6
_DIGITS = re.compile(r"(\d+)$")


def target_category(kind) -> str:
    if kind == "wall":
        return "wall"
    return "help" if kind in HELP_KINDS else "harm"


def _cell_hash(x: int, y: int, salt: int = 0) -> int:
    """Нүд бүрт тогтмол (deterministic) псевдо-санамсаргүй тоо."""
    return ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) & 0x7FFFFFFF


def _glow_surface(color, radius=GLOW_R) -> pygame.Surface:
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 16
    for i in range(steps):
        r = radius - i * radius // steps
        a = int(110 * ((i + 1) / steps) ** 2)
        pygame.draw.circle(surf, color + (a,), (radius, radius), r)
    return surf


class BoardView:
    def __init__(self, text: T.Text, sprites=None):
        self.text = text
        self.sprites = sprites          # ok=False үед ч хадгална: Dungeon sprite тусдаа ачаалагдсан байж болно
        self._t = 0.0
        self._theme_name = None
        self._tiles = None
        self._boards = {}               # theme → (surface, pos) cache
        self._board, self._board_pos = self._get_board(None)
        self._overlays = {}
        self._obst_key = None
        self._obst_surf = None
        self._scaled = {}
        self._shadow = None
        self._glow = None
        self._torch_pts = []

    # ---- сэдэв ----
    def set_theme(self, theme) -> None:
        """Давхрын сэдэв (slime/goblin/vampire/demon/hell). None → хуучин харагдац."""
        tiles = self.sprites.theme(theme) if (theme and self.sprites is not None) else None
        self._tiles = tiles
        self._theme_name = theme if tiles is not None else None
        self._board, self._board_pos = self._get_board(self._theme_name)
        self._obst_key = None
        self._glow = None
        if tiles is not None and tiles.torch is not None:
            cy0, cy1 = L.BOARD_Y + L.BOARD_PX_H // 4, L.BOARD_Y + 3 * L.BOARD_PX_H // 4
            xl, xr = L.BOARD_X - 2, L.BOARD_X + L.BOARD_PX_W + 2
            self._torch_pts = [(xl, cy0), (xl, cy1), (xr, cy0), (xr, cy1)]
            self._glow = _glow_surface(GLOW_COLORS.get(theme, (255, 160, 60)))
        else:
            self._torch_pts = []

    def tick(self, dt: float) -> None:
        """Бамбарын анивчилтын цаг (заавал биш; `draw(t=...)`-ийн оронд)."""
        self._t += dt

    def _get_board(self, theme):
        got = self._boards.get(theme)
        if got is None:
            got = self._build_themed(self._tiles, theme) if theme else \
                (self._build_board(), (L.BOARD_X, L.BOARD_Y))
            self._boards[theme] = got
        return got

    # ---- нэг удаа бэлтгэх surface ----
    def _build_board(self) -> pygame.Surface:
        surf = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H))
        shade = pygame.Surface((L.CELL, L.CELL), pygame.SRCALPHA)
        for x in range(BOARD_W):
            for y in range(BOARD_H):
                rect = (x * L.CELL, y * L.CELL, L.CELL, L.CELL)
                tile = self.sprites.floor(x, y) if self.sprites else None
                if tile is not None:   # Kenney шал + тодруулга харагдахуйц бараан давхарга
                    surf.blit(tile, rect[:2])
                    shade.fill((10, 10, 20, 120 if (x + y) % 2 == 0 else 150))
                    surf.blit(shade, rect[:2])
                else:
                    color = T.CELL_LIGHT if (x + y) % 2 == 0 else T.CELL_DARK
                    pygame.draw.rect(surf, color, rect)
        for i in range(BOARD_W + 1):
            pygame.draw.line(surf, T.GRID_LINE, (i * L.CELL, 0), (i * L.CELL, L.BOARD_PX_H))
        for i in range(BOARD_H + 1):
            pygame.draw.line(surf, T.GRID_LINE, (0, i * L.CELL), (L.BOARD_PX_W, i * L.CELL))
        for x in range(BOARD_W):   # координатын жижиг тэмдэг (debug, log уншихад)
            for y in range(BOARD_H):
                lbl = self.text.render(f"{x},{y}", 13, (90, 94, 108))
                surf.blit(lbl, (x * L.CELL + 3, y * L.CELL + 2))
        return surf

    def _build_themed(self, tiles, theme):
        """Сэдэвт талбар + эргэн тойрны хана: нэг том surface (хана хүртэл) болгож бэлтгэнэ."""
        W, H = L.BOARD_PX_W + 2 * FRAME, L.BOARD_PX_H + 2 * FRAME
        surf = pygame.Surface((W, H))
        surf.fill((14, 12, 16))
        every = FLOOR_ACCENT_EVERY.get(theme, FLOOR_ACCENT_DEFAULT)
        shade = pygame.Surface((L.CELL, L.CELL), pygame.SRCALPHA)
        for x in range(BOARD_W):
            for y in range(BOARD_H):
                idx = 0
                if len(tiles.floors) > 1 and _cell_hash(x, y, 1) % every == 0:
                    idx = 1
                pos = (FRAME + x * L.CELL, FRAME + y * L.CELL)
                surf.blit(tiles.floors[idx], pos)
                # хөдлөх/бай тодруулга харагдахын тулд бага зэрэг бараандуулна
                shade.fill((8, 8, 14, 70 if (x + y) % 2 == 0 else 100))
                surf.blit(shade, pos)
        grid = (0, 0, 0, 70)
        gl = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H), pygame.SRCALPHA)
        for i in range(BOARD_W + 1):
            pygame.draw.line(gl, grid, (i * L.CELL, 0), (i * L.CELL, L.BOARD_PX_H))
        for i in range(BOARD_H + 1):
            pygame.draw.line(gl, grid, (0, i * L.CELL), (L.BOARD_PX_W, i * L.CELL))
        surf.blit(gl, (FRAME, FRAME))
        # хана: wall tile-ийг зурвасын өргөнд багтааж (smoothscale), бараандуулна
        if tiles.wall is not None:
            wt = pygame.transform.smoothscale(tiles.wall, (FRAME, FRAME))
            wt.fill((115, 115, 125, 255), special_flags=pygame.BLEND_RGBA_MULT)
            for i in range(0, W, FRAME):
                surf.blit(wt, (i, 0))
                surf.blit(wt, (i, H - FRAME))
            for j in range(FRAME, H - FRAME, FRAME):
                surf.blit(wt, (0, j))
                surf.blit(wt, (W - FRAME, j))
            inner = pygame.Rect(FRAME - 1, FRAME - 1, L.BOARD_PX_W + 2, L.BOARD_PX_H + 2)
            pygame.draw.rect(surf, (10, 8, 12), inner, 2)
        # бамбар (ханан дээр, талбарын ирмэг рүү бага зэрэг орсон)
        if tiles.torch is not None:
            torch = pygame.transform.scale(tiles.torch, (TORCH_PX, TORCH_PX))
            cys = (L.BOARD_PX_H // 4, 3 * L.BOARD_PX_H // 4)
            for cx in (FRAME - 2, FRAME + L.BOARD_PX_W + 2):
                for cy in cys:
                    surf.blit(torch, (cx - TORCH_PX // 2, FRAME + cy - TORCH_PX // 2))
        return surf, (L.BOARD_X - FRAME, L.BOARD_Y - FRAME)

    def _overlay(self, rgba) -> pygame.Surface:
        surf = self._overlays.get(rgba)
        if surf is None:
            surf = pygame.Surface((L.CELL, L.CELL), pygame.SRCALPHA)
            surf.fill(rgba)
            self._overlays[rgba] = surf
        return surf

    def _fill(self, surf, cell, rgba, alpha=None):
        ov = self._overlay(rgba)
        if alpha is not None:
            ov = ov.copy()
            ov.set_alpha(int(255 * alpha))
        surf.blit(ov, L.cell_rect(cell)[:2])

    # ---- зурах ----
    def draw(self, surf, state, selection, anim, hover, interactive: bool, fx=None, t=None):
        """`t` — секундээр цаг (бамбарын анивчилт). None бол tick()/системийн цагийг ашиглана."""
        if t is None:
            t = self._t if self._t else pygame.time.get_ticks() / 1000.0
        surf.blit(self._board, self._board_pos)
        self._draw_obstacles(surf, state)
        self._draw_torch_glow(surf, t)
        self._draw_walls(surf, state.walls)
        for fl in anim.flashes:
            for cell in fl.cells:
                self._fill(surf, cell, T.FLASH_COLORS[fl.kind] + (150,), fl.alpha)

        if fx:
            fx("under")                      # VFX: дүрийн доорх (газрын) эффект
        sel = selection.unit
        hover_action = selection.hover_action(hover) if interactive else None
        if sel is not None:
            if selection.skill is None:
                self._draw_moves(surf, selection, sel, hover)
            else:
                self._draw_targets(surf, selection, hover, hover_action)
        if interactive and hover is not None:
            pygame.draw.rect(surf, T.HOVER_LINE, L.cell_rect(hover), 2)

        for fade in anim.fades:
            self._draw_unit_box(surf, fade.kind, fade.uid, L.cell_center(fade.cell), 1.0,
                                acted=False, alpha=fade.alpha)
        for u in state.alive_units():
            center = anim.unit_center(u.uid, u.pos)
            acted = u.acted and u.side == state.side_to_act
            self._draw_unit_box(surf, u.kind, u.uid, center, u.hp / u.max_hp, acted=acted)
            self._draw_badges(surf, u, center)
            if sel is not None and u.uid == sel.uid:
                self._outline(surf, center, T.SELECT_LINE)
        if sel is not None and selection.dest is not None and selection.dest != sel.pos:
            c = L.cell_center(selection.dest)
            self._draw_unit_box(surf, sel.kind, sel.uid, c, sel.hp / sel.max_hp, acted=False,
                                alpha=0.6)
            self._outline(surf, c, T.SELECT_LINE)

        if sel is not None and interactive:
            action = hover_action or selection.armed_action()
            self._draw_preview(surf, state, selection, selection.preview(action))
        if fx:
            fx("over")                       # VFX: дүрийн дээрх сум, оч, тэсрэлт
        for f in anim.floats:
            size = 20 if f.kind == "skill" else 26
            label = self.text.render(f.text, size, T.FLOAT_COLORS[f.kind], bold=True).copy()
            label.set_alpha(int(255 * f.alpha))
            x, y = f.pos()
            surf.blit(label, label.get_rect(center=(int(x), int(y) - L.CELL // 3)))

    def _draw_obstacles(self, surf, state) -> None:
        obs = getattr(state, "obstacles", None)
        if not obs:
            return
        key = (self._theme_name, frozenset(obs))
        if self._obst_key != key:
            layer = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H), pygame.SRCALPHA)
            tiles = self._tiles
            for (x, y) in obs:
                pos = (x * L.CELL, y * L.CELL)
                if tiles is not None and tiles.obstacles:
                    # ил тод дэвсгэртэй тул доор нь шалны tile тавина
                    layer.blit(tiles.floors[0], pos)
                    dark = pygame.Surface((L.CELL, L.CELL), pygame.SRCALPHA)
                    dark.fill((8, 8, 14, 110))
                    layer.blit(dark, pos)
                    ob = tiles.obstacles[_cell_hash(x, y, 2) % len(tiles.obstacles)]
                    layer.blit(ob, pos)
                else:
                    self._rock(layer, pos)
            self._obst_key, self._obst_surf = key, layer
        surf.blit(self._obst_surf, (L.BOARD_X, L.BOARD_Y))

    @staticmethod
    def _rock(layer, pos) -> None:
        """Сэдэвгүй үеийн саад: энгийн чулуу."""
        r = pygame.Rect(pos[0] + 8, pos[1] + 12, L.CELL - 16, L.CELL - 22)
        pygame.draw.ellipse(layer, (20, 20, 26), r.move(2, 3))
        pygame.draw.ellipse(layer, (96, 98, 112), r)
        pygame.draw.ellipse(layer, (140, 142, 158), r.inflate(-18, -20).move(-6, -6))
        pygame.draw.ellipse(layer, (50, 52, 62), r, 2)

    def _draw_torch_glow(self, surf, t: float) -> None:
        if self._glow is None:
            return
        for i, (cx, cy) in enumerate(self._torch_pts):
            k = 0.78 + 0.14 * math.sin(t * 9.0 + i * 2.1) + 0.08 * math.sin(t * 23.0 + i * 5.3)
            g = self._glow
            g.set_alpha(max(0, min(255, int(255 * k))))
            surf.blit(g, (cx - GLOW_R, cy - 4 - GLOW_R))

    def _draw_moves(self, surf, selection, sel, hover):
        for cell in selection.move_cells:
            if cell == sel.pos or cell == selection.dest:
                continue
            self._fill(surf, cell, T.MOVE_HOVER if cell == hover else T.MOVE_FILL)
        if selection.dest is not None and selection.dest != sel.pos:
            self._fill(surf, selection.dest, T.MOVE_HOVER)

    def _draw_targets(self, surf, selection, hover, hover_action):
        kind = selection.skill_kind(selection.skill)
        cat = target_category(kind)
        if not selection.needs_target:              # Taunt, Imp дуудах: дүрийн нүдийг тодруулна
            self._fill(surf, selection.dest, T.TARGET_HOVER["harm" if kind == "taunt" else "help"])
            return
        for cell in selection.target_cells:
            self._fill(surf, cell, T.TARGET_HOVER[cat] if cell == hover else T.TARGET_FILL[cat])
        if hover_action is None:
            return
        if kind == "area_damage":
            for cell in area_cells(hover_action.target):
                self._fill(surf, cell, T.AREA_PREVIEW)
        elif kind == "wall":
            self._draw_walls(surf, {c: "" for c in wall_cells(hover_action.target,
                                                             hover_action.variant)}, alpha=0.6)

    def _draw_preview(self, surf, state, selection, effects):
        """Хулгана дээр байгаа нүүдлийн үр дүн: хохирол, эдгэрэл, бамбай, хараал, taunt."""
        sel = selection.unit
        for uid, fx in effects.items():
            u = state.units[uid]
            cell = selection.dest if sel is not None and uid == sel.uid else u.pos
            cx, cy = L.cell_center(cell)
            parts = []
            if "hp" in fx:
                parts.append((f"{fx['hp']:+d}", T.PREVIEW_HARM if fx["hp"] < 0 else T.PREVIEW_HELP))
            if fx.get("dies"):
                parts.append(("унана", T.PREVIEW_HARM))
            if "shield" in fx:
                parts.append((f"бамбай {fx['shield']}", T.PREVIEW_HELP))
            if fx.get("cursed"):
                parts.append(("хараал", T.PREVIEW_STATUS))
            if fx.get("taunted"):
                parts.append(("taunt", T.PREVIEW_STATUS))
            if fx.get("dies"):
                r = pygame.Rect(L.cell_rect(cell)).inflate(-6, -6)
                pygame.draw.line(surf, T.PREVIEW_HARM, r.topleft, r.bottomright, 3)
                pygame.draw.line(surf, T.PREVIEW_HARM, r.topright, r.bottomleft, 3)
            y = cy - L.CELL // 2 - 2
            for text, color in parts:
                lbl = self.text.render(text, 20, color, bold=True)
                bg = lbl.get_rect(midbottom=(int(cx), int(y))).inflate(8, 2)
                pygame.draw.rect(surf, (15, 15, 22), bg, border_radius=4)
                surf.blit(lbl, lbl.get_rect(center=bg.center))
                y -= bg.height + 1

    def _draw_walls(self, surf, walls, alpha=1.0):
        for cell, turns in walls.items():
            x, y, w, h = L.cell_rect(cell)
            tile = pygame.Surface((w - 8, h - 8), pygame.SRCALPHA)
            r = tile.get_rect()
            if self.sprites and self.sprites.wall is not None:
                tile.blit(self.sprites.wall, (0, 0))
                pygame.draw.rect(tile, (230, 250, 255), r, 2, border_radius=2)
            else:
                pygame.draw.rect(tile, T.WALL, r, border_radius=4)
                pygame.draw.rect(tile, (230, 250, 255), r, 2, border_radius=4)
            if turns != "":
                lbl = self.text.render(str(turns), 22, (20, 50, 80), bold=True)
                bg = lbl.get_rect(center=r.center).inflate(8, 2)
                pygame.draw.rect(tile, (220, 240, 255), bg, border_radius=4)
                tile.blit(lbl, lbl.get_rect(center=r.center))
            if alpha < 1.0:
                tile.set_alpha(int(255 * alpha))
            surf.blit(tile, (x + 4, y + 4))

    @staticmethod
    def _outline(surf, center, color):
        r = pygame.Rect(0, 0, L.CELL - 4, L.CELL - 4)
        r.center = (int(center[0]), int(center[1]))
        pygame.draw.rect(surf, color, r, 3, border_radius=8)

    def _draw_badges(self, surf, u, center):
        """Бамбай (зүүн дээд), хараал / taunt (баруун дээд)."""
        size = L.CELL - 2 * UNIT_INSET
        left = int(center[0] - size / 2) - 4
        right = int(center[0] + size / 2) + 4
        top = int(center[1] - size / 2) - 6
        if u.shield:
            self._badge(surf, str(u.shield), T.BADGE_SHIELD, (left, top), "topleft")
        tags = []
        if u.cursed:
            tags.append((f"Х{u.cursed}", T.BADGE_CURSE))
        if u.taunted_by:
            tags.append((f"T{u.taunt_turns}", T.BADGE_TAUNT))
        for text, color in tags:
            r = self._badge(surf, text, color, (right, top), "topright")
            right = r.left - 2

    def _badge(self, surf, text, color, pos, anchor):
        lbl = self.text.render(text, 15, (255, 255, 255), bold=True)
        r = lbl.get_rect(**{anchor: pos}).inflate(6, 2)
        r = r.move(-3 if anchor == "topright" else 3, 1)
        pygame.draw.rect(surf, color, r, border_radius=5)
        pygame.draw.rect(surf, (20, 20, 28), r, 1, border_radius=5)
        surf.blit(lbl, lbl.get_rect(center=r.center))
        return r

    def _scaled_unit(self, kind, dim, px):
        key = (kind, dim, px)
        if key not in self._scaled:
            img = self.sprites.dungeon.unit(kind, dim)
            if img is not None and img.get_width() != px:
                img = pygame.transform.scale(img, (px, px))
            self._scaled[key] = img
        return self._scaled[key]

    def _shadow_surf(self) -> pygame.Surface:
        if self._shadow is None:
            sh = pygame.Surface((56, 22), pygame.SRCALPHA)
            for i in range(5):
                pygame.draw.ellipse(sh, (0, 0, 0, 30), (i * 2, i, 56 - i * 4, 22 - i * 2))
            self._shadow = sh
        return self._shadow

    def _draw_unit_box(self, surf, kind, uid, center, hp_frac, acted, alpha=1.0):
        """Дүр зурах: Dungeon 64 px sprite (сүүдэр, цагираг, HP) → хуучин sprite → өнгөт хайрцаг."""
        cx, cy = int(center[0]), int(center[1])
        boss = T.is_boss(kind)
        px = BOSS_PX if boss else SPRITE_PX
        sprite = self._scaled_unit(kind, acted, px) if self.sprites is not None else None
        if sprite is None:
            self._draw_unit_legacy(surf, kind, uid, center, hp_frac, acted, alpha)
            return
        W = 96
        box = pygame.Surface((W, W), pygame.SRCALPHA)
        m = W // 2
        feet = m + px // 2 - 12                     # хөлийн түвшин
        ring_c = T.side_ring_color(kind)
        if acted:
            ring_c = T.dim(ring_c, 0.6)
        box.blit(self._shadow_surf(), (m - 28, feet - 12))
        rw = 52 if boss else 46
        ring = pygame.Rect(0, 0, rw, 18 if boss else 16)
        ring.center = (m, feet - 1)
        pygame.draw.ellipse(box, ring_c + (70,), ring)
        pygame.draw.ellipse(box, ring_c, ring, 3 if boss else 2)
        box.blit(sprite, sprite.get_rect(midbottom=(m, feet + 8)))
        mt = _DIGITS.search(uid or "")
        if mt and not boss and kind != "knight":
            num = self.text.render(mt.group(1), 15, (255, 255, 255), bold=True)
            box.blit(num, (m - px // 2 + 2, feet - px + 14))
        bar_w = 48 if not boss else 56
        bar = pygame.Rect(m - bar_w // 2, feet + 12, bar_w, 5)
        pygame.draw.rect(box, (10, 10, 14), bar.inflate(2, 2), border_radius=3)
        frac = max(0.0, min(1.0, hp_frac))
        if frac > 0:
            fill = bar.copy()
            fill.w = max(2, int(bar_w * frac))
            col = T.HP_LOW if frac < 0.3 else (T.HP_HERO if T._is_hero(kind) else T.HP_DEMON)
            pygame.draw.rect(box, col, fill, border_radius=2)
        if alpha < 1.0:
            box.set_alpha(int(255 * alpha))
        surf.blit(box, box.get_rect(center=(cx, cy - 4)))

    def _draw_unit_legacy(self, surf, kind, uid, center, hp_frac, acted, alpha=1.0):
        size = L.CELL - 2 * UNIT_INSET
        color = T.unit_color(kind)
        if acted:
            color = T.dim(color)
        box = pygame.Surface((size, size), pygame.SRCALPHA)
        sprite = self.sprites.unit(kind, dim=acted) if self.sprites else None
        if sprite is not None:
            # багийн өнгөтэй тавцан + Kenney sprite
            pygame.draw.rect(box, color + (95,), (0, 0, size, size), border_radius=10)
            pygame.draw.rect(box, color, (0, 0, size, size), 2, border_radius=10)
            box.blit(sprite, sprite.get_rect(center=(size // 2, size // 2 - 4)))
            if kind == "imp" and uid[3:].isdigit():
                num = self.text.render(uid[3:], 15, (255, 255, 255), bold=True)
                box.blit(num, (4, 2))
        else:
            pygame.draw.rect(box, color, (0, 0, size, size), border_radius=10)
            pygame.draw.rect(box, T.dim(color, 0.6) if not acted else (40, 40, 50),
                             (0, 0, size, size), 2, border_radius=10)
            letter = T.unit_letter(kind)
            if kind == "imp" and uid[3:].isdigit():
                letter += uid[3:]
            lbl = self.text.render(letter, 34 if kind != "imp" else 28,
                                   (255, 255, 255) if not acted else (150, 150, 160), bold=True)
            box.blit(lbl, lbl.get_rect(center=(size // 2, size // 2 - 4)))
        # HP мөр
        bar_w = size - 10
        bar = pygame.Rect(5, size - HP_BAR_H - 5, bar_w, HP_BAR_H)
        pygame.draw.rect(box, T.HP_BG, bar, border_radius=3)
        frac = max(0.0, min(1.0, hp_frac))
        if frac > 0:
            fill = bar.copy()
            fill.w = max(2, int(bar_w * frac))
            hp_color = T.HP_LOW if frac < 0.3 else (T.HP_DEMON if not T._is_hero(kind)
                                                     else T.HP_HERO)
            pygame.draw.rect(box, hp_color, fill, border_radius=3)
        if alpha < 1.0:
            box.set_alpha(int(255 * alpha))
        surf.blit(box, box.get_rect(center=(int(center[0]), int(center[1]))))
