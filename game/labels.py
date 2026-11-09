"""Дүр, ээлж, үйл явдлын монгол нэр (pygame-гүй)."""

from __future__ import annotations

from typing import Optional

from engine import DEMONS, HEROES, SKILLS, UNIT_TYPES, GameState

TURN_NAMES = {HEROES: "Баатруудын ээлж", DEMONS: "Дайсны ээлж"}
WINNER_NAMES = {HEROES: "Ялалт! Баатрууд яллаа", DEMONS: "Ялагдал. Дайсан яллаа", "draw": "Тэнцээ"}


def _split_uid(uid: str) -> tuple:
    """"slime2" → ("slime", "2"), "demon_lord" → ("demon_lord", "")."""
    base = uid.rstrip("0123456789")
    return base, uid[len(base):]


def unit_name(uid: str, state: Optional[GameState] = None) -> str:
    """"imp1" → "Imp 1", "slime2" → "Slime 2", "demon_lord" → "Demon Lord"."""
    u = state.units.get(uid) if state is not None else None
    base, num = _split_uid(uid)
    kind = u.kind if u is not None else base
    t = UNIT_TYPES.get(kind)
    if t is None:
        return uid
    return f"{t.name} {num}" if num else t.name


def skill_name(sid: str) -> str:
    sk = SKILLS.get(sid)
    return sk.name if sk else sid


def action_label(action, state: GameState) -> str:
    """Нүүдлийг монголоор: «Манан алхам → Цус сорох Mage-т», «Нялцгай цохилт (Knight + Mage)»."""
    from engine import area_cells
    if action.is_end_turn:
        return "Ээлж дуусгах"
    u = state.units[action.unit]
    parts = []
    if action.leap and u.type.leap:
        parts.append(skill_name(u.type.leap) + " →")
    if action.skill is None:
        parts.append("Хүлээх" if action.dest == u.pos and not action.leap
                     else f"Хөдлөх ({action.dest[0]},{action.dest[1]})")
        return " ".join(parts)
    sk = SKILLS[action.skill]
    if action.target_uid:
        parts.append(f"{sk.name} {unit_name(action.target_uid, state)}-т")
    elif sk.kind == "area_damage" and action.target is not None:
        cells = set(area_cells(action.target))
        hit = [unit_name(e.uid, state) for e in state.alive_units()
               if e.side != u.side and e.pos in cells]
        parts.append(f"{sk.name} ({' + '.join(hit)})" if hit else sk.name)
    else:
        parts.append(sk.name)
    return " ".join(parts)


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
