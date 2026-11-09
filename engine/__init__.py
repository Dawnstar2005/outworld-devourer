"""Outworld Devourer — тоглоомын дүрмийн цөм (pygame-гүй).

Хэрэглээ:
    from engine import GameState, legal_actions, apply
    s = GameState.new_game()
    acts = legal_actions(s)
    events = apply(s, acts[0], validate=True)
"""
from .constants import DEMONS, HEROES, SKILLS, UNIT_TYPES
from .rules import (apply, area_cells, dist, is_legal, legal_actions, next_state,
                    reachable, unit_actions, wall_cells)
from .state import END_TURN, Action, GameState, Unit

__all__ = ["GameState", "Unit", "Action", "END_TURN", "HEROES", "DEMONS", "SKILLS",
           "UNIT_TYPES", "apply", "next_state", "legal_actions", "unit_actions",
           "is_legal", "reachable", "dist", "area_cells", "wall_cells"]
