import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _find_plural_cli():
    """Locate the plural CLI portably."""
    found = shutil.which("plural")
    if found:
        return Path(found)
    candidate = Path(sys.executable).parent / "plural"
    if candidate.exists():
        return candidate
    return None


PLURAL = _find_plural_cli()


def test_vendor_copy_in_sync():
    assert filecmp.cmp(ROOT / "environments/barrel/barrel_sim/playbook.py",
                       ROOT / "harnesses/barrel-scripted/vendor/playbook.py", shallow=False)


def test_runtime_timeout_above_max_seconds():
    env = yaml.safe_load((ROOT / "environments/barrel/environment.yaml").read_text())
    assert env["runtime"]["timeout_seconds"] > env["limits"]["max_seconds"]
    assert env["limits"].get("max_turns") is None


@pytest.mark.parametrize("task", sorted(p.name for p in (ROOT / "tasks").iterdir()))
def test_expected_matches_references(task):
    from barrel_sim.policies import references
    t = yaml.safe_load((ROOT / "tasks" / task / "task.yaml").read_text())
    r = references(t["initial_state"]["seed"], t["initial_state"]["variant"])
    for k, v in t["expected"].items():
        assert abs(r[k] - v) < 1.0, (task, k)


def test_harness_maps_playbook_args_to_app_tools():
    """Regression: playbook says batch=/offer=, the App tools take batch_id/offer_id."""
    import inspect
    import harness
    from environment import Barrel
    for k, v in harness._APP_ARGS.items():
        assert any(v in inspect.signature(getattr(Barrel, n)).parameters for n in ("bottle", "buy_lot"))


@pytest.mark.parametrize("kind,name", [("benchmark", "barrel"), ("benchmark", "barrel-dev"),
                                       ("verifier", "distillery-outcome"), ("harness", "barrel-scripted"),
                                       ("agent", "cellar-bot"), ("env", "barrel")])
def test_plural_validate(kind, name):
    if PLURAL is None:
        pytest.skip("plural CLI not found on PATH or next to Python executable")
    r = subprocess.run([str(PLURAL), kind, "validate", name], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
