"""Sprite ачаалах (pygame). Файл олдохгүй бол None буцааж, дүрслэл өнгөт дөрвөлжин рүү буцна.

Pixel art тул томруулахдаа `pygame.transform.scale` (хамгийн ойрын пиксел) ашиглана.
PyInstaller-ээр .exe болгоход файлууд `sys._MEIPASS/game/assets`-д задарна.
"""

import json
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

    def __init__(self, unit_size: int, cell_size: int, folder: Path = None,
                 dungeon_folder: Path = None):
        self.dungeon = DungeonSprites(cell_size, dungeon_folder)
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

    def dungeon_unit(self, kind: str, dim: bool = False):
        """Шинэ 64 px Dungeon sprite; байхгүй бол хуучин (Tiny Dungeon) эсвэл None."""
        img = self.dungeon.unit(kind, dim)
        return img if img is not None else self.unit(kind, dim)

    def theme(self, name):
        return self.dungeon.theme(name)

    def floor(self, x: int, y: int):
        """Шалны tile. Чулуу, нүхтэй tile саад мэт харагддаг тул зөвхөн энгийн шал."""
        return self._floor

    @property
    def wall(self):
        return self._wall


# ---- Dungeon Crawl (CC0, 32×32) sprite-ууд ----
DIM_MULT = (110, 110, 120, 255)


def _load_img(path: Path, size: int):
    """PNG-г ачаалж `size`-д pixel-art маягаар томруулна. Алдаа гарвал None."""
    try:
        img = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            img = img.convert_alpha()
        return pygame.transform.scale(img, (size, size))
    except (pygame.error, FileNotFoundError, OSError):
        return None


def tint_green(img: pygame.Surface) -> pygame.Surface:
    """Цэнхэр желе → ногоон слайм: G ба B сувгийг сольж ногоон болгоно."""
    out = img.copy()
    w, h = out.get_size()
    for x in range(w):
        for y in range(h):
            r, g, b, a = out.get_at((x, y))
            if a:
                out.set_at((x, y), (int(r * 0.8), min(255, int(b * 0.95) + 10), int(g * 0.7), a))
    return out


class ThemeTiles:
    """Нэг давхрын сэдвийн tile-ууд (cell хэмжээтэй). Дутуу файл → тухайн талбар хоосон."""

    def __init__(self, floors, wall, obstacles, torch):
        self.floors = floors          # list[Surface] (floor_0, floor_1 ...)
        self.wall = wall              # Surface | None
        self.obstacles = obstacles    # list[Surface]
        self.torch = torch            # Surface | None

    @property
    def ok(self) -> bool:
        return bool(self.floors)


class DungeonSprites:
    """manifest.json-оос ачаалсан 64 px дүр + сэдвийн tile. Бүх зүйл заавал биш."""

    def __init__(self, cell_size: int, folder: Path = None):
        self.folder = Path(folder) if folder else asset_dir() / "dungeon"
        self.cell_size = cell_size
        self.units = {}
        self.units_dim = {}
        self.themes = {}
        self.ok = False
        try:
            with open(self.folder / "manifest.json", encoding="utf-8") as f:
                man = json.load(f)
        except (OSError, ValueError):
            return
        tile = int(man.get("tile_size", 32))
        for kind, rel in man.get("units", {}).items():
            img = _load_img(self.folder / rel, tile * 2)
            if img is None:
                continue
            if kind == "slime":
                img = tint_green(img)
            self.units[kind] = img
            dim = img.copy()
            dim.fill(DIM_MULT, special_flags=pygame.BLEND_RGBA_MULT)
            self.units_dim[kind] = dim
        for name, t in man.get("themes", {}).items():
            floors = [i for i in (_load_img(self.folder / r, cell_size)
                                  for r in t.get("floor", ())) if i is not None]
            wall = _load_img(self.folder / t["wall"], cell_size) if t.get("wall") else None
            obst = [i for i in (_load_img(self.folder / r, cell_size)
                                for r in t.get("obstacles", ())) if i is not None]
            torch = _load_img(self.folder / t["torch"], cell_size) if t.get("torch") else None
            self.themes[name] = ThemeTiles(floors, wall, obst, torch)
        self.ok = bool(self.units or self.themes)

    def unit(self, kind: str, dim: bool = False):
        return (self.units_dim if dim else self.units).get(kind)

    def theme(self, name):
        t = self.themes.get(name) if name else None
        return t if t is not None and t.ok else None
