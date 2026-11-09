"""Тоглоомын тохиргоо: дууны түвшин, дайсны хурд, самбар, бүтэн дэлгэц (pygame-гүй).

Хадгалах файл: ахицын файлын хажууд (%APPDATA%/OutworldDevourer/settings.json),
`OUTWORLD_SETTINGS` орчны хувьсагчаар өөр зам өгч болно. path=None бол файл бичихгүй (тест).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Optional

from .campaign import default_save_path

SETTINGS_ENV = "OUTWORLD_SETTINGS"
VOLUME_STEP = 10
ENEMY_SPEEDS = ("slow", "normal", "fast")
ENEMY_SPEED_NAMES = {"slow": "Удаан", "normal": "Хэвийн", "fast": "Хурдан"}
ENEMY_STEP_DELAY = {"slow": 0.8, "normal": 0.5, "fast": 0.2}   # дайсны нүүдэл хооронд (сек)


def default_settings_path() -> Path:
    env = os.environ.get(SETTINGS_ENV)
    if env:
        return Path(env)
    return default_save_path().parent / "settings.json"


def _volume(v) -> int:
    v = int(round(float(v) / VOLUME_STEP)) * VOLUME_STEP
    return max(0, min(100, v))


@dataclass
class Settings:
    master: int = 80              # ерөнхий дуу, 0–100
    music: int = 70               # хөгжим
    sfx: int = 80                 # дууны эффект
    enemy_speed: str = "normal"   # slow | normal | fast
    boss_panel: bool = True       # «Боссын бодол» самбар анхдагчаар нээлттэй эсэх
    fullscreen: bool = False
    path: Optional[Path] = field(default=None, repr=False, compare=False)

    VOLUME_KEYS = ("master", "music", "sfx")

    @classmethod
    def load(cls, path=None) -> "Settings":
        path = Path(path) if path is not None else default_settings_path()
        s = cls(path=path)
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                s.update(**{k: v for k, v in raw.items() if k in s.keys()})
        except (OSError, ValueError, TypeError):
            pass                  # байхгүй / эвдэрсэн файл → анхны утга
        return s

    @staticmethod
    def keys() -> tuple:
        return tuple(f.name for f in fields(Settings) if f.name != "path")

    def update(self, **values) -> None:
        """Утгыг шалгаж оноох (танихгүй, буруу утгыг үл тоомсорлоно)."""
        for k, v in values.items():
            try:
                if k in self.VOLUME_KEYS:
                    setattr(self, k, _volume(v))
                elif k == "enemy_speed" and v in ENEMY_SPEEDS:
                    self.enemy_speed = v
                elif k in ("boss_panel", "fullscreen") and isinstance(v, bool):
                    setattr(self, k, v)
            except (TypeError, ValueError):
                continue

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("path", None)
        return d

    def save(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def reset(self) -> None:
        for k, v in Settings().to_dict().items():
            setattr(self, k, v)

    # ---- тооцоолсон утга ----
    @property
    def music_gain(self) -> float:
        return self.master * self.music / 10000.0

    @property
    def sfx_gain(self) -> float:
        return self.master * self.sfx / 10000.0

    @property
    def enemy_step_delay(self) -> float:
        return ENEMY_STEP_DELAY[self.enemy_speed]
