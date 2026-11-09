"""Туршилтын гүйцэтгэгч: bot баатрууд vs босс, олон тулаан, A/B, тэнцвэрийн хувилбар.

Бүх тулаан `bots.play_match`-аар (GameSession → engine) явагдана. Seed бүр тогтмол тул
дүн давтагдана. A/B-д хоёр бүлэг ИЖИЛ seed-үүдээр тоглодог (хос харьцуулалт).
"""

from __future__ import annotations

import contextlib
import dataclasses
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

from engine import constants as C

from bots import HERO_BOTS, play_match
from learning import GameLogger
from learning.profile import HERO_KINDS, profile_from_logs

BOT_NAMES = tuple(HERO_BOTS)


def make_boss_factory(kind: str = "eval", **kw) -> Callable:
    """(profile, seed) → боссын controller. kind: eval | mcts | placeholder.

    eval/mcts нь ai.BossAI шаардана (ai/ main-д ороогүй бол ModuleNotFoundError).
    """
    if kind == "placeholder":
        from game.boss_driver import PlaceholderBoss
        return lambda profile, seed: PlaceholderBoss(seed=seed)
    from ai import BossAI
    return lambda profile, seed: BossAI(profile=profile, mode=kind, seed=seed, **kw)


@dataclass
class GameRow:
    experiment: str
    variant: str
    group: str
    bot: str
    seed: int
    winner: Optional[str]
    rounds: int
    boss_hp: int
    heroes_alive: int
    first_dead: Optional[str]      # анх унасан баатар
    first_dead_round: Optional[int]
    top_priority: Optional[str]    # профайлын хамгийн өндөр priority-тэй баатар (A/B-д)
    seconds: float


def _first_death_hook():
    box = {"uid": None, "round": None}

    def hook(before, action, events):
        if box["uid"] is None:
            for ev in events:
                if ev.get("type") == "death" and ev.get("unit") in HERO_KINDS:
                    box["uid"], box["round"] = ev["unit"], before.round
                    break
    return box, hook


def run_games(n: int, make_boss: Callable, bots=BOT_NAMES, seed0: int = 0,
              profile_for: Optional[Callable] = None, experiment: str = "base",
              variant: str = "base", group: str = "-", progress=None) -> list:
    """n тулаан: i-р тулаанд bots[i % len], seed = seed0 + i."""
    rows = []
    for i in range(n):
        bot, seed = bots[i % len(bots)], seed0 + i
        profile = profile_for(bot) if profile_for else None
        top = None
        if profile:
            pr = profile.get("target_priority", {})
            top = max(pr, key=pr.get) if pr else None
        box, hook = _first_death_hook()
        r = play_match(HERO_BOTS[bot](seed=seed), make_boss(profile, seed), hooks=[hook])
        rows.append(GameRow(experiment, variant, group, bot, seed, r.winner, r.rounds, r.boss_hp,
                            r.heroes_alive, box["uid"], box["round"], top, round(r.seconds, 3)))
        if progress:
            progress(i + 1, n)
    return rows


def train_profiles(make_boss: Callable, bots=BOT_NAMES, games_per_bot: int = 5,
                   seed0: int = 1000) -> dict:
    """Bot бүрээр суралцаагүй боссын эсрэг тоглуулж log бичээд, тэр log-оос профайл гаргана."""
    profiles = {}
    with tempfile.TemporaryDirectory() as tmp:
        for b, bot in enumerate(bots):
            logger = GameLogger(f"{tmp}/{bot}")
            for k in range(games_per_bot):
                seed = seed0 + b * 100 + k
                play_match(HERO_BOTS[bot](seed=seed), make_boss(None, seed), logger=logger)
            profiles[bot] = profile_from_logs(f"{tmp}/{bot}")
    return profiles


