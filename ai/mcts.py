"""MCTS — «би ингэвэл тоглогч юу хийх вэ» гэж 2–3 ээлж урагш тооцоолох (WBS 3.2).

Мод нь ЭЭЛЖИЙН түвшинд байна: зангилаа бүр нэг талын ээлжийн эхлэл, ирмэг бүр
тухайн талын бүтэн ээлжийн төлөвлөгөө (дүр бүрийн Action-ууд).

* Үндэс (root) — боссын шилдэг 5 төлөвлөгөө (нөхцөл үнэлэх функцээс). Шинээр нэмэхгүй.
* Бусад зангилаа — progressive widening: зочилсон тоо өсөх тусам шинэ төлөвлөгөө
  түүвэрлэж нэмнэ (боломжит нүүдэл хэт олон тул бүгдийг дэлгэх боломжгүй).
* Сонголт — UCB1. Боссын зангилаанд оноог ихэсгэнэ, баатрын зангилаанд багасгана.
* Rollout — `lookahead` ээлж хүртэл түүвэрлэсэн төлөвлөгөөгөөр үргэлжлүүлж,
  төгсгөлийн төлөвийг `evaluate()`-ээр үнэлнэ.

Тоглогчийн загвар (opponent model): баатрын нүүдлийг default-оор «ихэвчлэн шунахай»
гэж таамаглана. DQ-ийн таамаглагчийг `predictor` болгон өгвөл түүний магадлалаар
түүвэрлэнэ:
    predictor(state, unit_uid, actions) -> магадлалын жагсаалт (len == len(actions))
Босс тоглогчийн ЖИНХЭНЭ нүүдлийг харахгүй — зөвхөн таамаглана.
"""

from __future__ import annotations

import math
import random
import time

from engine import DEMONS, END_TURN, HEROES, Action, GameState, apply, next_state
from engine.rules import leap_cells, reachable, skill_options

# Дүрүүдийн нүүх дараалал (түүвэрлэлтэд)
ORDER = {"knight": 0, "mage": 1, "healer": 2, "demon_lord": 0, "imp1": 1, "imp2": 2}


class Node:
    __slots__ = ("state", "children", "visits", "value")

    def __init__(self, state: GameState):
        self.state = state
        self.children = []   # [(plan, Node)]
        self.visits = 0
        self.value = 0.0     # боссын талын онооны нийлбэр

    @property
    def mean(self) -> float:
        return self.value / self.visits if self.visits else 0.0


def finish_turn(state: GameState, plan: list) -> GameState:
    """state-ийн хуулбар дээр plan-ыг хийж, ээлжийг дуусгана."""
    s = state.clone()
    side = s.side_to_act
    for a in plan:
        if s.is_over or s.side_to_act != side:
            break
        apply(s, a)
    if not s.is_over and s.side_to_act == side:
        apply(s, END_TURN)
    return s


