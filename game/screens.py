"""Цэс, удирдлагын тусламж, түр зогсолт, үр дүнгийн дэлгэц (pygame)."""

import pygame

from engine import DEMONS, HEROES

from . import layout as L
from . import theme as T
from .labels import WINNER_NAMES, unit_name

CONTROLS = [
    ("Зүүн товч баатар дээр", "Баатар сонгох"),
    ("Цэнхэр нүд дээр", "Очих нүд сонгох (дахин дарвал хөдөлнө)"),
    ("1 – 4  эсвэл товч", "Ур чадвар сонгох → бай дээр дарах"),
    ("Хулгана бай дээр", "Хохирол, «унана» урьдчилан харах"),
    ("V  /  хулганы дугуй", "Мөсөн ханын чиглэл солих"),
    ("W  /  Space", "Хөдлөх эсвэл байрандаа хүлээх"),
    ("E  /  Enter", "Ээлж дуусгах"),
    ("Баруун товч  /  Esc", "Нэг алхам буцах, сонголтгүй бол түр зогсоох"),
    ("Tab", "«Боссын бодол» самбар нээх / хаах"),
    ("M", "Дуу асаах / унтраах"),
]


class Screens:
    def __init__(self, text: T.Text, sprites=None):
        self.text = text
        self.sprites = sprites if sprites is not None and sprites.ok else None

    # ---- нийтлэг ----
    def _buttons(self, surf, menu, mouse_pos):
        w = surf.get_width()
        for i, (item, rect) in enumerate(zip(menu.items, menu.rects(w))):
            selected = i == menu.index and item.enabled
            color = T.BUTTON_HOVER if selected else (T.BUTTON if item.enabled else T.BUTTON_OFF)
            pygame.draw.rect(surf, color, rect, border_radius=10)
            if selected:
                pygame.draw.rect(surf, T.ACCENT, rect, 2, border_radius=10)
            r = pygame.Rect(rect)
            self.text.draw(surf, item.label, r.center, 24, T.TEXT if item.enabled else T.TEXT_DIM,
                           anchor="center")

    def _unit_row(self, surf, cx, y):
        """Гарчгийн доорх чимэглэл: баатрууд эсрэг чөтгөрүүд."""
        kinds = [("knight", "K"), ("mage", "M"), ("healer", "H"), None,
                 ("imp", "i"), ("demon_lord", "D"), ("imp", "i")]
        size, gap = 46, 10
        total = len(kinds) * size + (len(kinds) - 1) * gap
        x = cx - total // 2
        for k in kinds:
            if k is None:
                self.text.draw(surf, "vs", (x + size // 2, y + size // 2), 26, T.TEXT_DIM,
                               bold=True, anchor="center")
            else:
                kind, letter = k
                r = pygame.Rect(x, y, size, size)
                sprite = self.sprites.unit(kind) if self.sprites else None
                if sprite is not None:
                    plate = pygame.Surface((size, size), pygame.SRCALPHA)
                    pygame.draw.rect(plate, T.UNIT_COLORS[kind] + (95,), plate.get_rect(),
                                     border_radius=8)
                    pygame.draw.rect(plate, T.UNIT_COLORS[kind], plate.get_rect(), 2,
                                     border_radius=8)
                    surf.blit(plate, r)
                    img = pygame.transform.scale(sprite, (size - 6, size - 6))
                    surf.blit(img, img.get_rect(center=r.center))
                else:
                    pygame.draw.rect(surf, T.UNIT_COLORS[kind], r, border_radius=8)
                    self.text.draw(surf, letter, r.center, 28, (255, 255, 255), bold=True,
                                   anchor="center")
            x += size + gap

    # ---- үндсэн цэс ----
    def draw_menu(self, surf, menu, mouse_pos, note=""):
        w, h = surf.get_size()
        surf.fill(T.BG)
        cx = w // 2
        self.text.draw(surf, "Outwold devourer", (cx, 110), 76, T.ACCENT, bold=True,
                       anchor="center")
        self.text.draw(surf, "Тоглогчийн зуршлыг сурдаг AI босстой ээлжит тактик тоглоом",
                       (cx, 162), 22, T.TEXT_DIM, anchor="center")
        self._unit_row(surf, cx, 192)
        self._buttons(surf, menu, mouse_pos)
        if note:
            self.text.draw(surf, note, (cx, h - 56), 17, T.TEXT_DIM, anchor="center")
        self.text.draw(surf, "↑ ↓ / хулгана — сонгох · Enter — батлах", (cx, h - 30), 16,
                       T.TEXT_DIM, anchor="center")

    # ---- удирдлага ----
    def draw_help(self, surf):
        w, h = surf.get_size()
        surf.fill(T.BG)
        cx = w // 2
        self.text.draw(surf, "Удирдлага", (cx, 70), 48, T.ACCENT, bold=True, anchor="center")
        card = pygame.Rect(0, 0, min(760, w - 40), 46 + 40 * len(CONTROLS))
        card.midtop = (cx, 110)
        pygame.draw.rect(surf, T.PANEL_BG, card, border_radius=10)
        y = card.y + 24
        for key, action in CONTROLS:
            self.text.draw(surf, key, (card.x + 28, y), 20, T.ACCENT, bold=True)
            self.text.draw(surf, action, (card.x + 270, y), 20, T.TEXT)
            y += 40
        self.text.draw(surf, "Дүр дээрх тэмдэг: цэнхэр тоо — бамбай, Х2 — хараал, T2 — taunt",
                       (cx, card.bottom + 24), 18, T.TEXT_DIM, anchor="center")
        self.text.draw(surf, "Esc / Enter / дарах — буцах", (cx, h - 30), 18, T.TEXT_DIM,
                       anchor="center")

    # ---- түр зогсолт ----
    def draw_pause(self, surf, menu, mouse_pos):
        w, h = surf.get_size()
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        surf.blit(shade, (0, 0))
        self.text.draw(surf, "Түр зогсолт", (w // 2, menu.top - 60), 48, T.ACCENT, bold=True,
                       anchor="center")
        self._buttons(surf, menu, mouse_pos)

    # ---- үр дүн ----
    def draw_result(self, surf, state, stats, menu, mouse_pos):
        w, h = surf.get_size()
        surf.fill(T.BG)
        cx = w // 2
        winner = state.winner
        color = T.HP_HERO if winner == HEROES else (T.HP_DEMON if winner == DEMONS else T.ACCENT)
        self.text.draw(surf, WINNER_NAMES.get(winner, str(winner)), (cx, 62), 54, color,
                       bold=True, anchor="center")
        sub = f"{state.round} round"
        mvp = stats.mvp(HEROES, state)
        if mvp:
            sub += f" · Шилдэг баатар: {unit_name(mvp, state)}"
        self.text.draw(surf, sub, (cx, 108), 22, T.TEXT, anchor="center")

        cols = [("Дүр", 0), ("Хохирол", 230), ("Эдгээлт", 340), ("Алсан", 450), ("Төлөв", 540)]
        card = pygame.Rect(0, 0, 660, 52 + 32 * len(state.units))
        card.midtop = (cx, 140)
        pygame.draw.rect(surf, T.PANEL_BG, card, border_radius=10)
        y = card.y + 16
        for title, dx in cols:
            self.text.draw(surf, title, (card.x + 24 + dx, y), 18, T.TEXT_DIM, bold=True)
        y += 30
        for row in stats.rows(state):
            name_color = T.UNIT_COLORS["knight"] if row["side"] == HEROES else T.UNIT_COLORS["demon_lord"]
            pygame.draw.rect(surf, T.UNIT_COLORS[state.units[row["uid"]].kind],
                             (card.x + 24, y + 4, 14, 14), border_radius=3)
            self.text.draw(surf, unit_name(row["uid"], state), (card.x + 46, y), 20, T.TEXT)
            values = [row["damage"], row["heal"], row["kills"]]
            for (_, dx), v in zip(cols[1:4], values):
                self.text.draw(surf, str(v), (card.x + 24 + dx, y), 20,
                               T.TEXT if v else T.TEXT_DIM)
            status = f"{row['hp']}/{row['max_hp']}" if row["alive"] else "унасан"
            self.text.draw(surf, status, (card.x + 24 + cols[4][1], y), 20,
                           name_color if row["alive"] else T.TEXT_DIM)
            y += 32
        self._buttons(surf, menu, mouse_pos)
