"""Үндсэн давталт (pygame): оролт → нүүдэл → анимаци → зурах, 60 FPS.

Дэлгэц: "intro" (эхлэлийн дүр зураг) → "menu" (үндсэн цэс) → "dungeon" (давхар, үеийн
газрын зураг) → "game" (тулаан, Esc-ээр түр зогсоно) → "reward" (XP, level, олз) → "dungeon".
Цэсний «Хурдан тулаан» нь анхны Demon Lord-ийн тулаан → "result" (үр дүн).
Дэлгэц бүр өөрийн хөгжимтэй (music_track()). "help" (удирдлага) цэс болон түр зогсолтоос
нээгдэнэ. Tab — «Боссын бодол» самбар.

Dungeon-ий 1–4-р давхар, 5-р давхрын эхний гурван үед дайснуудыг TacticalAI (enemy_ai.py),
эцсийн 5-4 үед суралцдаг BossAI (ai/) удирдана. Ахиц game/campaign.py-д байнга хадгалагдана.

Хүний нүүдэл: хулгана/товчлуур → Selection → GameSession.play()
Боссын нүүдэл: BossDriver (thread) → decision.actions-ийг нэг нэгээр нь GameSession.play()
Хоёулаа GameSession-оор дамждаг тул on_action hook нүүдэл бүрт дуудагдана.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import deque
from typing import Callable, Optional

import pygame

from engine import END_TURN, HEROES
from engine.dungeon import FLOORS, HERO_UIDS

from . import layout as L
from . import theme as T
from .anim import Animator
from .vfx import Vfx
from .vfx_draw import VfxView
from .board_view import BoardView
from .boss_driver import BossDriver, PlaceholderBoss, ai_available, make_boss
from .boss_panel import BossPanel
from .campaign import FINAL_STAGE, Campaign, parse_key
from .dungeon_map import DungeonMap, reward_drop_buttons
from .dungeon_view import DungeonView, reward_drop_top
from .enemy_ai import TacticalAI
from .hud import Hud
from .input import Selection
from .labels import event_text
from .menu import Menu, MenuItem
from .music import MusicPlayer
from .options import OptionsMenu
from .screens import INTRO_DURATION, Screens
from .session import GameSession
from .settings import Settings
from .sound import SoundPlayer
from .sprites import Sprites
from .stats import MatchStats
from .widgets import ButtonRenderer

FPS = 60
BOSS_STEP_DELAY = 0.5      # боссын нүүдэл хооронд (сек), тоглогч юу болсныг харах
RESULT_DELAY = 1.6         # тоглолт дууссаны дараа үр дүнгийн дэлгэц гарах хүртэл (сек)
LOG_LINES = 14
SPRITE_SIZE = 48           # 16px sprite × 3 (pixel art бүхэл тоогоор томруулна)
BOSS_MODES = ("eval", "mcts")
BOSS_MODE_LABELS = {"eval": "хурдан (үнэлгээ)", "mcts": "ухаалаг (MCTS)"}


class App:
    def __init__(self, session: Optional[GameSession] = None, boss=None, fps: int = FPS,
                 boss_step_delay: Optional[float] = None,
                 boss_factory: Optional[Callable[[str], object]] = None,
                 boss_mode: str = "eval", start_screen: str = "menu",
                 show_boss_panel: Optional[bool] = None, sound: bool = True, logger=None,
                 campaign: Optional[Campaign] = None,
                 enemy_factory: Optional[Callable[[], object]] = None,
                 settings: Optional[Settings] = None):
        pygame.mixer.pre_init(44100, -16, 2, 512)   # дууны саатлыг багасгана
        pygame.init()
        pygame.display.set_caption("Outworld Devourer")
        self.settings = settings if settings is not None else Settings.load()
        self.show_boss_panel = self.settings.boss_panel if show_boss_panel is None \
            else show_boss_panel
        self.screen = None
        self._set_mode()
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.text = T.Text()
        self.sprites = Sprites(SPRITE_SIZE, L.CELL)
        self.sound = SoundPlayer(enabled=sound)
        self.music = MusicPlayer(enabled=sound)
        self._apply_audio()
        self.buttons = ButtonRenderer(self.text)
        self.options = OptionsMenu(self.settings)
        self.options_return = "menu"
        self.board = BoardView(self.text, self.sprites)
        self.hud = Hud(self.text)
        self.panel_view = BossPanel(self.text)
        self.screens = Screens(self.text, self.sprites, self.buttons)
        self.dungeon_view = DungeonView(self.text, self.sprites, self.buttons)
        self._campaign = campaign         # None бол анх хэрэг болоход save файлаас ачаална
        self.enemy_factory = enemy_factory or (lambda: TacticalAI())
        self.dungeon_map = None           # DungeonMap (газрын зургийн сонголт)
        self.stage_key = None             # тоглож буй dungeon-ий үе; None — хурдан тулаан
        self.reward = None                # campaign.Reward (шагналын дэлгэц)
        self.reward_t = 0.0

        self.session = session if session is not None else GameSession()
        self.selection = Selection(self.session, side=self.session.human_side)
        self.stats = MatchStats()
        self.session.add_hook(self.stats.on_action)
        self.logger = logger              # learning.GameLogger — тоглолтын log (DQ)
        if logger is not None:
            self.session.add_hook(logger.on_action)
        self.fixed_boss = boss
        self.boss_factory = boss_factory
        self.boss_mode = boss_mode
        self.boss = BossDriver(self._new_controller())
        self._fixed_step_delay = boss_step_delay       # None → тохиргооны «дайсны хурд»
        self.boss_step_delay = boss_step_delay if boss_step_delay is not None \
            else self.settings.enemy_step_delay
        self.anim = Animator()
        self.vfx = Vfx()
        self.vfx_view = VfxView()
        self.log: deque = deque(maxlen=LOG_LINES)

        self.boss_phase = "idle"          # idle | thinking | acting
        self.boss_queue: deque = deque()
        self.boss_timer = 0.0
        self.boss_panel = None            # decision.to_panel()
        self.boss_panel_round = None
        self.hover = None
        self.mouse_pos = None
        self.running = True

        self.screen_name = start_screen   # intro | menu | dungeon | options | help | game | result | reward
        self.intro_t = 0.0
        self.menu_t = 0.0                 # цэсний оч хөдлөх хугацаа
        self.paused = False
        self.help_return = "menu"
        self.over_timer = 0.0
        self.main_menu = Menu(self._main_items(), top=250, height=46, gap=10)
        self.pause_menu = Menu(self._pause_items(), top=220)
        self.result_menu = Menu([MenuItem("again", "Дахин тоглох"),
                                 MenuItem("menu", "Үндсэн цэс")], top=410)
        self.reward_menu = Menu([MenuItem("map", "Газрын зураг")], top=500)
        if logger is not None and start_screen == "game":   # --skip-menu: эхний тоглолтын log
            logger.start(self.state, meta=self._log_meta())

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
        return [MenuItem("play", "Тоглох (Dungeon)", primary=True,
                         hint="5 давхар, 20 үе — ахиц автоматаар хадгалагдана"),
                MenuItem("quick", "Хурдан тулаан: Demon Lord",
                         hint="Гурван баатар эсрэг тоглогчоос суралцдаг Demon Lord"),
                MenuItem("boss_mode", f"Босс: {BOSS_MODE_LABELS[self.boss_mode]}",
                         enabled=self._boss_mode_selectable(),
                         hint="Demon Lord-ийн AI: хурдан үнэлгээ эсвэл гүн MCTS (≤ 2 сек)"),
                MenuItem("options", "Тохиргоо",
                         hint="Дууны түвшин, дайсны хурд, бүтэн дэлгэц"),
                MenuItem("help", "Удирдлага", hint="Товчлуур, хулганы удирдлага"),
                MenuItem("quit", "Гарах")]

    def _pause_items(self) -> list:
        if self.stage_key is not None:
            back = MenuItem("map", "Газрын зураг руу")
        else:
            back = MenuItem("menu", "Үндсэн цэс")
        return [MenuItem("resume", "Үргэлжлүүлэх", primary=True),
                MenuItem("restart", "Шинээр эхлэх"),
                MenuItem("options", "Тохиргоо"),
                MenuItem("help", "Удирдлага"), back]

    @property
    def campaign(self) -> Campaign:
        if self._campaign is None:
            self._campaign = Campaign.load()
        return self._campaign

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
        self.vfx.push(events, self.state)
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
        """Хурдан тулаан: анхны Demon Lord-ийн тулаан (цэснээс, түр зогсолтоос, үр дүнгээс)."""
        self.stage_key = None
        self.board.set_theme(None)
        self._begin(None, self._new_controller())

    def start_stage(self, key: str) -> None:
        """Dungeon-ий үеийг эхлүүлнэ: баатрууд кампанит ажлын level, item-тэй."""
        state = self.campaign.new_state(key)
        self.stage_key = key
        self.board.set_theme(FLOORS[parse_key(key)[0] - 1].theme)
        if key == FINAL_STAGE:                       # эцсийн тулаан — суралцдаг BossAI
            controller = self._new_controller()
        else:
            controller = self.enemy_factory()
        self._begin(state, controller)

    def _begin(self, state, controller) -> None:
        self.boss.cancel()
        self.boss = BossDriver(controller)
        self.session.reset(state)
        self.pause_menu.items = self._pause_items()
        self.reward = None
        if self.logger is not None:
            self.logger.start(self.state, meta=self._log_meta())
        self.stats.reset()
        self.selection.clear()
        self.anim.clear()
        self.vfx.clear()
        self.log.clear()
        self.boss_phase = "idle"
        self.boss_queue.clear()
        self.boss_panel = None
        self.boss_panel_round = None
        self.over_timer = 0.0
        self.paused = False
        self.screen_name = "game"

    def restart(self) -> None:
        if self.stage_key is not None:
            self.start_stage(self.stage_key)
        else:
            self.start_game()

    def _log_meta(self) -> dict:
        """Log-ийн meta: аль босс, суралцсан (профайлтай) эсэх, dungeon-ий үе — A/B-д ялгана."""
        meta = {"boss": self._boss_label(),
                "learned": bool(getattr(self.boss.controller, "profile", None))}
        if self.stage_key is not None:
            meta["stage"] = self.stage_key
        return meta

    def _boss_label(self) -> str:
        c = self.boss.controller
        if isinstance(c, PlaceholderBoss):
            return "placeholder"
        if isinstance(c, TacticalAI):
            return "tactic"
        return getattr(c, "mode", type(c).__name__)

    def go_menu(self) -> None:
        self._leave_battle()
        self.screen_name = "menu"
        self.main_menu.index = 0

    def go_map(self, select: Optional[str] = None) -> None:
        """Dungeon-ий газрын зураг (цэснээс, шагналын дэлгэцээс, түр зогсолтоос)."""
        self._leave_battle()
        if self.dungeon_map is None:
            self.dungeon_map = DungeonMap(self.campaign)
        self.dungeon_map.refresh()
        if not self.dungeon_map.select(select or self.campaign.next_stage()):
            self.dungeon_map.select(self.campaign.next_stage())
        self.screen_name = "dungeon"

    def _leave_battle(self) -> None:
        if self.logger is not None:
            self.logger.close("menu")
        self.boss.cancel()
        self.boss_phase = "idle"
        self.paused = False

    def toggle_boss_panel(self) -> None:
        self.show_boss_panel = not self.show_boss_panel
        self.settings.boss_panel = self.show_boss_panel
        self.settings.save()
        self._set_mode()

    def _set_mode(self) -> None:
        """Цонхны хэмжээ (самбартай/самбаргүй), бүтэн дэлгэц бол SCALED — байршил өөрчлөгдөхгүй."""
        size = L.screen_size(self.show_boss_panel)
        if self.settings.fullscreen:
            try:
                self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.SCALED)
                return
            except pygame.error:
                self.settings.fullscreen = False
        self.screen = pygame.display.set_mode(size)

    def _apply_audio(self) -> None:
        self.sound.set_gain(self.settings.sfx_gain)
        self.music.set_gain(self.settings.music_gain)

    # ------------------------------------------------------------------ тохиргоо
    def open_options(self, came_from: str) -> None:
        self.options_return = came_from          # "menu" | "pause"
        self.options.index = 0
        self.options.dragging = None
        self.screen_name = "options"

    def close_options(self) -> None:
        self.settings.save()
        self.options.dragging = None
        self.screen_name = "game" if self.options_return == "pause" else "menu"

    def _on_setting(self, key) -> None:
        """Тохиргоо өөрчлөгдсөний дараа шууд хэрэгжүүлж хадгална."""
        if key is None:
            return
        if key in Settings.VOLUME_KEYS:
            self._apply_audio()
            self.sound.play("tick")              # эффектийн түвшинг сонсгоно
        elif key == "enemy_speed" and self._fixed_step_delay is None:
            self.boss_step_delay = self.settings.enemy_step_delay
        elif key == "boss_panel" and self.show_boss_panel != self.settings.boss_panel:
            self.show_boss_panel = self.settings.boss_panel
            self._set_mode()
        elif key == "fullscreen":
            self._set_mode()
        elif key == "defaults":
            self._apply_audio()
            if self._fixed_step_delay is None:
                self.boss_step_delay = self.settings.enemy_step_delay
            self.show_boss_panel = self.settings.boss_panel
            self._set_mode()
        self.settings.save()

    def _options_event(self, e) -> None:
        opts = self.options
        w = self.screen.get_width()
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_DOWN):
                opts.move(-1 if e.key == pygame.K_UP else 1)
                self.sound.play("tick")
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._on_setting(opts.adjust(-1 if e.key == pygame.K_LEFT else 1))
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self._activate_option(opts.index)
            elif e.key == pygame.K_ESCAPE:
                self.sound.play("back")
                self.close_options()
        elif e.type == pygame.MOUSEMOTION:
            if opts.dragging is not None:
                self._on_setting(opts.set_slider_from_x(opts.dragging, e.pos[0], w))
            else:
                hit = opts.hit(e.pos, w)
                if hit is not None and hit[1] != opts.index:
                    opts.index = hit[1]
                    self.sound.play("tick")
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            hit = opts.hit(e.pos, w)
            if hit is None:
                return
            opts.index = hit[1]
            if hit[0] == "slider":
                opts.dragging = hit[1]
                self._on_setting(opts.set_slider_from_x(hit[1], e.pos[0], w))
            else:
                self._activate_option(hit[1])
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            opts.dragging = None

    def _activate_option(self, index: int) -> None:
        key = self.options.activate(index)
        if key == "back":
            self.sound.play("back")
            self.close_options()
        elif key is not None:
            self.sound.play("click")
            self._on_setting(key)

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
        elif self.screen_name == "dungeon":
            self._map_event(e)
        elif self.screen_name == "options":
            self._options_event(e)
        elif self.screen_name == "reward":
            self._reward_event(e)
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
            self.go_map()
        elif key == "quick":
            self.start_game()
        elif key == "options":
            self.open_options("menu")
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
            self.restart()
        elif key == "options":
            self.open_options("pause")
        elif key == "help":
            self.help_return = "pause"
            self.screen_name = "help"
        elif key == "menu":
            self.go_menu()
        elif key == "map":
            self.go_map(self.stage_key)

    def _on_result(self, key: str) -> None:
        if key == "again":
            self.start_game()
        elif key == "menu":
            self.go_menu()

    # ---- dungeon-ий газрын зураг ----
    def _map_event(self, e) -> None:
        dm = self.dungeon_map
        w = self.screen.get_width()
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self._map_click(dm, dm.hit(e.pos, w))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            dm.bag_pick = None
        elif e.type == pygame.KEYDOWN:
            moves = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                     pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}
            if e.key in moves:
                if dm.move(*moves[e.key], w):
                    self.sound.play("tick")
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                self.sound.play("click")
                self.start_stage(dm.selected)
            elif e.key == pygame.K_ESCAPE:
                self.sound.play("back")
                self.go_menu()

    def _map_click(self, dm, hit) -> None:
        if hit is None:
            return
        if hit[0] == "node":
            if dm.selected == hit[1] and self.campaign.is_unlocked(hit[1]):
                self.sound.play("click")
                self.start_stage(hit[1])          # сонгосон зангилаан дээр дахин дарах
            else:
                self.sound.play("select" if dm.select(hit[1]) else "error")
        elif hit[0] == "button":
            self.sound.play("click")
            if hit[1] == "start" and self.campaign.is_unlocked(dm.selected):
                self.start_stage(dm.selected)
            elif hit[1] == "back":
                self.go_menu()
            elif hit[1] == "reset":
                dm.press_reset()
        elif hit[0] == "bag":
            self.sound.play("tick")
            dm.click_bag(hit[1])
        elif hit[0] == "item":
            if dm.bag_pick is not None:
                self.sound.play("select" if dm.click_hero(hit[1]) else "error")
            elif dm.click_item(hit[1], hit[2]):
                self.sound.play("back")
        elif hit[0] == "hero" and dm.bag_pick is not None:
            self.sound.play("select" if dm.click_hero(hit[1]) else "error")

    # ---- шагналын дэлгэц ----
    def _finish_stage(self) -> None:
        """Тулаан дууссаны дараа XP, олзыг тооцож хадгалаад шагналын дэлгэц рүү шилжинэ."""
        won = self.state.winner == HEROES
        self.reward = self.campaign.finish_stage(self.stage_key, won, self.state.round)
        if won and self.reward.unlocked:
            items = [MenuItem("next", f"Дараагийн үе: {self.reward.unlocked}"),
                     MenuItem("map", "Газрын зураг")]
        elif won:
            items = [MenuItem("map", "Газрын зураг"), MenuItem("again", "Дахин тоглох")]
        else:
            items = [MenuItem("again", "Дахин оролдох"), MenuItem("map", "Газрын зураг")]
        self.reward_menu = Menu(items, top=self.screen.get_height() - 140)
        self.reward_t = 0.0
        self.screen_name = "reward"

    def _reward_event(self, e) -> None:
        r = self.reward
        if r is not None and r.drop is not None and r.assigned_to is None:
            target = None
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for name, rect in reward_drop_buttons(self.screen.get_width(),
                                                      reward_drop_top()).items():
                    if L.point_in(rect, e.pos):
                        target = name
            elif e.type == pygame.KEYDOWN and pygame.K_1 <= e.key <= pygame.K_4:
                target = (list(HERO_UIDS) + ["bag"])[e.key - pygame.K_1]
            if target is not None:
                self._assign_drop(target)
                return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.go_map(self.stage_key)
        else:
            self._menu_event(self.reward_menu, e, self._on_reward)

    def _assign_drop(self, target: str) -> None:
        r = self.reward
        if target == "bag":
            r.assigned_to = "bag"
            self.sound.play("tick")
        elif self.campaign.equip(r.drop, target):
            r.assigned_to = target
            self.sound.play("select")
        else:
            self.sound.play("error")

    def _on_reward(self, key: str) -> None:
        if key == "next":
            self.start_stage(self.reward.unlocked)
        elif key == "again":
            self.start_stage(self.reward.key)
        elif key == "map":
            self.go_map(self.reward.unlocked or self.reward.key)

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
        elif key == pygame.K_r and self.state.is_over and self.stage_key is None:
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
        """Одоогийн дэлгэцэд тохирох хөгжим. Тоглолт дуусах агшинд None — jingle сонсогдоно."""
        name = self.screen_name
        if name == "help":
            name = "game" if self.help_return == "pause" else "menu"
        if name == "options":
            name = "game" if self.options_return == "pause" else "menu"
        if name == "game" and self.state.is_over:
            return None
        return {"intro": "intro", "menu": "title", "dungeon": "title", "game": "battle",
                "result": "result", "reward": "result"}.get(name)

    def update(self, dt: float) -> None:
        self.music.play(self.music_track())
        self.music.update(dt)
        if self.screen_name == "intro":
            self.intro_t += dt
            if self.intro_t >= INTRO_DURATION:
                self.go_menu()
            return
        if self.screen_name in ("menu", "help", "dungeon", "options"):
            self.menu_t += dt
        if self.screen_name == "dungeon" and self.dungeon_map is not None:
            self.dungeon_map.update(dt)
        if self.screen_name == "reward":
            self.reward_t += dt
        if self.screen_name != "game" or self.paused:
            return
        self.anim.update(dt)
        self.vfx.update(dt)
        self.update_boss(dt)
        if self.state.is_over and not self.anim.busy:
            self.over_timer += dt
            if self.over_timer >= RESULT_DELAY:
                if self.stage_key is not None:
                    self._finish_stage()
                else:
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
            self.screens.draw_menu(self.screen, self.main_menu, self.mouse_pos, note, self.menu_t,
                                   footer=self._progress_footer())
        elif self.screen_name == "options":
            from_pause = self.options_return == "pause"
            if from_pause:
                self._draw_game(overlay=False)
            self.screens.draw_options(self.screen, self.options, self.mouse_pos, self.menu_t,
                                      dimmed_bg=from_pause)
        elif self.screen_name == "dungeon":
            self.dungeon_view.draw_map(self.screen, self.dungeon_map, self.mouse_pos, self.menu_t)
        elif self.screen_name == "reward":
            self.dungeon_view.draw_reward(self.screen, self.reward, self.campaign, self.state,
                                          self.stats, self.reward_menu, self.mouse_pos,
                                          self.reward_t)
        elif self.screen_name == "help":
            self.screens.draw_help(self.screen)
        elif self.screen_name == "result":
            self.screens.draw_result(self.screen, self.state, self.stats, self.result_menu,
                                     self.mouse_pos)
        else:
            self._draw_game()
        pygame.display.flip()

    def _progress_footer(self) -> str:
        c = self.campaign
        return f"Dungeon: {len(c.data['cleared'])}/20 үе · Lv {c.level}"

    def _draw_game(self, overlay: bool = True) -> None:
        interactive = not self.input_locked
        self.board.draw(self.screen, self.state, self.selection, self.anim,
                        self.hover if interactive else None, interactive,
                        fx=lambda layer: self.vfx_view.draw(self.screen, self.vfx, layer))
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
        if self.paused and overlay:
            self.screens.draw_pause(self.screen, self.pause_menu, self.mouse_pos)

    def run(self, max_frames: Optional[int] = None) -> None:
        frames = 0
        while self.running:
            dt = min(self.clock.tick(self.fps) / 1000.0, 0.1)
            self.step(dt)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if self.logger is not None:
            self.logger.close("quit")
        pygame.quit()


def current_profile(args):
    """Шинэ тоглолтын өмнө боссын профайл: log-оос шинээр гаргана (auto), файлаас, эсвэл None.

    auto үед гарсан профайлыг <log-dir>/profile.json-д хадгална (тайлан, шалгалтад).
    Тоглолтын log байхгүй бол None — суралцаагүй босс.
    """
    if args.profile == "none":
        return None
    from learning.profile import load_profile, profile_from_logs, save_profile
    if args.profile != "auto":
        return load_profile(args.profile)
    prof = profile_from_logs(args.log_dir)
    if not prof["stats"]["games"]:
        return None
    try:
        save_profile(prof, os.path.join(args.log_dir, "profile.json"))
    except OSError:
        pass
    return prof


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m game", description="Outworld Devourer")
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--seed", type=int, default=None, help="боссын санамсаргүй сонголтын seed")
    p.add_argument("--boss-mode", choices=BOSS_MODES, default="eval",
                   help="боссын AI-ийн горим (ai/ суусан үед)")
    p.add_argument("--placeholder-boss", action="store_true",
                   help="ai/ байсан ч түр боссыг ашиглах")
    p.add_argument("--skip-intro", action="store_true", help="эхлэлийн дүр зургийг алгасах")
    p.add_argument("--skip-menu", action="store_true", help="цэсгүйгээр шууд тоглоом эхлүүлэх")
    p.add_argument("--log-dir", default="logs", help="тоглолтын log хадгалах хавтас")
    p.add_argument("--no-log", action="store_true", help="тоглолтын log бичихгүй")
    p.add_argument("--profile", default="auto",
                   help="зуршлын профайл: auto (log-оос, тоглолт бүрийн өмнө), none, эсвэл JSON зам")
    p.add_argument("--save", default=None,
                   help="dungeon-ий ахицын файл (анхдагч: %%APPDATA%%/OutworldDevourer/save.json)")
    p.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    boss = PlaceholderBoss(seed=args.seed) if args.placeholder_boss else None
    logger = None
    if not args.no_log:
        from learning import GameLogger
        logger = GameLogger(args.log_dir, human_side=HEROES)
    app = App(GameSession(human_side=HEROES), boss=boss, fps=args.fps, logger=logger,
              boss_factory=lambda mode: make_boss(mode=mode, seed=args.seed,
                                                  profile=current_profile(args)),
              campaign=Campaign.load(args.save) if args.save else None,
              enemy_factory=lambda: TacticalAI(profile=current_profile(args), seed=args.seed),
              boss_mode=args.boss_mode,
              start_screen="game" if args.skip_menu else ("menu" if args.skip_intro else "intro"))
    app.run(max_frames=args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
