"""Тоглогчийн зуршлын профайл — тоглолтын log-оос (pygame-гүй).

Гаралт нь `BossAI(profile=...)`-д шууд өгөх dict:

    {"version": 1,
     "target_priority": {"knight": 1.0, "mage": 1.2, "healer": 1.8},   # босс хэнийг түрүүлж онилох
     "habits": ["Healer-т их найддаг (эдгээлт 74/тулаан)", ...],       # «Боссын бодол» самбарт
     "stats": {...}}                                                     # тайлан, тайлбарт

target_priority: тоглогч аль баатраас хамгийн их хамаардаг (өгсөн хохирол + эдгээлт + бамбай +
taunt-аар хамгаалсан) хувийг тооцоод, default аюулын түвшинг тэр хэмжээгээр өсгөж/бууруулна.
Өгөгдөл бага үед default-аас бага холдоно (confidence).

Ажиллуулах:  python -m learning.profile [logs] [--out logs/profile.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Optional

from engine import HEROES, dist

from .log import iter_logs

PROFILE_VERSION = 1
HERO_KINDS = ("knight", "mage", "healer")
HERO_NAMES = {"knight": "Knight", "mage": "Mage", "healer": "Healer"}

try:   # ai/ main-д орсны дараа эх утгыг тэндээс авна
    from ai.evaluate import DEFAULT_PRIORITY
except ImportError:   # ai/-ийн DEFAULT_PRIORITY-тэй ижил байх ёстой
    DEFAULT_PRIORITY = {"knight": 1.0, "mage": 1.3, "healer": 1.4}

# ---- шинжилгээний тохиргоо (тоглоомын тоо биш — профайл гаргах дүрэм) ----
TAUNT_VALUE = 10            # taunt-д орсон дайсан бүрийг 10 HP хамгаалсантай тэнцүүлнэ
PRIORITY_RANGE = (0.7, 1.6) # default-ийг хамгийн ихдээ хэд дахин өөрчлөх
FULL_CONFIDENCE_ACTIONS = 60  # ~2 тулаан: үүнээс олон хүний нүүдэл байвал бүрэн итгэнэ
MAX_GAMES = 20              # сүүлийн 20 тулаанаас суралцана
MIN_HUMAN_ACTIONS = 5       # үүнээс цөөн нүүдэлтэй log-ийг алгасна
MAX_HABITS = 4


def _new_stats() -> dict:
    return {"games": 0, "actions": 0, "value": Counter(), "damage": Counter(), "heal": Counter(),
            "shield": Counter(), "taunted": Counter(), "skills": Counter(), "acts": Counter(),
            "waits": Counter(), "early_end": 0, "dist_sum": Counter(), "dist_n": Counter(),
            "healer_behind": 0, "healer_moves": 0, "hit_boss": 0, "hit_imps": 0,
            "wins": 0, "finished": 0}


def _accumulate(st: dict, records: list, human_side: str) -> int:
    """Нэг тоглолтын хүний нүүдлүүдийг st-д нэмнэ. Хүний нүүдлийн тоог буцаана.

    Бамбайн үнэ цэнийг тавьсан хэмжээгээр биш, бодитоор шингээсэн хохирлоор (ихэнхдээ боссын
    ээлжинд) тоолно — тиймээс боссын нүүдлийн events-ийг ч уншина.
    """
    n = 0
    shielded_by = {}                                      # бамбайтай дүр -> бамбай тавьсан баатар
    for rec in records:
        if rec.get("type") == "end" and rec.get("reason") == "game_over":
            st["finished"] += 1
            st["wins"] += rec.get("winner") == human_side
        if rec.get("type") != "action":
            continue
        for ev in rec["events"]:
            if ev.get("type") == "shield":
                shielded_by[ev["dst"]] = ev["src"]
            elif ev.get("type") == "damage" and ev.get("absorbed") and ev["dst"] in shielded_by:
                st["shield"][shielded_by[ev["dst"]]] += ev["absorbed"]
        if rec.get("actor") != "human":
            continue
        n += 1
        act = rec["action"]
        units = {u["uid"]: u for u in rec["state"]["units"]}
        uid = act["unit"]
        if not uid:                                       # END_TURN
            if any(u["alive"] and not u["acted"] and u["side"] == human_side
                   for u in units.values()):
                st["early_end"] += 1
            continue
        kind = units[uid]["kind"]
        st["acts"][kind] += 1
        here = (units[uid]["x"], units[uid]["y"])
        dest = tuple(act["dest"])
        if act["skill"] is None and dest == here:
            st["waits"][kind] += 1
        if act["skill"]:
            st["skills"][act["skill"]] += 1
        boss = units["demon_lord"]
        if boss["alive"]:
            st["dist_sum"][kind] += dist(dest, (boss["x"], boss["y"]))
            st["dist_n"][kind] += 1
            if kind == "healer" and units["knight"]["alive"]:
                knight = (units["knight"]["x"], units["knight"]["y"])
                bpos = (boss["x"], boss["y"])
                st["healer_moves"] += 1
                if dist(dest, knight) <= 2 and dist(dest, bpos) > dist(knight, bpos):
                    st["healer_behind"] += 1
        for ev in rec["events"]:
            t = ev.get("type")
            src = units.get(ev.get("src"), {}).get("kind")
            if t == "damage" and src in HERO_KINDS:
                st["damage"][src] += ev["amount"]
                if ev["dst"] == "demon_lord":
                    st["hit_boss"] += ev["amount"]
                else:
                    st["hit_imps"] += ev["amount"]
            elif t == "heal" and src in HERO_KINDS:
                st["heal"][src] += ev["amount"]
            elif t == "taunt" and src in HERO_KINDS:
                st["taunted"][src] += len(ev["targets"])
    return n


def _priority(st: dict) -> dict:
    for k in HERO_KINDS:
        st["value"][k] = (st["damage"][k] + st["heal"][k] + st["shield"][k]
                          + TAUNT_VALUE * st["taunted"][k])
    total = sum(st["value"][k] for k in HERO_KINDS)
    conf = min(1.0, st["actions"] / FULL_CONFIDENCE_ACTIONS)
    out = {}
    for k in HERO_KINDS:
        base = DEFAULT_PRIORITY[k]
        if total <= 0:
            out[k] = base
            continue
        ratio = (st["value"][k] / total) * len(HERO_KINDS)      # 1.0 = дунджаар хувь нэмэр
        factor = min(PRIORITY_RANGE[1], max(PRIORITY_RANGE[0], ratio ** 0.5))
        out[k] = round(base + conf * (base * factor - base), 2)
    return out


def _habits(st: dict) -> list:
    """(хүч, мөр) жагсаалт → хүчээр эрэмбэлж эхний MAX_HABITS-ийг буцаана."""
    g = max(1, st["games"])
    found = []
    total = sum(st["value"][k] for k in HERO_KINDS) or 1
    top = max(HERO_KINDS, key=lambda k: st["value"][k])
    share = st["value"][top] / total
    if share >= 0.45:
        if top == "healer":
            amount = (st["heal"]["healer"] + st["shield"]["healer"]) / g
            found.append((share, f"Healer-т их найддаг (эдгээлт, бамбай {amount:.0f}/тулаан)"))
        else:
            found.append((share, f"{HERO_NAMES[top]}-ийн хохиролд их найддаг "
                                 f"(нийт хувь нэмрийн {share:.0%})"))
    if st["healer_moves"] >= 5:
        r = st["healer_behind"] / st["healer_moves"]
        if r >= 0.5:
            found.append((r, "Healer Knight-ийн ард нуугддаг"))

    def avg_dist(kind):
        return st["dist_sum"][kind] / st["dist_n"][kind] if st["dist_n"][kind] >= 5 else None

    kd, md = avg_dist("knight"), avg_dist("mage")
    if kd is not None and kd <= 1.8:
        found.append((0.9 - kd / 10, "Knight урд талд түрж тоглодог"))
    if md is not None and md >= 4.8:
        found.append((0.4 + md / 20, f"Mage алсаас довтолдог (боссоос дунджаар {md:.1f} нүд)"))
    hits = st["hit_boss"] + st["hit_imps"]
    if hits >= 60:
        boss_share = st["hit_boss"] / hits
        if boss_share >= 0.8:
            found.append((boss_share - 0.1, "Боссыг шууд онилдог"))
        elif boss_share <= 0.4:
            found.append((0.9 - boss_share, "Imp-үүдийг түрүүлж устгадаг"))
    taunts = st["skills"]["taunt"] / g
    if taunts >= 1.5:
        found.append((0.5 + min(taunts, 5) / 10, f"Taunt-ийг байнга ашигладаг ({taunts:.1f}/тулаан)"))
    walls = st["skills"]["ice_wall"] / g
    mage_skills = st["skills"]["ice_wall"] + st["skills"]["fireball"]
    if walls >= 2.0 and mage_skills and st["skills"]["ice_wall"] / mage_skills >= 0.4:
        found.append((0.5 + min(walls, 4) / 10, f"Мөсөн ханаар хамгаалдаг ({walls:.1f}/тулаан)"))
    acts = sum(st["acts"].values())
    if acts >= 15:
        wait_rate = sum(st["waits"].values()) / acts
        if wait_rate >= 0.3:
            found.append((wait_rate, "Ихэнхдээ байрандаа хүлээдэг"))
    if st["early_end"] / g >= 2:
        found.append((0.6, "Ээлжээ эрт дуусгадаг"))
    found.sort(key=lambda x: -x[0])
    return [text for _, text in found[:MAX_HABITS]]


def build_profile(games: Iterable[list], human_side: str = HEROES,
                  max_games: int = MAX_GAMES) -> dict:
    """Тоглолтуудын log records-оос профайл гаргана (сүүлийн `max_games`)."""
    games = [g for g in games if g]
    st = _new_stats()
    for records in games[-max_games:]:
        n = _accumulate(st, records, human_side)
        if n >= MIN_HUMAN_ACTIONS:
            st["games"] += 1
            st["actions"] += n
    priority = _priority(st)
    g = max(1, st["games"])
    total = sum(st["value"][k] for k in HERO_KINDS)
    return {
        "version": PROFILE_VERSION,
        "target_priority": priority,
        "habits": _habits(st) if st["games"] else [],
        "stats": {
            "games": st["games"], "human_actions": st["actions"],
            "finished": st["finished"], "wins": st["wins"],
            "contribution": {k: round(st["value"][k] / total, 3) if total else 0.0
                             for k in HERO_KINDS},
            "per_game": {"damage": {k: round(st["damage"][k] / g, 1) for k in HERO_KINDS},
                         "heal": round(st["heal"]["healer"] / g, 1),
                         "shield": round(st["shield"]["healer"] / g, 1),
                         "skills": {k: round(v / g, 2) for k, v in sorted(st["skills"].items())}},
        },
    }


def profile_from_logs(folder: str | os.PathLike = "logs", human_side: str = HEROES,
                      max_games: int = MAX_GAMES) -> dict:
    games = [records for _, records in iter_logs(folder)
             if records[0].get("human_side", HEROES) == human_side]
    return build_profile(games, human_side, max_games)


def save_profile(profile: dict, path: str | os.PathLike) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_profile(path: str | os.PathLike) -> Optional[dict]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m learning.profile",
                                description="Тоглолтын log-оос зуршлын профайл гаргана")
    p.add_argument("logs", nargs="?", default="logs")
    p.add_argument("--out", default=None, help="хадгалах зам (default: <logs>/profile.json)")
    args = p.parse_args(argv)
    prof = profile_from_logs(args.logs)
    out = save_profile(prof, args.out or Path(args.logs) / "profile.json")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({k: prof[k] for k in ("target_priority", "habits")}, ensure_ascii=False,
                     indent=2))
    print(f"{prof['stats']['games']} тулаан, {prof['stats']['human_actions']} нүүдлээс → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
