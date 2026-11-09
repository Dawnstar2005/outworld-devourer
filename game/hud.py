"""Ээлжийн мөр, дүрүүдийн HP, сонгосон дүрийн мэдээлэл, log, товч (pygame)."""

import pygame

from engine import DEMONS, HEROES, SKILLS
from engine.constants import MAX_ROUNDS

from . import layout as L
from . import theme as T
from .labels import TURN_NAMES, WINNER_NAMES, skill_name, unit_name

ROW_H = 24
LOG_LINE_H = 18
BUTTON_LABELS = {"wait": "Хүлээх (W)", "end_turn": "Ээлж дуусгах (E)"}
HINT = "Хулгана: сонгох, хөдөлгөх · Баруун товч / Esc: цуцлах"


class Hud:
    def __init__(self, text: T.Text):
        self.text = text

    def draw(self, surf, state, selection, log_lines, status, buttons_enabled, mouse_pos):
        self._top_bar(surf, state, status)
        pygame.draw.rect(surf, T.PANEL_BG, (L.PANEL_X, L.PANEL_Y, L.PANEL_W, L.PANEL_H),
                         border_radius=8)
        y = self._units(surf, state, selection, L.PANEL_Y + 10)
        y = self._selected(surf, state, selection, y + 10)
        self._log(surf, log_lines, y + 10)
        self._buttons(surf, buttons_enabled, mouse_pos)

    # ---- дээд мөр ----
    def _top_bar(self, surf, state, status):
        side = TURN_NAMES.get(state.side_to_act, state.side_to_act)
        color = T.UNIT_COLORS["knight"] if state.side_to_act == HEROES else T.UNIT_COLORS["demon_lord"]
        if state.is_over:
            side, color = "Тоглолт дууслаа", T.ACCENT
        cy = L.TOP_BAR_H // 2 + L.MARGIN // 2
        self.text.draw(surf, f"Round {state.round}/{MAX_ROUNDS}", (L.BOARD_X, cy), 24,
                       T.TEXT_DIM, anchor="midleft")
        self.text.draw(surf, side, (L.BOARD_X + 150, cy), 26, color, bold=True,
                       anchor="midleft")
        if status:
            self.text.draw(surf, status, (L.BOARD_X + L.BOARD_PX_W, cy), 22, T.ACCENT,
                           anchor="midright")
        self.text.draw(surf, HINT, (L.PANEL_X + L.PANEL_W, cy), 16, T.TEXT_DIM,
                       anchor="midright")

    # ---- дүрүүдийн жагсаалт ----
    def _units(self, surf, state, selection, y):
        x0 = L.PANEL_X + 12
        self.text.draw(surf, "Дүрүүд", (x0, y), 20, T.TEXT_DIM, bold=True)
        y += 26
        for side in (HEROES, DEMONS):
            for u in (u for u in state.units.values() if u.side == side):
                acted = u.alive and u.acted and u.side == state.side_to_act
                name_color = T.TEXT if u.alive and not acted else T.TEXT_DIM
                swatch = T.UNIT_COLORS[u.kind] if u.alive else T.dim(T.UNIT_COLORS[u.kind])
                pygame.draw.rect(surf, swatch, (x0, y + 4, 14, 14), border_radius=3)
                if selection.unit_uid == u.uid:
                    pygame.draw.rect(surf, T.SELECT_LINE, (x0 - 3, y + 1, 20, 20), 2,
                                     border_radius=4)
                self.text.draw(surf, unit_name(u.uid, state), (x0 + 22, y + 3), 19, name_color)
                bar = pygame.Rect(x0 + 122, y + 6, 110, 10)
                pygame.draw.rect(surf, T.HP_BG, bar, border_radius=3)
                if u.alive and u.hp > 0:
                    frac = u.hp / u.max_hp
                    fill = bar.copy()
                    fill.w = max(2, int(bar.w * frac))
                    col = T.HP_LOW if frac < 0.3 else (T.HP_HERO if side == HEROES else T.HP_DEMON)
                    pygame.draw.rect(surf, col, fill, border_radius=3)
                hp_text = f"{u.hp}/{u.max_hp}" if u.alive else "унасан"
                self.text.draw(surf, hp_text, (x0 + 240, y + 3), 17, name_color)
                y += ROW_H
        return y

    # ---- сонгосон дүр ----
    def _selected(self, surf, state, selection, y):
        x0 = L.PANEL_X + 12
        pygame.draw.line(surf, T.PANEL_LINE, (x0, y), (L.PANEL_X + L.PANEL_W - 12, y))
        y += 8
        u = selection.unit
        if u is None:
            msg = "Баатар сонгоно уу" if selection.my_turn else ""
            self.text.draw(surf, msg, (x0, y), 19, T.TEXT_DIM)
            return y + 4 * 20
        self.text.draw(surf, unit_name(u.uid, state), (x0, y), 22, T.ACCENT, bold=True)
        self.text.draw(surf, f"HP {u.hp}/{u.max_hp} · хөдөлгөөн {u.move}", (x0 + 110, y + 3),
                       17, T.TEXT)
        y += 24
        sids = list(u.type.skills) + ([u.type.leap] if u.type.leap else [])
        for sid in sids:
            cd = u.cooldowns.get(sid, 0)
            ready = cd == 0
            status = "бэлэн" if ready else f"{cd} ээлж"
            self.text.draw(surf, f"{skill_name(sid)}", (x0 + 8, y), 18,
                           T.TEXT if ready else T.TEXT_DIM)
            self.text.draw(surf, f"зай {SKILLS[sid].range} · {status}", (x0 + 150, y), 17,
                           T.TEXT_DIM)
            y += 20
        return y + max(0, 3 - len(sids)) * 20

    # ---- log ----
    def _log(self, surf, lines, y):
        x0 = L.PANEL_X + 12
        pygame.draw.line(surf, T.PANEL_LINE, (x0, y), (L.PANEL_X + L.PANEL_W - 12, y))
        y += 6
        bottom = L.PANEL_Y + L.PANEL_H - L.BUTTON_H - 10
        fit = max(0, (bottom - y) // LOG_LINE_H)
        for line in list(lines)[-fit:] if fit else []:
            color = T.ACCENT if line.startswith("—") else T.TEXT_DIM
            self.text.draw(surf, line, (x0, y), 16, color)
            y += LOG_LINE_H

    # ---- товч ----
    def _buttons(self, surf, enabled, mouse_pos):
        for name, rect in L.BUTTONS.items():
            on = enabled.get(name, False)
            hover = on and mouse_pos is not None and L.point_in(rect, mouse_pos)
            color = T.BUTTON_HOVER if hover else (T.BUTTON if on else T.BUTTON_OFF)
            pygame.draw.rect(surf, color, rect, border_radius=8)
            r = pygame.Rect(rect)
            self.text.draw(surf, BUTTON_LABELS[name], r.center, 20,
                           T.TEXT if on else T.TEXT_DIM, anchor="center")

    # ---- тоглолт дууссан ----
    def draw_game_over(self, surf, state):
        shade = pygame.Surface((L.BOARD_PX_W, L.BOARD_PX_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        surf.blit(shade, (L.BOARD_X, L.BOARD_Y))
        cx = L.BOARD_X + L.BOARD_PX_W // 2
        cy = L.BOARD_Y + L.BOARD_PX_H // 2
        title = WINNER_NAMES.get(state.winner, str(state.winner))
        color = T.HP_HERO if state.winner == HEROES else (T.HP_DEMON if state.winner == DEMONS
                                                          else T.ACCENT)
        box = pygame.Rect(0, 0, L.BOARD_PX_W - 80, 130)
        box.center = (cx, cy + 5)
        pygame.draw.rect(surf, T.PANEL_BG, box, border_radius=12)
        pygame.draw.rect(surf, color, box, 2, border_radius=12)
        self.text.draw(surf, title, (cx, cy - 20), 48, color, bold=True, anchor="center")
        self.text.draw(surf, f"{state.round} round · R — дахин эхлэх", (cx, cy + 30), 24,
                       T.TEXT, anchor="center")
