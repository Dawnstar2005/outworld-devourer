"""Dungeon кампанит ажлын ахиц ба байнгын хадгалалт (pygame-гүй).

Дүрэм, тоо бүгд engine-д (engine/dungeon.py, engine/progression.py, engine/constants.py) —
энд зөвхөн тоглогчийн ахицыг хадгалж, engine-ийн функцуудыг дуудна.

Хадгалах файл (JSON): Windows-д %APPDATA%/OutworldDevourer/save.json, бусад үед
~/.outworld_devourer/save.json. `OUTWORLD_SAVE` орчны хувьсагчаар өөр зам өгч болно
(тест, туршилт). Файл эвдэрсэн бол .bak болгон хадгалж, шинээр эхэлнэ.

    {"version": 1, "xp": 0,                     # багийн нийт XP (гурван баатар хамт ахина)
     "items": {"knight": [...], ...},           # баатар бүрийн зүүсэн item
     "bag": [...],                              # хуваарилаагүй олз
     "cleared": ["1-1", ...],                   # давсан үеүд
     "best_rounds": {"1-1": 6}, "wins": 0, "losses": 0}
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from engine import ITEMS
from engine.constants import MAX_ITEMS_PER_HERO
from engine.dungeon import FLOORS, HERO_UIDS, STAGES_PER_FLOOR, get_stage, new_stage_state
from engine.progression import hero_stats, level_for_xp, level_progress, roll_drop, stage_xp

SAVE_VERSION = 1
SAVE_ENV = "OUTWORLD_SAVE"
STAGE_KEYS = tuple(st.key for f in FLOORS for st in f.stages)
FINAL_STAGE = STAGE_KEYS[-1]


def default_save_path() -> Path:
    env = os.environ.get(SAVE_ENV)
    if env:
        return Path(env)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "OutworldDevourer" / "save.json"
    return Path.home() / ".outworld_devourer" / "save.json"


def parse_key(key: str) -> tuple:
    f, i = key.split("-")
    return int(f), int(i)


def fresh_data() -> dict:
    return {"version": SAVE_VERSION, "xp": 0, "items": {uid: [] for uid in HERO_UIDS},
            "bag": [], "cleared": [], "best_rounds": {}, "wins": 0, "losses": 0}


@dataclass
class Reward:
    """Нэг үеийн дараах шагнал — үр дүнгийн дэлгэцэд харуулна."""
    key: str
    won: bool
    xp_gained: int
    xp_before: int
    xp_after: int
    level_before: int
    level_after: int
    drop: Optional[str] = None           # item id (цүнхэнд орсон) эсвэл None
    first_clear: bool = False
    unlocked: Optional[str] = None       # шинээр нээгдсэн үеийн key
    campaign_complete: bool = False      # Demon Lord-ийг анх удаа ялсан
    assigned_to: Optional[str] = None    # олзыг зүүсэн баатар (дэлгэц дээр сонгосны дараа)

    @property
    def leveled_up(self) -> bool:
        return self.level_after > self.level_before


@dataclass
class Campaign:
    path: Optional[Path] = None
    rng: random.Random = field(default_factory=random.Random)
    autosave: bool = True
    data: dict = field(default_factory=fresh_data)
    load_error: Optional[str] = None

    @classmethod
    def load(cls, path=None, rng: Optional[random.Random] = None,
             autosave: bool = True) -> "Campaign":
        path = Path(path) if path is not None else default_save_path()
        c = cls(path=path, rng=rng or random.Random(), autosave=autosave)
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    c.data = _sanitize(json.load(f))
            except (OSError, ValueError, TypeError, AttributeError) as err:
                c.load_error = str(err)
                try:
                    os.replace(path, path.with_suffix(".bak"))
                except OSError:
                    pass
                c.data = fresh_data()
        return c

    # ------------------------------------------------------------------ хадгалах
    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)        # бичих үед унтарсан ч хуучин файл эвдрэхгүй
        except OSError as err:
            self.load_error = f"хадгалж чадсангүй: {err}"

    def _changed(self) -> None:
        if self.autosave:
            self.save()

    def reset(self) -> None:
        self.data = fresh_data()
        self._changed()

    # ------------------------------------------------------------------ ахиц
    @property
    def xp(self) -> int:
        return self.data["xp"]

    @property
    def level(self) -> int:
        return level_for_xp(self.xp)

    def progress(self) -> tuple:
        """(level, энэ level-ийн эхлэх XP, дараагийн level-ийн XP эсвэл None)."""
        return level_progress(self.xp)

    def items(self, hero: str) -> list:
        return list(self.data["items"].get(hero, []))

    @property
    def bag(self) -> list:
        return list(self.data["bag"])

    def hero_stats(self, level: Optional[int] = None) -> dict:
        lv = self.level if level is None else level
        return {uid: hero_stats(uid, lv, self.data["items"].get(uid, [])) for uid in HERO_UIDS}

    def is_cleared(self, key: str) -> bool:
        return key in self.data["cleared"]

    def is_unlocked(self, key: str) -> bool:
        if key not in STAGE_KEYS:
            return False
        f, i = parse_key(key)
        if (f, i) == (1, 1):
            return True
        prev = f"{f}-{i - 1}" if i > 1 else f"{f - 1}-{STAGES_PER_FLOOR}"
        return self.is_cleared(prev)

    def floor_unlocked(self, floor: int) -> bool:
        return self.is_unlocked(f"{floor}-1")

    def floor_cleared(self, floor: int) -> bool:
        return self.is_cleared(f"{floor}-{STAGES_PER_FLOOR}")

    @property
    def complete(self) -> bool:
        return self.is_cleared(FINAL_STAGE)

    def next_stage(self) -> str:
        """Дараагийн давах үе (бүгд давсан бол эцсийн үе)."""
        for key in STAGE_KEYS:
            if self.is_unlocked(key) and not self.is_cleared(key):
                return key
        return FINAL_STAGE

    def new_state(self, key: str):
        """Үеийн эхлэх GameState: баатрууд одоогийн level, item-тэй."""
        if not self.is_unlocked(key):
            raise ValueError(f"{key} үе хараахан нээгдээгүй")
        return new_stage_state(get_stage(*parse_key(key)), self.hero_stats())

    def finish_stage(self, key: str, won: bool, rounds: Optional[int] = None) -> Reward:
        """Үе дууссаны дараа: XP, level, олз (ялвал), нээгдэх үе. Хадгална."""
        f, i = parse_key(key)
        stage = get_stage(f, i)
        first = won and not self.is_cleared(key)
        xp_before, lv_before = self.xp, self.level
        gained = stage_xp(f, stage.is_boss, won)
        self.data["xp"] = xp_before + gained
        drop = unlocked = None
        if won:
            self.data["wins"] += 1
            # боссын баталгаатай олз зөвхөн анх ялахад; дахин тоглоход энгийн олз
            drop = roll_drop(f, stage.is_boss and first, self.rng)
            if drop is not None:
                self.data["bag"].append(drop)
            if first:
                self.data["cleared"].append(key)
                nxt = STAGE_KEYS.index(key) + 1
                if nxt < len(STAGE_KEYS):
                    unlocked = STAGE_KEYS[nxt]
            if rounds is not None:
                best = self.data["best_rounds"].get(key)
                if best is None or rounds < best:
                    self.data["best_rounds"][key] = rounds
        else:
            self.data["losses"] += 1
        self._changed()
        return Reward(key=key, won=won, xp_gained=gained, xp_before=xp_before,
                      xp_after=self.xp, level_before=lv_before, level_after=self.level,
                      drop=drop, first_clear=first, unlocked=unlocked,
                      campaign_complete=first and key == FINAL_STAGE)

    # ------------------------------------------------------------------ item
    def can_equip(self, hero: str) -> bool:
        return hero in HERO_UIDS and len(self.data["items"][hero]) < MAX_ITEMS_PER_HERO

    def equip(self, iid: str, hero: str) -> bool:
        """Цүнхнээс баатарт зүүлгэнэ. Амжилтгүй бол False (цүнхэнд байхгүй, слот дүүрсэн)."""
        if iid not in self.data["bag"] or not self.can_equip(hero):
            return False
        self.data["bag"].remove(iid)
        self.data["items"][hero].append(iid)
        self._changed()
        return True

    def unequip(self, hero: str, index: int) -> bool:
        """Баатрын item-ийг цүнх рүү буцаана."""
        items = self.data["items"].get(hero, [])
        if not 0 <= index < len(items):
            return False
        self.data["bag"].append(items.pop(index))
        self._changed()
        return True


def _sanitize(raw) -> dict:
    """Хуучин / гараар засварласан файлыг уншихдаа танихгүй утгыг хаяна."""
    if not isinstance(raw, dict):
        raise ValueError("save файл dict биш")
    d = fresh_data()
    d["xp"] = max(0, int(raw.get("xp", 0)))
    for uid in HERO_UIDS:
        its = [i for i in raw.get("items", {}).get(uid, []) if i in ITEMS]
        d["items"][uid] = its[:MAX_ITEMS_PER_HERO]
    d["bag"] = [i for i in raw.get("bag", []) if i in ITEMS]
    d["cleared"] = [k for k in STAGE_KEYS if k in set(raw.get("cleared", []))]
    d["best_rounds"] = {k: int(v) for k, v in raw.get("best_rounds", {}).items()
                        if k in STAGE_KEYS}
    d["wins"] = max(0, int(raw.get("wins", 0)))
    d["losses"] = max(0, int(raw.get("losses", 0)))
    return d
