"""experiments/ — тулаан гүйцэтгэгч, A/B, тэнцвэрийн хувилбар, тайлан."""

import csv
import subprocess
import sys

import pytest

from engine import HEROES, GameState
from engine import constants as C
from experiments import (BALANCE_VARIANTS, balance_sweep, make_boss_factory, patched_constants,
                         run_ab, run_games, train_profiles)
from experiments.report import ab_metrics, markdown_report, paired_bootstrap, summarize, write_csv

PLACEHOLDER = make_boss_factory("placeholder")


def test_run_games_is_deterministic_and_rotates_bots():
    rows = run_games(6, PLACEHOLDER)
    assert [r.bot for r in rows] == ["random", "greedy", "healer_reliant", "mage_reliant",
                                     "aggressive", "cautious"]
    assert [r.seed for r in rows] == list(range(6))
    again = run_games(6, PLACEHOLDER)
    key = lambda r: (r.winner, r.rounds, r.boss_hp, r.first_dead, r.first_dead_round)  # noqa
    assert [key(r) for r in rows] == [key(r) for r in again]
    for r in rows:
        assert r.winner in ("heroes", "demons", "draw")
        assert (r.first_dead is None) == (r.first_dead_round is None)


def test_patched_constants_changes_game_and_restores():
    hp0 = C.UNIT_TYPES["demon_lord"].hp
    cd0 = C.SKILLS["hellfire"].cooldown
    knight0 = C.UNIT_TYPES["knight"]
    changes = BALANCE_VARIANTS["boss_hp_x0.8"] + BALANCE_VARIANTS["hellfire_cd+1"]
    with patched_constants(changes) as applied:
        assert GameState.new_game().boss.max_hp == round(hp0 * 0.8)
        assert C.SKILLS["hellfire"].cooldown == cd0 + 1
        assert applied == {"demon_lord.hp": (hp0, round(hp0 * 0.8)),
                           "hellfire.cooldown": (cd0, cd0 + 1)}
    assert C.UNIT_TYPES["demon_lord"].hp == hp0 and C.SKILLS["hellfire"].cooldown == cd0
    with pytest.raises(RuntimeError):
        with patched_constants(BALANCE_VARIANTS["heroes_hp_x1.25"]):
            raise RuntimeError("алдаа гарсан ч сэргээнэ")
    assert C.UNIT_TYPES["knight"] is knight0                        # яг анхны объект
    assert GameState.new_game().units["knight"].max_hp == knight0.hp


def test_ab_pairs_same_seeds_and_profiles():
    profiles = train_profiles(PLACEHOLDER, bots=("greedy", "cautious"), games_per_bot=1)
    assert set(profiles) == {"greedy", "cautious"}
    assert all("target_priority" in p for p in profiles.values())
    rows = run_ab(4, PLACEHOLDER, profiles, bots=("greedy", "cautious"))
    a = [r for r in rows if r.group == "A"]
    b = [r for r in rows if r.group == "B"]
    assert [r.seed for r in a] == [r.seed for r in b] and len(a) == 4
    assert all(r.top_priority in ("knight", "mage", "healer") for r in a + b)
    for name, va, vb, d, lo, hi in ab_metrics(rows):     # түр босс профайлыг тоодоггүй → ялгаа 0
        assert va == vb and d == 0 and lo == 0 and hi == 0, name


def test_ab_uses_profile_in_boss():
    seen = []

    def factory(profile, seed):
        seen.append(profile)
        return PLACEHOLDER(profile, seed)

    profiles = {"greedy": {"target_priority": {"healer": 2.0}, "habits": []}}
    run_ab(2, factory, profiles, bots=("greedy",))
    assert seen[:2] == [profiles["greedy"]] * 2 and seen[2:] == [None, None]


def test_paired_bootstrap_and_summary():
    d, lo, hi = paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0])
    assert d == 1 and lo == 1 and hi == 1
    d, lo, hi = paired_bootstrap([0, 2, 0, 2, 1, 1], [1, 1, 1, 1, 1, 1])
    assert d == 0 and lo <= 0 <= hi
    rows = run_games(3, PLACEHOLDER)
    s = summarize(rows)
    assert s["n"] == 3 and abs(s["hero_win"] + s["boss_win"] + s["draw"] - 1) < 1e-9


def test_balance_sweep_and_report(tmp_path):
    variants = {"base": [], "boss_hp_x0.7": BALANCE_VARIANTS["boss_hp_x0.7"]}
    rows, applied = balance_sweep(2, PLACEHOLDER, variants, bots=("greedy",))
    assert [r.variant for r in rows] == ["base", "base", "boss_hp_x0.7", "boss_hp_x0.7"]
    assert applied["base"] == {} and "demon_lord.hp" in applied["boss_hp_x0.7"]
    weak = [r for r in rows if r.variant == "boss_hp_x0.7"]
    assert all(r.boss_hp <= round(C.UNIT_TYPES["demon_lord"].hp * 0.7) for r in weak)
    base = run_games(2, PLACEHOLDER, bots=("greedy",))
    profiles = train_profiles(PLACEHOLDER, bots=("greedy",), games_per_bot=1)
    ab = run_ab(2, PLACEHOLDER, profiles, bots=("greedy",))
    md = markdown_report({"date": "2026-11-09", "boss": "placeholder", "bots": ("greedy",),
                          "train_games": 1}, base, ab, profiles, rows, applied)
    for heading in ("## 1.", "## 2. A/B", "## 3.", "## Дүгнэлт", "boss_hp_x0.7"):
        assert heading in md
    path = write_csv(base + ab + rows, tmp_path / "g.csv")
    with open(path, encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 10


def test_cli_with_placeholder(tmp_path):
    out = tmp_path / "res"
    code = subprocess.run([sys.executable, "-m", "experiments", "--games", "2", "--boss",
                           "placeholder", "--train-games", "1", "--skip", "balance",
                           "--out", str(out)], capture_output=True, encoding="utf-8",
                          errors="replace")
    assert code.returncode == 0, code.stderr
    assert (out / "REPORT.md").is_file() and (out / "games.csv").is_file()
    assert (out / "profiles.json").is_file()


def test_experiments_do_not_import_pygame():
    code = "import sys, experiments, experiments.report; print('pygame' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_heroes_win_counts_use_engine_winner():
    rows = run_games(6, PLACEHOLDER)
    s = summarize(rows)
    assert s["hero_win"] == sum(r.winner == HEROES for r in rows) / 6
