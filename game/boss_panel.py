"""«Боссын бодол» самбар (pygame). Tab товчоор нээж, хаана.

Өгөгдөл нь `decision.to_panel()` (ai/):
    {"habits": [...], "options": [{"label", "score", "chosen"}, ...], "enraged": bool,
     "random_pick": bool, "ms": int, "mode": "lookahead" | "mcts" | "eval", "iterations": int}
Түр босс (`PlaceholderBoss`) None буцаадаг — тэр үед тайлбар харуулна.

Доод хэсэг «Таны дараагийн нүүдэл»: game/prediction.py-ийн `PredictionTracker.panel()` —
нүүгээгүй баатар бүрийн таамаг, таамаг хэдэн удаа зөв байсан.
"""

import pygame

from . import layout as L
from . import theme as T

X0 = L.BOSS_PANEL_X + 14
INNER_W = L.BOSS_PANEL_W - 28
MODE_NAMES = {"lookahead": "Lookahead", "mcts": "MCTS", "eval": "Үнэлгээ", "tactic": "Тактик"}
# "iterations"-ийн нэгж: MCTS-д симуляци, lookahead-д тоглогчийн хариуг тооцсон төлөвлөгөө
ITERATION_UNITS = {"lookahead": "төлөвлөгөө"}
BOSS_RED = (225, 70, 80)
PRED_BLUE = (120, 180, 255)
PRED_H = 30 + 3 * 20 + 22 + 20      # таамгийн хэсгийн өндөр (гарчиг, 3 мөр, оноо, сүүлийн)


