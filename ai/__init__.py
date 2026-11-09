"""Боссын AI. Хэрэглээ:

    from ai import BossAI
    boss = BossAI(profile=None)          # profile: DQ-ийн зуршлын профайл
    decision, events = boss.play_turn(state)   # боссын ээлжинд
    decision.to_panel()                  # «Боссын бодол» самбарын өгөгдөл
"""
from .boss import BossAI, Decision, Option, action_label
from .evaluate import DEFAULT_PRIORITY, evaluate

__all__ = ["BossAI", "Decision", "Option", "action_label", "evaluate", "DEFAULT_PRIORITY"]
