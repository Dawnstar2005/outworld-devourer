"""Баатруудын ахиц: туршлага (XP), level, item-ийн нөлөө, олз (pygame-гүй).

Бүх тоо constants.py-д (LEVEL_XP, LEVEL_HP_GROWTH, LEVEL_POWER_GROWTH, ITEMS, ...).
Хадгалалт (save файл) энд биш — game/campaign.py-д.
"""

from __future__ import annotations

import random

from .constants import (BOSS_DROPS, BOSS_STAGE_XP, ITEM_DROP_CHANCE, ITEMS, LEVEL_HP_GROWTH,
                        LEVEL_POWER_GROWTH, LEVEL_XP, LOSS_XP_FRACTION, MAX_LEVEL,
                        RARE_DROP_CHANCE, STAGE_XP, UNIT_TYPES)


def level_for_xp(xp: int) -> int:
    level = 1
    for n, need in enumerate(LEVEL_XP, start=1):
        if xp >= need:
            level = n
    return min(level, MAX_LEVEL)


def level_progress(xp: int) -> tuple:
    """(одоогийн level, энэ level-ийн эхлэх XP, дараагийн level-ийн XP эсвэл None)."""
    level = level_for_xp(xp)
    start = LEVEL_XP[level - 1]
    nxt = LEVEL_XP[level] if level < MAX_LEVEL else None
    return level, start, nxt


def hero_stats(kind: str, level: int, items=()) -> dict:
    """Level ба item-ээс тооцсон баатрын үзүүлэлт."""
    base = UNIT_TYPES[kind]
    its = [ITEMS[i] for i in items if i in ITEMS]
    hp = base.hp * (1.0 + LEVEL_HP_GROWTH * (level - 1)) + sum(i.hp for i in its)
    power = 1.0 + LEVEL_POWER_GROWTH * (level - 1) + sum(i.power for i in its)
    move = base.move + sum(i.move for i in its)
    return {"max_hp": int(round(hp)), "power_mult": round(power, 4), "move": move,
            "level": level}


def stage_xp(floor: int, boss_stage: bool, won: bool) -> int:
    xp = (BOSS_STAGE_XP if boss_stage else STAGE_XP) * floor
    return xp if won else int(xp * LOSS_XP_FRACTION)


def roll_drop(floor: int, boss_stage: bool, rng: random.Random):
    """Үе давахад унах item-ийн id эсвэл None. Давхрын боссоос баталгаатай олз."""
    if boss_stage and floor in BOSS_DROPS:
        return BOSS_DROPS[floor]
    if rng.random() >= ITEM_DROP_CHANCE:
        return None
    rare = rng.random() < RARE_DROP_CHANCE
    pool = sorted(i.iid for i in ITEMS.values() if i.rarity == ("rare" if rare else "common"))
    return rng.choice(pool) if pool else None
