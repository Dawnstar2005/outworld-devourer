"""Тоглоомын дүрэм: боломжит нүүдэл гаргах, нүүдэл хийх, ээлж солих.

Ээлжийн бүтэц
-------------
* Хоёр тал ээлжилнэ: эхлээд HEROES, дараа нь DEMONS. Хоёул нэг удаа нүүвэл нэг round.
* Өөрийн ээлжинд тал бүрийн амьд дүр бүр нэг Action хийнэ (дарааллыг нь тоглогч/AI сонгоно).
  Action = хөдлөх (эсвэл Сүүдрийн үсрэлт) + нэг ур чадвар (эсвэл юу ч үгүй).
* END_TURN нь үлдсэн дүрүүдийг алгасаад ээлжийг дуусгана.
* Бүх дүр нүүсний дараа ээлж автоматаар солигдоно.

Хугацааны дүрэм
--------------
* Ур чадвар хэрэглэхэд cooldown = skill.cooldown. Тал бүрийн ээлж эхлэхэд 1-ээр буурна,
  0 болвол дахин хэрэглэж болно (cooldown=1 → ээлж бүр, 2 → хоёр ээлж тутам).
* Хараал, Taunt нь нөлөөлсөн дүрийн өөрийн ээлж дуусах бүрт 1-ээр буурна
  (жишээ нь Taunt нь боссын дараагийн 2 ээлжид үйлчилнэ).
* Мөсөн хана DEMONS-ийн ээлж дуусах бүрт 1-ээр буурна (боссын 2 ээлжийг хаана).
* Taunt-д орсон дайсны НЭГ БАЙТАЙ ур чадвар (damage, drain, curse) Taunt хийсэн дүр хүрэх
  зайд байвал зөвхөн түүн рүү чиглэнэ. Бүсийн (area) ур чадвар чөлөөтэй.

Dungeon (2026-11-09)
--------------------
* Хохирол / эдгээлт / бамбайн хэмжээ = skill.power × unit.power_mult (level, item, давхрын хүч).
* drain — хохирол учруулаад, учруулсан хохирлын skill.drain хувиар өөрийгөө эдгээнэ.
* summon — skill.summons төрлийн үхсэн дагуулыг хажууд нь сэргээнэ (амьд нь MAX_SUMMONS хүртэл).
* Ялалт: босс (UnitType.boss) байгаа бол түүнийг унагахад, байхгүй бол бүх дайсныг унагахад.
* state.obstacles — байнгын саад, хөдөлгөөн болон мөсөн ханыг хаана.
"""

from __future__ import annotations

from collections import deque

from .constants import BOARD_H, BOARD_W, DEMONS, HEROES, MAX_ROUNDS, MAX_SUMMONS, SKILLS
from .state import END_TURN, Action, GameState, Unit

NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def dist(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def other_side(side: str) -> str:
    return DEMONS if side == HEROES else HEROES


def area_cells(center):
    """3×3 бүсийн нүднүүд (талбайгаас гарсныг хасна)."""
    cx, cy = center
    return [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if GameState.in_bounds((cx + dx, cy + dy))]


def scaled_power(unit: Unit, sk) -> int:
    """Ур чадварын бодит хэмжээ: skill.power × unit.power_mult (бүхэл тоо)."""
    return max(0, int(round(sk.power * unit.power_mult)))


def wall_cells(target, variant):
    x, y = target
    return [(x, y), (x + 1, y)] if variant == 0 else [(x, y), (x, y + 1)]


# --------------------------------------------------------------------------- хөдөлгөөн

def reachable(state: GameState, unit: Unit, blocked=None) -> dict:
    """Алхаж хүрч болох нүднүүд {нүд: зай}. Өөрийн нүд (0) орно."""
    if blocked is None:
        blocked = state.blocked_cells()
    start = unit.pos
    seen = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        d = seen[c]
        if d == unit.move:
            continue
        for dx, dy in NEIGHBORS:
            n = (c[0] + dx, c[1] + dy)
            if n in seen or n in blocked or not GameState.in_bounds(n):
                continue
            seen[n] = d + 1
            q.append(n)
    return seen


def leap_cells(state: GameState, unit: Unit, blocked=None, exclude=()) -> list:
    """Сүүдрийн үсрэлтээр очиж болох хоосон нүднүүд."""
    leap = unit.type.leap
    if not leap or unit.cooldowns.get(leap, 1) > 0:
        return []
    if blocked is None:
        blocked = state.blocked_cells()
    r = SKILLS[leap].range
    out = []
    for x in range(max(0, unit.x - r), min(BOARD_W, unit.x + r + 1)):
        for y in range(max(0, unit.y - r), min(BOARD_H, unit.y + r + 1)):
            c = (x, y)
            if c not in blocked and c not in exclude and dist(c, unit.pos) <= r:
                out.append(c)
    return out


# --------------------------------------------------------------------------- ур чадварын бай

def skill_options(state: GameState, unit: Unit, src, blocked_after):
    """`src` нүднээс хэрэглэж болох (skill, target, target_uid, variant) жагсаалт.

    blocked_after — дүр src руу хөдөлсний дараах хаагдсан нүднүүд.
    """
    out = []
    enemies = state.alive_units(other_side(unit.side))
    allies = state.alive_units(unit.side)
    taunter = state.units.get(unit.taunted_by) if unit.taunted_by else None
    if taunter is not None and not taunter.alive:
        taunter = None

    for sid in unit.type.skills:
        if unit.cooldowns[sid] > 0:
            continue
        sk = SKILLS[sid]
        k = sk.kind
        if k in ("damage", "drain", "curse"):
            in_range = [e for e in enemies if dist(src, e.pos) <= sk.range]
            if taunter is not None and taunter in in_range:
                in_range = [taunter]
            for e in in_range:
                out.append((sid, e.pos, e.uid, 0))
        elif k == "area_damage":
            enemy_cells = {e.pos for e in enemies}
            for x in range(max(0, src[0] - sk.range), min(BOARD_W, src[0] + sk.range + 1)):
                for y in range(max(0, src[1] - sk.range), min(BOARD_H, src[1] + sk.range + 1)):
                    c = (x, y)
                    if dist(src, c) <= sk.range and any(a in enemy_cells for a in area_cells(c)):
                        out.append((sid, c, None, 0))
        elif k == "taunt":
            if any(dist(src, e.pos) <= sk.range for e in enemies):
                out.append((sid, None, None, 0))
        elif k == "wall":
            for x in range(max(0, src[0] - sk.range), min(BOARD_W, src[0] + sk.range + 1)):
                for y in range(max(0, src[1] - sk.range), min(BOARD_H, src[1] + sk.range + 1)):
                    c = (x, y)
                    if not (1 <= dist(src, c) <= sk.range):
                        continue
                    for v in (0, 1):
                        cells = wall_cells(c, v)
                        if all(GameState.in_bounds(w) and w not in blocked_after for w in cells):
                            out.append((sid, c, None, v))
        elif k == "heal":
            for a in allies:
                p = src if a is unit else a.pos
                if dist(src, p) <= sk.range and a.hp < a.max_hp and a.cursed == 0:
                    out.append((sid, p, a.uid, 0))
        elif k == "shield":
            for a in allies:
                p = src if a is unit else a.pos
                if dist(src, p) <= sk.range and a.shield < scaled_power(unit, sk):
                    out.append((sid, p, a.uid, 0))
        elif k == "summon":
            kind = sk.summons or "imp"
            dead = [u for u in state.units.values() if u.kind == kind and not u.alive]
            alive_n = sum(1 for u in allies if u.kind == kind)
            if dead and alive_n < MAX_SUMMONS and _free_neighbors(src, blocked_after):
                out.append((sid, None, None, 0))
    return out


def _free_neighbors(cell, blocked):
    return [n for n in ((cell[0] + dx, cell[1] + dy) for dx, dy in NEIGHBORS)
            if GameState.in_bounds(n) and n not in blocked]


# --------------------------------------------------------------------------- боломжит нүүдэл

def unit_actions(state: GameState, unit: Unit, blocked=None) -> list:
    """Нэг дүрийн боломжит бүх Action."""
    if blocked is None:
        blocked = state.blocked_cells()
    moves = [(c, False) for c in reachable(state, unit, blocked)]
    moves += [(c, True) for c in leap_cells(state, unit, blocked, exclude={m for m, _ in moves})]
    out = []
    for dest, leap in moves:
        after = (blocked - {unit.pos}) | {dest}
        out.append(Action(unit.uid, dest, leap=leap))  # зөвхөн хөдлөх / хүлээх
        for sid, tgt, tuid, var in skill_options(state, unit, dest, after):
            out.append(Action(unit.uid, dest, sid, tgt, tuid, var, leap))
    return out


def legal_actions(state: GameState, include_end_turn: bool = True) -> list:
    """Одоогийн талын боломжит бүх Action. Тоглоом дууссан бол хоосон."""
    if state.is_over:
        return []
    blocked = state.blocked_cells()
    out = []
    for u in state.alive_units(state.side_to_act):
        if not u.acted:
            out.extend(unit_actions(state, u, blocked))
    if include_end_turn:
        out.append(END_TURN)
    return out


def is_legal(state: GameState, action: Action) -> bool:
    if action.is_end_turn:
        return not state.is_over
    u = state.units.get(action.unit)
    if u is None or not u.alive or u.acted or u.side != state.side_to_act or state.is_over:
        return False
    return action in unit_actions(state, u)


# --------------------------------------------------------------------------- нүүдэл хийх

def apply(state: GameState, action: Action, validate: bool = False) -> list:
    """Нүүдлийг state дээр шууд хийнэ (mutate). Үйл явдлын жагсаалт буцаана.

    Үйл явдлыг UI анимаци, тоглолтын log-д ашиглана. AI simulation-д
    validate=False (хурдан); UI-аас ирсэн нүүдэлд validate=True.
    """
    if state.is_over:
        raise ValueError("game is over")
    if validate and not is_legal(state, action):
        raise ValueError(f"illegal action: {action}")
    events = []
    if action.is_end_turn:
        _end_side_turn(state, events)
        return events

    u = state.units[action.unit]
    if action.dest != u.pos:
        events.append({"type": "move", "unit": u.uid, "from": u.pos, "to": action.dest,
                       "leap": action.leap})
        u.x, u.y = action.dest
    if action.leap:
        u.cooldowns[u.type.leap] = SKILLS[u.type.leap].cooldown

    if action.skill:
        _use_skill(state, u, action, events)

    u.acted = True
    _check_winner(state, events)
    if not state.is_over and all(x.acted for x in state.alive_units(state.side_to_act)):
        _end_side_turn(state, events)
    return events


def next_state(state: GameState, action: Action) -> GameState:
    """Хуулбар дээр нүүдэл хийж шинэ төлөв буцаана (эх state өөрчлөгдөхгүй)."""
    s = state.clone()
    apply(s, action)
    return s


def _use_skill(state: GameState, u: Unit, a: Action, events: list):
    sk = SKILLS[a.skill]
    u.cooldowns[a.skill] = sk.cooldown
    events.append({"type": "skill", "unit": u.uid, "skill": a.skill, "target": a.target,
                   "target_uid": a.target_uid})
    k = sk.kind
    power = scaled_power(u, sk)
    if k == "damage":
        _deal(state, u, state.units[a.target_uid], power, events)
    elif k == "drain":
        dealt = _deal(state, u, state.units[a.target_uid], power, events)
        amount = 0 if u.cursed else min(int(round(dealt * sk.drain)), u.max_hp - u.hp)
        if amount > 0:
            u.hp += amount
            events.append({"type": "heal", "src": u.uid, "dst": u.uid, "amount": amount})
    elif k == "area_damage":
        cells = set(area_cells(a.target))
        for e in state.alive_units(other_side(u.side)):
            if e.pos in cells:
                _deal(state, u, e, power, events)
    elif k == "curse":
        t = state.units[a.target_uid]
        t.cursed = sk.duration
        events.append({"type": "curse", "src": u.uid, "dst": t.uid, "turns": sk.duration})
    elif k == "taunt":
        hit = []
        for e in state.alive_units(other_side(u.side)):
            if dist(u.pos, e.pos) <= sk.range:
                e.taunted_by, e.taunt_turns = u.uid, sk.duration
                hit.append(e.uid)
        events.append({"type": "taunt", "src": u.uid, "targets": hit, "turns": sk.duration})
    elif k == "wall":
        cells = wall_cells(a.target, a.variant)
        for c in cells:
            state.walls[c] = sk.duration
        events.append({"type": "wall", "src": u.uid, "cells": cells, "turns": sk.duration})
    elif k == "heal":
        t = state.units[a.target_uid]
        amount = min(power, t.max_hp - t.hp)
        t.hp += amount
        events.append({"type": "heal", "src": u.uid, "dst": t.uid, "amount": amount})
    elif k == "shield":
        t = state.units[a.target_uid]
        t.shield = power
        events.append({"type": "shield", "src": u.uid, "dst": t.uid, "amount": power})
    elif k == "summon":
        kind = sk.summons or "imp"
        blocked = state.blocked_cells()
        free = _free_neighbors(u.pos, blocked)
        alive_n = sum(1 for x in state.alive_units(u.side) if x.kind == kind)
        spawned = []
        for dead in [x for x in state.units.values() if x.kind == kind and not x.alive]:
            if not free or alive_n >= MAX_SUMMONS:
                break
            fresh = Unit(dead.uid, kind, free.pop(0))
            fresh.max_hp = fresh.hp = dead.max_hp          # давхрын хүчийг хадгална
            fresh.power_mult, fresh.level = dead.power_mult, dead.level
            fresh.acted = True  # дуудагдсан ээлждээ нүүхгүй
            state.units[dead.uid] = fresh
            alive_n += 1
            spawned.append({"unit": dead.uid, "pos": fresh.pos})
        events.append({"type": "summon", "src": u.uid, "spawned": spawned})


def _deal(state: GameState, src: Unit, dst: Unit, amount: int, events: list) -> int:
    """Хохирол учруулна. HP-ээс бодитоор хасагдсан хэмжээг буцаана (drain-д)."""
    absorbed = min(dst.shield, amount)
    dst.shield -= absorbed
    dmg = amount - absorbed
    lost = min(dst.hp, dmg)
    dst.hp = max(0, dst.hp - dmg)
    events.append({"type": "damage", "src": src.uid, "dst": dst.uid, "amount": dmg,
                   "absorbed": absorbed, "hp": dst.hp})
    if dst.hp == 0:
        dst.alive = False
        dst.shield = 0
        dst.taunted_by, dst.taunt_turns, dst.cursed = None, 0, 0
        events.append({"type": "death", "unit": dst.uid})
    return lost


def _check_winner(state: GameState, events: list):
    if state.winner:
        return
    boss = state.boss
    if (boss is not None and not boss.alive) or (boss is None and not state.alive_units(DEMONS)):
        state.winner = HEROES
    elif not state.alive_units(HEROES):
        state.winner = DEMONS
    if state.winner:
        events.append({"type": "game_over", "winner": state.winner, "round": state.round})


def _end_side_turn(state: GameState, events: list):
    side = state.side_to_act
    for u in state.alive_units(side):
        if u.cursed:
            u.cursed -= 1
        if u.taunt_turns:
            u.taunt_turns -= 1
            if u.taunt_turns == 0:
                u.taunted_by = None
    if side == DEMONS:
        for c in list(state.walls):
            state.walls[c] -= 1
            if state.walls[c] <= 0:
                del state.walls[c]
    events.append({"type": "turn_end", "side": side, "round": state.round})

    new = other_side(side)
    state.side_to_act = new
    if new == HEROES:
        state.round += 1
        if state.round > MAX_ROUNDS:
            state.winner = "draw"
            events.append({"type": "game_over", "winner": "draw", "round": state.round - 1})
            return
    for u in state.units.values():
        u.acted = False
        if u.side == new:
            for s in u.cooldowns:
                if u.cooldowns[s] > 0:
                    u.cooldowns[s] -= 1
    events.append({"type": "turn_start", "side": new, "round": state.round})
