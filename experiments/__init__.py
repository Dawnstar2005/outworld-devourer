"""Туршилтууд (pygame-гүй): 100 тулаан, A/B (суралцсан vs суралцаагүй босс), тэнцвэрийн хувилбар.

Ажиллуулах:  python -m experiments --games 100 --boss eval --out experiments/results
"""

from .runner import (BALANCE_VARIANTS, GameRow, balance_sweep, make_boss_factory,
                     patched_constants, run_ab, run_games, train_profiles)

__all__ = ["GameRow", "run_games", "run_ab", "train_profiles", "balance_sweep",
           "patched_constants", "BALANCE_VARIANTS", "make_boss_factory"]
