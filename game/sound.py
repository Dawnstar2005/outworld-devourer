"""Дууны эффект. apply()-ийн events → дууны нэр (pygame-гүй), тоглуулах нь pygame.mixer.

Audio төхөөрөмж байхгүй, эсвэл файл олдохгүй бол `SoundPlayer` чимээгүй ажиллана (тоглоом
зогсохгүй). M товч дуу асааж/унтраана. Файлын эх сурвалж: game/assets/CREDITS.md.
"""

from __future__ import annotations

from pathlib import Path

from engine import HEROES

SOUND_NAMES = ("step", "leap", "slash", "dark_flame", "blast", "death", "summon", "ice", "heal",
               "shield", "curse", "taunt", "select", "tick", "click", "back", "error", "win",
               "lose", "your_turn")
SOUND_FILES = {name: f"{name}.ogg" for name in SOUND_NAMES}

SKILL_SOUNDS = {
    "sword": "slash", "claw": "slash", "dark_flame": "dark_flame",
    "fireball": "blast", "hellfire": "blast",
    "curse": "curse", "taunt": "taunt", "ice_wall": "ice",
    "heal": "heal", "shield": "shield", "summon_imp": "summon",
    # dungeon-ий мангас, боссууд
    "acid": "slash", "slime_slam": "blast", "acid_spit": "dark_flame", "split": "summon",
    "stab": "slash", "cleave": "slash", "spear_throw": "slash", "call_goblins": "summon",
    "bite": "slash", "blood_drain": "dark_flame", "bat_swarm": "blast",
    "demon_claw": "slash", "hellblade": "slash", "fire_claw": "slash", "ember": "dark_flame",
}

DEFAULT_VOLUME = 0.6
DEFAULT_SFX_GAIN = 0.64       # тохиргооны анхны утга (ерөнхий 80% × эффект 80%) — VOLUMES-ийг хэвээр
VOLUMES = {"step": 0.35, "tick": 0.35, "select": 0.45, "click": 0.45, "back": 0.4,
           "your_turn": 0.45, "win": 0.7, "lose": 0.7}


def sounds_for_events(events: list, human_side: str = HEROES) -> list:
    """Нэг нүүдлийн events → тоглуулах дууны нэрс (давхардалгүй, дарааллаар)."""
    out = []
    for ev in events:
        t = ev.get("type")
        if t == "move":
            out.append("leap" if ev.get("leap") else "step")
        elif t == "skill":
            name = SKILL_SOUNDS.get(ev.get("skill"))
            if name:
                out.append(name)
        elif t == "death":
            out.append("death")
        elif t == "turn_start" and ev.get("side") == human_side:
            out.append("your_turn")
        elif t == "game_over":
            out.append("win" if ev.get("winner") == human_side else "lose")
    if "win" in out or "lose" in out:           # тоглолт дууссан бол ээлжийн дохио хэрэггүй
        out = [n for n in out if n != "your_turn"]
    return list(dict.fromkeys(out))


class SoundPlayer:
    def __init__(self, enabled: bool = True, folder: Path | None = None):
        self.muted = False
        self.ok = False
        self.gain = DEFAULT_SFX_GAIN
        self._sounds = {}
        if not enabled:
            return
        try:
            import pygame

            from .sprites import asset_dir
            folder = Path(folder) if folder else asset_dir() / "sounds"
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            for name, file in SOUND_FILES.items():
                snd = pygame.mixer.Sound(str(folder / file))
                snd.set_volume(self._volume(name))
                self._sounds[name] = snd
            self.ok = True
        except Exception:   # audio төхөөрөмжгүй (pygame.error), файл алга — чимээгүй үргэлжилнэ
            self._sounds = {}
            self.ok = False

    def _volume(self, name: str) -> float:
        return min(1.0, VOLUMES.get(name, DEFAULT_VOLUME) * self.gain / DEFAULT_SFX_GAIN)

    def set_gain(self, gain: float) -> None:
        """Тохиргооны «ерөнхий × эффект» түвшин (0–1)."""
        self.gain = max(0.0, min(1.0, gain))
        for name, snd in self._sounds.items():
            snd.set_volume(self._volume(name))

    def play(self, name: str) -> None:
        if self.ok and not self.muted and self.gain > 0:
            snd = self._sounds.get(name)
            if snd is not None:
                snd.play()

    def play_events(self, events: list, human_side: str = HEROES) -> None:
        for name in sounds_for_events(events, human_side):
            self.play(name)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted
