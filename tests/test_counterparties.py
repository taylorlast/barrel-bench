"""Procedural counterparties: seeding, hidden types, memory, voice fallback and replay."""

from pathlib import Path

import pytest

from barrel_sim import Scenario, World
from barrel_sim.exogenous import generate
from barrel_sim.parties import HIDDEN_KEYS
from barrel_sim.report import settle
from barrel_sim.voice import Voice, facts_preserved
from barrel_sim.world import Refused
from sanity_policy import play


def world(**kw):
    return World(Scenario.from_dict({"master_seed": 11, **kw}))


def _names(w):
    return [p["name"] for p in sorted(w.parties.values(), key=lambda p: p["id"])]


def test_same_seed_same_parties():
    assert _names(world()) == _names(world())


def test_different_master_seed_changes_identities():
    a = World(Scenario.from_dict({"master_seed": 1}))
    b = World(Scenario.from_dict({"master_seed": 2}))
    assert _names(a) != _names(b)
    assert a.home_state != b.home_state or any(
        a.parties[k]["name"] != b.parties[k]["name"] for k in a.parties if k in b.parties
    )


def test_parties_seed_isolated_from_factor_paths():
    base = generate(Scenario.from_dict({"master_seed": 5}))
    moved = generate(Scenario.from_dict({"master_seed": 5, "counterparties": {"seed": 99}}))
    assert base.corn == moved.corn and base.demand == moved.demand and base.prime == moved.prime
    wa = World(Scenario.from_dict({"master_seed": 5}))
    wb = World(Scenario.from_dict({"master_seed": 5, "counterparties": {"seed": 99}}))
    assert _names(wa) != _names(wb)


def test_contacts_hide_hidden_economics():
    w = world()
    cards = w.list_contacts()
    assert len(cards) >= 20
    kinds = {c["kind"] for c in cards}
    assert {"distributor", "control", "export", "grain", "cooperage", "bank", "regulator"} <= kinds
    card = w.read_contact(cards[0]["id"])
    for key in HIDDEN_KEYS:
        assert key not in card
        assert key not in cards[0]
    with pytest.raises(Refused):
        w.read_contact("NO-SUCH")


def test_send_email_reaches_party_and_they_reply():
    w = world()
    did = next(k for k, d in w.distributors.items() if d["kind"] == "distributor")
    msg = w.send_email(did, "Introduction", "We just signed a lease and would like to stay in touch.")
    assert did in msg
    assert any(h["kind"] == "outbound" for h in w.parties[did]["memory"])
    w.end_week(3)
    replies = [e for e in w.emails if e.get("party_id") == did and e["subject"].startswith("Re:")]
    assert replies
    bounce = w.send_email("not-a-real-firm@example.com", "Hi", "Hello")
    assert "failed" in bounce.lower()


def test_named_supplier_quotes_do_not_change_spot():
    w = world()
    q = w.quotes()
    # spot prices stay the posted index; named suppliers surround them
    assert "suppliers" in q["grain_bu"] and q["grain_bu"]["suppliers"]
    spot = q["new_barrels"]["price"]
    po = w.place_order("new_barrels", 20)
    assert "spot desk" in po
    # a named buy uses that supplier's price, not necessarily the spot
    sid = q["grain_bu"]["suppliers"][0]["id"]
    row = w.request_quote("grain_bu", sid)
    assert row["id"] == sid
    w.place_order("grain_bu", 100, sid)
    assert w.orders[-1]["supplier_id"] == sid
    # default order still charged the spot (first PO)
    assert w.orders[0]["supplier"] == "spot desk"
    assert abs(w.orders[0]["cost"] / 20 - spot) < 0.01


def test_phone_call_and_contracts_on_lease():
    w = world()
    lid = w.site_landlords["edge_of_town"]
    out = w.call_party(lid, "check_in", "Just introducing ourselves.")
    assert "summary" in out and "picked_up" in out
    w.sign_lease("edge_of_town")
    kinds = {c["kind"] for c in w.list_contracts()}
    assert "lease" in kinds
    card = w.read_contact(lid)
    assert card["recent"]