class BossPanel:
    def __init__(self, text: T.Text):
        self.text = text

    def draw(self, surf, panel, *, thinking: bool, elapsed: float, enraged_now: bool,
             decision_round, ai_connected: bool, prediction: dict = None):
        pygame.draw.rect(surf, T.PANEL_BG, (L.BOSS_PANEL_X, L.PANEL_Y, L.BOSS_PANEL_W, L.PANEL_H),
                         border_radius=8)
        pygame.draw.rect(surf, (90, 40, 50), (L.BOSS_PANEL_X, L.PANEL_Y, L.BOSS_PANEL_W, 4),
                         border_top_left_radius=8, border_top_right_radius=8)
        y = L.PANEL_Y + 12
        self.text.draw(surf, "Боссын бодол", (X0, y), 26, BOSS_RED, bold=True)
        self.text.draw(surf, "Tab", (X0 + INNER_W, y + 4), 16, T.TEXT_DIM, anchor="topright")
        y += 32

        if thinking:
            dots = "." * (1 + int(elapsed * 3) % 3)
            self.text.draw(surf, f"Бодож байна{dots}  {elapsed:.1f} сек", (X0, y), 18, T.ACCENT)
        elif panel:
            ms = panel.get("ms", 0)
            took = f"{ms} мс" if ms < 1000 else f"{ms / 1000:.1f} сек"
            meta = f"{MODE_NAMES.get(panel.get('mode'), panel.get('mode'))} · {took}"
            if panel.get("iterations"):
                unit = ITERATION_UNITS.get(panel.get("mode"), "симуляци")
                meta += f" · {panel['iterations']} {unit}"
            self.text.draw(surf, meta, (X0, y), 16, T.TEXT_DIM)
        y += 26

        if enraged_now or (panel and panel.get("enraged")):
            r = pygame.Rect(X0, y, INNER_W, 30)
            pygame.draw.rect(surf, (120, 25, 35), r, border_radius=6)
            pygame.draw.rect(surf, BOSS_RED, r, 2, border_radius=6)
            self.text.draw(surf, "УУР ХИЛЭН — HP 30%-иас доош", r.center, 18, (255, 220, 220),
                           bold=True, anchor="center")
            y += 40

        bottom = L.PANEL_Y + L.PANEL_H - 12
        if prediction is not None:
            bottom -= PRED_H
            self._prediction(surf, prediction, bottom + 6)

        if not ai_connected:
            y = self._section(surf, "AI холбогдоогүй", y)
            msg = ("Одоо түр босс ажиллаж байна. Боссын AI (ai/) main-д орсны дараа "
                   "энд түүний танисан зуршил, эхний 3 сонголт, оноо харагдана.")
            for line in self.text.wrap(msg, 17, INNER_W):
                self.text.draw(surf, line, (X0, y), 17, T.TEXT_DIM)
                y += 20
            return

        y = self._section(surf, "Танисан зуршил", y)
        habits = (panel or {}).get("habits") or []
        if not habits:
            self.text.draw(surf, "Одоогоор танигдаагүй", (X0, y), 17, T.TEXT_DIM)
            y += 22
        for h in habits[:4]:
            lines = self.text.wrap(h, 17, INNER_W - 14)
            self.text.draw(surf, "•", (X0, y), 17, T.ACCENT)
            for line in lines[:2]:
                self.text.draw(surf, line, (X0 + 14, y), 17, T.TEXT)
                y += 20
        y += 8

        title = "Сонголтууд" + (f" (round {decision_round})" if decision_round else "")
        y = self._section(surf, title, y)
        options = (panel or {}).get("options") or []
        if not options:
            self.text.draw(surf, "Босс хараахан шийдвэр гаргаагүй", (X0, y), 17, T.TEXT_DIM)
            return
        for i, opt in enumerate(options[:3]):
            if y + 50 > bottom:                          # таамгийн хэсэгт багтахгүй бол
                break
            y = self._option(surf, i, opt, y, dim=thinking,
                             random_pick=bool(panel.get("random_pick")))
        if prediction is not None:
            return
        note = ("Оноо (0–1): тухайн нүүдлийн дараах байдлыг босс хэр ашигтай гэж үнэлсэн. "
                "Заримдаа санамсаргүй сонгож, тоглогчид урьдчилан таамаглахад хэцүү болгоно.")
        y = max(y + 6, L.PANEL_Y + L.PANEL_H - 12 - 18 * 4)
        for line in self.text.wrap(note, 15, INNER_W)[:4]:
            self.text.draw(surf, line, (X0, y), 15, T.TEXT_DIM)
            y += 18

    def _fit(self, text, size, width):
        if self.text.render(text, size).get_width() <= width:
            return text
        while text and self.text.render(text + "…", size).get_width() > width:
            text = text[:-1]
        return text + "…"

    def _prediction(self, surf, pred, y):
        """«Таны дараагийн нүүдэл»: баатар бүрийн таамаг, хэдэн удаа зөв таасан."""
        self.text.draw(surf, "Таны дараагийн нүүдэл (таамаг)", (X0, y), 18, PRED_BLUE, bold=True)
        pygame.draw.line(surf, T.PANEL_LINE, (X0, y + 22), (X0 + INNER_W, y + 22))
        y += 30
        guesses = pred.get("guesses") or []
        if not guesses:
            self.text.draw(surf, "Таны ээлжинд гарна", (X0, y), 16, T.TEXT_DIM)
        from .labels import unit_name
        for uid, label, p in guesses[:3]:
            name = unit_name(uid)
            self.text.draw(surf, name, (X0, y), 16, T.ACCENT, bold=True)
            pct = self.text.render(f"{round(p * 100)}%", 16, PRED_BLUE, bold=True)
            surf.blit(pct, pct.get_rect(topright=(X0 + INNER_W, y)))
            lx = X0 + 64
            self.text.draw(surf, self._fit(label, 16, X0 + INNER_W - pct.get_width() - 8 - lx),
                           (lx, y), 16, T.TEXT)
            y += 20
        y += 4
        total = pred.get("total", 0)
        if total:
            hits, hits3 = pred.get("hits", 0), pred.get("hits3", 0)
            msg = f"Зөв таасан: {hits}/{total} ({round(100 * hits / total)}%) · top-3: {hits3}/{total}"
        else:
            msg = "Зөв таасан: — (нүүдэл хийгээгүй)"
        self.text.draw(surf, self._fit(msg, 15, INNER_W), (X0, y), 15, T.TEXT_DIM)
        last = pred.get("last")
        if last:
            uid, guess, actual, hit = last
            mark = "Зөв" if hit else "Буруу"
            text = f"{mark} — {unit_name(uid)}: {actual}" + ("" if hit else f" (таамаг: {guess})")
            self.text.draw(surf, self._fit(text, 15, INNER_W), (X0, y + 20), 15,
                           T.HP_HERO if hit else (230, 150, 120))

    def _section(self, surf, title, y):
        self.text.draw(surf, title, (X0, y), 18, T.TEXT_DIM, bold=True)
        pygame.draw.line(surf, T.PANEL_LINE, (X0, y + 22), (X0 + INNER_W, y + 22))
        return y + 30

    def _option(self, surf, i, opt, y, dim, random_pick):
        chosen = bool(opt.get("chosen"))
        lines = self.text.wrap(f"{i + 1}. {opt.get('label', '')}", 17, INNER_W - 16)[:2]
        h = 14 + 20 * len(lines) + 16
        card = pygame.Surface((INNER_W, h), pygame.SRCALPHA)
        pygame.draw.rect(card, (52, 40, 52) if chosen else (40, 40, 54), card.get_rect(),
                         border_radius=6)
        if chosen:
            pygame.draw.rect(card, BOSS_RED, card.get_rect(), 2, border_radius=6)
        ty = 7
        for line in lines:
            lbl = self.text.render(line, 17, T.TEXT if chosen else (200, 200, 212))
            card.blit(lbl, (8, ty))
            ty += 20
        score = max(0.0, min(1.0, float(opt.get("score", 0))))
        num = self.text.render(f"{score:.2f}", 15, T.TEXT_DIM)
        right = INNER_W - 8 - num.get_width() - 8
        tag_lbl = None
        if chosen:
            tag = "сонгосон (санамсаргүй)" if random_pick else "сонгосон"
            tag_lbl = self.text.render(tag, 14, BOSS_RED, bold=True)
            right -= tag_lbl.get_width() + 8
        bar = pygame.Rect(8, ty + 4, max(20, right - 8), 6)
        pygame.draw.rect(card, T.HP_BG, bar, border_radius=3)
        fill = bar.copy()
        fill.w = max(2, int(bar.w * score))
        pygame.draw.rect(card, BOSS_RED if chosen else (120, 120, 140), fill, border_radius=3)
        card.blit(num, num.get_rect(midright=(INNER_W - 8, bar.centery)))
        if tag_lbl is not None:
            card.blit(tag_lbl, tag_lbl.get_rect(midright=(INNER_W - 16 - num.get_width(),
                                                          bar.centery)))
        if dim:
            card.set_alpha(110)
        surf.blit(card, (X0, y))
        return y + h + 8
