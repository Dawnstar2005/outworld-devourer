"""Арын хөгжим (pygame.mixer.music, stream): эхлэл — "intro", цэс — "title",
тулаан — "battle", үр дүн — "result".

Дэлгэц солигдоход хуучин хөгжмийг зөөлөн намсгаад (fade out) шинийг эхлүүлнэ — үндсэн
давталтыг хүлээлгэхгүйн тулд `update(dt)` дотор кадр бүрт бага багаар хийнэ.
Файл олдохгүй эсвэл audio төхөөрөмжгүй бол чимээгүй үргэлжилнэ. Эх сурвалж: assets/CREDITS.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

MUSIC_TRACKS = {"intro": "intro.mp3", "title": "title.mp3", "battle": "battle.mp3",
                "result": "result.ogg"}
MUSIC_VOLUME = 0.45
DEFAULT_MUSIC_GAIN = 0.56     # тохиргооны анхны утга (ерөнхий 80% × хөгжим 70%) → MUSIC_VOLUME
FADE_OUT = 0.8          # сек
FADE_IN_MS = 1500


class MusicPlayer:
    def __init__(self, enabled: bool = True, folder: Path | None = None):
        self.ok = False
        self.muted = False
        self.current: Optional[str] = None   # одоо тоглож буй (эсвэл файлгүй тул чимээгүй) зам
        self.target: Optional[str] = None    # тоглох ёстой зам
        self.gain = DEFAULT_MUSIC_GAIN
        self._fade = 0.0
        self._mixer = None
        if not enabled:
            return
        try:
            import pygame

            from .sprites import asset_dir
            self.folder = Path(folder) if folder else asset_dir() / "music"
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._mixer = pygame.mixer
            self.ok = True
        except Exception:   # audio төхөөрөмжгүй
            self.ok = False

    def available(self, track: str) -> bool:
        return self.ok and (self.folder / MUSIC_TRACKS[track]).is_file()

    def play(self, track: Optional[str]) -> None:
        """Тоглох замыг заана (None — хөгжимгүй). Бодит солилт update()-д явагдана."""
        self.target = track

    def _volume(self) -> float:
        if self.muted:
            return 0.0
        return min(1.0, MUSIC_VOLUME * self.gain / DEFAULT_MUSIC_GAIN)

    def set_gain(self, gain: float) -> None:
        """Тохиргооны «ерөнхий × хөгжим» түвшин (0–1), шууд хэрэгжинэ."""
        self.gain = max(0.0, min(1.0, gain))
        if self.ok and self._fade == 0.0:
            self._mixer.music.set_volume(self._volume())

    def set_muted(self, muted: bool) -> None:
        self.muted = muted
        if self.ok:
            self._mixer.music.set_volume(self._volume())

    def update(self, dt: float) -> None:
        if not self.ok or self.target == self.current:
            return
        music = self._mixer.music
        if self.current is not None and music.get_busy():
            self._fade += dt
            if self._fade < FADE_OUT:
                music.set_volume(self._volume() * (1 - self._fade / FADE_OUT))
                return
            music.stop()
        self._fade = 0.0
        self.current = self.target
        if self.target is None or not self.available(self.target):
            return
        try:
            music.load(str(self.folder / MUSIC_TRACKS[self.target]))
            music.set_volume(self._volume())
            music.play(loops=-1, fade_ms=FADE_IN_MS)
        except Exception:   # эвдэрсэн файл — хөгжимгүй үргэлжилнэ
            pass
