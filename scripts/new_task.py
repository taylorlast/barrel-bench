"""Write a Barrel v2 Task. Example:

    python scripts/new_task.py barrel-test-7 --seed 7 --preset volatile --split test \
        --factor demand.volatility=2.0 --factor fire.enabled=false \
        --shock '{"week": 100, "event": "warehouse_fire", "share": 0.3}'
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _val(s: str):
    try:
        return yaml.safe_load(s)
    except yaml.YAMLError:
        return s


def write(name: str, seed: int, preset: str, split: str, years: float = 7.0, factors=None, shocks=None,
          seed_capital: float = 2_000_000, target_moic: float = 3.0, note: str = "") -> Path:
    scenario: dict = {"preset": preset, "master_seed": seed, "horizon_years": years,
                      "seed_capital": seed_capital, "target_moic": target_moic}
    if factors:
        scenario["factors"] = factors
    if shocks:
        scenario["shocks"] = shocks
    d = ROOT / "tasks" / name
    d.mkdir(parents=True, exist_ok=True)
    text = (ROOT / "scripts" / "instruction.md").read_text()
    text = text.replace("{seed_capital}", f"{seed_capital:,.0f}").replace("{years}", f"{years:g}")
    text = text.replace("{weeks}", str(int(round(years * 52))))
    (d / "instruction.md").write_text(text)
    header = (f"# Task: one Barrel v2 world ({preset}{', ' + note if note else ''}). The scenario block\n"
              "# controls every external factor: preset, master seed, per-factor seed/volatility/\n"
              "# event_rate/enabled, and scheduled shocks. Same block => same world.\n")
    body = {"name": name, "version": "0.1.0", "instructions": "instruction.md", "environment": "barrel",
            "verifiers": ["enterprise-value"],
            "initial_state": {"office": {"split": split, "scenario": scenario}}}
    (d / "task.yaml").write_text(header + yaml.safe_dump(body, sort_keys=False))
    return d


TASKS = [
    ("barrel-dev-calm-1", 1, "calm", "dev", None, None, ""),
    ("barrel-dev-realistic-2", 2, "realistic", "dev", None, None, ""),
    ("barrel-dev-volatile-3", 3, "volatile", "dev", None, None, ""),
    ("barrel-dev-shutdown-4", 4, "realistic", "dev", None,
     [{"week": 8, "event": "government_shutdown", "weeks": 10}], "shutdown during permitting"),
    ("barrel-test-realistic-101", 101, "realistic", "test", None, None, ""),
    ("barrel-test-realistic-102", 102, "realistic", "test", None, None, ""),
    ("barrel-test-volatile-103", 103, "volatile", "test", None, None, ""),
    ("barrel-test-crisis-104", 104, "crisis", "test", None, None, ""),
    ("barrel-test-fire-105", 105, "realistic", "test", {"fire": {"enabled": False}},
     [{"week": 150, "event": "warehouse_fire", "share": 0.3}], "scheduled fire"),
    ("barrel-test-boom-106", 106, "realistic", "test", {"demand": {"start_regime": "boom", "volatility": 1.5}},
     [{"week": 120, "event": "demand_regime", "regime": "glut"}], "boom then glut"),
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--preset", default="realistic")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--years", type=float, default=7.0)
    ap.add_argument("--factor", action="append", default=[], help="factor.key=value")
    ap.add_argument("--shock", action="append", default=[], help="JSON shock")
    ap.add_argument("--all", action="store_true", help="(re)write the standard Task set")
    a = ap.parse_args()
    if a.all or not a.name:
        for n, s, p, sp, f, sh, note in TASKS:
            print(write(n, s, p, sp, factors=f, shocks=sh, note=note))
    else:
        f: dict = {}
        for item in a.factor:
            k, v = item.split("=", 1)
            fac, key = k.split(".", 1)
            f.setdefault(fac, {})[key] = _val(v)
        print(write(a.name, a.seed, a.preset, a.split, a.years, f or None, [json.loads(s) for s in a.shock] or None))
