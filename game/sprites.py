"""Sprite ачаалах (pygame). Файл олдохгүй бол None буцааж, дүрслэл өнгөт дөрвөлжин рүү буцна.

Pixel art тул томруулахдаа `pygame.transform.scale` (хамгийн ойрын пиксел) ашиглана.
PyInstaller-ээр .exe болгоход файлууд `sys._MEIPASS/game/assets`-д задарна.
"""

import sys
from pathlib import Path

import pygame


def asset_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "game" / "assets"
    return Path(__file__).resolve().parent / "assets"


UNIT_KINDS = ("knight", "mage", "healer", "demon_lord", "imp")


class Sprites:
    """Дүр, шал, хананы sprite. `ok` худал бол бүх get() None буцаана."""

    def __init__(self, unit_size: int, cell_size: int, folder: Path = None):
        self.folder = Path(folder) if folder else asset_dir() / "sprites"
        self.unit_size = unit_size
        self.cell_size = cell_size
        self._units = {}
        self._units_dim = {}
        self._floor = None
        self._wall = None
        try:
            for kind in UNIT_KINDS:
                img = self._load(kind, unit_size)
                self._units[kind] = img
                dim = img.copy()
                dim.fill((110, 110, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
                self._units_dim[kind] = dim
            self._floor = self._load("floor", cell_size)
            wall = self._load("wall", cell_size - 8)
            wall.fill((150, 215, 255, 255), special_flags=pygame.BLEND_RGBA_MULT)
            wall.fill((40, 60, 80, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._wall = wall
            self.ok = True
        except (pygame.error, FileNotFoundError, OSError):
            self._units, self._units_dim, self._floor, self._wall = {}, {}, None, None
            self.ok = False

    def _load(self, name: str, size: int) -> pygame.Surface:
        img = pygame.image.load(str(self.folder / f"{name}.png"))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        return pygame.transform.scale(img, (size, size))

    def unit(self, kind: str, dim: bool = False):
        return (self._units_dim if dim else self._units).get(kind)

    def floor(self, x: int, y: int):
        """Шалны tile. Чулуу, нүхтэй tile саад мэт харагддаг тул зөвхөн энгийн шал."""
        return self._floor

    @property
    def wall(self):
        return self._wall
