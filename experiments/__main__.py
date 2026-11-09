"""python -m experiments — 100 тулаан, A/B, тэнцвэрийн хувилбар, таамаглагч → CSV + Markdown."""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from .report import markdown_report, write_csv
from .runner import (BALANCE_VARIANTS, BOT_NAMES, balance_sweep, make_boss_factory, run_ab,
                     run_games, train_profiles)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m experiments")
    p.add_argument("--games", type=int, default=100, help="туршилт бүрийн тулааны тоо")
    p.add_argument("--boss", choices=("eval", "mcts", "placeholder"), default="eval")
    p.add_argument("--mcts-iters", type=int, default=400,
                   help="mcts горимд шийдвэр бүрийн давталт (хугацааны оронд — давтагдахуйц)")
    p.add_argument("--train-games", type=int, default=5, help="профайл гаргах bot бүрийн тулаан")
    p.add_argument("--predictor-games", type=int, default=30,
                   help="таамаглагчийн туршилтад bot бүрийн тулаан (70% сургалт / 30% тест)")
    p.add_argument("--human-logs", default="logs",
                   help="хүний тоглолтын log (leave-one-game-out); байхгүй бол алгасна")
    p.add_argument("--skip", nargs="*", default=[],
                   choices=("base", "ab", "balance", "predictor"))
    p.add_argument("--out", default="experiments/results")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    kw = {"max_iters": args.mcts_iters} if args.boss == "mcts" else {}
    try:
        make_boss = make_boss_factory(args.boss, **kw)
    except ModuleNotFoundError as e:
        print(f"Боссын AI олдсонгүй ({e}). ai/ main-д орсны дараа ажиллуулна уу, "
              f"эсвэл --boss placeholder.", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    def step(title):
        print(f"[{time.perf_counter() - t0:6.1f}s] {title}", flush=True)

    base = ab = balance = []
    profiles, applied = {}, {}
    predictor = None
    if "base" not in args.skip:
        step(f"1. Үндсэн туршилт: {args.games} тулаан")
        base = run_games(args.games, make_boss, BOT_NAMES, seed0=0, experiment="base")
    if "ab" not in args.skip:
        step(f"2. Профайл сургах: bot бүрт {args.train_games} тулаан")
        profiles = train_profiles(make_boss, BOT_NAMES, games_per_bot=args.train_games)
        step(f"2. A/B: {args.games} + {args.games} тулаан")
        ab = run_ab(args.games, make_boss, profiles, BOT_NAMES, seed0=0)
    if "balance" not in args.skip:
        step(f"3. Тэнцвэр: {len(BALANCE_VARIANTS)} хувилбар × {args.games} тулаан")
        balance, applied = balance_sweep(args.games, make_boss, BALANCE_VARIANTS, BOT_NAMES)
    if "predictor" not in args.skip:
        from learning.predictor import MovePredictor, save_predictor

        from .predictor_eval import bot_logs, human_eval, split_eval, timing
        step(f"4. Таамаглагч: bot бүрт {args.predictor_games} тулааны log")
        logs = bot_logs(make_boss, BOT_NAMES, games_per_bot=args.predictor_games)
        rows_p = split_eval(logs)
        human = human_eval(args.human_logs)
        all_games = [g for games in logs.values() for g in games]
        model = MovePredictor().fit(all_games)
        save_predictor(model, out / "predictor.json")
        predictor = {"rows": rows_p + ([human] if human else []),
                     "timing": timing(all_games, model), "human_logs": args.human_logs,
                     "games_per_bot": args.predictor_games}
    step("Тайлан бичиж байна")

    rows = base + ab + balance
    write_csv(rows, out / "games.csv")
    (out / "profiles.json").write_text(json.dumps(profiles, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    meta = {"date": date.today().isoformat(), "boss": args.boss + (
        f" (max_iters={args.mcts_iters})" if args.boss == "mcts" else ""), "bots": BOT_NAMES,
        "train_games": args.train_games}
    report = markdown_report(meta, base, ab, profiles, balance, applied, predictor)
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    step(f"Дууслаа: {out / 'REPORT.md'}, {out / 'games.csv'} ({len(rows)} тулаан)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
