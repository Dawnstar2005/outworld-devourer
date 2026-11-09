"""Үндсэн давталт (pygame): оролт → нүүдэл → анимаци → зурах, 60 FPS.

Дэлгэц: "intro" (эхлэлийн дүр зураг) → "menu" (үндсэн цэс) → "game" (тоглоом, Esc-ээр
түр зогсоно) → "result" (үр дүн). Хөгжим: эхлэл/цэс — "title", тулаан — "battle".
"help" (удирдлага) цэс болон түр зогсолтоос нээгдэнэ. Tab — «Боссын бодол» самбар.

Хүний нүүдэл: хулгана/товчлуур → Selection → GameSession.play()
Боссын нүүдэл: BossDriver (thread) → decision.actions-ийг нэг нэгээр нь GameSession.play()
Хоёулаа GameSession-оор дамждаг тул on_action hook нүүдэл бүрт дуудагдана.
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from typing import Callable, Optional

import pygame

from engine import END_TURN, HEROES

from . import layout as L
from . import theme as T
from .anim import Animator
from .board_view import BoardView
from .boss_driver import BossDriver, PlaceholderBoss, ai_available, make_boss
from .boss_panel import BossPanel
from .hud import Hud
from .input import Selection
from .labels import event_text
from .menu import Menu, MenuItem
from .music import MusicPlayer
from .screens import INTRO_DURATION, Screens
from .session import GameSession
from .sound import SoundPlayer
from .sprites import Sprites
from .stats import MatchStats

FPS = 60
BOSS_STEP_DELAY = 0.5      # боссын нүүдэл хооронд (сек), тоглогч юу болсныг харах
RESULT_DELAY = 1.6         # тоглолт дууссаны дараа үр дүнгийн дэлгэц гарах хүртэл (сек)
LOG_LINES = 14
SPRITE_SIZE = 48           # 16px sprite × 3 (pixel art бүхэл тоогоор томруулна)
BOSS_MODES = ("eval", "mcts")
BOSS_MODE_LABELS = {"eval": "хурдан (үнэлгээ)", "mcts": "ухаалаг (MCTS)"}


class App:
    def __init__(self, session: Optional[GameSession] = None, boss=None, fps: int = FPS,
                 boss_step_delay: float = BOSS_STEP_DELAY,
                 boss_factory: Optional[Callable[[str], object]] = None,
                 boss_mode: str = "eval", start_screen: str = "menu",
                 show_boss_panel: bool = True, sound: bool = True):
        pygame.mixer.pre_init(44100, -16, 2, 512)   # дууны саатлыг багасгана
        pygame.init()
        pygame.display.set_caption("Outwold devourer")
        self.show_boss_panel = show_boss_panel
        self.screen = pygame.display.set_mode(L.screen_size(show_boss_panel))
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.text = T.Text()
        self.sprites = Sprites(SPRITE_SIZE, L.CELL)
        self.sound = SoundPlayer(enabled=sound)
        self.music = MusicPlayer(enabled=sound)
        self.board = BoardView(self.text, self.sprites)
        self.hud = Hud(self.text)
        self.panel_view = BossPanel(self.text)
        self.screens = Screens(self.text, self.sprites)

        self.session = session if session is not None else GameSession()
        self.selection = Selection(self.session, side=self.session.human_side)
        self.stats = MatchStats()
        self.session.add_hook(self.stats.on_action)
        self.fixed_boss = boss
        self.boss_factory = boss_factory
        self.boss_mode = boss_mode
        self.boss = BossDriver(self._new_controller())
        self.boss_step_delay = boss_step_delay
        self.anim = Animator()
        self.log: deque = deque(maxlen=LOG_LINES)

        self.boss_phase = "idle"          # idle | thinking | acting
        self.boss_queue: deque = deque()
        self.boss_timer = 0.0
        self.boss_panel = None            # decision.to_panel()
        self.boss_panel_round = None
        self.hover = None
        self.mouse_pos = None
        self.running = True

        self.screen_name = start_screen   # intro | menu | help | game | result
        self.intro_t = 0.0
        self.menu_t = 0.0                 # цэсний оч хөдлөх хугацаа
        self.paused = False
        self.help_return = "menu"
        self.over_timer = 0.0
        self.main_menu = Menu(self._main_items(), top=270)
        self.pause_menu = Menu([MenuItem("resume", "Үргэлжлүүлэх"),
                                MenuItem("restart", "Шинээр эхлэх"),
                                MenuItem("help", "Удирдлага"),
                                MenuItem("menu", "Үндсэн цэс")], top=230)
        self.result_menu = Menu([MenuItem("again", "Дахин тоглох"),
                                 MenuItem("menu", "Үндсэн цэс")], top=410)

    # ------------------------------------------------------------------ босс үүсгэх
    def _new_controller(self):
        if self.fixed_boss is not None:
            return self.fixed_boss
        factory = self.boss_factory or (lambda mode: make_boss(mode=mode))
        return factory(self.boss_mode)

    @property
    def ai_connected(self) -> bool:
        return not isinstance(self.boss.controller, PlaceholderBoss)

    def _boss_mode_selectable(self) -> bool:
        return self.fixed_boss is None and ai_available()

    def _main_items(self) -> list:
        return [MenuItem("play", "Тоглох"),
                MenuItem("boss_mode", f"Босс: {BOSS_MODE_LABELS[self.boss_mode]}",
                         enabled=self._boss_mode_selectable()),
                MenuItem("help", "Удирдлага"),
                MenuItem("quit", "Гарах")]

    # ------------------------------------------------------------------ нүүдэл
    @property
    def state(self):
        return self.session.state

    @property
    def input_locked(self) -> bool:
        return self.paused or self.anim.busy or not self.session.human_to_act

    def play(self, action) -> list:
        events = self.session.play(action)
        self.anim.push(events, self.state)
        self.sound.play_events(events, self.session.human_side)
        for ev in events:
            if ev["type"] == "turn_start":   # ээлж солигдсон: боссын өмнөх ээлжийн төлөвийг цэвэрлэнэ
                self.boss_phase = "idle"
                self.boss_queue.clear()
            line = event_text(ev, self.state)
            if line:
                self.log.append(line)
        self.selection.refresh()
        return events

    def start_game(self) -> None:
        """Шинэ тоглолт (цэснээс, түр зогсолтоос, үр дүнгээс)."""
        self.boss.cancel()
        if self.fixed_boss is None:
            self.boss = BossDriver(self._new_controller())
        self.session.reset()
        self.stats.reset()
        self.selection.clear()
        self.anim.clear()
        self.log.clear()
        self.boss_phase = "idle"
        self.boss_queue.clear()
        self.boss_panel = None
        self.boss_panel_round = None
        self.over_timer = 0.0
        self.paused = False
        self.screen_name = "game"

    restart = start_game

    def go_menu(self) -> None:
        self.boss.cancel()
        self.boss_phase = "idle"
        self.paused = False
        self.screen_name = "menu"
        self.main_menu.index = 0

    def toggle_boss_panel(self) -> None:
        self.show_boss_panel = not self.show_boss_panel
        self.screen = pygame.display.set_mode(L.screen_size(self.show_boss_panel))

    # ------------------------------------------------------------------ оролт
    def handle_event(self, e) -> None:
        if e.type == pygame.QUIT:
            self.running = False
            return
        if e.type == pygame.MOUSEMOTION:
            self.mouse_pos = e.pos
        if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
            self.toggle_boss_panel()
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            self.music.set_muted(self.sound.toggle_mute())
            return
        if self.screen_name == "intro":
            if e.type == pygame.KEYDOWN or (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                self.go_menu()                     # алгасах
        elif self.screen_name == "menu":
            self._menu_event(self.main_menu, e, self._on_main)
        elif self.screen_name == "help":
            if e.type == pygame.KEYDOWN or (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                self.sound.play("back")
                self.screen_name = "game" if self.help_return == "pause" else "menu"
        elif self.screen_name == "result":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.go_menu()
            else:
                self._menu_event(self.result_menu, e, self._on_result)
        elif self.paused:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.paused = False
            else:
                self._menu_event(self.pause_menu, e, self._on_pause)
        else:
            self._game_event(e)

    def _menu_event(self, menu: Menu, e, on_select) -> None:
        w = self.screen.get_width()
        if e.type == pygame.MOUSEMOTION:
            before = menu.index
            menu.hover(e.pos, w)
            if menu.index != before:
                self.sound.play("tick")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            key = menu.click(e.pos, w)
            if key is not None:
                self.sound.play("click")
                on_select(key)
        elif e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_DOWN):
                menu.move(-1 if e.key == pygame.K_UP else 1)
                self.sound.play("tick")
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.sound.play("click")
                on_select(menu.selected)

    def _on_main(self, key: str) -> None:
        if key == "play":
            self.start_game()
        elif key == "boss_mode":
            i = BOSS_MODES.index(self.boss_mode)
            self.boss_mode = BOSS_MODES[(i + 1) % len(BOSS_MODES)]
            self.main_menu.items = self._main_items()
        elif key == "help":
            self.help_return = "menu"
            self.screen_name = "help"
        elif key == "quit":
            self.running = False

    def _on_pause(self, key: str) -> None:
        if key == "resume":
            self.paused = False
        elif key == "restart":
            self.start_game()
        elif key == "help":
            self.help_return = "pause"
            self.screen_name = "help"
        elif key == "menu":
            self.go_menu()

    def _on_result(self, key: str) -> None:
        if key == "again":
            self.start_game()
        elif key == "menu":
            self.go_menu()

    def _game_event(self, e) -> None:
        sel = self.selection
        before = (sel.unit_uid, sel.dest, sel.skill, self.state.side_to_act, self.paused)
        self._game_input(e)
        self._ui_sound(e, before)

    def _ui_sound(self, e, before) -> None:
        """Сонголт өөрчлөгдөхөд богино дуу (нүүдлийн дуу play()-д тоглогдоно)."""
        if e.type not in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN, pygame.MOUSEWHEEL):
            return
        sel = self.selection
        uid, dest, skill, side, paused = before
        if self.paused != paused:
            self.sound.play("click")
        elif sel.unit_uid is not None and sel.unit_uid != uid:
            self.sound.play("select")
        elif sel.unit_uid is not None and (sel.skill != skill or sel.dest != dest):
            self.sound.play("tick" if sel.skill is not None or sel.dest != dest else "back")
        elif uid is not None and sel.unit_uid is None and self.state.units[uid].acted is False                 and self.state.side_to_act == side:
            self.sound.play("back")                   # нүүдэлгүйгээр цуцлагдсан
        elif getattr(e, "key", None) in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)                 and sel.unit_uid is not None and sel.skill == skill:
            self.sound.play("error")                  # cooldown / бай алга

    def _game_input(self, e) -> None:
        if e.type == pygame.MOUSEMOTION:
            self.hover = L.cell_at(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.mouse_pos = e.pos
            if e.button == 3:
                self.selection.back()
            elif e.button == 1:
                self._left_click(e.pos)
        elif e.type == pygame.MOUSEWHEEL:
            if self.selection.skill_kind(self.selection.skill) == "wall":
                self.selection.rotate()
        elif e.type == pygame.KEYDOWN:
            self._key(e.key)

    def _left_click(self, pos) -> None:
        if self.input_locked:
            return
        button = L.button_at(pos)
        if button == "wait":
            self._try(self.selection.confirm_move())
        elif button == "end_turn":
            self._try(self.selection.end_turn())
        elif button is not None and button.startswith("skill:"):
            self._try(self.selection.arm_index(int(button.split(":")[1])))
        else:
            cell = L.cell_at(pos)
            if cell is not None:
                self._try(self.selection.click(cell))

    def _key(self, key) -> None:
        if key == pygame.K_ESCAPE:
            if self.selection.unit is not None:
                self.selection.back()
            else:
                self.paused = True
                self.pause_menu.index = 0
        elif key == pygame.K_r and self.state.is_over:
            self.start_game()
        elif self.input_locked:
            return
        elif key in (pygame.K_e, pygame.K_RETURN):
            self._try(self.selection.end_turn())
        elif key in (pygame.K_w, pygame.K_SPACE):
            self._try(self.selection.confirm_move())
        elif key == pygame.K_v:
            self.selection.rotate()
        elif pygame.K_1 <= key <= pygame.K_4:
            self._try(self.selection.arm_index(key - pygame.K_1))

    def _try(self, action) -> None:
        if action is None:
            return
        try:
            self.play(action)
        except ValueError as err:   # Selection engine-ээс авдаг тул гарах ёсгүй
            self.log.append(f"Буруу нүүдэл: {err}")

    # ------------------------------------------------------------------ босс
    def update_boss(self, dt: float) -> None:
        s = self.state
        if s.is_over or s.side_to_act == self.session.human_side:
            self.boss_phase = "idle"
            self.boss_queue.clear()
            return
        if self.anim.busy:
            return
        if self.boss_phase == "idle":
            self.boss.start(s)
            self.boss_phase = "thinking"
        elif self.boss_phase == "thinking":
            try:
                decision = self.boss.poll()
            except Exception as err:
                self.log.append(f"Боссын AI алдаа: {err}")
                self._try(END_TURN)
                return
            if decision is not None:
                self.boss_queue = deque(decision.actions)
                self.boss_panel = decision.to_panel()
                self.boss_panel_round = s.round
                self.boss_phase = "acting"
                self.boss_timer = 0.0
        elif self.boss_phase == "acting":
            self.boss_timer -= dt
            if self.boss_timer > 0:
                return
            if self.boss_queue:
                action = self.boss_queue.popleft()
                try:
                    self.play(action)
                except ValueError as err:
                    self.log.append(f"Боссын нүүдэл буруу: {err}")
                    self.boss_queue.clear()
                self.boss_timer = self.boss_step_delay
            elif not self.state.is_over and self.state.side_to_act != self.session.human_side:
                self._try(END_TURN)     # шийдвэрт ороогүй дүрүүд үлдсэн бол ээлжийг дуусгана

    # ------------------------------------------------------------------ давталт
    def status_text(self) -> str:
        if self.boss_phase == "thinking":
            dots = "." * (1 + int(self.boss.elapsed * 3) % 3)
            return f"Босс бодож байна{dots}"
        if self.sound.muted:
            return "Дуу унтраалттай (M)"
        return ""

    def music_track(self):
        """Одоогийн дэлгэцэд тохирох хөгжим (None — хөгжимгүй, үр дүнд jingle сонсогдоно)."""
        name = self.screen_name
        if name == "help":
            name = "game" if self.help_return == "pause" else "menu"
        return {"intro": "title", "menu": "title", "game": "battle"}.get(name)

    def update(self, dt: float) -> None:
        self.music.play(self.music_track())
        self.music.update(dt)
        if self.screen_name == "intro":
            self.intro_t += dt
            if self.intro_t >= INTRO_DURATION:
                self.go_menu()
            return
        if self.screen_name in ("menu", "help"):
            self.menu_t += dt
        if self.screen_name != "game" or self.paused:
            return
        self.anim.update(dt)
        self.update_boss(dt)
        if self.state.is_over and not self.anim.busy:
            self.over_timer += dt
            if self.over_timer >= RESULT_DELAY:
                self.screen_name = "result"
                self.result_menu.index = 0

    def step(self, dt: float) -> None:
        for e in pygame.event.get():
            self.handle_event(e)
        self.update(dt)
        self.draw()

    def draw(self) -> None:
        self.screen.fill(T.BG)
        if self.screen_name == "intro":
            self.screens.draw_intro(self.screen, self.intro_t)
        elif self.screen_name == "menu":
            note = "" if self._boss_mode_selectable() else \
                "Боссын AI (ai/) хараахан суугаагүй — түр босс тоглоно"
            self.screens.draw_menu(self.screen, self.main_menu, self.mouse_pos, note, self.menu_t)
        elif self.screen_name == "help":
            self.screens.draw_help(self.screen)
        elif self.screen_name == "result":
            self.screens.draw_result(self.screen, self.state, self.stats, self.result_menu,
                                     self.mouse_pos)
        else:
            self._draw_game()
        pygame.display.flip()

    def _draw_game(self) -> None:
        interactive = not self.input_locked
        self.board.draw(self.screen, self.state, self.selection, self.anim,
                        self.hover if interactive else None, interactive)
        enabled = {"wait": interactive and self.selection.unit is not None,
                   "end_turn": interactive, "skills": interactive}
        hover_unit = self.state.unit_at(self.hover) if self.hover is not None else None
        self.hud.draw(self.screen, self.state, self.selection, self.log, self.status_text(),
                      enabled, self.mouse_pos, hover_unit,
                      panel_hint=not self.show_boss_panel)
        if self.show_boss_panel:
            self.panel_view.draw(self.screen, self.boss_panel,
                                 thinking=self.boss_phase == "thinking",
                                 elapsed=self.boss.elapsed, enraged_now=self.state.boss_enraged,
                                 decision_round=self.boss_panel_round,
                                 ai_connected=self.ai_connected)
        if self.state.is_over and not self.anim.busy:
            self.hud.draw_game_over(self.screen, self.state)
        if self.paused:
            self.screens.draw_pause(self.screen, self.pause_menu, self.mouse_pos)

    def run(self, max_frames: Optional[int] = None) -> None:
        frames = 0
        while self.running:
            dt = min(self.clock.tick(self.fps) / 1000.0, 0.1)
            self.step(dt)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        pygame.quit()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m game", description="Outwold devourer")
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--seed", type=int, default=None, help="боссын санамсаргүй сонголтын seed")
    p.add_argument("--boss-mode", choices=BOSS_MODES, default="eval",
                   help="боссын AI-ийн горим (ai/ суусан үед)")
    p.add_argument("--placeholder-boss", action="store_true",
                   help="ai/ байсан ч түр боссыг ашиглах")
    p.add_argument("--skip-intro", action="store_true", help="эхлэлийн дүр зургийг алгасах")
    p.add_argument("--skip-menu", action="store_true", help="цэсгүйгээр шууд тоглоом эхлүүлэх")
    p.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    boss = PlaceholderBoss(seed=args.seed) if args.placeholder_boss else None
    app = App(GameSession(human_side=HEROES), boss=boss, fps=args.fps,
              boss_factory=lambda mode: make_boss(mode=mode, seed=args.seed),
              boss_mode=args.boss_mode,
              start_screen="game" if args.skip_menu else ("menu" if args.skip_intro else "intro"))
    app.run(max_frames=args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
