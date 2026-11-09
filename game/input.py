"""Хулганы сонголт → Action (pygame-гүй, тестлэгдэнэ).

Дүрмийг энд шалгахгүй. Дүр сонгоход `engine.unit_actions(state, unit)`-аас тухайн
дүрийн бүх боломжит нүүдлийг авна:

    хөдөлж болох нүд          = {a.dest for a in actions}
    тэр нүднээс хийх нүүдлүүд = [a for a in actions if a.dest == сонгосон нүд]

Сонголтын дараалал (11/15):
    1. Ээлж нь болсон, нүүгээгүй баатар дээр дарна → сонгогдоно, хөдөлж болох нүд тодорно.
    2. Тодорсон нүдэн дээр дарна → тэр нүд рүү хөдлөх Action буцаана.
       Өөр баатар дээр дарвал сонголт шилжинэ. Сонгосон баатар эсвэл хүрэхгүй нүд дээр дарвал цуцлагдана.
    `wait()` — хөдлөхгүй, юу ч хийхгүй (тухайн дүрийн ээлж дуусна).
    `end_turn()` — END_TURN (үлдсэн дүрүүдийг алгасна).
Ур чадвар сонгох шат (11/20) `skill_actions_at()` дээр нэмэгдэнэ.
"""

from __future__ import annotations

from typing import Optional

from engine import END_TURN, HEROES, Action, Unit, unit_actions


class Selection:
    def __init__(self, session, side: str = HEROES):
        self.session = session          # GameSession (state-ийг reset хийхэд шинэчлэгдэнэ)
        self.side = side
        self.unit_uid: Optional[str] = None
        self.actions: list[Action] = []

    # ---- асуулга ----
    @property
    def state(self):
        return self.session.state

    @property
    def unit(self) -> Optional[Unit]:
        return self.state.units.get(self.unit_uid) if self.unit_uid else None

    @property
    def my_turn(self) -> bool:
        return not self.state.is_over and self.state.side_to_act == self.side

    def selectable(self, unit: Optional[Unit]) -> bool:
        return (unit is not None and self.my_turn and unit.alive and unit.side == self.side
                and not unit.acted)

    @property
    def move_cells(self) -> set:
        """Сонгосон дүрийн хөдөлж болох нүднүүд (одоогийн нүд орно)."""
        return {a.dest for a in self.actions}

    def actions_at(self, dest) -> list:
        """`dest` нүд рүү хөдөлсний дараах бүх нүүдэл (хөдлөх л, эсвэл + ур чадвар)."""
        return [a for a in self.actions if a.dest == dest]

    def skill_actions_at(self, dest) -> list:
        return [a for a in self.actions if a.dest == dest and a.skill is not None]

    def move_action(self, dest) -> Optional[Action]:
        """`dest` рүү зөвхөн хөдлөх Action (алхах нь үсрэлтээс түрүүлнэ)."""
        moves = [a for a in self.actions if a.dest == dest and a.skill is None]
        moves.sort(key=lambda a: a.leap)
        return moves[0] if moves else None

    # ---- үйлдэл ----
    def select(self, uid: str) -> bool:
        u = self.state.units.get(uid)
        if not self.selectable(u):
            return False
        self.unit_uid = uid
        self.actions = unit_actions(self.state, u)
        return True

    def clear(self) -> None:
        self.unit_uid = None
        self.actions = []

    def refresh(self) -> None:
        """Төлөв өөрчлөгдсөний дараа дуудна: сонгосон дүр нүүх боломжгүй болсон бол цуцална."""
        uid = self.unit_uid
        self.clear()
        if uid is not None:
            self.select(uid)

    def click(self, cell) -> Optional[Action]:
        """Талбарын нүдэн дээр дарсан. Хийх Action эсвэл None буцаана."""
        if not self.my_turn:
            self.clear()
            return None
        clicked = self.state.unit_at(cell)
        sel = self.unit
        if sel is None:
            if self.selectable(clicked):
                self.select(clicked.uid)
            return None
        if cell == sel.pos:
            self.clear()
            return None
        if self.selectable(clicked):
            self.select(clicked.uid)
            return None
        action = self.move_action(cell)
        self.clear()
        return action

    def wait(self) -> Optional[Action]:
        """Сонгосон дүр байрандаа үлдэж ээлжээ дуусгана."""
        sel = self.unit
        if sel is None or not self.my_turn:
            return None
        action = self.move_action(sel.pos)
        self.clear()
        return action

    def end_turn(self) -> Optional[Action]:
        if not self.my_turn:
            return None
        self.clear()
        return END_TURN
