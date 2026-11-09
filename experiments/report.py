"""Туршилтын дүнг нэгтгэх: хүснэгт, bootstrap 95% итгэх интервал, CSV, Markdown тайлан (монгол)."""

from __future__ import annotations

import csv
import dataclasses
import random
import statistics
from pathlib import Path

from engine import DEMONS, HEROES

from .runner import BALANCE_VARIANTS

BOT_LABELS = {"random": "Санамсаргүй", "greedy": "Тэнцвэртэй (greedy)",
              "healer_reliant": "Healer-т найддаг", "mage_reliant": "Mage-т найддаг",
              "aggressive": "Түрэмгий", "cautious": "Болгоомжтой",
              "human": "Хүн (leave-one-game-out)"}
TARGET_HERO_WIN = (0.35, 0.60)    # жишээ зорилт: баатрууд 35–60% ялах (PM шийднэ)


def _mean(xs):
    return statistics.fmean(xs) if xs else float("nan")


def summarize(rows: list) -> dict:
    n = len(rows)
    hero_wins = sum(r.winner == HEROES for r in rows)
    boss_wins = sum(r.winner == DEMONS for r in rows)
    boss_win_rounds = [r.rounds for r in rows if r.winner == DEMONS]
    return {"n": n, "hero_win": hero_wins / n if n else 0.0, "boss_win": boss_wins / n if n else 0.0,
            "draw": (n - hero_wins - boss_wins) / n if n else 0.0,
            "rounds": _mean([r.rounds for r in rows]),
            "boss_win_rounds": _mean(boss_win_rounds),
            "boss_hp": _mean([r.boss_hp for r in rows]),
            "heroes_alive": _mean([r.heroes_alive for r in rows]),
            "seconds": _mean([r.seconds for r in rows])}


def paired_bootstrap(a: list, b: list, iters: int = 4000, seed: int = 0) -> tuple:
    """Хос утгуудын (a_i - b_i) дундаж ба bootstrap 95% интервал."""
    diffs = [x - y for x, y in zip(a, b)]
    if not diffs:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    k = len(diffs)
    means = sorted(statistics.fmean(rng.choices(diffs, k=k)) for _ in range(iters))
    return statistics.fmean(diffs), means[int(0.025 * iters)], means[int(0.975 * iters) - 1]


def ab_metrics(rows: list) -> list:
    """A/B хос харьцуулалт: [(нэр, A, B, ялгаа, доод, дээд), ...]."""
    a = sorted((r for r in rows if r.group == "A"), key=lambda r: r.seed)
    b = sorted((r for r in rows if r.group == "B"), key=lambda r: r.seed)
    metrics = [
        ("Боссын ялалт (%)", lambda r: 100.0 * (r.winner == DEMONS)),
        ("Тулааны урт (round)", lambda r: r.rounds),
        ("Боссын үлдсэн HP", lambda r: r.boss_hp),
        ("Амьд үлдсэн баатар", lambda r: r.heroes_alive),
        ("«Гол бай» анх унасан (%)",
         lambda r: 100.0 * (r.first_dead is not None and r.first_dead == r.top_priority)),
    ]
    out = []
    for name, f in metrics:
        va, vb = [f(r) for r in a], [f(r) for r in b]
        diff, lo, hi = paired_bootstrap(va, vb)
        out.append((name, _mean(va), _mean(vb), diff, lo, hi))
    return out


