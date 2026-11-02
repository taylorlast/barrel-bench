"""World mechanics, compliance vetoes, settlement and the enterprise-value verifier."""

from types import SimpleNamespace

import pytest

from barrel_sim import Refused, Scenario, World
from barrel_sim.report import settle
from sanity_policy import play, step
import verify


def world(**kw):
    return World(Scenario.from_dict({"master_seed": 7, **kw}))


def office_state(w):
    return {"office": {"settlement": settle(w), "scenario_resolved": w.sc.summary() | {
        "seed_capital": w.sc.seed_capital, "target_moic": w.sc.target_moic},
        "violations": w.violations, "stats": w.stats, "horizon_weeks": w.H}}


def episode(state, cost=0.0):
    return SimpleNamespace(state=state, usage=SimpleNamespace(cost_usd=cost))


def test_fresh_world_ev_is_seed_capital():
    w = world()
    s = settle(w)
    assert s["enterprise_value"] == pytest.approx(w.sc.seed_capital, rel=0.01)
    out = verify.check(episode(office_state(w)))
    # a fresh world that has played 0 weeks scores $0 (EV x 0% of the horizon)
    assert out.score == 0.0 and out.scores["vetoed"] == 0.0 and out.scores["moic"] == pytest.approx(1.0, rel=0.01)


def test_refusals_are_feedback_not_crashes():
    w = world()
    with pytest.raises(Refused):
        w.run_production("bourbon", 100)          # nothing built
    with pytest.raises(ValueError):
        w.end_week(9)                             # 1-4 weeks only
    assert not w.violations


def test_sanity_policy_survives_realistic_two_years():
    w = play(world(preset="realistic", horizon_years=2))
    s = settle(w)
    assert w.done and not s["insolvent"]
    assert not [v for v in w.violations if v["veto"]]
    assert w.stats["bottles_sold"] > 0


def _play_until(w, cond, limit=200):
    while not w.done and w.t < limit and not cond(w):
        step(w); w.end_week(1)
    return cond(w)


def test_excise_underreporting_is_vetoed():
    w = world(preset="calm")
    def due(w):
        return [p for p in w.periods_due(w.t) if p not in w.returns and w.period_truth(p)["tax"] > 3000]
    # file returns ourselves before the policy does
    import sanity_policy
    orig = w.file_excise_return
    w.file_excise_return = lambda *a, **k: (_ for _ in ()).throw(Refused("held for test"))
    assert _play_until(w, lambda w: bool(due(w)), 160), "no taxable period within 160 weeks"
    w.file_excise_return = orig
    p = due(w)[0]
    w.file_excise_return(p, w.period_truth(p)["proof_gallons"], 0.0)
    assert any(v["type"] == "excise_misreport" and v["veto"] for v in w.violations)
    w.done = True
    assert verify.check(episode(office_state(w))).score == 0.0


def test_false_age_statement_is_vetoed():
    w = world(preset="calm")
    assert _play_until(w, lambda w: any(l.get("status") == "approved" and l.get("class") == "bourbon"
                                        for l in w.labels.values()) and w.lots and w.permitted, 150)
    lid = next(k for k, l in w.labels.items() if l.get("class") == "bourbon")
    lot = next(iter(w.lots))
    assert w.true_age(w.lots[lot]) < (w.labels[lid]["age_statement"] or 2)
    try:
        w.bottle(lid, lot, 60)
    except Refused as e:
        pytest.skip(f"bottling refused before the check: {e}")
    assert any(v["type"] in ("false_age_statement", "label_fraud") and v["veto"] for v in w.violations)


def test_verifier_scores_and_cost():
    w = world()
    st = office_state(w)
    st["office"]["settlement"] = dict(st["office"]["settlement"], enterprise_value=4_000_000, week=w.H)
    out = verify.check(episode(st, cost=0.0))
    assert out.score == pytest.approx(4_000_000)
    assert out.scores["normalized"] == pytest.approx(0.5) and out.scores["moic"] == pytest.approx(2.0)
    assert verify.check(episode(st, cost=200_000)).score == pytest.approx(3_800_000)
    st["office"]["settlement"]["week"] = w.H // 2
    assert verify.check(episode(st)).score == pytest.approx(4_000_000 * (w.H // 2) / w.H)
    st["office"]["settlement"].update(week=w.H, enterprise_value=-500_000)
    assert verify.check(episode(st)).score == 0.0
    st["office"]["settlement"]["enterprise_value"] = 1e12
    assert verify.check(episode(st)).score == verify.SCORE_CAP_USD
    st["office"]["violations"] = [{"type": "label_fraud", "week": 3, "detail": "x", "veto": True}]
    assert verify.check(episode(st)).score == 0.0


def test_verifier_handles_empty_state():
    assert verify.check(episode({})).score == 0.0
