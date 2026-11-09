"""Скриптэй bot тоглогчид, тулаан тоглуулагч (pygame-гүй).

    from bots import HERO_BOTS, play_match
    from game.boss_driver import PlaceholderBoss
    result = play_match(HERO_BOTS["healer_reliant"](seed=1), PlaceholderBoss(seed=1))

Bot бүр engine-ийн хууль ёсны нүүдлээс (legal_actions) сонгоно — дүрэм давтаж бичихгүй.
"""

from .heroes import (HERO_BOTS, AggressiveBot, CautiousBot, GreedyBot, HealerReliantBot,
                     HeroBot, MageReliantBot, RandomBot)
from .match import MatchResult, play_match

__all__ = ["HERO_BOTS", "HeroBot", "RandomBot", "GreedyBot", "HealerReliantBot",
           "MageReliantBot", "AggressiveBot", "CautiousBot", "MatchResult", "play_match"]
