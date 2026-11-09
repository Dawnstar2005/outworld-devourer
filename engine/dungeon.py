"""Dungeon-ий агуулга: 5 давхар × 4 үе (pygame-гүй).

Давхар бүр өөрийн сэдэв (theme), жижиг мангас, босстой (PM-ийн дизайн, 2026-11-09):
  1. Нялцгай гуу        — slime,            босс Slime King
  2. Гоблины агуй       — goblin,           босс Goblin King
  3. Цус соруулын ордон — low_vampire,      босс Vampire Lord
  4. Чөтгөрийн легион   — demon, imp,       босс Legion Commander
  5. Тамд бүтсэн        — hell_demon, imp,  эцсийн босс Demon Lord (анхны тулаан, суралцдаг AI)
1–3-р үе: 3 жижиг мангас. 4-р үе: давхрын босс + 2 дагуул.

Энд зөвхөн байрлал, бүрэлдэхүүн байна. HP, хохирол, давхрын хүч зэрэг тоо constants.py-д.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import FLOOR_ENEMY_SCALE, START_POSITIONS, UNIT_TYPES
from .state import GameState

STAGES_PER_FLOOR = 4
HERO_UIDS = ("knight", "mage", "healer")
HERO_START = {uid: START_POSITIONS[uid] for uid in HERO_UIDS}


@dataclass(frozen=True)
class Stage:
    floor: int
    index: int            # 1..STAGES_PER_FLOOR
    enemies: tuple        # ((uid, kind, (x, y)), ...)
    obstacles: tuple = ()  # ((x, y), ...)

    @property
    def key(self) -> str:
        return f"{self.floor}-{self.index}"

    @property
    def is_boss(self) -> bool:
        return self.index == STAGES_PER_FLOOR


@dataclass(frozen=True)
class Floor:
    index: int
    name: str
    theme: str            # slime | goblin | vampire | demon | hell (дүрслэлд)
    boss: str             # боссын төрөл
    mobs: tuple           # жижиг мангасын төрлүүд
    stages: tuple


def _mobs(kind: str, cells, start: int = 1) -> tuple:
    return tuple((f"{kind}{i}", kind, c) for i, c in enumerate(cells, start))


FLOORS = (
    Floor(1, "Нялцгай гуу", "slime", "slime_king", ("slime",), (
        Stage(1, 1, _mobs("slime", [(2, 1), (4, 1), (6, 1)]), ((1, 4), (6, 4))),
        Stage(1, 2, _mobs("slime", [(1, 1), (4, 0), (6, 2)]), ((0, 3), (3, 3), (7, 4))),
        Stage(1, 3, _mobs("slime", [(2, 2), (3, 0), (5, 1)]), ((2, 4), (5, 4), (6, 3))),
        Stage(1, 4, (("slime_king", "slime_king", (4, 1)),) + _mobs("slime", [(2, 1), (6, 1)]),
              ((1, 3), (6, 3))),
    )),
    Floor(2, "Гоблины агуй", "goblin", "goblin_king", ("goblin",), (
        Stage(2, 1, _mobs("goblin", [(1, 1), (4, 1), (6, 1)]), ((2, 3), (5, 3))),
        Stage(2, 2, _mobs("goblin", [(2, 0), (5, 0), (4, 2)]), ((0, 4), (3, 4), (7, 3))),
        Stage(2, 3, _mobs("goblin", [(1, 2), (3, 1), (6, 2)]), ((2, 4), (5, 4), (4, 3))),
        Stage(2, 4, (("goblin_king", "goblin_king", (4, 1)),) + _mobs("goblin", [(3, 1), (5, 1)]),
              ((2, 3), (5, 3), (0, 2), (7, 2))),
    )),
    Floor(3, "Цус соруулын ордон", "vampire", "vampire_lord", ("low_vampire",), (
        Stage(3, 1, _mobs("low_vampire", [(2, 1), (5, 1), (3, 0)]), ((1, 3), (6, 3))),
        Stage(3, 2, _mobs("low_vampire", [(1, 0), (4, 1), (7, 1)]), ((2, 3), (4, 4), (6, 3))),
        Stage(3, 3, _mobs("low_vampire", [(2, 2), (5, 2), (4, 0)]), ((1, 4), (3, 3), (6, 4))),
        Stage(3, 4, (("vampire_lord", "vampire_lord", (4, 0)),)
              + _mobs("low_vampire", [(2, 1), (6, 1)]), ((3, 3), (4, 3), (1, 2), (6, 2))),
    )),
    Floor(4, "Чөтгөрийн легион", "demon", "legion_commander", ("demon", "imp"), (
        Stage(4, 1, _mobs("demon", [(2, 1), (5, 1)]) + _mobs("imp", [(4, 0)]), ((1, 3), (6, 3))),
        Stage(4, 2, _mobs("demon", [(3, 1)]) + _mobs("imp", [(1, 0), (6, 0)]),
              ((2, 4), (5, 4), (4, 2))),
        Stage(4, 3, _mobs("demon", [(1, 1), (4, 0), (6, 1)]), ((3, 3), (2, 2), (5, 3))),
        Stage(4, 4, (("legion_commander", "legion_commander", (4, 1)),)
              + _mobs("imp", [(2, 1), (6, 1)]), ((1, 3), (3, 3), (6, 3))),
    )),
    Floor(5, "Тамд бүтсэн", "hell", "demon_lord", ("hell_demon", "imp"), (
        Stage(5, 1, _mobs("hell_demon", [(2, 1), (5, 1)]) + _mobs("imp", [(4, 0)]),
              ((1, 4), (6, 4))),
        Stage(5, 2, _mobs("hell_demon", [(1, 1), (4, 1), (6, 0)]), ((3, 3), (5, 3), (0, 4))),
        Stage(5, 3, _mobs("hell_demon", [(3, 0), (5, 2)]) + _mobs("imp", [(1, 1)]),
              ((2, 4), (4, 4), (6, 3))),
        # Эцсийн тулаан — анхны тулаантай ижил бүрэлдэхүүн (BossAI энэ дээр тааруулагдсан)
        Stage(5, 4, (("demon_lord", "demon_lord", (4, 1)),) + _mobs("imp", [(2, 1), (6, 1)])),
    )),
)


def get_stage(floor: int, index: int) -> Stage:
    return FLOORS[floor - 1].stages[index - 1]


def stage_encounter(stage: Stage) -> dict:
    """GameState.new_game(encounter)-д өгөх dict."""
    units = dict(HERO_START)
    for uid, kind, pos in stage.enemies:
        units[uid] = (kind, pos)
    return {"units": units, "obstacles": list(stage.obstacles)}


def new_stage_state(stage: Stage, hero_stats: Optional[dict] = None) -> GameState:
    """Үеийн эхлэх төлөв: дайснуудад давхрын хүч (FLOOR_ENEMY_SCALE), баатруудад ахиц.

    hero_stats = {uid: {"max_hp": int, "power_mult": float, "move": int, "level": int}}
    (engine/progression.py-ийн hero_stats()).
    """
    s = GameState.new_game(stage_encounter(stage))
    hp_mult, power_mult = FLOOR_ENEMY_SCALE.get(stage.floor, (1.0, 1.0))
    for uid, _, _ in stage.enemies:
        u = s.units[uid]
        u.max_hp = u.hp = int(round(UNIT_TYPES[u.kind].hp * hp_mult))
        u.power_mult = power_mult
        u.level = stage.floor
    for uid, st in (hero_stats or {}).items():
        u = s.units.get(uid)
        if u is None:
            continue
        u.max_hp = u.hp = int(st["max_hp"])
        u.power_mult = float(st["power_mult"])
        u.move = int(st["move"])
        u.level = int(st.get("level", 1))
    return s
