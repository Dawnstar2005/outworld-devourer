"""Дүр, ээлж, үйл явдлын монгол нэр (pygame-гүй)."""

from __future__ import annotations

from typing import Optional

from engine import DEMONS, HEROES, SKILLS, UNIT_TYPES, GameState

TURN_NAMES = {HEROES: "Баатруудын ээлж", DEMONS: "Боссын ээлж"}
WINNER_NAMES = {HEROES: "Ялалт! Баатрууд яллаа", DEMONS: "Ялагдал. Босс яллаа", "draw": "Тэнцээ"}


def unit_name(uid: str, state: Optional[GameState] = None) -> str:
    """"imp1" → "Imp 1", "demon_lord" → "Demon Lord"."""
    u = state.units.get(uid) if state is not None else None
    kind = u.kind if u is not None else ("imp" if uid.startswith("imp") else uid)
    t = UNIT_TYPES.get(kind)
    if t is None:
        return uid
    if kind == "imp" and uid[3:].isdigit():
        return f"{t.name} {uid[3:]}"
    return t.name


def skill_name(sid: str) -> str:
    sk = SKILLS.get(sid)
    return sk.name if sk else sid


def event_text(ev: dict, state: Optional[GameState] = None) -> Optional[str]:
    """Нэг үйл явдлыг log-ийн мөр болгоно. Харуулах шаардлагагүй бол None."""
    t = ev.get("type")
    n = lambda uid: unit_name(uid, state)  # noqa: E731
    if t == "move":
        x, y = ev["to"]
        return f"{n(ev['unit'])} → ({x},{y})" + (" үсрэлтээр" if ev.get("leap") else "")
    if t == "skill":
        text = f"{n(ev['unit'])}: {skill_name(ev['skill'])}"
        return text + (f" → {n(ev['target_uid'])}" if ev.get("target_uid") else "")
    if t == "damage":
        text = f"   {n(ev['dst'])} -{ev['amount']} HP"
        return text + (f" (бамбай {ev['absorbed']})" if ev.get("absorbed") else "")
    if t == "heal":
        return f"   {n(ev['dst'])} +{ev['amount']} HP"
    if t == "death":
        return f"   {n(ev['unit'])} унав"
    if t == "shield":
        return f"   {n(ev['dst'])}: бамбай {ev['amount']}"
    if t == "curse":
        return f"   {n(ev['dst'])} хараалд орлоо ({ev['turns']} ээлж)"
    if t == "taunt":
        names = ", ".join(n(u) for u in ev["targets"]) or "хэн ч биш"
        return f"   Taunt: {names} ({ev['turns']} ээлж)"
    if t == "wall":
        return f"   Мөсөн хана ({ev['turns']} ээлж)"
    if t == "summon":
        return f"   {len(ev['spawned'])} Imp дуудагдлаа"
    if t == "turn_start":
        return f"— Round {ev['round']}: {TURN_NAMES.get(ev['side'], ev['side'])} —"
    if t == "game_over":
        return WINNER_NAMES.get(ev["winner"], str(ev["winner"]))
    return None
