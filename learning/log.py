"""Тоглолтын log — JSON Lines (pygame-гүй).

Нэг тоглолт = нэг файл (`logs/20261109-153012-0000-1a2b3c.jsonl`). Мөр бүр нэг JSON объект:

    {"type": "start", "version": 1, "time": "...", "human_side": "heroes",
     "meta": {"boss": "mcts"}, "state": {...}}
    {"type": "action", "i": 0, "round": 1, "side": "heroes", "actor": "human",
     "state": {...нүүдлээс өмнөх...}, "action": {...}, "events": [...]}
    ...
    {"type": "end", "winner": "heroes" | "demons" | "draw" | null, "rounds": 7,
     "actions": 58, "reason": "game_over" | "restart" | "menu" | "quit"}

`state` нь `GameState.to_dict()`, `action` нь `Action.to_dict()`, `events` нь `apply()`-ийн
буцаасан жагсаалт. Тиймээс log-оос тоглолтыг яг дахин тоглуулж болно (`replay_check`).
Мөр бүрийг бичмэгц flush хийнэ — тоглоом гэнэт хаагдсан ч бичсэн хэсэг үлдэнэ.
"""

from __future__ import annotations

import itertools
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from engine import HEROES, Action, GameState, apply

LOG_VERSION = 1
_SEQ = itertools.count()   # нэг секундэд хэд хэдэн тоглолт эхэлбэл файлын нэр дарааллаа хадгална


def _jsonable(obj):
    """events доторх tuple-ийг list болгоно (JSON-д tuple байхгүй)."""
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


class GameLogger:
    """`on_action(state_before, action, events)` hook-оор тоглолт бүрийг файлд бичнэ."""

    def __init__(self, folder: str | os.PathLike = "logs", human_side: str = HEROES,
                 meta: Optional[dict] = None):
        self.folder = Path(folder)
        self.human_side = human_side
        self.meta = dict(meta or {})
        self.path: Optional[Path] = None
        self._file = None
        self._count = 0
        self._last_round = 0

    @property
    def active(self) -> bool:
        return self._file is not None

    def _write(self, record: dict) -> None:
        self._file.write(json.dumps(_jsonable(record), ensure_ascii=False) + "\n")
        self._file.flush()

    def start(self, state: GameState, meta: Optional[dict] = None) -> Path:
        """Шинэ тоглолтын файл нээнэ (өмнөх нээлттэй бол "restart" гэж хаана)."""
        if self.active:
            self.close("restart")
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = self.folder / f"{stamp}-{next(_SEQ):04d}-{uuid.uuid4().hex[:6]}.jsonl"
        self._file = open(self.path, "w", encoding="utf-8")
        self._count = 0
        self._last_round = state.round
        self._write({"type": "start", "version": LOG_VERSION,
                     "time": datetime.now().isoformat(timespec="seconds"),
                     "human_side": self.human_side, "meta": {**self.meta, **(meta or {})},
                     "state": state.to_dict()})
        return self.path

    def on_action(self, state_before: GameState, action: Action, events: list) -> None:
        if not self.active:
            self.start(state_before)
        self._write({"type": "action", "i": self._count, "round": state_before.round,
                     "side": state_before.side_to_act,
                     "actor": "human" if state_before.side_to_act == self.human_side else "boss",
                     "state": state_before.to_dict(), "action": action.to_dict(),
                     "events": events})
        self._count += 1
        self._last_round = state_before.round
        for ev in events:
            if ev.get("type") == "game_over":
                self._end(ev.get("winner"), ev.get("round", self._last_round), "game_over")
                break

    def _end(self, winner, rounds, reason) -> None:
        self._write({"type": "end", "winner": winner, "rounds": rounds,
                     "actions": self._count, "reason": reason})
        self._file.close()
        self._file = None

    def close(self, reason: str = "quit") -> None:
        """Дуусаагүй тоглолтыг хаана (шинэ тоглолт, цэс, програмаас гарах)."""
        if self.active:
            self._end(None, self._last_round, reason)


# --------------------------------------------------------------------------- унших

def read_log(path: str | os.PathLike) -> list:
    """Log файлын бүх мөр. Сүүлийн мөр дутуу бичигдсэн (гэнэт хаагдсан) бол алгасна."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return records


def iter_logs(folder: str | os.PathLike = "logs", finished_only: bool = False) -> Iterator:
    """(path, records) — хавтсан дахь log бүр, хуучнаас шинэ рүү."""
    folder = Path(folder)
    if not folder.is_dir():
        return
    for path in sorted(folder.glob("*.jsonl")):
        records = read_log(path)
        if not records or records[0].get("type") != "start":
            continue
        if finished_only and records[-1].get("reason") != "game_over":
            continue
        yield path, records


def replay_check(records: list) -> bool:
    """Log-ийг engine-ээр дахин тоглуулж, мөр бүрийн төлөв, events таарч байгааг шалгана."""
    actions = [r for r in records if r.get("type") == "action"]
    if not actions:
        return True
    state = GameState.from_dict(actions[0]["state"])
    for rec in actions:
        if json.dumps(_jsonable(state.to_dict()), sort_keys=True) != \
                json.dumps(rec["state"], sort_keys=True):
            return False
        events = apply(state, Action.from_dict(rec["action"]), validate=True)
        if _jsonable(events) != rec["events"]:
            return False
    return True
