"""Ээлжийн мөр, дүрүүдийн HP, сонгосон дүр + ур чадварын товч, log, товч (pygame)."""

import pygame

from engine import DEMONS, HEROES, SKILLS
from engine.constants import MAX_ROUNDS

from . import layout as L
from . import theme as T
from .labels import TURN_NAMES, WINNER_NAMES, skill_name, unit_name

ROW_H = 24
MIN_ROW_H = 16
LOG_LINE_H = 18
VARIANT_NAMES = {0: "хэвтээ", 1: "босоо"}


def hint_text(selection) -> str:
    """Дээд мөрний баруун талын зөвлөмж — одоо юу хийж болохыг хэлнэ."""
    if not selection.my_turn:
        return ""
    if selection.unit is None:
        return "Баатар сонгоно уу · E: ээлж дуусгах"
    if selection.skill is None:
        return "Нүд: очих · 1–4: ур чадвар · W: хүлээх/хөдлөх · баруун товч: буцах"
    if not selection.needs_target:
        return "Дүр эсвэл товчийг дахин дарж хэрэглэнэ · баруун товч: буцах"
    if selection.skill_kind(selection.skill) == "wall":
        return "Бай нүд сонгоно уу · V / дугуй: чиглэл · баруун товч: буцах"
    return "Бай сонгоно уу · баруун товч: буцах"


