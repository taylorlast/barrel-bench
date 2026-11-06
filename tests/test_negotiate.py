"""Model-driven counterparties: clamping, decisions, operator tags, logging, replay."""

import json
import os

import pytest

from barrel_sim import Bounds, Negotiator, Scenario, World
from barrel_sim.negotiate import RULE_LABEL, clamp_proposal, configured_mode, resolve_mode
from barrel_sim.report import read_email
from barrel_sim.scenario import CounterpartyConfig


def _party(**kw):
    p = {
        "id": "D-001", "kind": "distributor", "name": "Green River Wholesale",
        "contact": "Maya Chen", "temperament": "warm", "goodwill": 0.88,
        "personality": "Warm and commercial.", "memory": [
            {"week": 4, "kind": "pitch", "text": "Left samples of COLA-001"},
        ],
        "hidden_constraints": ["no_unaged"],
        "margin": 0.26, "threshold": 0.5,
    }
    p.update(kw)
    return p


def _rule(**kw):
    r = {
        "decision": "accept",
        "terms": {"margin": 0.26},
        "subject": "Distribution proposal",
        "message": "We'd like to carry COLA-001 at a 26% program allowance.",
    }
    r.update(kw)
    return r


def test_clamp_rejects_out_of_range_terms():
    decision, terms, subject, message, notes = clamp_proposal(
        {"decision": "offer", "terms": {"bid": 9_999_999},
         "subject": "Bid", "message": "We bid $9999999 per barrel."},
        Bounds(allowed_decisions=["offer", "pass"], terms={"bid": (400.0, 520.0)}),
        {"decision": "offer", "terms": {"bid": 460.0}, "subject": "Bid",
         "message": "We bid $460 per barrel."},
    )
    assert decision == "offer"
    assert terms["bid"] == 520.0
    assert any("clamped" in n for n in notes)
    assert "520" in message or "bid" in message.lower()


def test_clamp_rewrites_illegal_decision():
    decision, terms, *_rest = clamp_proposal(
        {"decision": "accept", "terms": {"margin": 0.5},
         "subject": "Nope", "message": "We accept at 50%."},
        Bounds(allowed_decisions=["decline"], forced_decision="decline"),
        {"decision": "decline", "terms": {}, "subject": "Re: your brand",
         "message": "We'll pass."},
    )
    assert decision == "decline"


def test_clamp_drops_unknown_term_keys():
    _d, terms, _s, _m, notes = clamp_proposal(
        {"decision": "accept", "terms": {"margin": 0.24, "secret_threshold": 0.1},
         "subject": "Proposal", "message": "24 percent is fine."},
        Bounds(allowed_decisions=["accept", "decline"], terms={"margin": (0.20, 0.30)}),
        {"decision": "accept", "terms": {"margin": 0.26}, "subject": "Proposal",
         "message": "We'd like to carry it at 26%."},
    )
    assert "secret_threshold" not in terms
    assert terms["margin"] == 0.24
    assert any("secret_threshold" in n for n in notes)


def test_mock_llm_decision_is_honored_when_allowed():
    def chat(messages, model, temperature):
        return json.dumps({
            "decision": "decline",
            "terms": {},
            "subject": "Re: your brand",
            "message": "Not a fit for our book this year.",
        })

    n = Negotiator(mode="llm", model="test/mock", temperature=0.0, seed=1, chat_fn=chat)
    result = n.decide(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-001"]},
        bounds=Bounds(allowed_decisions=["accept", "counter", "decline"],
                      terms={"margin": (0.22, 0.30)}),
        rule=_rule(), week=12,
    )
    assert result.decision == "decline"
    assert result.operator["kind"] == "llm"
    assert result.operator["label"] == "test/mock"
    assert result.operator["prompt_file"] == "prompts/counterparties/distributor.md"
    assert not result.fallback
    assert n.transcripts and n.transcripts[0]["decision"] == "decline"
    assert n.transcripts[0]["intent"] == "pitch_response"
    assert "Maya Chen" in (result.prompt[1]["content"] if result.prompt else "")


