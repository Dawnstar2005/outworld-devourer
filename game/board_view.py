"""8×8 талбар, дүр, тодруулга зурах (pygame).

Дүрүүдийг одоохондоо өнгөт дөрвөлжин + үсгээр зурна (11/29-нд Kenney CC0 sprite орно).
Зурах дараалал: талбар → мөсөн хана → хөдлөх нүд → сонголт → бүдгэрэх дүр → дүр → хөвөх тоо.
"""

import pygame

from engine.constants import BOARD_H, BOARD_W

from . import layout as L
from . import theme as T

UNIT_INSET = 8
HP_BAR_H = 6


class BoardView:
    def __init__(self, text: T.Text):
        self.text = text
        self._board = self._build_board()
        self._move_fill = self._cell_overlay(T.MOVE_FILL)
        self._move_hover = self._cell_overlay(T.MOVE_HOVER)

    # ---- нэг удаа бэлтгэх surface ----
    def _build_board(self) -> pygame.Surface:
        surf = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H))
        for x in range(BOARD_W):
            for y in range(BOARD_H):
                color = T.CELL_LIGHT if (x + y) % 2 == 0 else T.CELL_DARK
                pygame.draw.rect(surf, color, (x * L.CELL, y * L.CELL, L.CELL, L.CELL))
        for i in range(BOARD_W + 1):
            pygame.draw.line(surf, T.GRID_LINE, (i * L.CELL, 0), (i * L.CELL, L.BOARD_PX_H))
        for i in range(BOARD_H + 1):
            pygame.draw.line(surf, T.GRID_LINE, (0, i * L.CELL), (L.BOARD_PX_W, i * L.CELL))
        for x in range(BOARD_W):   # координатын жижиг тэмдэг (debug, log уншихад)
            for y in range(BOARD_H):
                lbl = self.text.render(f"{x},{y}", 13, (90, 94, 108))
                surf.blit(lbl, (x * L.CELL + 3, y * L.CELL + 2))
        return surf

    @staticmethod
    def _cell_overlay(rgba) -> pygame.Surface:
        surf = pygame.Surface((L.CELL, L.CELL), pygame.SRCALPHA)
        surf.fill(rgba)
        return surf

    # ---- зурах ----
    def draw(self, surf, state, selection, anim, hover, interactive: bool):
        surf.blit(self._board, (L.BOARD_X, L.BOARD_Y))
        self._draw_walls(surf, state)
        sel_unit = selection.unit
        if sel_unit is not None:
            for cell in selection.move_cells:
                if cell == sel_unit.pos:
                    continue
                overlay = self._move_hover if cell == hover else self._move_fill
                surf.blit(overlay, L.cell_rect(cell)[:2])
        if interactive and hover is not None:
            pygame.draw.rect(surf, T.HOVER_LINE, L.cell_rect(hover), 2)
        for fade in anim.fades:
            self._draw_unit_box(surf, fade.kind, fade.uid, L.cell_center(fade.cell), 1.0,
                                acted=False, alpha=fade.alpha)
        for u in state.alive_units():
            center = anim.unit_center(u.uid, u.pos)
            acted = u.acted and u.side == state.side_to_act
            self._draw_unit_box(surf, u.kind, u.uid, center, u.hp / u.max_hp, acted=acted)
            if sel_unit is not None and u.uid == sel_unit.uid:
                r = pygame.Rect(0, 0, L.CELL - 4, L.CELL - 4)
                r.center = (int(center[0]), int(center[1]))
                pygame.draw.rect(surf, T.SELECT_LINE, r, 3, border_radius=8)
        for f in anim.floats:
            label = self.text.render(f.text, 26, T.FLOAT_COLORS[f.kind], bold=True).copy()
            label.set_alpha(int(255 * f.alpha))
            x, y = f.pos()
            surf.blit(label, label.get_rect(center=(int(x), int(y) - L.CELL // 3)))

    def _draw_walls(self, surf, state):
        for cell, turns in state.walls.items():
            x, y, w, h = L.cell_rect(cell)
            r = pygame.Rect(x + 4, y + 4, w - 8, h - 8)
            pygame.draw.rect(surf, T.WALL, r, border_radius=4)
            pygame.draw.rect(surf, (230, 250, 255), r, 2, border_radius=4)
            self.text.draw(surf, str(turns), r.center, 22, (40, 80, 110), bold=True,
                           anchor="center")

    def _draw_unit_box(self, surf, kind, uid, center, hp_frac, acted, alpha=1.0):
        size = L.CELL - 2 * UNIT_INSET
        color = T.UNIT_COLORS[kind]
        if acted:
            color = T.dim(color)
        box = pygame.Surface((size, size), pygame.SRCALPHA)
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