def test_voice_template_is_deterministic():
    a, b = world(), world()
    assert [e["body"] for e in a.emails] == [e["body"] for e in b.emails]
    assert a.voice.mode == "template"


def test_llm_voice_falls_back_without_a_working_client(monkeypatch):
    def fail(self, *a, **k):
        return None, "RuntimeError: no key", 0.0, []

    monkeypatch.setattr(Voice, "_rewrite", fail)
    w = World(Scenario.from_dict({"master_seed": 3, "voice": "llm"}))
    bodies = " ".join(e["body"] for e in w.emails)
    assert "2,000,000" in bodies
    assert any(row.get("fallback") for row in w.voice.transcripts)


def test_transcripts_replay_exactly(tmp_path):
    original = "Lock 400 bu at $5.25/bu, delivered week 40."
    rewritten = "We can lock 400 bu at $5.25/bu, delivered week 40. Let me know."
    assert facts_preserved(original, rewritten)

    v = Voice(mode="llm", seed=4, temperature=0.6)
    v._rewrite = lambda *a, **k: (rewritten, None, 0.01, [{"role": "user", "content": "x"}])
    text = v.phrase("A Farmer", "Harvest contract", original, week=12, kind="grain_contract")
    assert text == rewritten and v.cost_usd == pytest.approx(0.01)
    path = tmp_path / "cp.jsonl"
    v.dump_transcripts(path)
    v2 = Voice(mode="replay", seed=4, temperature=0.6, replay_path=path)
    again = v2.phrase("A Farmer", "Harvest contract", original, week=12, kind="grain_contract")
    assert again == rewritten
    # a missing key falls back to the template
    miss = v2.phrase("A Farmer", "Other", "Hello $1", week=1, kind="info")
    assert miss == "Hello $1"
    assert any(row["fallback"] for row in v2.transcripts)


def test_voice_does_not_change_economic_outcomes():
    sc = {"preset": "calm", "master_seed": 8, "horizon_years": 1.0}
    s1 = settle(play(World(Scenario.from_dict({**sc, "voice": "template"}))))

    orig = Voice.phrase

    def noisy(self, sender, subject, body, **kw):
        return "Note — " + body

    Voice.phrase = noisy
    try:
        s2 = settle(play(World(Scenario.from_dict({**sc, "voice": "llm"}))))
    finally:
        Voice.phrase = orig
    assert s1 == s2


def test_high_churn_lets_parties_enter():
    w = World(Scenario.from_dict({"master_seed": 4, "counterparties": {"churn_rate": 80.0}}))
    n0 = len(w.parties)
    ids0 = set(w.parties)
    while w.t < 36:
        w.end_week(1)
    assert len(w.parties) > n0
    assert set(w.parties) - ids0


def test_unknown_counterparties_key_rejected():
    with pytest.raises(ValueError, match="unknown counterparties"):
        Scenario.from_dict({"counterparties": {"telepathy": True}})
    with pytest.raises(ValueError, match="voice"):
        Scenario.from_dict({"voice": "shout"})


def test_reply_to_new_kinds_accepts_and_declines():
    w = world()
    # inject a press request as if it had arrived
    pid = next(p["id"] for p in w.parties.values() if p["kind"] == "press")
    oid = "PRS-ASK-999"
    w.offers[oid] = {"kind": "press_request", "party_id": pid, "week": 0}
    eid = w.email("press", "Interview request", "Have 30 minutes?", "press_request",
                  {"offer": oid}, deadline=4, party_id=pid)
    assert "accept" in __import__("barrel_sim.report", fromlist=["read_email"]).read_email(w, eid)["decisions"]
    w.reply_email(eid, "", "accept")
    assert w.awareness > 0.02
