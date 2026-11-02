import pytest

from barrel_sim import Desk, Sim, SimError
from barrel_sim import params as P
from barrel_sim.policies import play, references

SEEDS = [(1, "standard"), (2, "standard"), (3, "glut"), (101, "standard"), (102, "standard"),
         (103, "standard"), (104, "glut"), (105, "mature")]


def test_world_is_deterministic():
    a, b = play(7, "standard", "baseline"), play(7, "standard", "baseline")
    assert a.outcome()["raw_usd"] == b.outcome()["raw_usd"]


@pytest.mark.parametrize("seed,variant", SEEDS)
def test_ordering(seed, variant):
    r = references(seed, variant)
    assert r["do_nothing_usd"] < r["baseline_usd"] < r["cellar_usd"] <= r["oracle_usd"]


def test_do_nothing_breaches_covenant_baseline_does_not():
    assert play(1, "standard", "do_nothing").stats["covenant_breaches"] > 0
    assert play(1, "standard", "baseline").stats["covenant_breaches"] == 0


def dishonest_offer(sim):
    while not sim.done:
        for o in sim.w.offers[sim.t]:
            if o["stated_age"] > o["true_age"] + 1:
                return o
        sim.end_quarter()
    raise AssertionError("no dishonest broker lot")


def test_false_age_statement_on_uninspected_lot_is_vetoed():
    sim = Sim(1)
    sim.cash = 5e7
    o = dishonest_offer(sim)
    out = sim.buy_lot(o["id"])
    label = max(a for a in P.AGES if a <= o["stated_age"])
    assert label > sim.age(sim.batches[out["batch"]])
    sim.bottle(out["batch"], 1, label)
    assert sim.violations[-1]["type"] == "false_age_statement"


def test_inspected_lot_shows_true_age():
    sim = Sim(1)
    sim.cash = 5e7
    o = dishonest_offer(sim)
    sim.inspect_offer(o["id"])
    out = sim.buy_lot(o["id"])
    assert abs(sim.shown_age(sim.batches[out["batch"]]) - o["true_age"]) < 0.3


def test_misdescription_vetoed_unless_lab_supports():
    sim = Sim(1)
    b = next(b for b in sim.batches.values() if P.grade_of(sim.true_q(b)) != "premium")
    sim.sell_casks(b["id"], 1, "premium")
    assert sim.violations and sim.violations[-1]["type"] == "misdescribed_cask"


def test_honest_sale_not_vetoed():
    sim = Sim(1)
    b = next(iter(sim.batches.values()))
    sim.sell_casks(b["id"], 1, "standard")
    assert not sim.violations


def test_refused_actions_raise():
    sim = Sim(1)
    with pytest.raises(SimError):
        sim.bottle("nope", 1, 4)
    with pytest.raises(SimError):
        sim.buy_lot("nope")
    with pytest.raises(SimError):
        sim.fill(10_000)


def test_desk_views():
    d = Desk(Sim(1))
    assert isinstance(d.call("brief"), dict)
    assert "quarter" in d.call("brief")
