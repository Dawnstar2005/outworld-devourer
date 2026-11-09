"""Дараагийн нүүдэл таамаглагчийн нарийвчлал ба хурд (DQ, PDF-ийн шаардлага 4).

* Bot бүр: `games_per_bot` тулааны log → эхний 70%-иар сургаж, үлдсэн 30%-иар top-1/top-3.
  Харьцуулалт: санамсаргүй таавар, сургаагүй (зөвхөн heuristic) загвар.
* Бүх bot нийлсэн нэг загвар (70/30).
* Хүний log байвал: тоглолт тус бүрийг ээлжлэн тест болгож (leave-one-game-out) хэмжинэ.
* Хурд: MCTS-ийн rollout-ийнх шиг 6 нүдний түүвэр дээр `predict()`-ийн хугацаа.
"""

from __future__ import annotations

import random
import statistics
import tempfile
import time
from typing import Callable, Optional

from engine import unit_actions

from bots import HERO_BOTS, play_match
from learning import GameLogger, iter_logs
from learning.predictor import MovePredictor, evaluate_accuracy

from .runner import BOT_NAMES


def _row(group: str, train_games: int, test_games: int, acc: dict, base: dict,
         samples: int) -> dict:
    return {"group": group, "train_games": train_games, "test_games": test_games,
            "decisions": acc["n"], "classes": acc["classes"],
            "chance1": acc["chance1"], "chance3": acc["chance3"],
            "heur1": base["top1"], "heur3": base["top3"],
            "top1": acc["top1"], "top3": acc["top3"], "samples": samples}


def bot_logs(make_boss: Callable, bots=BOT_NAMES, games_per_bot: int = 30,
             seed0: int = 5000) -> dict:
    """{bot: [records, ...]} — bot бүрээр суралцаагүй боссын эсрэг тоглуулсан log."""
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for b, bot in enumerate(bots):
            logger = GameLogger(f"{tmp}/{bot}")
            for k in range(games_per_bot):
                seed = seed0 + b * 1000 + k
                play_match(HERO_BOTS[bot](seed=seed), make_boss(None, seed), logger=logger)
            out[bot] = [records for _, records in iter_logs(f"{tmp}/{bot}")]
    return out


def split_eval(games_by_bot: dict, train_frac: float = 0.7) -> list:
    rows, train_all, test_all = [], [], []
    for bot, games in games_by_bot.items():
        cut = max(1, int(len(games) * train_frac))
        train, test = games[:cut], games[cut:]
        train_all += train
        test_all += test
        model = MovePredictor().fit(train)
        rows.append(_row(bot, len(train), len(test), evaluate_accuracy(model, test),
                         evaluate_accuracy(MovePredictor(), test), model.n_samples))
    model = MovePredictor().fit(train_all)
    rows.append(_row("all_bots", len(train_all), len(test_all),
                     evaluate_accuracy(model, test_all),
                     evaluate_accuracy(MovePredictor(), test_all), model.n_samples))
    return rows


def human_eval(folder) -> Optional[dict]:
    """Хүний log-оор leave-one-game-out. 2-оос цөөн тоглолттой бол None."""
    games = [records for _, records in iter_logs(folder)
             if sum(r.get("actor") == "human" for r in records) >= 5]
    if len(games) < 2:
        return None
    tot = {"n": 0, "classes": 0.0, "top1": 0.0, "top3": 0.0, "chance1": 0.0, "chance3": 0.0}
    base = {"top1": 0.0, "top3": 0.0}
    samples = 0
    for i in range(len(games)):
        model = MovePredictor().fit(games[:i] + games[i + 1:])
        samples += model.n_samples
        acc = evaluate_accuracy(model, [games[i]])
        b = evaluate_accuracy(MovePredictor(), [games[i]])
        n = acc["n"]
        tot["n"] += n
        for key in ("classes", "top1", "top3", "chance1", "chance3"):
            tot[key] += acc[key] * n
        base["top1"] += b["top1"] * n
        base["top3"] += b["top3"] * n
    n = tot["n"] or 1
    acc = {k: (v / n if k != "n" else v) for k, v in tot.items()}
    return _row("human", len(games) - 1, 1, acc,
                {"top1": base["top1"] / n, "top3": base["top3"] / n}, samples // len(games))


def timing(games: list, model: MovePredictor, dest_samples: int = 6, calls: int = 3000,
           seed: int = 0) -> dict:
    """MCTS-ийн `sample_unit_action`-ийнх шиг: `dest_samples` нүд × ур чадвар — нэр дэвшигчид."""
    rng = random.Random(seed)
    cases = []
    for state, uid, _ in MovePredictor.decisions(games):
        acts = unit_actions(state, state.units[uid])
        dests = sorted({a.dest for a in acts})
        keep = set(rng.sample(dests, min(dest_samples, len(dests))))
        cases.append((state, uid, [a for a in acts if a.dest in keep]))
        if len(cases) >= 300:
            break
    times = []
    for i in range(calls):
        state, uid, cands = cases[i % len(cases)]
        t0 = time.perf_counter()
        model.predict(state, uid, cands)
        times.append(time.perf_counter() - t0)
    times.sort()
    return {"median_ms": statistics.median(times) * 1e3,
            "p95_ms": times[int(0.95 * len(times))] * 1e3,
            "cands": statistics.median(len(c[2]) for c in cases)}
