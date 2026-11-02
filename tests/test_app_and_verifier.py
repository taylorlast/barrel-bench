import json
from types import SimpleNamespace

import pytest

import verify
from environment import Barrel


def app(seed=1, variant="standard"):
    a = Barrel()
    a.reset({"seed": seed, "variant": variant})
    return a


def score(a, expected=None):
    return verify.check(SimpleNamespace(state=a.snapshot(), expected=expected, usage=None))


def test_reset_and_views():
    a = Barrel()
    assert a.reset({"seed": 1}).startswith("You run the distillery")
    assert isinstance(a.brief(fmt="json"), (dict, str))
    with pytest.raises(ValueError):
        a.reset({"seed": 1, "variant": "bogus"})


def test_refused_action_not_logged():
    a = app()
    with pytest.raises(ValueError):
        a.bottle("nope", 1, 4)
    assert a.state.log == []


def test_idle_scores_zero_and_vetoed_scores_zero():
    a = app()
    assert score(a).score == 0
    a2 = app()
    b = next(iter(a2._sim.batches))
    a2.sell_casks(b, 1, "premium")
    if a2.state.violations:
        assert score(a2).score == 0


def test_normalization():
    assert verify.normalized(10, 10, 20) == 0
    assert verify.normalized(15, 10, 20) == 0.5
    assert verify.normalized(30, 10, 20) == 1
    assert verify.normalized(0, 10, 20) == 0


def test_rebuild_replays_log():
    a = app()
    a.fill(50, fmt="json")
    a.end_quarter()
    snap = a.snapshot()
    b = Barrel()
    b.state = type(a.state)(**{**a.state.model_dump()})
    b._sim = None
    assert b._sim_ready().t == a._sim.t
