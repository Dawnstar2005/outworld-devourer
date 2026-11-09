"""Нэг тоглолтын session: төлөв, нүүдэл хийх, on_action hook (pygame-гүй).

Хүний болон боссын бүх нүүдэл `GameSession.play()`-ээр дамжина. Нүүдэл бүрийн дараа
бүртгэсэн hook бүрийг дуудна:

    on_action(state_before, action, events)

    state_before — нүүдлээс өмнөх төлөвийн хуулбар (GameState)
    action       — хийсэн Action (END_TURN орно)
    events       — apply()-ийн буцаасан үйл явдлууд

DQ-ийн log-д жишээ:

    session.add_hook(lambda before, a, ev: log.write(json.dumps(
        {"state": before.to_dict(), "action": a.to_dict(), "events": ev})))
"""

from __future__ import annotations

import sys
import traceback
from typing import Callable, Optional

from engine import HEROES, Action, GameState, apply

OnAction = Callable[[GameState, Action, list], None]


class GameSession:
    def __init__(self, state: Optional[GameState] = None, human_side: str = HEROES,
                 on_action: Optional[OnAction] = None):
        self.state = state if state is not None else GameState.new_game()
        self.human_side = human_side
        self._hooks: list[OnAction] = []
        if on_action is not None:
            self.add_hook(on_action)

    # ---- hook ----
    def add_hook(self, fn: OnAction) -> None:
        self._hooks.append(fn)

    def remove_hook(self, fn: OnAction) -> None:
        self._hooks.remove(fn)

    # ---- нүүдэл ----
    def play(self, action: Action) -> list:
        """Нүүдлийг шалгаж (validate=True) хийнэ, hook-уудыг дуудаад events буцаана.

        Хууль бус нүүдэл бол ValueError (төлөв өөрчлөгдөхгүй, hook дуудагдахгүй).
        """
        before = self.state.clone()
        events = apply(self.state, action, validate=True)
        for fn in list(self._hooks):
            try:
                fn(before, action, events)
            except Exception:  # log бичих алдаа тоглоомыг зогсоохгүй, гэхдээ нуухгүй
                print("on_action hook алдаа:", file=sys.stderr)
                traceback.print_exc()
        return events

    def reset(self, state: Optional[GameState] = None) -> None:
        """Шинэ тоглолт эхлүүлнэ. Hook-ууд хэвээр үлдэнэ."""
        self.state = state if state is not None else GameState.new_game()

    # ---- асуулга ----
    @property
    def human_to_act(self) -> bool:
        return not self.state.is_over and self.state.side_to_act == self.human_side
