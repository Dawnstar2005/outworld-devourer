"""Тоглогчийн дараагийн нүүдлийн таамаг — «Боссын бодол» самбарт (pygame-гүй).

`PredictionTracker` нь баатруудын ээлж бүрт нүүдлээ хийгээгүй баатар бүрийн хамгийн
магадлалтай нүүдлийг (learning/predictor.py-ийн MovePredictor) тооцоолж, тоглогч бодитоор
нүүх бүрт таамаг зөв байсан эсэхийг тоолно — тоглогч «босс намайг хэр сайн таньж байна»
гэдгийг шууд харна (PDF-ийн шаардлага 4).

`LearnedModels` нь тоглолтын log-оос таамаглагчийг ТУСДАА THREAD-д сургана (50 тулаанд ~3 сек),
log шинээр нэмэгдсэн үед л дахин сургана. Бэлэн болтол `predictor` нь өмнөх загвар эсвэл None.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from engine import HEROES, GameState

from .labels import skill_name, unit_name

TOP_K = 3


def class_label(key: tuple, state: Optional[GameState] = None) -> str:
    """(skill, target_uid) → «Хар дөл Mage-т», «Эдгээх», «Хөдлөх / хүлээх»."""
    skill, target = key
    if skill is None:
        return "Хөдлөх / хүлээх"
    name = skill_name(skill)
    return f"{name} {unit_name(target, state)}-т" if target else name


@dataclass
class Guess:
    uid: str
    key: tuple
    label: str
    p: float


@dataclass
class PredictionTracker:
    predictor: object
    human_side: str = HEROES
    guesses: list = field(default_factory=list)      # [Guess] — нүүгээгүй баатар бүрийн top-1
    hits: int = 0                                     # top-1 зөв
    hits3: int = 0                                    # top-3 дотор
    total: int = 0
    last: Optional[tuple] = None                      # (uid, таамаг label, бодит label, зөв эсэх)

    def refresh(self, state: GameState) -> None:
        """Тоглогчийн ээлжинд нүүгээгүй баатар бүрийн хамгийн магадлалтай нүүдэл."""
        self.guesses = []
        if state.is_over or state.side_to_act != self.human_side:
            return
        for u in state.alive_units(self.human_side):
            if u.acted:
                continue
            probs = self.predictor.class_probs(state, u.uid)
            if probs:
                key, p = probs[0]
                self.guesses.append(Guess(u.uid, key, class_label(key, state), p))

    def on_action(self, state_before: GameState, action, events: list) -> None:
        """GameSession-ийн hook: тоглогчийн нүүдэл бүрийг таамагтай харьцуулна."""
        if state_before.side_to_act != self.human_side or action.is_end_turn:
            return
        top = [k for k, _ in self.predictor.class_probs(state_before, action.unit)[:TOP_K]]
        if not top:
            return
        actual = (action.skill, action.target_uid)
        hit = actual == top[0]
        self.total += 1
        self.hits += hit
        self.hits3 += actual in top
        self.last = (action.unit, class_label(top[0], state_before),
                     class_label(actual, state_before), hit)

    def reset(self) -> None:
        self.guesses, self.last = [], None
        self.hits = self.hits3 = self.total = 0

    def panel(self) -> dict:
        """BossPanel-д өгөх өгөгдөл."""
        return {"guesses": [(g.uid, g.label, g.p) for g in self.guesses],
                "hits": self.hits, "hits3": self.hits3, "total": self.total,
                "last": self.last}


def _log_signature(folder) -> tuple:
    try:
        files = [e for e in os.scandir(folder) if e.name.endswith(".jsonl")]
    except OSError:
        return (0, 0.0)
    return (len(files), max((e.stat().st_mtime for e in files), default=0.0))


class LearnedModels:
    """Log-оос таамаглагчийг арын thread-д сургана. `predictor` — хамгийн сүүлийн бэлэн загвар."""

    def __init__(self, log_dir, build: Optional[Callable] = None, max_games: int = 30):
        self.log_dir = Path(log_dir)
        self.max_games = max_games
        self._build = build or self._default_build
        self.predictor = None
        self.error: Optional[str] = None
        self._signature = None
        self._thread: Optional[threading.Thread] = None

    def _default_build(self):
        from learning.predictor import predictor_from_logs
        return predictor_from_logs(self.log_dir, max_games=self.max_games)

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def refresh(self) -> bool:
        """Log өөрчлөгдсөн бол арын thread-д дахин сургаж эхэлнэ. Эхэлсэн бол True."""
        sig = _log_signature(self.log_dir)
        if sig == self._signature or self.busy or sig[0] == 0:
            return False
        self._signature = sig
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        try:
            model = self._build()
            if getattr(model, "n_samples", 1) > 0:
                self.predictor = model
        except Exception as err:          # log эвдэрсэн ч тоглоом үргэлжилнэ
            self.error = str(err)

    def wait(self, timeout: float = 10.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
