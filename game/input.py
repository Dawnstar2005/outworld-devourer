"""Хулганы сонголт → Action (pygame-гүй, тестлэгдэнэ).

Дүрмийг энд шалгахгүй. Дүр сонгоход `engine.unit_actions(state, unit)`-аас тухайн
дүрийн бүх боломжит нүүдлийг авна:

    хөдөлж болох нүд          = {a.dest for a in actions}
    тэр нүднээс хийх нүүдлүүд = [a for a in actions if a.dest == сонгосон нүд]
    ур чадварын бай нүд       = {a.target for a in тэр нүднээс хийх нүүдлүүд if a.skill == sid}

Сонголтын дараалал (11/20):
    1. Нүүгээгүй баатар дээр дарна → сонгогдоно. Очих нүд (`dest`) = одоогийн нүд.
    2. Тодорсон нүдэн дээр дарна → `dest` тэнд шилжинэ (дүрийн сүүдэр харагдана).
       Тэр нүдэн дээр дахин дарвал зөвхөн хөдөлнө (`confirm_move()` — W / Space ч мөн адил).
    3. Ур чадвар сонгоно (`arm(sid)`, 1–4 товч) → `dest`-ээс онох бай нүд тодорно.
       Бай дээр дарвал Action буцаана. Бай шаардахгүй (Taunt, Imp дуудах) бол
       тухайн товчийг дахин дарах эсвэл дүрийн нүдэн дээр дарна.
       Ур чадвар сонгосон үед өөр очих нүд дээр дарвал байрлал солигдоно (ур чадвар хэвээр),
       бай биш газар дарвал ур чадвар цуцлагдана.
       Мөсөн хана: `rotate()` (V / хулганы дугуй) чиглэлийг солино.
    `back()` (баруун товч / Esc) — нэг алхам буцна: ур чадвар → очих нүд → сонголт.
    `end_turn()` — END_TURN (үлдсэн дүрүүдийг алгасна).
"""

from __future__ import annotations

from typing import Optional

from engine import END_TURN, HEROES, SKILLS, Action, Unit, next_state, unit_actions