def run_ab(n: int, make_boss: Callable, profiles: dict, bots=BOT_NAMES, seed0: int = 0,
           progress=None) -> list:
    """A — суралцсан (bot-ын профайлтай), B — суралцаагүй босс; ижил n seed."""
    a = run_games(n, make_boss, bots, seed0, profile_for=profiles.get, experiment="ab",
                  group="A", progress=progress)
    b = run_games(n, make_boss, bots, seed0, experiment="ab", group="B", progress=progress)
    for row_b, row_a in zip(b, a):   # B-д ч ижил «гол бай»-г тэмдэглэнэ (харьцуулахад)
        row_b.top_priority = row_a.top_priority
    return a + b


# --------------------------------------------------------------------------- тэнцвэрийн хувилбар

# (хүснэгт, түлхүүр, талбар, үйлдэл, утга) — ОДООГИЙН constants-аас харьцангуй тооцно
BALANCE_VARIANTS = {
    "base": [],
    "boss_hp_x0.8": [("unit", "demon_lord", "hp", "mul", 0.8)],
    "boss_hp_x0.7": [("unit", "demon_lord", "hp", "mul", 0.7)],
    "heroes_hp_x1.25": [("unit", k, "hp", "mul", 1.25) for k in HERO_KINDS],
    "dark_flame_x0.75": [("skill", "dark_flame", "power", "mul", 0.75)],
    "hellfire_cd+1": [("skill", "hellfire", "cooldown", "add", 1)],
    "boss_hp_x0.8+dark_flame_x0.75": [("unit", "demon_lord", "hp", "mul", 0.8),
                                      ("skill", "dark_flame", "power", "mul", 0.75)],
    # хүчтэй хослолууд — анхны туршилтаар зөөлөн хувилбарууд хангалтгүй (≤2%) гарсан тул
    "boss_hp_x0.7+dark_flame_x0.75+heroes_hp_x1.25":
        [("unit", "demon_lord", "hp", "mul", 0.7), ("skill", "dark_flame", "power", "mul", 0.75)]
        + [("unit", k, "hp", "mul", 1.25) for k in HERO_KINDS],
    "boss_hp_x0.6+dark_flame_x0.75+heroes_hp_x1.25":
        [("unit", "demon_lord", "hp", "mul", 0.6), ("skill", "dark_flame", "power", "mul", 0.75)]
        + [("unit", k, "hp", "mul", 1.25) for k in HERO_KINDS],
}


@contextlib.contextmanager
def patched_constants(changes: list):
    """engine.constants-ийн UNIT_TYPES / SKILLS-ийг ЗӨВХӨН энэ процесст түр өөрчилнө.

    constants.py файл өөрчлөгдөхгүй. Гарахад анхны утгыг сэргээнэ. Буцаах:
    {"demon_lord.hp": (400, 320), ...} — тайланд бичих.
    """
    tables = {"unit": C.UNIT_TYPES, "skill": C.SKILLS}
    saved, applied = [], {}
    try:
        for table, key, field, op, value in changes:
            d = tables[table]
            old = d[key]
            cur = getattr(old, field)
            new = round(cur * value) if op == "mul" else cur + value
            saved.append((d, key, old))
            d[key] = dataclasses.replace(old, **{field: new})
            applied[f"{key}.{field}"] = (cur, new)
        yield applied
    finally:
        for d, key, old in reversed(saved):
            d[key] = old


def balance_sweep(n: int, make_boss: Callable, variants: Optional[dict] = None,
                  bots=BOT_NAMES, seed0: int = 0, progress=None) -> tuple:
    """Хувилбар бүрт суралцаагүй боссын эсрэг n тулаан. (rows, {variant: applied})."""
    rows, applied = [], {}
    for name, changes in (variants or BALANCE_VARIANTS).items():
        with patched_constants(changes) as info:
            applied[name] = info
            rows += run_games(n, make_boss, bots, seed0, experiment="balance", variant=name,
                              progress=progress)
    return rows, applied
