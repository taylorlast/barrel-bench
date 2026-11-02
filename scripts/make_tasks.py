"""Write tasks/*/task.yaml with each world's anchors as the hidden Task.expected answer key.

Run after any change to barrel_sim:  .venv/bin/python scripts/make_tasks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "environments" / "barrel"))
from barrel_sim.policies import references  # noqa: E402

TASKS = [
    ("barrel-dev-1", 1, "standard", "dev"), ("barrel-dev-2", 2, "standard", "dev"),
    ("barrel-dev-glut-3", 3, "glut", "dev"),
    ("barrel-test-101", 101, "standard", "test"), ("barrel-test-102", 102, "standard", "test"),
    ("barrel-test-103", 103, "standard", "test"), ("barrel-test-glut-104", 104, "glut", "test"),
    ("barrel-test-mature-105", 105, "mature", "test"),
]


def main() -> None:
    instruction = (ROOT / "scripts" / "instruction.md").read_text()
    for name, seed, variant, split in TASKS:
        ref = references(seed, variant)
        d = ROOT / "tasks" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "instruction.md").write_text(instruction)
        body = {
            "name": name, "version": "0.1.0", "instructions": "instruction.md", "environment": "barrel",
            "verifiers": ["distillery-outcome"],
            "initial_state": {"seed": seed, "variant": variant, "split": split, "broker_voice": "scripted"},
            "expected": {k: round(v, 2) for k, v in ref.items()},
        }
        head = ("# Task: one 10-year Barrel world. The seed pins the world, so every attempt faces the\n"
                "# same demand cycle, shocks, brokers and casks. `expected` is the hidden answer key\n"
                "# (Verifiers only): baseline and oracle anchors, written by scripts/make_tasks.py.\n")
        (d / "task.yaml").write_text(head + yaml.safe_dump(body, sort_keys=False))
        print(name, {k: round(v / 1e6, 2) for k, v in ref.items()})


if __name__ == "__main__":
    main()