class Hud:
    def __init__(self, text: T.Text):
        self.text = text

    def draw(self, surf, state, selection, log_lines, status, buttons_enabled, mouse_pos,
             hover_unit=None, panel_hint=False):
        self._top_bar(surf, state, status, hint_text(selection))
        pygame.draw.rect(surf, T.PANEL_BG, (L.PANEL_X, L.PANEL_Y, L.PANEL_W, L.PANEL_H),
                         border_radius=8)
        self._units(surf, state, selection, L.UNITS_Y)
        if panel_hint:   # «Боссын бодол» хаалттай үед хаана нээхийг сануулна
            self.text.draw(surf, "Tab — Боссын бодол", (L.PANEL_X + L.PANEL_W - 12, L.UNITS_Y + 2),
                           16, T.TEXT_DIM, anchor="topright")
        info = selection.unit or hover_unit
        self._info(surf, state, selection, info, mouse_pos, buttons_enabled.get("skills", False))
        self._log(surf, log_lines, L.LOG_Y)
        self._buttons(surf, selection, buttons_enabled, mouse_pos)

    # ---- дээд мөр ----
    def _top_bar(self, surf, state, status, hint):
        side = TURN_NAMES.get(state.side_to_act, state.side_to_act)
        color = T.UNIT_COLORS["knight"] if state.side_to_act == HEROES else T.unit_color("demon_lord")
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
        if hint:
            self.text.draw(surf, hint, (L.PANEL_X + L.PANEL_W, cy), 16, T.TEXT_DIM,
                           anchor="midright")

    # ---- дүрүүдийн жагсаалт ----
    @staticmethod
    def unit_rows(state) -> list:
        """Баатрууд эхэлж, дараа нь дайснууд; тус бүрдээ амьд нь түрүүлж (босс тэргүүнд)."""
        def order(side):
            us = [u for u in state.units.values() if u.side == side]
            return sorted(us, key=lambda u: (not u.alive, not u.type.boss))
        return order(HEROES) + order(DEMONS)

    def _units(self, surf, state, selection, y):
        x0 = L.PANEL_X + 12
        self.text.draw(surf, "Дүрүүд", (x0, y), 20, T.TEXT_DIM, bold=True)
        y += 26
        rows = self.unit_rows(state)
        avail = L.INFO_Y - 4 - y
        row_h = max(MIN_ROW_H, min(ROW_H, avail // max(1, len(rows))))
        fit = max(1, avail // row_h)
        hidden = 0
        if len(rows) > fit:       # багтахгүй бол сүүлийн (унасан) мөрүүдийг «+N» болгож нэгтгэнэ
            hidden = len(rows) - (fit - 1)
            rows = rows[:fit - 1]
        compact = row_h < ROW_H
        fs = 15 if compact else 17
        for u in rows:
            side = u.side
            acted = u.alive and u.acted and u.side == state.side_to_act
            name_color = T.TEXT if u.alive and not acted else T.TEXT_DIM
            boss = u.type.boss
            if boss and u.alive:
                name_color = T.BOSS_RING
            base = T.unit_color(u.kind)
            swatch = base if u.alive else T.dim(base)
            pygame.draw.rect(surf, swatch, (x0, y + 3, 12, 12), border_radius=3)
            if boss:
                pygame.draw.rect(surf, T.BOSS_RING, (x0 - 1, y + 2, 14, 14), 1, border_radius=3)
            if selection.unit_uid == u.uid:
                pygame.draw.rect(surf, T.SELECT_LINE, (x0 - 3, y + 1, 18, 18), 2,
                                 border_radius=4)
            name = unit_name(u.uid, state)
            lvl = getattr(u, "level", 1)
            if lvl and lvl > 1 and side == HEROES:
                name += f" L{lvl}"
            self.text.draw(surf, name, (x0 + 20, y + 1), fs, name_color, bold=boss)
            bar = pygame.Rect(x0 + 148, y + 4, 84, 9 if compact else 10)
            pygame.draw.rect(surf, T.HP_BG, bar, border_radius=3)
            if u.alive and u.hp > 0:
                frac = u.hp / u.max_hp
                fill = bar.copy()
                fill.w = max(2, int(bar.w * frac))
                col = T.HP_LOW if frac < 0.3 else (T.HP_HERO if side == HEROES else T.HP_DEMON)
                pygame.draw.rect(surf, col, fill, border_radius=3)
                if u.shield:   # бамбайг HP мөрийн үргэлжлэл шиг харуулна
                    sh = pygame.Rect(fill.right, bar.y, 0, bar.h)
                    sh.w = min(bar.right - fill.right, int(bar.w * u.shield / u.max_hp))
                    if sh.w > 0:
                        pygame.draw.rect(surf, T.BADGE_SHIELD, sh, border_radius=3)
            hp_text = f"{u.hp}/{u.max_hp}" if u.alive else "унасан"
            self.text.draw(surf, hp_text, (x0 + 236, y + 1), 15 if compact else 17, name_color)
            y += row_h
        if hidden:
            self.text.draw(surf, f"+{hidden} дүр", (x0 + 20, y + 1), 15, T.TEXT_DIM)
            y += row_h
        return y

    # ---- сонгосон / хулгана дээрх дүр ----
    def _info(self, surf, state, selection, u, mouse_pos, skills_enabled):
        x0 = L.PANEL_X + 12
        y = L.INFO_Y
        pygame.draw.line(surf, T.PANEL_LINE, (x0, y), (L.PANEL_X + L.PANEL_W - 12, y))
        y += 8
        if u is None:
            return
        selected = selection.unit is not None and u.uid == selection.unit.uid
        self.text.draw(surf, unit_name(u.uid, state), (x0, y), 22,
                       T.ACCENT if selected else T.TEXT, bold=True)
        self.text.draw(surf, f"HP {u.hp}/{u.max_hp} · хөдөлгөөн {u.move}", (x0 + 120, y + 3),
                       17, T.TEXT)
        y += 24
        tags = []
        if u.shield:
            tags.append(f"бамбай {u.shield}")
        if u.cursed:
            tags.append(f"хараал {u.cursed} ээлж")
        if u.taunted_by:
            tags.append(f"taunt {u.taunt_turns} ээлж")
        if u.type.leap:
            cd = u.cooldowns.get(u.type.leap, 0)
            tags.append(f"{skill_name(u.type.leap)}: " + ("бэлэн" if cd == 0 else f"{cd} ээлж"))
        if u.acted and u.side == state.side_to_act:
            tags.append("нүүсэн")
        self.text.draw(surf, " · ".join(tags), (x0, y), 16, T.TEXT_DIM)

        for i, sid in enumerate(u.type.skills[:L.MAX_SKILLS]):
            rect = L.SKILL_BUTTONS[i]
            if selected:
                status = selection.skill_status(sid)
                armed = selection.skill == sid
            else:
                status = "ready" if u.cooldowns.get(sid, 0) == 0 else "cooldown"
                armed = False
            on = selected and skills_enabled and status == "ready"
            hover = on and mouse_pos is not None and L.point_in(rect, mouse_pos)
            color = T.BUTTON_HOVER if hover else (T.BUTTON if on else T.BUTTON_OFF)
            pygame.draw.rect(surf, color, rect, border_radius=6)
            if armed:
                pygame.draw.rect(surf, T.ACCENT, rect, 2, border_radius=6)
            r = pygame.Rect(rect)
            prefix = f"{i + 1}. " if selected else ""
            self.text.draw(surf, prefix + skill_name(sid), (r.x + 10, r.centery), 18,
                           T.TEXT if status == "ready" else T.TEXT_DIM, anchor="midleft")
            self.text.draw(surf, self._skill_right_text(selection, u, sid, status, armed),
                           (r.right - 10, r.centery), 15, T.ACCENT if armed else T.TEXT_DIM,
                           anchor="midright")

    @staticmethod
    def _skill_right_text(selection, u, sid, status, armed) -> str:
        sk = SKILLS[sid]
        if armed:
            if sk.kind == "wall":
                return f"{VARIANT_NAMES[selection.variant]} (V)"
            return "бай сонго" if selection.needs_target else "дахин дар"
        if status == "cooldown":
            return f"{u.cooldowns.get(sid, 0)} ээлж"
        if status == "no_target":
            return f"зай {sk.range} · бай алга"
        return f"зай {sk.range} · бэлэн"

    # ---- log ----
    def _log(self, surf, lines, y):
        x0 = L.PANEL_X + 12
        pygame.draw.line(surf, T.PANEL_LINE, (x0, y), (L.PANEL_X + L.PANEL_W - 12, y))
        y += 6
        bottom = L.PANEL_Y + L.PANEL_H - L.BUTTON_H - 6
        fit = max(0, (bottom - y) // LOG_LINE_H)
        for line in list(lines)[-fit:] if fit else []:
            color = T.ACCENT if line.startswith("—") else T.TEXT_DIM
            self.text.draw(surf, line, (x0, y), 16, color)
            y += LOG_LINE_H

    # ---- товч ----
    def _buttons(self, surf, selection, enabled, mouse_pos):
        u = selection.unit
        moving = u is not None and selection.dest is not None and selection.dest != u.pos
        labels = {"wait": "Хөдлөх (W)" if moving else "Хүлээх (W)",
                  "end_turn": "Ээлж дуусгах (E)"}
        for name, rect in L.BUTTONS.items():
            on = enabled.get(name, False)
            hover = on and mouse_pos is not None and L.point_in(rect, mouse_pos)
            color = T.BUTTON_HOVER if hover else (T.BUTTON if on else T.BUTTON_OFF)
            pygame.draw.rect(surf, color, rect, border_radius=8)
            r = pygame.Rect(rect)
            self.text.draw(surf, labels[name], r.center, 20, T.TEXT if on else T.TEXT_DIM,
                           anchor="center")

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