class Selection:
    def __init__(self, session, side: str = HEROES):
        self.session = session          # GameSession (state-ийг reset хийхэд шинэчлэгдэнэ)
        self.side = side
        self.unit_uid: Optional[str] = None
        self.actions: list[Action] = []
        self.dest = None                # очих нүд (сонгосон дүрийн одоогийн нүд эсвэл шинэ)
        self.skill: Optional[str] = None
        self.variant = 0                # Мөсөн ханын илүүд үзэх чиглэл
        self._preview_cache: tuple = (None, None)

    # ------------------------------------------------------------------ асуулга
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
        """Сонгосон дүрийн очиж болох нүднүүд (одоогийн нүд орно)."""
        return {a.dest for a in self.actions}

    def actions_at(self, dest) -> list:
        """`dest` нүд рүү хөдөлсний дараах бүх нүүдэл (хөдлөх л, эсвэл + ур чадвар)."""
        return [a for a in self.actions if a.dest == dest]

    def skill_actions_at(self, dest, sid: Optional[str] = None) -> list:
        return [a for a in self.actions if a.dest == dest and a.skill is not None
                and (sid is None or a.skill == sid)]

    def move_action(self, dest) -> Optional[Action]:
        """`dest` рүү зөвхөн хөдлөх Action (алхах нь үсрэлтээс түрүүлнэ)."""
        moves = [a for a in self.actions if a.dest == dest and a.skill is None]
        moves.sort(key=lambda a: a.leap)
        return moves[0] if moves else None

    @property
    def skills(self) -> tuple:
        """Сонгосон дүрийн ур чадварууд (1–4 товчны дарааллаар). Үсрэлт хөдөлгөөнд орно."""
        u = self.unit
        return u.type.skills if u is not None else ()

    def skill_status(self, sid: str) -> str:
        """"ready" | "cooldown" | "no_target" — HUD-ийн товчинд."""
        u = self.unit
        if u is None or u.cooldowns.get(sid, 0) > 0:
            return "cooldown"
        return "ready" if self.skill_actions_at(self.dest, sid) else "no_target"

    @property
    def needs_target(self) -> bool:
        """Сонгосон ур чадвар бай нүд шаардах эсэх (Taunt, Imp дуудах шаардахгүй)."""
        return any(a.target is not None for a in self.skill_actions_at(self.dest, self.skill))

    @property
    def target_cells(self) -> set:
        if self.skill is None:
            return set()
        return {a.target for a in self.skill_actions_at(self.dest, self.skill)
                if a.target is not None}

    def action_for_target(self, cell) -> Optional[Action]:
        """Сонгосон ур чадварыг `cell` руу хэрэглэх Action (Мөсөн хана: `variant`-ийг илүүд үзнэ)."""
        if self.skill is None:
            return None
        acts = [a for a in self.skill_actions_at(self.dest, self.skill) if a.target == cell]
        if not acts:
            return None
        acts.sort(key=lambda a: (a.variant != self.variant, a.leap))
        return acts[0]

    def hover_action(self, cell) -> Optional[Action]:
        """`cell` дээр дарвал хийгдэх Action (урьдчилан харуулахад). Байхгүй бол None."""
        u = self.unit
        if u is None or cell is None:
            return None
        if self.skill is not None:
            if self.needs_target:
                return self.action_for_target(cell)
            if cell == self.dest:
                return self._no_target_action()
            return None
        if cell == self.dest and cell != u.pos:
            return self.move_action(cell)
        return None

    def armed_action(self) -> Optional[Action]:
        """Бай шаардахгүй ур чадвар сонгогдсон бол түүний Action."""
        return self._no_target_action() if self.skill is not None and not self.needs_target else None

    def _no_target_action(self) -> Optional[Action]:
        acts = self.skill_actions_at(self.dest, self.skill)
        acts.sort(key=lambda a: a.leap)
        return acts[0] if acts else None

    def preview(self, action: Optional[Action]) -> dict:
        """Action хийвэл дүр бүрт юу болохыг engine.next_state()-ээр тооцоолно.

        Буцаах: {uid: {"hp": өөрчлөлт, "dies": bool, "shield": int, "cursed": bool,
                       "taunted": bool}} — зөвхөн өөрчлөгдсөн дүрүүд.
        """
        if action is None:
            return {}
        if self._preview_cache[0] == action:
            return self._preview_cache[1]
        before = self.state
        after = next_state(before, action)
        out = {}
        for uid, b in before.units.items():
            a = after.units[uid]
            if not b.alive:
                continue
            fx = {}
            if a.hp != b.hp:
                fx["hp"] = a.hp - b.hp
            if not a.alive:
                fx["dies"] = True
            if a.shield > b.shield:
                fx["shield"] = a.shield
            if a.cursed > b.cursed:
                fx["cursed"] = True
            if a.taunt_turns > b.taunt_turns or (a.taunted_by and a.taunted_by != b.taunted_by):
                fx["taunted"] = True
            if fx:
                out[uid] = fx
        self._preview_cache = (action, out)
        return out

    @staticmethod
    def skill_kind(sid: Optional[str]) -> Optional[str]:
        sk = SKILLS.get(sid) if sid else None
        return sk.kind if sk else None

    # ------------------------------------------------------------------ үйлдэл
    def select(self, uid: str) -> bool:
        u = self.state.units.get(uid)
        if not self.selectable(u):
            return False
        self.unit_uid = uid
        self.actions = unit_actions(self.state, u)
        self.dest = u.pos
        self.skill = None
        self._preview_cache = (None, None)
        return True

    def clear(self) -> None:
        self.unit_uid = None
        self.actions = []
        self.dest = None
        self.skill = None
        self._preview_cache = (None, None)

    def refresh(self) -> None:
        """Төлөв өөрчлөгдсөний дараа дуудна: сонгосон дүр нүүх боломжгүй болсон бол цуцална."""
        uid = self.unit_uid
        self.clear()
        if uid is not None:
            self.select(uid)

    def stage(self, dest) -> bool:
        """Очих нүдийг сонгоно. Сонгосон ур чадвар тэндээс хэрэглэгдэхгүй бол цуцлагдана."""
        if self.unit is None or dest not in self.move_cells:
            return False
        self.dest = dest
        if self.skill is not None and not self.skill_actions_at(dest, self.skill):
            self.skill = None
        return True

    def arm(self, sid: str) -> Optional[Action]:
        """Ур чадвар сонгох. Бай шаардахгүй ур чадварыг дахин сонговол Action буцаана."""
        if self.unit is None or sid not in self.skills or self.skill_status(sid) != "ready":
            return None
        if self.skill == sid:
            action = self.armed_action()
            if action is not None:
                self.clear()
                return action
            self.skill = None           # бай шаарддаг бол дахин дарахад цуцлагдана
            return None
        self.skill = sid
        return None

    def arm_index(self, i: int) -> Optional[Action]:
        skills = self.skills
        return self.arm(skills[i]) if 0 <= i < len(skills) else None

    def rotate(self) -> None:
        """Мөсөн ханын чиглэл: хэвтээ ↔ босоо."""
        self.variant = 1 - self.variant

    def back(self) -> None:
        """Нэг алхам буцах: ур чадвар → очих нүд → сонголт."""
        u = self.unit
        if u is None:
            return
        if self.skill is not None:
            self.skill = None
        elif self.dest != u.pos:
            self.dest = u.pos
        else:
            self.clear()

    def confirm_move(self) -> Optional[Action]:
        """Очих нүд рүү зөвхөн хөдөлнө (очих нүд = одоогийн нүд бол байрандаа хүлээнэ)."""
        if self.unit is None or not self.my_turn:
            return None
        action = self.move_action(self.dest)
        self.clear()
        return action

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
        if self.skill is not None:
            action = self.hover_action(cell)
            if action is not None:
                self.clear()
                return action
            if cell != self.dest and self.stage(cell):   # байрлалаа солих, ур чадвар хэвээр
                return None
            if clicked is not None and clicked is not sel and self.selectable(clicked):
                self.select(clicked.uid)
                return None
            self.skill = None                    # бай биш газар дарвал ур чадвар цуцлагдана
            return None
        if cell == self.dest:
            if cell == sel.pos:                  # өөр дээрээ дарвал сонголт цуцлагдана
                self.clear()
                return None
            action = self.move_action(cell)
            self.clear()
            return action
        if clicked is not None and clicked is not sel and self.selectable(clicked):
            self.select(clicked.uid)
            return None
        if self.stage(cell):
            return None
        self.clear()
        return None

    def end_turn(self) -> Optional[Action]:
        if not self.my_turn:
            return None
        self.clear()
        return END_TURN
