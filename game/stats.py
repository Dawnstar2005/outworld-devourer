"""Тоглолтын статистик — үр дүнгийн дэлгэцэд (pygame-гүй).

`on_action` hook-оор events-ийг сонсож, дүр бүрийн өгсөн хохирол, эдгээлт, алсан тоог
тоолно. DQ-ийн log-той адил hook ашигладаг тул дүрмийг дахин тооцоолохгүй.

    stats = MatchStats()
    session.add_hook(stats.on_action)
"""

from __future__ import annotations

from collections import Counter

from engine import HEROES


class MatchStats:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.damage = Counter()     # uid -> өгсөн хохирол (engine-ийн amount: бамбайд шингэсэн орохгүй)
        self.heal = Counter()       # uid -> эдгээсэн HP
        self.kills = Counter()      # uid -> алсан дүрийн тоо
        self.deaths = Counter()     # uid -> унасан тоо (Imp дахин дуудагдаж болно)
        self.skills = Counter()     # uid -> ур чадвар хэрэглэсэн тоо
        self.winner = None
        self.rounds = 0

    def on_action(self, state_before, action, events) -> None:
        last_hit = {}
        for ev in events:
            t = ev["type"]
            if t == "damage":
                self.damage[ev["src"]] += ev["amount"]
                last_hit[ev["dst"]] = ev["src"]
            elif t == "heal":
                self.heal[ev["src"]] += ev["amount"]
            elif t == "death":
                self.deaths[ev["unit"]] += 1
                killer = last_hit.get(ev["unit"])
                if killer is not None:
                    self.kills[killer] += 1
            elif t == "skill":
                self.skills[ev["unit"]] += 1
            elif t == "game_over":
                self.winner = ev["winner"]
                self.rounds = ev["round"]

    def rows(self, state) -> list:
        """Дүр бүрийн мөр: баатрууд эхэлж, дараа нь чөтгөрүүд."""
        units = sorted(state.units.values(), key=lambda u: (u.side != HEROES,))
        return [{"uid": u.uid, "side": u.side, "alive": u.alive, "hp": u.hp, "max_hp": u.max_hp,
                 "damage": self.damage[u.uid], "heal": self.heal[u.uid],
                 "kills": self.kills[u.uid], "deaths": self.deaths[u.uid]}
                for u in units]

    def mvp(self, side: str, state):
        """Тухайн талын хамгийн их хувь нэмэр оруулсан дүр: хохирол + эдгээлт, тэнцвэл алсан тоо."""
        scored = [((self.damage[u.uid] + self.heal[u.uid], self.kills[u.uid]), u.uid)
                  for u in state.units.values() if u.side == side]
        scored = [x for x in scored if x[0] > (0, 0)]
        return max(scored)[1] if scored else None