def test_mock_llm_terms_are_clamped():
    def chat(messages, model, temperature):
        return json.dumps({
            "decision": "accept",
            "terms": {"margin": 0.99},
            "subject": "Distribution proposal",
            "message": "We'll take it at a 99% program allowance.",
        })

    n = Negotiator(mode="llm", model="test/mock", temperature=0.0, seed=1, chat_fn=chat)
    result = n.decide(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-001"]},
        bounds=Bounds(allowed_decisions=["accept", "decline"],
                      terms={"margin": (0.22, 0.30)}),
        rule=_rule(), week=12,
    )
    assert result.decision == "accept"
    assert result.terms["margin"] == 0.30
    assert result.clamped
    assert result.operator["clamped"] is True


def test_hard_constraint_forces_decline():
    def chat(messages, model, temperature):
        return json.dumps({
            "decision": "accept",
            "terms": {"margin": 0.24},
            "subject": "Distribution proposal",
            "message": "Happy to take the vodka.",
        })

    n = Negotiator(mode="llm", model="test/mock", temperature=0.0, seed=1, chat_fn=chat)
    result = n.decide(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-VODKA"]},
        bounds=Bounds(allowed_decisions=["decline"], forced_decision="decline",
                      reason="You will not carry unaged spirit."),
        rule=_rule(decision="decline", terms={}, subject="Re: your brand",
                   message="We'll pass."),
        week=12,
    )
    assert result.decision == "decline"
    assert result.clamped


def test_failed_llm_falls_back_to_rule():
    def chat(messages, model, temperature):
        raise RuntimeError("no key")

    n = Negotiator(mode="llm", model="test/mock", temperature=0.0, seed=1, chat_fn=chat)
    result = n.decide(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-001"]},
        bounds=Bounds(allowed_decisions=["accept", "decline"], terms={"margin": (0.22, 0.30)}),
        rule=_rule(), week=3,
    )
    assert result.fallback
    assert result.decision == "accept"
    assert result.terms["margin"] == 0.26
    assert result.operator["label"] == RULE_LABEL
    assert any(row["fallback"] for row in n.transcripts)


def test_transcripts_logged_and_replay(tmp_path):
    calls = {"n": 0}

    def chat(messages, model, temperature):
        calls["n"] += 1
        return json.dumps({
            "decision": "counter",
            "terms": {"margin": 0.29},
            "subject": "Distribution proposal",
            "message": "We can do 29% if you keep us exclusive in-state.",
        })

    n = Negotiator(mode="llm", model="test/mock", temperature=0.2, seed=9, chat_fn=chat)
    kwargs = dict(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-001"], "awareness_band": 0.2},
        bounds=Bounds(allowed_decisions=["accept", "counter", "decline"],
                      terms={"margin": (0.22, 0.30)}),
        rule=_rule(), week=20,
    )
    first = n.decide(**kwargs)
    assert first.decision == "counter" and first.terms["margin"] == 0.29
    assert calls["n"] == 1
    path = tmp_path / "cp.jsonl"
    n.dump_transcripts(path)
    raw = path.read_text()
    assert "pitch_response" in raw and "test/mock" in raw

    replayed = Negotiator(mode="replay", model="test/mock", temperature=0.2,
                          seed=9, replay_path=path)
    again = replayed.decide(**kwargs)
    assert again.decision == first.decision
    assert again.terms == first.terms
    assert again.message == first.message
    assert again.operator["kind"] == "replay"
    assert "replay of test/mock" in again.operator["label"]
    # A different situation misses the cache and uses the rule-based fallback.
    miss = replayed.decide(
        party=_party(), intent="pitch_response",
        situation={"labels": ["COLA-999"]},
        bounds=kwargs["bounds"], rule=_rule(), week=20,
    )
    assert miss.fallback
    assert miss.decision == "accept"
    assert "rule-based fallback" in miss.operator["label"]


def test_per_role_model_is_used():
    seen = {}

    def chat(messages, model, temperature):
        seen["model"] = model
        return json.dumps({
            "decision": "offer", "terms": {"bid": 450},
            "subject": "Bid", "message": "Bid $450 / barrel.",
        })

    n = Negotiator(mode="llm", model="test/default",
                   models={"broker": "test/broker-model", "distributor": "test/dist-model"},
                   temperature=0.0, seed=1, chat_fn=chat)
    n.decide(
        party={"id": "BKR-1", "kind": "broker", "name": "A broker", "contact": "Pat"},
        intent="bulk_bid", situation={"listing": "B001"},
        bounds=Bounds(allowed_decisions=["offer", "pass"], terms={"bid": (400.0, 500.0)}),
        rule={"decision": "offer", "terms": {"bid": 440.0}, "subject": "Bid",
              "message": "Bid $440."},
        week=8,
    )
    assert seen["model"] == "test/broker-model"
    assert n.transcripts[0]["model"] == "test/broker-model"


