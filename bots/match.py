"""Bot баатрууд vs босс — нэг тулааныг эхнээс нь дуустал тоглуулна (pygame-гүй).

Нүүдэл бүр GameSession.play()-ээр дамждаг тул тоглоомтой яг адилхан on_action hook
(log, статистик) ажиллана.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from engine import END_TURN, HEROES, GameState

from game.session import GameSession


@dataclass
class MatchResult:
    winner: str | None
    rounds: int
    boss_hp: int
    heroes_alive: int
    seconds: float
    actions: int = 0
    log_path: str | None = None
    extra: dict = field(default_factory=dict)


def play_match(hero_bot, boss, logger=None, state: GameState | None = None,
               max_actions: int = 5000, meta: dict | None = None, hooks=()) -> MatchResult:
    """`hero_bot.choose(state)` ба `boss.decide(state).actions`-аар нэг тулаан тоглуулна.

    hooks — нэмэлт on_action(state_before, action, events) функцууд (туршилтын хэмжилт).
    """
    session = GameSession(state=state or GameState.new_game(), human_side=HEROES)
    count = [0]
    session.add_hook(lambda *_: count.__setitem__(0, count[0] + 1))
    for hook in hooks:
        session.add_hook(hook)
    if logger is not None:
        session.add_hook(logger.on_action)
        logger.start(session.state, meta={"bot": getattr(hero_bot, "name", "?"), **(meta or {})})
    t0 = time.perf_counter()
    while not session.state.is_over and count[0] < max_actions:
        s = session.state
        if s.side_to_act == HEROES:
            session.play(hero_bot.choose(s))
            continue
        for a in boss.decide(s.clone()).actions:
            if session.state.is_over or session.state.side_to_act == HEROES:
                break
            session.play(a)
        if not session.state.is_over and session.state.side_to_act != HEROES:
            session.play(END_TURN)
    if logger is not None and logger.active:
        logger.close("max_actions")
    s = session.state
    boss_hp = s.boss.hp if s.boss is not None else sum(u.hp for u in s.alive_units() if u.side != HEROES)
    return MatchResult(winner=s.winner, rounds=s.round, boss_hp=boss_hp,
                       heroes_alive=len(s.alive_units(HEROES)),
                       seconds=time.perf_counter() - t0, actions=count[0],
                       log_path=str(logger.path) if logger is not None else None)