class MCTSPlanner:
    def __init__(self, evaluate, rng: random.Random, lookahead: int = 3,
                 time_limit: float = 1.5, max_iters: int | None = None,
                 c_explore: float = 0.4, widen_c: float = 1.0, widen_alpha: float = 0.5,
                 dest_samples: int = 6, greedy_p: float = 0.75, predictor=None):
        self.evaluate = evaluate          # state -> боссын талын 0..1
        self.rng = rng
        self.lookahead = lookahead        # үндсээс хойш хэдэн ээлж тооцоолох
        self.time_limit = time_limit
        self.max_iters = max_iters
        self.c = c_explore
        self.widen_c = widen_c
        self.widen_alpha = widen_alpha
        self.dest_samples = dest_samples
        self.greedy_p = greedy_p
        self.predictor = predictor
        self.iterations = 0

    # ------------------------------------------------------------------ гол функц
    def search(self, state: GameState, root_plans: list) -> list:
        """root_plans — боссын нэр дэвшигч төлөвлөгөөнүүд.

        [(plan, visits, mean)] буцаана — зочилсон тоогоор эрэмбэлсэн.
        """
        root = Node(state)
        for plan in root_plans:
            root.children.append((plan, Node(finish_turn(state, plan))))
        t_end = time.perf_counter() + self.time_limit
        self.iterations = 0
        while True:
            if self.max_iters is not None and self.iterations >= self.max_iters:
                break
            if self.max_iters is None and time.perf_counter() >= t_end:
                break
            self._iterate(root)
            self.iterations += 1
        out = [(plan, n.visits, n.mean) for plan, n in root.children]
        out.sort(key=lambda t: (t[1], t[2]), reverse=True)
        return out

    def _iterate(self, root: Node):
        path = [root]
        node = self._select(root)
        path.append(node)
        depth = 1
        while depth < self.lookahead and not node.state.is_over:
            limit = max(1, math.ceil(self.widen_c * (node.visits ** self.widen_alpha)))
            if len(node.children) < limit:
                plan = self.sample_turn(node.state)
                child = Node(finish_turn(node.state, plan))
                node.children.append((plan, child))
                path.append(child)
                node = child
                depth += 1
                break
            node = self._select(node)
            path.append(node)
            depth += 1
        value = self._rollout(node.state, self.lookahead - depth)
        for n in path:
            n.visits += 1
            n.value += value

    def _select(self, node: Node) -> Node:
        boss_turn = node.state.side_to_act == DEMONS
        log_n = math.log(node.visits + 1)
        best, best_u = None, -1e9
        for _, ch in node.children:
            if ch.visits == 0:
                return ch
            m = ch.mean if boss_turn else 1.0 - ch.mean
            u = m + self.c * math.sqrt(log_n / ch.visits)
            if u > best_u:
                best, best_u = ch, u
        return best

    def _rollout(self, state: GameState, turns: int) -> float:
        s = state
        for _ in range(turns):
            if s.is_over:
                break
            s = finish_turn(s, self.sample_turn(s))
        return self.evaluate(s)

    # ------------------------------------------------------------------ түүвэрлэлт
    def sample_turn(self, state: GameState) -> list:
        """Одоогийн талын бүтэн ээлжийн төлөвлөгөө түүвэрлэнэ."""
        s = state.clone()
        side = s.side_to_act
        plan = []
        for u in sorted(s.alive_units(side), key=lambda u: ORDER.get(u.uid, 9)):
            if s.is_over or s.side_to_act != side:
                break
            if u.acted or not u.alive:
                continue
            a = self.sample_unit_action(s, u)
            plan.append(a)
            apply(s, a)
        return plan

    def sample_unit_action(self, s: GameState, u) -> Action:
        blocked = s.blocked_cells()
        moves = [(c, False) for c in reachable(s, u, blocked)]
        walk = {c for c, _ in moves}
        moves += [(c, True) for c in leap_cells(s, u, blocked, exclude=walk)]
        if len(moves) > self.dest_samples:
            keep = [(u.pos, False)]   # байрандаа үлдэх сонголт үргэлж байна
            keep += self.rng.sample(moves, self.dest_samples - 1)
            moves = keep
        cands = []
        for dest, leap in moves:
            after = (blocked - {u.pos}) | {dest}
            cands.append(Action(u.uid, dest, leap=leap))
            for sid, tgt, tuid, var in skill_options(s, u, dest, after):
                cands.append(Action(u.uid, dest, sid, tgt, tuid, var, leap))

        if u.side == HEROES and self.predictor is not None:
            probs = self.predictor(s, u.uid, cands)
            if probs and len(probs) == len(cands) and sum(probs) > 0:
                return self.rng.choices(cands, weights=probs, k=1)[0]

        if self.rng.random() > self.greedy_p:
            return self.rng.choice(cands)
        sign = 1.0 if u.side == DEMONS else -1.0
        return max(cands, key=lambda a: sign * self.evaluate(next_state(s, a)))
