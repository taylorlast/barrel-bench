"""Reproducibility and per-factor isolation of the exogenous randomness."""

import pytest

from barrel_sim import FACTORS, Scenario, World
from barrel_sim.exogenous import generate
from barrel_sim.report import settle
from sanity_policy import play

# Which Paths fields each factor drives (used to check isolation).
FIELDS = {"corn": ["corn"], "energy": ["energy"], "weather": ["temp_f", "humidity"],
          "demand": ["demand", "consumer_noise"], "interest": ["prime"], "glass": ["glass_index"],
          "cooperage": ["cooperage_index"], "fire": ["fire_u"], "tourism": ["tourism"]}


def paths(d):
    return generate(Scenario.from_dict(d)).as_dict()


def test_same_scenario_same_world():
    a, b = paths({"preset": "volatile", "master_seed": 9}), paths({"preset": "volatile", "master_seed": 9})
    assert a == b


def test_different_master_seed_differs():
    assert paths({"master_seed": 1})["corn"] != paths({"master_seed": 2})["corn"]


def test_full_episode_reproducible():
    sc = {"preset": "realistic", "master_seed": 3, "horizon_years": 2}
    s1 = settle(play(World(Scenario.from_dict(sc))))
    s2 = settle(play(World(Scenario.from_dict(sc))))
    assert s1 == s2


@pytest.mark.parametrize("factor", sorted(FIELDS))
def test_factor_seed_isolated(factor):
    base = paths({"master_seed": 5})
    moved = paths({"master_seed": 5, "factors": {factor: {"seed": 777}}})
    for f in FIELDS[factor]:
        assert base[f] != moved[f], f"{factor} seed did not move {f}"
    for other, fields in FIELDS.items():
        if other != factor:
            for f in fields:
                assert base[f] == moved[f], f"{factor} seed leaked into {f}"


@pytest.mark.parametrize("factor", ["corn", "demand", "interest", "weather"])
def test_zero_volatility_and_events_is_calmer_and_isolated(factor):
    base = paths({"master_seed": 5})
    calm = paths({"master_seed": 5, "factors": {factor: {"volatility": 0.0, "event_rate": 0.0}}})
    f = FIELDS[factor][0]
    spread = lambda xs: max(xs[:300]) - min(xs[:300])
    assert spread(calm[f]) < spread(base[f]) or spread(calm[f]) < 1e-9
    for other, fields in FIELDS.items():
        if other != factor:
            for g in fields:
                assert base[g] == calm[g]


def test_disabled_fire_never_burns_but_shock_does():
    sc = Scenario.from_dict({"master_seed": 5, "preset": "volatile", "factors": {"fire": {"enabled": False}}})
    assert sc.factors["fire"].enabled is False
    forced = generate(Scenario.from_dict({"master_seed": 5, "factors": {"fire": {"enabled": False}},
                                          "shocks": [{"week": 50, "event": "warehouse_fire", "share": 0.3}]}))
    unforced = generate(sc)
    assert min(unforced.fire_u) >= 1.0 and not unforced.forced  # disabled factor: no random fires
    assert forced.forced["warehouse_fire"] == [50] and forced.fire_share[50] == 0.3


def test_presets_and_validation():
    for p in ("calm", "realistic", "volatile", "crisis"):
        assert Scenario.from_dict({"preset": p}).preset == p
    with pytest.raises(ValueError):
        Scenario.from_dict({"preset": "apocalypse"})
    with pytest.raises(ValueError):
        Scenario.from_dict({"factors": {"unicorns": {}}})
    with pytest.raises(ValueError):
        Scenario.from_dict({"shocks": [{"week": 3, "event": "meteor"}]})
    assert set(FACTORS) >= set(FIELDS)


def test_shock_schedule_changes_world():
    a = paths({"master_seed": 5})
    b = paths({"master_seed": 5, "shocks": [{"week": 30, "event": "corn_spike", "mult": 2.0, "weeks": 20}]})
    assert a["corn"][:30] == b["corn"][:30] and a["corn"][35] != b["corn"][35]
    assert a["demand"] == b["demand"]
