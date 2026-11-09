"""Үндсэн давталт (pygame): оролт → нүүдэл → анимаци → зурах, 60 FPS.

Хүний нүүдэл: хулгана/товчлуур → Selection → GameSession.play()
Боссын нүүдэл: BossDriver (thread) → decision.actions-ийг нэг нэгээр нь GameSession.play()
Хоёулаа GameSession-оор дамждаг тул on_action hook нүүдэл бүрт дуудагдана.
"""

from __future__ import annotations

import argparse
import sys
from collections import deque
from typing import Optional

import pygame

from engine import END_TURN, HEROES

from . import layout as L
from . import theme as T
from .anim import Animator
from .board_view import BoardView
from .boss_driver import BossDriver, make_boss
from .hud import Hud
from .input import Selection
from .labels import event_text
from .session import GameSession

FPS = 60
BOSS_STEP_DELAY = 0.5      # боссын нүүдэл хооронд (сек), тоглогч юу болсныг харах
LOG_LINES = 14


class App:
    def __init__(self, session: Optional[GameSession] = None, boss=None, fps: int = FPS,
                 boss_step_delay: float = BOSS_STEP_DELAY):
        pygame.init()
        pygame.display.set_caption("Outworld Devourer")
        self.screen = pygame.display.set_mode((L.SCREEN_W, L.SCREEN_H))
        self.clock = pygame.time.Clock()
        self.fps = fps
        self.text = T.Text()
        self.board = BoardView(self.text)
        self.hud = Hud(self.text)

        self.session = session if session is not None else GameSession()
        self.selection = Selection(self.session, side=self.session.human_side)
        self.boss = BossDriver(boss if boss is not None else make_boss())
        self.boss_step_delay = boss_step_delay
        self.anim = Animator()
        self.log: deque = deque(maxlen=LOG_LINES)

        self.boss_phase = "idle"          # idle | thinking | acting
        self.boss_queue: deque = deque()
        self.boss_timer = 0.0
        self.boss_panel = None            # «Боссын бодол» (11/29)
        self.hover = None
        self.mouse_pos = None
        self.running = True

    # ------------------------------------------------------------------ нүүдэл
    @property
    def state(self):
        return self.session.state

    @property
    def input_locked(self) -> bool:
        return self.anim.busy or not self.session.human_to_act

    def play(self, action) -> list:
        events = self.session.play(action)
        self.anim.push(events, self.state)
        for ev in events:
            if ev["type"] == "turn_start":   # ээлж солигдсон: боссын өмнөх ээлжийн төлөвийг цэвэрлэнэ
                self.boss_phase = "idle"
                self.boss_queue.clear()
            line = event_text(ev, self.state)
            if line:
                self.log.append(line)
        self.selection.refresh()
        return events

    def restart(self) -> None:
        self.boss.cancel()
        self.session.reset()
        self.selection.clear()
        self.anim.clear()
        self.log.clear()
        self.boss_phase = "idle"
        self.boss_queue.clear()
        self.boss_panel = None

    # ------------------------------------------------------------------ оролт
    def handle_event(self, e) -> None:
        if e.type == pygame.QUIT:
            self.running = False
        elif e.type == pygame.MOUSEMOTION:
            self.mouse_pos = e.pos
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
            self.selection.back()
        elif key == pygame.K_r and self.state.is_over:
            self.restart()
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
        return ""

    def step(self, dt: float) -> None:
        for e in pygame.event.get():
            self.handle_event(e)
        self.anim.update(dt)
        self.update_boss(dt)
        self.draw()

    def draw(self) -> None:
        self.screen.fill(T.BG)
        interactive = not self.input_locked
        self.board.draw(self.screen, self.state, self.selection, self.anim,
                        self.hover if interactive else None, interactive)
        enabled = {"wait": interactive and self.selection.unit is not None,
                   "end_turn": interactive, "skills": interactive}
        hover_unit = self.state.unit_at(self.hover) if self.hover is not None else None
        self.hud.draw(self.screen, self.state, self.selection, self.log, self.status_text(),
                      enabled, self.mouse_pos, hover_unit)
        if self.state.is_over and not self.anim.busy:
            self.hud.draw_game_over(self.screen, self.state)
        pygame.display.flip()

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
    p = argparse.ArgumentParser(prog="python -m game", description="Outworld Devourer")
    p.add_argument("--fps", type=int, default=FPS)
    p.add_argument("--seed", type=int, default=None, help="боссын санамсаргүй сонголтын seed")
    p.add_argument("--placeholder-boss", action="store_true",
                   help="ai/ байсан ч түр боссыг ашиглах")
    p.add_argument("--frames", type=int, default=None, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    if args.placeholder_boss:
        from .boss_driver import PlaceholderBoss
        boss = PlaceholderBoss(seed=args.seed)
    else:
        boss = make_boss(mode="eval", seed=args.seed)
    App(GameSession(human_side=HEROES), boss=boss, fps=args.fps).run(max_frames=args.frames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
