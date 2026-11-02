"""The economics are survivable but not trivial: a competent hand policy grows the
company in calm/realistic worlds, and harsher presets hurt it. Slow (full 7-year runs)."""

import pytest

from barrel_sim import Scenario, World
from barrel_sim.report import settle
from sanity_policy import play


def ev(preset, seed):
    w = play(World(Scenario.from_dict({"preset": preset, "master_seed": seed})))
    return settle(w)


@pytest.mark.parametrize("seed", [1, 2])
def test_realistic_is_survivable_but_not_trivial(seed):
    s = ev("realistic", seed)
    assert not s["insolvent"]
    assert 2_000_000 < s["enterprise_value"] < 6_000_000  # grows, but far from target in every world


def test_crisis_is_harder_than_calm():
    assert ev("crisis", 1)["enterprise_value"] < ev("calm", 1)["enterprise_value"]


def test_score_range_covers_calibration():
    import verify, yaml
    from pathlib import Path
    top = max(ev(p, 1)["enterprise_value"] for p in ("calm", "realistic"))
    for b in Path(__file__).resolve().parents[1].glob("benchmarks/*/benchmark.yaml"):
        lo, hi = yaml.safe_load(b.read_text())["scoring"]["score_range"]
        assert lo == 0 and hi == verify.SCORE_CAP_USD and top < hi / 10
