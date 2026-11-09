"""Эхлэлийн дүр зураг, цэс, удирдлагын тусламж, түр зогсолт, үр дүнгийн дэлгэц (pygame)."""

import math

import pygame

from engine import DEMONS, HEROES

from . import layout as L
from . import theme as T
from .labels import WINNER_NAMES, unit_name

# Эхлэлийн дүр зураг: мөр бүр ээлжлэн тодорно, дараа нь гарчиг. Дурын товч — алгасах.
INTRO_LINES = [
    "Эрт урьдын цагт гурван баатар Outwold-ын хаалгыг битүүмжилжээ.",
    "Мянган жил өнгөрч, битүүмжлэл сулрахад Demon Lord сэрлээ.",
    "Тэр тулаан бүрээс суралцаж, дайснаа таньж, улам хүчирхэгжинэ.",
    "Knight, Mage, Healer — хаалганы сүүлчийн хамгаалагчид дахин нэгдэв.",
]
LINE_START = 0.8        # сек
LINE_STEP = 2.4
LINE_FADE = 1.0
TEXT_OUT = LINE_START + (len(INTRO_LINES) - 1) * LINE_STEP + 3.0
TITLE_IN = TEXT_OUT + 0.8
INTRO_DURATION = TITLE_IN + 6.0   # үүний дараа цэс рүү автоматаар шилжинэ
EMBER_COUNT = 110


def _ramp(t: float, start: float, length: float) -> float:
    return max(0.0, min(1.0, (t - start) / length))


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
        self._vignette = None
        self._glow = None

    # ---- уур амьсгал: оч, vignette ----
    def _embers(self, surf, t: float, strength: float = 1.0):
        """Доороос өгсөх галын оч. Байрлал нь зөвхөн t-ээс хамаарна (төлөв хадгалахгүй)."""
        w, h = surf.get_size()
        span = h + 40
        for i in range(EMBER_COUNT):
            r1 = (i * 0.618034) % 1.0
            r2 = (i * 0.414214 + 0.3) % 1.0
            r3 = (i * 0.732051 + 0.7) % 1.0
            rise = (t * (16 + 38 * r2) + r3 * span) % span
            y = h + 20 - rise
            x = r1 * w + 14 * math.sin(t * (0.5 + r2) + i)
            k = strength * max(0.0, 1.0 - rise / span) * (0.55 + 0.45 * math.sin(t * 3 + i * 1.7))
            if k <= 0.03:
                continue
            color = (int(255 * k), int((110 + 90 * r1) * k), int(40 * k))
            pygame.draw.circle(surf, color, (int(x), int(y)), 1 + int(r3 * 3.2))

    def _draw_vignette(self, surf):
        size = surf.get_size()
        if self._vignette is None or self._vignette.get_size() != size:
            small = pygame.Surface((128, 72), pygame.SRCALPHA)
            for x in range(128):
                for y in range(72):
                    d = math.hypot((x - 63.5) / 64, (y - 35.5) / 36)
                    small.set_at((x, y), (0, 0, 0, int(min(1.0, max(0.0, d - 0.45) * 1.6) * 235)))
            self._vignette = pygame.transform.smoothscale(small, size)
        surf.blit(self._vignette, (0, 0))

    def _draw_hell_glow(self, surf, t: float, strength: float = 1.0):
        """Доод талын улаан туяа — аажуухан лугшина."""
        w, h = surf.get_size()
        gh = h // 2
        if self._glow is None or self._glow.get_size() != (w, gh):
            small = pygame.Surface((1, 64), pygame.SRCALPHA)
            for y in range(64):
                small.set_at((0, y), (140, 25, 15, int(150 * (y / 63) ** 2.2)))
            self._glow = pygame.transform.smoothscale(small, (w, gh))
        glow = self._glow.copy()
        glow.set_alpha(int(255 * strength * (0.75 + 0.25 * math.sin(t * 1.3))))
        surf.blit(glow, (0, h - gh))

    def _glow_title(self, surf, text, center, size, alpha=1.0):
        glow = self.text.render(text, size, (150, 20, 20), bold=True).copy()
        glow.set_alpha(int(110 * alpha))
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2)):
            surf.blit(glow, glow.get_rect(center=(center[0] + dx, center[1] + dy)))
        main = self.text.render(text, size, T.ACCENT, bold=True).copy()
        main.set_alpha(int(255 * alpha))
        surf.blit(main, main.get_rect(center=center))

    # ---- эхлэлийн дүр зураг ----
    def draw_intro(self, surf, t: float):
        w, h = surf.get_size()
        surf.fill((8, 6, 10))
        self._draw_hell_glow(surf, t, strength=min(1.0, t / 3.0))
        self._embers(surf, t, strength=min(1.0, t / 2.0))
        self._draw_vignette(surf)
        out = 1.0 - _ramp(t, TEXT_OUT, 1.0)
        y = h // 2 - (len(INTRO_LINES) * 44) // 2
        for i, line in enumerate(INTRO_LINES):
            a = _ramp(t, LINE_START + i * LINE_STEP, LINE_FADE) * out
            if a > 0:
                lbl = self.text.render(line, 24, (225, 210, 190)).copy()
                lbl.set_alpha(int(255 * a))
                surf.blit(lbl, lbl.get_rect(center=(w // 2, y + int(8 * (1 - a)))))
            y += 44
        ta = _ramp(t, TITLE_IN, 1.6)
        if ta > 0:
            self._glow_title(surf, "Outwold devourer", (w // 2, h // 2 - 20), 84, ta)
            sub = self.text.render("Тоглогчийн зуршлыг сурдаг AI босс", 22, T.TEXT_DIM).copy()
            sub.set_alpha(int(255 * ta))
            surf.blit(sub, sub.get_rect(center=(w // 2, h // 2 + 40)))
        if t > TITLE_IN + 1.6 and int(t * 2) % 2 == 0:
            self.text.draw(surf, "Дурын товч дарж үргэлжлүүлнэ үү", (w // 2, h - 70), 20, T.TEXT,
                           anchor="center")
        self.text.draw(surf, "Алгасах: дурын товч", (w - 20, h - 24), 15, (110, 100, 110),
                       anchor="midright")

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
    def draw_menu(self, surf, menu, mouse_pos, note="", t: float = 0.0):
        w, h = surf.get_size()
        surf.fill((14, 12, 18))
        self._draw_hell_glow(surf, t, strength=0.6)
        self._embers(surf, t, strength=0.6)
        self._draw_vignette(surf)
        cx = w // 2
        self._glow_title(surf, "Outwold devourer", (cx, 110), 76)
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
