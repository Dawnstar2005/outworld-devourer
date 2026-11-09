"""8×8 талбар, дүр, тодруулга зурах (pygame).

Дүр, шал, мөсөн хана: Kenney CC0 sprite (game/sprites.py). Файл олдохгүй бол өнгөт
дөрвөлжин + үсгээр зурна.
Зурах дараалал: талбар → мөсөн хана → гэрэлтэлт → хөдлөх/бай нүд → урьдчилсан харагдац →
бүдгэрэх дүр → дүр (+ тэмдэг) → очих нүдний сүүдэр → үр нөлөөний тоо → хөвөх тоо.

Бай нүд, 3×3 бүс, Мөсөн ханын нүд бүгд engine-ээс (unit_actions, area_cells, wall_cells) ирнэ.
"""

import pygame

from engine import area_cells, wall_cells
from engine.constants import BOARD_H, BOARD_W

from . import layout as L
from . import theme as T

UNIT_INSET = 8
HP_BAR_H = 6
HELP_KINDS = ("heal", "shield")


def target_category(kind) -> str:
    if kind == "wall":
        return "wall"
    return "help" if kind in HELP_KINDS else "harm"


class BoardView:
    def __init__(self, text: T.Text, sprites=None):
        self.text = text
        self.sprites = sprites if sprites is not None and sprites.ok else None
        self._board = self._build_board()
        self._overlays = {}

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
    def draw(self, surf, state, selection, anim, hover, interactive: bool):
        surf.blit(self._board, (L.BOARD_X, L.BOARD_Y))
        self._draw_walls(surf, state.walls)
        for fl in anim.flashes:
            for cell in fl.cells:
                self._fill(surf, cell, T.FLASH_COLORS[fl.kind] + (150,), fl.alpha)

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
        for f in anim.floats:
            size = 20 if f.kind == "skill" else 26
            label = self.text.render(f.text, size, T.FLOAT_COLORS[f.kind], bold=True).copy()
            label.set_alpha(int(255 * f.alpha))
            x, y = f.pos()
            surf.blit(label, label.get_rect(center=(int(x), int(y) - L.CELL // 3)))

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

    def _draw_unit_box(self, surf, kind, uid, center, hp_frac, acted, alpha=1.0):
        size = L.CELL - 2 * UNIT_INSET
        color = T.UNIT_COLORS[kind]
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
            letter = T.UNIT_LETTERS[kind]
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
            hp_color = T.HP_LOW if frac < 0.3 else (T.HP_DEMON if kind in ("demon_lord", "imp")
                                                     else T.HP_HERO)
            pygame.draw.rect(box, hp_color, fill, border_radius=3)
        if alpha < 1.0:
            box.set_alpha(int(255 * alpha))
        surf.blit(box, box.get_rect(center=(int(center[0]), int(center[1]))))