def write_csv(rows: list, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [f.name for f in dataclasses.fields(rows[0])] if rows else []
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(dataclasses.asdict(r))
    return path


def _pct(x):
    return f"{100 * x:.0f}%"


def _bot_table(rows: list) -> list:
    lines = ["| Bot | Тулаан | Баатрууд ялсан | Босс ялсан | Дундаж round | Боссын үлдсэн HP | Амьд баатар |",
             "|---|---|---|---|---|---|---|"]
    bots = list(dict.fromkeys(r.bot for r in rows))
    for bot in bots + ["**Нийт**"]:
        sub = rows if bot == "**Нийт**" else [r for r in rows if r.bot == bot]
        s = summarize(sub)
        lines.append(f"| {BOT_LABELS.get(bot, bot)} | {s['n']} | {_pct(s['hero_win'])} | "
                     f"{_pct(s['boss_win'])} | {s['rounds']:.1f} | {s['boss_hp']:.0f} | "
                     f"{s['heroes_alive']:.2f} |")
    return lines


def predictor_section(pred: dict) -> list:
    """4-р хэсэг: дараагийн нүүдэл таамаглагч (PDF-ийн шаардлага 4: top-3 ≥ 60%)."""
    L = ["## 4. Дараагийн нүүдэл таамаглагч (`learning/predictor.py`)", "",
         f"Анги = (ур чадвар, бай). Bot бүрийн {pred['games_per_bot']} тулааны log-ийн эхний 70%-иар "
         "сургаж, үлдсэн 30%-иар хэмжсэн. «Санамсаргүй» — боломжит ангиас санамсаргүй тааварласан "
         "бол хүлээгдэх хувь, «Heuristic» — сургаагүй загвар (зөвхөн шууд үр ашиг).", "",
         "| Бүлэг | Тест шийдвэр | Анги/шийдвэр | Санамсаргүй top-1 / top-3 | Heuristic top-1 / top-3 "
         "| **Сургасан top-1 / top-3** |",
         "|---|---|---|---|---|---|"]
    for r in pred["rows"]:
        name = BOT_LABELS.get(r["group"], r["group"])
        if r["group"] == "all_bots":
            name = "**Бүх bot нийлсэн**"
        L.append(f"| {name} | {r['decisions']} | {r['classes']:.1f} | {_pct(r['chance1'])} / "
                 f"{_pct(r['chance3'])} | {_pct(r['heur1'])} / {_pct(r['heur3'])} | "
                 f"**{_pct(r['top1'])} / {_pct(r['top3'])}** |")
    t = pred["timing"]
    human = [r for r in pred["rows"] if r["group"].startswith("human")]
    allb = next((r for r in pred["rows"] if r["group"] == "all_bots"), pred["rows"][0])
    ok3 = all(r["top3"] >= 0.6 for r in pred["rows"])
    L += ["", f"- **Хурд:** MCTS-ийн rollout-ийнх шиг 6 нүдний түүвэр (дунджаар {t['cands']:.0f} "
              f"нүүдэл) дээр `predict()` — median **{t['median_ms']:.3f} мс**, p95 "
              f"{t['p95_ms']:.3f} мс (шаардлага ≤ 0.2 мс).",
          f"- **Шалгуур (top-3 ≥ 60%)**: {'бүх бүлэгт хангасан' if ok3 else 'зарим бүлэгт хангаагүй'}. "
          f"⚠️ Гэхдээ (ур чадвар, бай) гэсэн ангиар шийдвэр бүрт дунджаар {allb['classes']:.1f} "
          f"л анги байдаг (Галт бөмбөгийн бүх бай, хөдөлгөөний бүх нүд нэг анги) тул санамсаргүй "
          f"таавар ч top-3-т {_pct(allb['chance3'])} хүрдэг — энэ шалгуур бараг автоматаар хангагдана. "
          f"Бодит ялгааг top-1 харуулна: санамсаргүй {_pct(allb['chance1'])} → heuristic "
          f"{_pct(allb['heur1'])} → сургасан **{_pct(allb['top1'])}** (бүх bot нийлсэн)."]
    if human:
        h = human[0]
        L.append(f"- **Хүний log** (`{pred['human_logs']}`, {h['train_games'] + 1} тоглолт, "
                 f"leave-one-game-out): top-1 {_pct(h['top1'])}, top-3 {_pct(h['top3'])} — "
                 "тоглолт цөөн тул итгэл бага; тоглох тусам нэмэгдэнэ.")
    else:
        L.append(f"- Хүний log (`{pred['human_logs']}`) 2-оос цөөн тоглолттой тул хэмжээгүй.")
    L.append("")
    return L


def markdown_report(meta: dict, base_rows: list, ab_rows: list, profiles: dict,
                    balance_rows: list, balance_applied: dict, predictor: dict | None = None) -> str:
    L = [f"# Туршилтын тайлан — {meta.get('date', '')}", "",
         f"Босс: **{meta.get('boss')}** · тулаан бүрийн seed тогтмол (давтагдана) · "
         f"bot-ууд: {', '.join(BOT_LABELS.get(b, b) for b in meta.get('bots', []))}.",
         "Бүх тулаан `bots.play_match`-аар engine дээр тоглогдсон. Bot-ууд хүн биш тул дүн нь "
         "хүний тоглолтоос зөрж болно (ихэвчлэн хүн bot-оос сайн тоглоно).", ""]

    s = summarize(base_rows)
    L += [f"## 1. Үндсэн туршилт — суралцаагүй босс, {s['n']} тулаан", ""]
    L += _bot_table(base_rows)
    L += ["", f"Баатрууд нийт **{_pct(s['hero_win'])}** ялсан, босс **{_pct(s['boss_win'])}**. "
              f"Нэг тулаан дунджаар {s['rounds']:.1f} round, тооцоолол {s['seconds']:.2f} сек.", ""]

    if ab_rows:
        n = len(ab_rows) // 2
        L += [f"## 2. A/B — суралцсан (A) vs суралцаагүй (B) босс, {n} + {n} тулаан", "",
              f"A бүлэгт босс тухайн bot-ын урьдчилсан {meta.get('train_games', 5)} тулааны log-оос "
              "гаргасан профайлтай "
              "(`learning/profile.py`). Хоёр бүлэг яг ижил seed-ээр тоглосон тул ялгаа нь зөвхөн "
              "профайлаас үүдэлтэй. Ялгааны 95% интервал — paired bootstrap (4000 давталт).", "",
              "| Хэмжүүр | A (суралцсан) | B (суралцаагүй) | A − B | 95% интервал |",
              "|---|---|---|---|---|"]
        for name, va, vb, d, lo, hi in ab_metrics(ab_rows):
            sig = " ✱" if (lo > 0 or hi < 0) else ""
            L.append(f"| {name} | {va:.1f} | {vb:.1f} | {d:+.1f}{sig} | [{lo:+.1f}, {hi:+.1f}] |")
        L += ["", "✱ — интервал 0-ийг агуулахгүй (статистикийн хувьд ач холбогдолтой ялгаа).",
              "«Гол бай» — профайлын хамгийн өндөр `target_priority`-тэй баатар.", "",
              "Bot бүрийн профайл:", "", "| Bot | target_priority | Танисан зуршил |", "|---|---|---|"]
        for bot, prof in profiles.items():
            pr = ", ".join(f"{k} {v}" for k, v in prof["target_priority"].items())
            habits = "; ".join(prof["habits"]) or "—"
            L.append(f"| {BOT_LABELS.get(bot, bot)} | {pr} | {habits} |")
        L.append("")

    if balance_rows:
        per = len(balance_rows) // max(1, len(balance_applied))
        L += [f"## 3. Тэнцвэрийн хувилбарууд — суралцаагүй босс, хувилбар бүрт {per} тулаан", "",
              "`engine/constants.py` өөрчлөгдөөгүй — утгыг зөвхөн туршилтын процесст түр сольсон.", "",
              "| Хувилбар | Өөрчлөлт | Баатрууд ялсан | Дундаж round | Боссын үлдсэн HP |",
              "|---|---|---|---|---|"]
        best, best_gap = None, None
        lo_t, hi_t = TARGET_HERO_WIN
        mid = (lo_t + hi_t) / 2
        in_band = []
        for name, applied in balance_applied.items():
            sub = [r for r in balance_rows if r.variant == name]
            s = summarize(sub)
            change = ", ".join(f"`{k}` {a}→{b}" for k, (a, b) in applied.items()) or "—"
            L.append(f"| {name} | {change} | {_pct(s['hero_win'])} | {s['rounds']:.1f} | "
                     f"{s['boss_hp']:.0f} |")
            if name == "base":
                continue
            if lo_t <= s["hero_win"] <= hi_t:
                in_band.append(f"{name} ({_pct(s['hero_win'])})")
            gap = abs(s["hero_win"] - mid)             # зорилтын төвөөс зай
            if best_gap is None or gap < best_gap:
                best, best_gap = name, gap
        L.append("")
        base = summarize([r for r in balance_rows if r.variant == "base"])
        L += ["## Дүгнэлт (PM-д)", ""]
        if base["hero_win"] < lo_t:
            L.append(f"- Одоогийн утгаар баатрууд зөвхөн {_pct(base['hero_win'])} ялж байна — "
                     f"жишээ зорилт ({_pct(lo_t)}–{_pct(hi_t)})-оос доогуур, тоглоом хэт хэцүү.")
        elif base["hero_win"] > hi_t:
            L.append(f"- Одоогийн утгаар баатрууд {_pct(base['hero_win'])} ялж байна — хэт амархан.")
        else:
            L.append(f"- Одоогийн утгаар баатрууд {_pct(base['hero_win'])} ялж байна — зорилтод багтана.")
        if in_band:
            L.append(f"- Зорилтод багтсан хувилбарууд: {', '.join(in_band)}.")
        else:
            L.append("- Туршсан хувилбаруудын аль нь ч зорилтод багтаагүй — илүү хүчтэй өөрчлөлт хэрэгтэй.")
        if best:
            L.append(f"- Зорилтын төвд ({_pct(mid)}) хамгийн ойр нь **{best}** "
                     f"({', '.join(f'`{k}` {a}→{b}' for k, (a, b) in balance_applied[best].items())}).")
        L.append("- Анхааруулга: зөвхөн боссын HP эсвэл зөвхөн Хар дөлийг багасгах нь хангалтгүй "
                 "(≤2%) — баатруудын амьд үлдэх чадвар ба боссын HP-ийг хамт өөрчлөх шаардлагатай.")
        L.append("- Эцсийн утгыг PM шийднэ (`engine/constants.py`); хүн тоглогчоор давхар шалгах нь зүйтэй.")
    if predictor:
        L += [""] + predictor_section(predictor)
    return "\n".join(L) + "\n"


__all__ = ["summarize", "paired_bootstrap", "ab_metrics", "write_csv", "markdown_report",
           "BALANCE_VARIANTS"]
