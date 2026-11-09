"""Нөхцөл үнэлэх функц (WBS 3.2).

`evaluate(state)` нь төлөвийг БОССЫН талаас 0..1 оноогоор үнэлнэ:
1.0 = босс ялсан, 0.0 = баатрууд ялсан, 0.5 орчим = тэнцүү.

Оноонд нөлөөлөх зүйлс (PDF, 2-р хэсэг):
* баатруудад учруулсан хохирол — баатар бүрийн аюулын түвшнээр (priority) жинлэнэ;
* үхсэн баатар;
* боссын өөрийн HP, аюулгүй байдал;
* Imp-үүд амьд, арын эгнээ рүү дарамт үзүүлж байгаа эсэх;
* Healer хараалтай эсэх, баатруудын бамбай.

Баатруудын priority-г тоглогчийн зуршлын профайлаас (DQ) өгч болно. Жишээ нь
тоглогч Healer-т их найддаг бол Healer-ийн priority өснө → босс түүнийг түрүүлж онилно.
"""

from __future__ import annotations

import math

from engine import DEMONS, HEROES, GameState, dist

# Баатар бүрийн аюулын түвшин (default). Профайл үүнийг өөрчилнө.
DEFAULT_PRIORITY = {"knight": 1.0, "mage": 1.3, "healer": 1.4}

DEFAULT_WEIGHTS = {
    "hero_damage": 3.0,   # баатруудад учруулсан хохирол (priority-гаар жинлэсэн, 0..1)
    "hero_dead": 2.0,     # үхсэн баатрууд (priority-гаар жинлэсэн, 0..1)
    "boss_hp": 2.5,       # боссын алдсан HP (сөрөг)
    "imps": 0.3,          # амьд Imp
    "imp_pressure": 0.2,  # Imp-үүд арын эгнээнд ойр
    "curse": 0.3,         # хараалтай баатар (priority-гаар)
    "hero_shield": 0.4,   # баатруудын бамбай (сөрөг)
    "boss_safety": 0.2,   # Knight-аас холуур байх
}

# Уур хилэнгийн шат: илүү түрэмгий — хохиролд илүү, өөрийгөө хамгаалахад бага.
ENRAGE_MULT = {"hero_damage": 1.4, "hero_dead": 1.4, "boss_hp": 0.5, "boss_safety": 0.0}

SIGMOID_K = 1.0
SIGMOID_CENTER = 0.54  # эхлэх байрлалын raw оноо → 0.5 болгоно


def weights_for(state: GameState, base: dict | None = None) -> dict:
    w = dict(base or DEFAULT_WEIGHTS)
    if state.boss_enraged:
        for k, m in ENRAGE_MULT.items():
            w[k] = w[k] * m
    return w


def raw_score(state: GameState, weights: dict | None = None,
              priority: dict | None = None) -> float:
    w = weights_for(state, weights)
    pr = priority or DEFAULT_PRIORITY
    units = state.units
    boss = units["demon_lord"]

    total_p = 0.0
    dmg = dead = curse = shield = 0.0
    hero_cells = []
    for u in units.values():
        if u.side != HEROES:
            continue
        p = pr.get(u.kind, 1.0)
        total_p += p
        if not u.alive:
            dead += p
            dmg += p
            continue
        dmg += p * (1.0 - u.hp / u.max_hp)
        if u.cursed:
            curse += p
        shield += u.shield
        hero_cells.append((p, u))
    dmg /= total_p
    dead /= total_p
    curse /= total_p

    score = w["hero_damage"] * dmg + w["hero_dead"] * dead + w["curse"] * curse
    score -= w["hero_shield"] * min(1.0, shield / 60.0)
    score -= w["boss_hp"] * (1.0 - boss.hp / boss.max_hp)

    imps = [u for u in units.values() if u.kind == "imp" and u.alive]
    score += w["imps"] * len(imps) / 2.0
    if imps and hero_cells:
        best_p = max(p for p, _ in hero_cells)
        press = 0.0
        for imp in imps:
            d = min(dist(imp.pos, h.pos) for p, h in hero_cells if p == best_p)
            press += max(0.0, 1.0 - d / 10.0)
        score += w["imp_pressure"] * press / 2.0

    knight = units.get("knight")
    if knight is not None and knight.alive and boss.alive:
        score += w["boss_safety"] * min(1.0, dist(boss.pos, knight.pos) / 5.0)
    return score


def evaluate(state: GameState, weights: dict | None = None,
             priority: dict | None = None) -> float:
    """Боссын талаас 0..1 оноо."""
    if state.winner == DEMONS:
        return 1.0
    if state.winner == HEROES:
        return 0.0
    if state.winner == "draw":
        return 0.5
    r = raw_score(state, weights, priority)
    return 1.0 / (1.0 + math.exp(-SIGMOID_K * (r - SIGMOID_CENTER)))
