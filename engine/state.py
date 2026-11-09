"""Тоглоомын төлөв (GameState), дүр (Unit), нүүдэл (Action).

Энэ модуль pygame-гүй. Тоглоом (game/) болон боссын AI (ai/) хоёулаа
яг энэ төлөвийг ашиглана, тиймээс дүрэм хоёр газар зөрөхгүй.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import (BOARD_H, BOARD_W, DEMONS, ENRAGE_THRESHOLD, HEROES,
                        START_POSITIONS, UNIT_TYPES)

Cell = tuple  # (x, y)


@dataclass(frozen=True, slots=True)
class Action:
    """Нэг дүрийн нэг ээлжийн үйлдэл: хөдлөх (эсвэл үсрэх) + нэг ур чадвар.

    unit      — дүрийн id ("knight", "imp1", ...). Хоосон бол END_TURN.
    dest      — хөдөлсний дараах нүд (хөдлөхгүй бол одоогийн нүд).
    leap      — True бол dest рүү Сүүдрийн үсрэлтээр очно (зөвхөн Demon Lord).
    skill     — ур чадварын id, эсвэл None (зөвхөн хөдлөх / хүлээх).
    target    — ур чадварын бай нүд (taunt, summon-д None).
    target_uid— бай дүрийн id (нэг байтай ур чадварт). Log, таамаглалд хэрэгтэй.
    variant   — Мөсөн ханын чиглэл: 0 = хэвтээ (x, x+1), 1 = босоо (y, y+1).
    """

    unit: str
    dest: Cell = (-1, -1)
    skill: Optional[str] = None
    target: Optional[Cell] = None
    target_uid: Optional[str] = None
    variant: int = 0
    leap: bool = False

    @property
    def is_end_turn(self) -> bool:
        return self.unit == ""

    def to_dict(self) -> dict:
        return {"unit": self.unit, "dest": list(self.dest), "skill": self.skill,
                "target": list(self.target) if self.target else None,
                "target_uid": self.target_uid, "variant": self.variant, "leap": self.leap}

    @staticmethod
    def from_dict(d: dict) -> "Action":
        return Action(unit=d["unit"], dest=tuple(d["dest"]), skill=d.get("skill"),
                      target=tuple(d["target"]) if d.get("target") else None,
                      target_uid=d.get("target_uid"), variant=d.get("variant", 0),
                      leap=d.get("leap", False))


END_TURN = Action(unit="")


class Unit:
    __slots__ = ("uid", "kind", "side", "hp", "max_hp", "x", "y", "move", "cooldowns",
                 "shield", "cursed", "taunted_by", "taunt_turns", "acted", "alive",
                 "power_mult", "level")
    # Хуучин log/save-д байхгүй байж болох талбарууд ба default утга
    _DEFAULTS = {"power_mult": 1.0, "level": 1}

    def __init__(self, uid: str, kind: str, pos: Cell):
        t = UNIT_TYPES[kind]
        self.uid = uid
        self.kind = kind
        self.side = t.side
        self.hp = t.hp
        self.max_hp = t.hp
        self.x, self.y = pos
        self.move = t.move
        skills = t.skills + ((t.leap,) if t.leap else ())
        self.cooldowns = {s: 0 for s in skills}   # 0 = хэрэглэж болно
        self.shield = 0          # шингээх хохирлын үлдэгдэл
        self.cursed = 0          # эдгэрэл авахгүй үлдсэн ээлж
        self.taunted_by = None   # Taunt хийсэн дүрийн uid
        self.taunt_turns = 0
        self.acted = False
        self.alive = True
        self.power_mult = 1.0    # хохирол / эдгээлт / бамбайн үржвэр (level, item, давхрын хүч)
        self.level = 1

    @property
    def pos(self) -> Cell:
        return (self.x, self.y)

    @property
    def type(self):
        return UNIT_TYPES[self.kind]

    def copy(self) -> "Unit":
        u = Unit.__new__(Unit)
        u.uid, u.kind, u.side = self.uid, self.kind, self.side
        u.hp, u.max_hp, u.x, u.y, u.move = self.hp, self.max_hp, self.x, self.y, self.move
        u.cooldowns = dict(self.cooldowns)
        u.shield, u.cursed = self.shield, self.cursed
        u.taunted_by, u.taunt_turns = self.taunted_by, self.taunt_turns
        u.acted, u.alive = self.acted, self.alive
        u.power_mult, u.level = self.power_mult, self.level
        return u

    def to_dict(self) -> dict:
        return {s: getattr(self, s) for s in self.__slots__}

    @staticmethod
    def from_dict(d: dict) -> "Unit":
        u = Unit.__new__(Unit)
        for s in Unit.__slots__:
            setattr(u, s, d[s] if s in d else Unit._DEFAULTS[s])
        u.cooldowns = dict(d["cooldowns"])
        return u

    def __repr__(self):
        return f"Unit({self.uid} hp={self.hp}/{self.max_hp} @{self.pos}{'' if self.alive else ' DEAD'})"


class GameState:
    __slots__ = ("units", "walls", "side_to_act", "round", "winner", "obstacles")

    def __init__(self):
        self.units: dict[str, Unit] = {}
        self.walls: dict[Cell, int] = {}   # нүд -> үлдсэн ээлж
        self.obstacles: set = set()        # байнгын саад (чулуу, багана) — хөдөлгөөнийг хаана
        self.side_to_act = HEROES
        self.round = 1
        self.winner: Optional[str] = None  # HEROES | DEMONS | "draw" | None

    # ---- үүсгэх, хуулах ----
    @staticmethod
    def new_game(encounter: Optional[dict] = None) -> "GameState":
        """Эхлэх төлөв. encounter=None бол анхны тулаан (Demon Lord + 2 Imp).

        encounter = {"units": {uid: (kind, (x, y)), ...}, "obstacles": [(x, y), ...]}
        (engine/dungeon.py-ийн stage_encounter() үүсгэнэ).
        """
        s = GameState()
        units = START_POSITIONS if encounter is None else encounter["units"]
        for uid, (kind, pos) in units.items():
            s.units[uid] = Unit(uid, kind, tuple(pos))
        if encounter is not None:
            s.obstacles = {tuple(c) for c in encounter.get("obstacles", ())}
        return s

    def clone(self) -> "GameState":
        s = GameState.__new__(GameState)
        s.units = {k: u.copy() for k, u in self.units.items()}
        s.walls = dict(self.walls)
        s.obstacles = self.obstacles      # тулааны дунд өөрчлөгддөггүй тул хуваалцана
        s.side_to_act, s.round, s.winner = self.side_to_act, self.round, self.winner
        return s

    def to_dict(self) -> dict:
        return {"units": [u.to_dict() for u in self.units.values()],
                "walls": [[x, y, t] for (x, y), t in self.walls.items()],
                "obstacles": [[x, y] for x, y in sorted(self.obstacles)],
                "side_to_act": self.side_to_act, "round": self.round, "winner": self.winner}

    @staticmethod
    def from_dict(d: dict) -> "GameState":
        s = GameState()
        for ud in d["units"]:
            u = Unit.from_dict(ud)
            s.units[u.uid] = u
        s.walls = {(x, y): t for x, y, t in d["walls"]}
        s.obstacles = {(x, y) for x, y in d.get("obstacles", [])}
        s.side_to_act, s.round, s.winner = d["side_to_act"], d["round"], d["winner"]
        return s

    # ---- асуулга ----
    @property
    def is_over(self) -> bool:
        return self.winner is not None

    @property
    def boss(self) -> Optional[Unit]:
        """Давхрын босс (UnitType.boss) — анхны тулаанд Demon Lord. Жижиг мангасын үед None."""
        u = self.units.get("demon_lord")
        if u is not None:
            return u
        for u in self.units.values():
            if u.type.boss:
                return u
        return None

    @property
    def boss_enraged(self) -> bool:
        b = self.boss
        return b is not None and b.alive and b.hp < b.max_hp * ENRAGE_THRESHOLD

    def alive_units(self, side: Optional[str] = None):
        return [u for u in self.units.values() if u.alive and (side is None or u.side == side)]

    def unit_at(self, cell: Cell) -> Optional[Unit]:
        for u in self.units.values():
            if u.alive and u.x == cell[0] and u.y == cell[1]:
                return u
        return None

    def blocked_cells(self) -> set:
        """Дүр, мөсөн хана эсвэл саад байгаа нүднүүд."""
        b = {u.pos for u in self.units.values() if u.alive}
        b.update(self.walls.keys())
        b.update(self.obstacles)
        return b

    @staticmethod
    def in_bounds(cell: Cell) -> bool:
        return 0 <= cell[0] < BOARD_W and 0 <= cell[1] < BOARD_H

    def render(self) -> str:
        """Debug-д зориулсан текст зураг."""
        sym = {"knight": "K", "mage": "M", "healer": "H", "demon_lord": "D", "imp": "i"}
        grid = [["." for _ in range(BOARD_W)] for _ in range(BOARD_H)]
        for (x, y) in self.obstacles:
            grid[y][x] = "o"
        for (x, y) in self.walls:
            grid[y][x] = "#"
        for u in self.alive_units():
            grid[u.y][u.x] = sym.get(u.kind, "B" if u.type.boss else "e")
        lines = ["  " + " ".join(str(i) for i in range(BOARD_W))]
        lines += [f"{y} " + " ".join(row) for y, row in enumerate(grid)]
        lines.append(f"round {self.round}, {self.side_to_act} to act"
                     + (f", winner={self.winner}" if self.winner else ""))
        for u in self.alive_units():
            extra = []
            if u.shield: extra.append(f"shield {u.shield}")
            if u.cursed: extra.append(f"cursed {u.cursed}")
            if u.taunted_by: extra.append(f"taunted {u.taunt_turns}")
            lines.append(f"  {u.uid:<11} {u.hp:>3}/{u.max_hp:<3} {' '.join(extra)}")
        return "\n".join(lines)

    def __repr__(self):
        return self.render()


__all__ = ["Action", "END_TURN", "Unit", "GameState", "HEROES", "DEMONS"]
