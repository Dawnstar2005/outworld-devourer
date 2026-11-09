"""Тоглогчийн дараагийн нүүдэл таамаглагч (DQ, PDF-ийн шаардлага 4) — pygame-гүй.

Таамаглалын «анги» = (skill, target_uid). skill=None бол «хөдлөх/хүлээх». Нэг ангид олон
Action (өөр өөр нүд) байвал жинг тэдгээрийн хооронд тэгш хуваана.

Загвар — нөхцөлт logit (choice model). Боломжит анги бүрийн оноо:

    score(c) = heur_w · heuristic(c) / max_heuristic  +  Σ w[f]  (f — c-ийн шинжүүд)

шинжүүд: (дүрийн төрөл, ур чадвар), (…, байны төрөл), (…, байны HP-ийн бүлэг).
heuristic — нүүдлийн шууд үр ашиг HP-ээр (хохирол, эдгээлт, бамбай, taunt-д орох дайсан).
P(c) = softmax(score). SGD-ээр log-likelihood-ийг өсгөнө; w-г 0 руу, heur_w-г HEUR_PRIOR
руу L2-оор татна — өгөгдөл бага үед загвар heuristic руу зөөлөн шилжинэ (smoothing).

`predict()`-г MCTS rollout дотор олон мянган удаа дууддаг тул дотор нь next_state() болон
хүнд тооцоолол хийхгүй — зөвхөн dict хайлт, энгийн арифметик.

    from learning.predictor import MovePredictor, predictor_from_logs
    mp = predictor_from_logs("logs")            # эсвэл MovePredictor().fit(games)
    BossAI(predictor=mp)                          # mp(state, unit_uid, actions) дуудагдана

Ажиллуулах:  python -m learning.predictor [logs] [--out logs/predictor.json]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Iterable, Optional

from engine import SKILLS, Action, GameState, unit_actions

from .log import iter_logs

PREDICTOR_VERSION = 1

# ---- загварын тохиргоо (тоглоомын тоо биш) ----
HEUR_PRIOR = 3.0        # heuristic-ийн жингийн prior — өгөгдөлгүй үед ч ухаалаг таамаглана
LEARNING_RATE = 0.08
L2_FEATURES = 0.002     # w → 0 руу татах хүч
L2_HEUR = 0.01          # heur_w → HEUR_PRIOR руу татах хүч
EPOCHS = 8
MOVE_VALUE = 4.0        # зөвхөн хөдлөх/хүлээхийн heuristic үнэ цэнэ (HP-тэй харьцуулахуйц)
KILL_BONUS = 15.0       # унагах цохилтод нэмэх
CURSE_VALUE = 12.0
WALL_VALUE = 5.0
TAUNT_PER_ENEMY = 6.0
SUMMON_VALUE = 10.0


def class_key(a: Action) -> tuple:
    return (a.skill, a.target_uid)


def _hp_bucket(u) -> int:
    r = u.hp / u.max_hp if u.max_hp else 0.0
    return 0 if r < 0.34 else 1 if r < 0.67 else 2 if r < 1.0 else 3


def _features(kind: str, key: tuple, target) -> tuple:
    skill = key[0] or "move"
    if target is None:
        return (("s", kind, skill), ("t", kind, skill, "none"))
    return (("s", kind, skill), ("t", kind, skill, target.kind),
            ("h", kind, skill, _hp_bucket(target)))


def _heuristic(state: GameState, unit, acts: list) -> float:
    """Ангийн шууд үр ашиг (HP-ээр). Ангид олон Action байвал хамгийн сайныг нь авна."""
    sid = acts[0].skill
    if sid is None:
        return MOVE_VALUE
    sk = SKILLS[sid]
    kind = sk.kind
    units = state.units
    if kind == "damage":
        t = units.get(acts[0].target_uid)
        if t is None or not t.alive:
            return 0.0
        dmg = max(0, sk.power - t.shield)
        return min(dmg, t.hp) + (KILL_BONUS if dmg >= t.hp else 0.0)
    if kind == "area_damage":
        enemies = [e for e in units.values() if e.alive and e.side != unit.side]
        best = 0.0
        for a in acts:
            cx, cy = a.target
            v = 0.0
            for e in enemies:
                if abs(e.x - cx) <= 1 and abs(e.y - cy) <= 1:
                    dmg = max(0, sk.power - e.shield)
                    v += min(dmg, e.hp) + (KILL_BONUS if dmg >= e.hp else 0.0)
            if v > best:
                best = v
        return best
    if kind == "heal":
        t = units.get(acts[0].target_uid)
        return 0.0 if t is None or t.cursed else float(min(sk.power, t.max_hp - t.hp))
    if kind == "shield":
        t = units.get(acts[0].target_uid)
        if t is None:
            return 0.0
        return max(0, sk.power - t.shield) * (0.5 + 0.5 * (1.0 - t.hp / t.max_hp))
    if kind == "curse":
        return CURSE_VALUE
    if kind == "taunt":
        enemies = [e for e in units.values() if e.alive and e.side != unit.side]
        best = 0
        for a in acts:
            dx, dy = a.dest
            n = sum(1 for e in enemies if abs(e.x - dx) + abs(e.y - dy) <= sk.range)
            if n > best:
                best = n
        return TAUNT_PER_ENEMY * best
    if kind == "wall":
        return WALL_VALUE
    if kind == "summon":
        return SUMMON_VALUE
    return 0.0


def _group(actions: list) -> dict:
    groups = {}
    for i, a in enumerate(actions):
        groups.setdefault((a.skill, a.target_uid), []).append(i)
    return groups


def _key_str(f: tuple) -> str:
    return "|".join(str(x) for x in f)


def _key_parse(s: str) -> tuple:
    parts = s.split("|")
    if parts[0] == "h":
        parts[3] = int(parts[3])
    return tuple(parts)


class MovePredictor:
    """Тоглогчийн дараагийн нүүдлийн магадлал. `predictor(state, unit_uid, actions)` гэж дуудна."""

    def __init__(self, seed: int = 0):
        self.w: dict = {}
        self.heur_w = HEUR_PRIOR
        self.n_samples = 0
        self.seed = seed

    # ------------------------------------------------------------------ таамаглал
    def _class_scores(self, state, unit, actions, groups):
        units = state.units
        keys = list(groups)
        hs = [_heuristic(state, unit, [actions[i] for i in groups[k]]) for k in keys]
        hmax = max(hs)
        inv = 1.0 / hmax if hmax > 0 else 0.0
        w = self.w
        kind = unit.kind
        scores = []
        for k, h in zip(keys, hs):
            s = self.heur_w * h * inv
            for f in _features(kind, k, units.get(k[1]) if k[1] else None):
                s += w.get(f, 0.0)
            scores.append(s)
        return keys, scores

    def predict(self, state: GameState, unit_uid: str, actions: list) -> list:
        """actions-тэй ижил урттай жин (нийлбэр 1). Нэг ангийн Action-ууд тэнцүү хуваана."""
        if not actions:
            return []
        unit = state.units[unit_uid]
        groups = _group(actions)
        keys, scores = self._class_scores(state, unit, actions, groups)
        m = max(scores)
        ex = [math.exp(s - m) for s in scores]
        z = sum(ex)
        out = [0.0] * len(actions)
        for k, e in zip(keys, ex):
            idx = groups[k]
            share = e / z / len(idx)
            for i in idx:
                out[i] = share
        return out

    __call__ = predict

    def class_probs(self, state: GameState, unit_uid: str, actions: Optional[list] = None) -> list:
        """[((skill, target_uid), p), ...] магадлалаар буурахаар."""
        unit = state.units[unit_uid]
        if actions is None:
            actions = unit_actions(state, unit)
        groups = _group(actions)
        keys, scores = self._class_scores(state, unit, actions, groups)
        m = max(scores)
        ex = [math.exp(s - m) for s in scores]
        z = sum(ex)
        return sorted(((k, e / z) for k, e in zip(keys, ex)), key=lambda t: -t[1])

    def top_k(self, state: GameState, unit_uid: str, k: int = 3) -> list:
        """[(skill, target_uid), ...] — хамгийн магадлалтай k анги (engine-ийн бүх хууль ёсны нүүдлээс)."""
        return [key for key, _ in self.class_probs(state, unit_uid)[:k]]

    # ------------------------------------------------------------------ сургалт
    @staticmethod
    def decisions(games: Iterable[list], human_only: bool = True):
        """Log-оос (state, unit_uid, chosen_key) — тоглогчийн дүр бүрийн шийдвэр."""
        for records in games:
            for rec in records:
                if rec.get("type") != "action":
                    continue
                if human_only and rec.get("actor") != "human":
                    continue
                act = rec["action"]
                if not act.get("unit"):
                    continue                                  # END_TURN
                yield (GameState.from_dict(rec["state"]), act["unit"],
                       (act.get("skill"), act.get("target_uid")))

    def _sample(self, state, uid, chosen):
        unit = state.units[uid]
        actions = unit_actions(state, unit)
        groups = _group(actions)
        if chosen not in groups:
            return None
        units = state.units
        keys = list(groups)
        hs = [_heuristic(state, unit, [actions[i] for i in groups[k]]) for k in keys]
        hmax = max(hs)
        hs = [h / hmax if hmax > 0 else 0.0 for h in hs]
        feats = [_features(unit.kind, k, units.get(k[1]) if k[1] else None) for k in keys]
        return feats, hs, keys.index(chosen)

    def fit(self, games: Iterable[list], human_only: bool = True) -> "MovePredictor":
        samples = []
        for state, uid, chosen in self.decisions(games, human_only):
            s = self._sample(state, uid, chosen)
            if s is not None:
                samples.append(s)
        self.n_samples += len(samples)
        rng = random.Random(self.seed)
        w = self.w
        for _ in range(EPOCHS):
            rng.shuffle(samples)
            for feats, hs, ci in samples:
                scores = [self.heur_w * h + sum(w.get(f, 0.0) for f in fs)
                          for fs, h in zip(feats, hs)]
                m = max(scores)
                ex = [math.exp(s - m) for s in scores]
                z = sum(ex)
                p = [e / z for e in ex]
                grad = {}
                for fs, pc in zip(feats, p):
                    for f in fs:
                        grad[f] = grad.get(f, 0.0) - pc
                for f in feats[ci]:
                    grad[f] = grad.get(f, 0.0) + 1.0
                for f, g in grad.items():
                    cur = w.get(f, 0.0)
                    w[f] = cur + LEARNING_RATE * (g - L2_FEATURES * cur)
                g_h = hs[ci] - sum(pc * h for pc, h in zip(p, hs))
                self.heur_w += LEARNING_RATE * (g_h - L2_HEUR * (self.heur_w - HEUR_PRIOR))
        return self

    # ------------------------------------------------------------------ хадгалах
    def to_dict(self) -> dict:
        return {"version": PREDICTOR_VERSION, "heur_w": round(self.heur_w, 6),
                "n_samples": self.n_samples,
                "weights": {_key_str(f): round(v, 6) for f, v in sorted(self.w.items(), key=str)
                            if abs(v) > 1e-6}}

    @classmethod
    def from_dict(cls, d: dict) -> "MovePredictor":
        mp = cls()
        mp.heur_w = float(d.get("heur_w", HEUR_PRIOR))
        mp.n_samples = int(d.get("n_samples", 0))
        mp.w = {_key_parse(k): float(v) for k, v in d.get("weights", {}).items()}
        return mp


# --------------------------------------------------------------------------- үнэлгээ, log-оос

def evaluate_accuracy(model: MovePredictor, games: Iterable[list], ks=(1, 3),
                      human_only: bool = True) -> dict:
    """top-k нарийвчлал: жинхэнэ (skill, target_uid) эхний k таамаглалд багтсан хувь.

    Харьцуулахад: `classes` — шийдвэр бүрийн боломжит ангийн дундаж тоо, `chance{k}` —
    санамсаргүй тааварласан бол top-k-д багтах хүлээгдэх хувь (min(k, n)/n-ийн дундаж).
    """
    hits = {k: 0 for k in ks}
    chance = {k: 0.0 for k in ks}
    n = 0
    n_classes = 0
    for state, uid, chosen in MovePredictor.decisions(games, human_only):
        probs = model.class_probs(state, uid)
        ranked = [key for key, _ in probs]
        n += 1
        n_classes += len(ranked)
        for k in ks:
            hits[k] += chosen in ranked[:k]
            chance[k] += min(k, len(ranked)) / len(ranked)
    out = {"n": n, "classes": n_classes / n if n else 0.0}
    for k in ks:
        out[f"top{k}"] = hits[k] / n if n else 0.0
        out[f"chance{k}"] = chance[k] / n if n else 0.0
    return out


def predictor_from_logs(folder: str | os.PathLike = "logs", max_games: int = 50) -> MovePredictor:
    games = [records for _, records in iter_logs(folder)][-max_games:]
    return MovePredictor().fit(games)


def save_predictor(model: MovePredictor, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_predictor(path) -> Optional[MovePredictor]:
    try:
        return MovePredictor.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m learning.predictor",
                                description="Тоглолтын log-оос дараагийн нүүдэл таамаглагч сургана")
    p.add_argument("logs", nargs="?", default="logs")
    p.add_argument("--out", default=None, help="default: <logs>/predictor.json")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    model = predictor_from_logs(args.logs)
    out = save_predictor(model, args.out or Path(args.logs) / "predictor.json")
    games = [r for _, r in iter_logs(args.logs)]
    acc = evaluate_accuracy(model, games)
    print(f"{model.n_samples} шийдвэрээс сургав → {out}")
    print(f"сургасан өгөгдөл дээрх нарийвчлал: top-1 {acc['top1']:.0%}, top-3 {acc['top3']:.0%}"
          f" ({acc['n']} шийдвэр)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