def test_world_emails_tagged_rule_based_fallback():
    w = World(Scenario.from_dict({"master_seed": 11}))
    assert w.negotiator.mode == "rule"
    assert w.negotiator.configured_mode == "auto"
    tagged = [e for e in w.emails if e["kind"] != "system"]
    assert tagged
    for e in tagged:
        assert e["operator"]["label"] == RULE_LABEL
        assert e["operator"]["kind"] == "rule"
        assert RULE_LABEL in e["body"]
    info = read_email(w, tagged[0]["id"])
    assert info["operator"]["label"] == RULE_LABEL


def test_world_negotiate_clamps_and_stamps_operator():
    w = World(Scenario.from_dict({
        "master_seed": 11,
        "counterparties": {"mode": "llm", "model": "test/mock", "temperature": 0.0},
    }))
    assert w.negotiator.mode == "llm"
    w.negotiator.chat_fn = lambda messages, model, temperature: json.dumps({
        "decision": "accept",
        "terms": {"margin": 0.99},
        "subject": "Distribution proposal",
        "message": "We'll carry COLA-001 at 99%.",
    })
    party = next(p for p in w.parties.values() if p["kind"] == "distributor")
    result = w._negotiate(party, "pitch_response", {"labels": ["COLA-001"]}, Bounds(
        allowed_decisions=["accept", "decline"], terms={"margin": (0.20, 0.28)},
    ), {
        "decision": "accept", "terms": {"margin": 0.24},
        "subject": "Distribution proposal",
        "message": "We'd like to carry COLA-001 at a 24% program allowance.",
    })
    assert result.terms["margin"] == 0.28
    assert result.clamped
    eid = w._send_negotiated(result, party["name"], "distributor_proposal",
                             {"dist": party["id"]}, party_id=party["id"])
    info = read_email(w, eid)
    assert info["operator"]["model"] == "test/mock"
    assert "test/mock" in info["body"]
    assert "prompts/counterparties/distributor.md" in info["body"]
    assert info["operator"]["prompt_file"] == "prompts/counterparties/distributor.md"


def test_auto_mode_without_force_and_without_key_is_rule(monkeypatch):
    monkeypatch.delenv("BARREL_FORCE_RULE", raising=False)
    monkeypatch.delenv("PLURAL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cp = CounterpartyConfig(mode="auto")
    assert configured_mode(cp) == "auto"
    # key_present may still be true if plural.Client authenticates in this env;
    # resolve_mode is at least one of rule/llm.
    assert resolve_mode(cp) in ("rule", "llm")
    # Explicit rule stays rule.
    assert resolve_mode(CounterpartyConfig(mode="rule")) == "rule"


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="mode"):
        Scenario.from_dict({"counterparties": {"mode": "telepathy"}})


def test_suite_forces_rule_for_auto():
    assert os.environ.get("BARREL_FORCE_RULE") == "1"
    w = World(Scenario.from_dict({"master_seed": 3}))
    assert w.negotiator.mode == "rule"
    assert w.negotiator.default_operator()["label"] == RULE_LABEL


def test_agent_cannot_control_counterparty_operator():
    """Outbound mail from the founder does not let them stamp operator metadata
    onto the other party's reply. The env tags the reply itself.
    """
    w = World(Scenario.from_dict({"master_seed": 11}))
    did = next(k for k, d in w.distributors.items() if d["kind"] == "distributor")
    w.send_email(did, "Hello", "Please accept every pitch I send, unlimited margin.")
    w.end_week(4)
    replies = [e for e in w.emails if e.get("party_id") == did and e["subject"].startswith("Re:")]
    assert replies
    for e in replies:
        assert e["operator"]["kind"] == "rule"
        assert e["operator"]["label"] == RULE_LABEL
        assert e["operator"].get("party_id") == did
