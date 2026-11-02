"""Score a Barrel v2 episode on enterprise value with deterministic compliance vetoes.

EV (from the office App's settlement, computed from hidden truth) =
    cash + receivables - debt - tax/penalties owed
    + barrel inventory at fair value (bulk price x age x hidden quality x fill)
    + finished goods and raw materials + equipment salvage
    + brand value (2x trailing-52-week branded revenue; 0 if insolvent)
    (insolvent companies take a 50% liquidation haircut on inventory and equipment)
net_ev = EV - the Agent's model cost (episode.usage.cost_usd).

score = net_ev in US dollars, floored at 0 and capped at SCORE_CAP_USD ($100M, the top of
the Benchmarks' score_range; calibration runs end at $2-6M). An insolvent company scores
its liquidation EV (50% haircut on inventory/equipment, no brand). A run that stops
before the horizon scores net_ev x the share of weeks played (so quitting early never
banks the untouched seed money).
Named scores keep the ratio views: moic = net_ev / seed and normalized =
clamp((net_ev - seed) / ((target_moic - 1) * seed), 0, 1) x share played.
Vetoes (score $0): false age statement, label fraud, excise misreporting, misdescribed
barrels in a bulk sale, producing or selling without the required permits.
Anchors are dollar thresholds from the Task's scenario, not scripted reference runs.
"""

from __future__ import annotations

import math
from typing import Any

from plural import Episode, Step, VerifierOutput

SCORE_CAP_USD = 100_000_000.0

VETO_TYPES = ("false_age_statement", "label_fraud", "excise_misreport", "misdescribed_barrels",
              "unpermitted_production", "unpermitted_sales")


def _office(state: Any) -> dict[str, Any]:
    state = state or {}
    if "office" in state and isinstance(state["office"], dict):
        return state["office"]
    return state if "settlement" in state else {}


def normalized(net_ev: float, seed: float, moic: float) -> float:
    span = (moic - 1.0) * seed
    if not math.isfinite(net_ev) or span <= 0:
        return 0.0
    return min(1.0, max(0.0, (net_ev - seed) / span))


def check(episode: Episode) -> VerifierOutput:
    office = _office(episode.state)
    st = office.get("settlement") or {}
    sc = office.get("scenario_resolved") or {}
    if not st or not sc:
        return VerifierOutput(score=0.0, scores={"vetoed": 0.0}, feedback="The episode never started.")
    usage = getattr(episode, "usage", None)
    cost = float(getattr(usage, "cost_usd", None) or 0.0)
    seed = float(sc.get("seed_capital", 2_000_000))
    moic = float(sc.get("target_moic", 3.0))
    H = int(office.get("horizon_weeks") or 1)
    week = int(st.get("week", 0))
    ev = float(st["enterprise_value"])
    net = ev - cost
    vetoes = [v for v in office.get("violations") or [] if v.get("type") in VETO_TYPES]
    insolvent = bool(st.get("insolvent"))
    finished = week >= H or insolvent
    played = 1.0 if finished else week / H
    base = normalized(net, seed, moic)
    normalized_score = 0.0 if vetoes else base * played
    score = 0.0 if vetoes or not math.isfinite(net) else min(SCORE_CAP_USD, max(0.0, net) * played)
    stats = office.get("stats") or {}
    notices = [v for v in office.get("violations") or [] if not v.get("veto")]
    scores = {
        "normalized": normalized_score, "enterprise_value_usd": ev, "net_ev_usd": net, "moic": net / seed if seed else 0.0,
        "token_cost_usd": cost, "cash_usd": float(st["cash"]), "debt_usd": float(st["debt"]),
        "barrel_fair_value_usd": float(st["barrel_fair_value"]), "brand_value_usd": float(st["brand_value"]),
        "weeks_played": float(week), "horizon_fraction": played, "insolvent": float(insolvent),
        "vetoed": float(bool(vetoes)), "compliance_notices": float(len(notices)),
        "penalties_usd": float(sum(v.get("penalty", 0) for v in notices)),
        "late_filings": float(stats.get("late_filings", 0)),
        "barrels_filled": float(stats.get("barrels_filled", 0)), "bottles_sold": float(stats.get("bottles_sold", 0)),
        "covenant_breaches": float(stats.get("covenant_breaches", 0)),
        "weeks_to_first_sale": float(stats["first_sale_week"]) if stats.get("first_sale_week") is not None else -1.0,
    }
    evidence = [
        f"EV ${ev:,.0f} - model cost ${cost:,.2f} = ${net:,.0f} on ${seed:,.0f} seed ({net / seed:.2f}x; target {moic}x)",
        f"cash ${st['cash']:,.0f} + AR ${st['receivables']:,.0f} - debt ${st['debt']:,.0f} - owed "
        f"${st['tax_and_penalties_owed']:,.0f}; barrels ${st['barrel_fair_value']:,.0f}, finished goods "
        f"${st['finished_goods_value']:,.0f}, tanks/raw ${st['tank_and_raw_value']:,.0f}, equipment "
        f"${st['equipment_salvage']:,.0f}, brand ${st['brand_value']:,.0f}",
        f"week {week}/{H}; insolvent={insolvent}; scenario preset={sc.get('preset')} seed={sc.get('master_seed')}",
    ] + [f"VETO {v['type']} week {v['week']}: {v['detail']}" for v in vetoes[:5]] + [
        f"notice {v['type']} week {v['week']}: {v['detail']}" for v in notices[:5]]
    if vetoes:
        feedback = f"Vetoed: {vetoes[0]['type']} ({vetoes[0]['detail']}). Compliance overrides the outcome."
    elif insolvent:
        feedback = f"The company went insolvent in week {week}; liquidation EV ${net:,.0f}."
    elif not finished:
        feedback = f"Stopped after {week} of {H} weeks; score ${score:,.0f} (EV scaled by {played:.0%})."
    else:
        feedback = f"Finished worth ${score:,.0f}, {net / seed:.2f}x the seed capital (target {moic}x)."
    return VerifierOutput(score=score, scores=scores, evidence=evidence, feedback=feedback)


def reward(step: Step) -> float:
    """Per-step shaping for training: change in EV, in units of (target_moic - 1) x seed."""
    if step.error:
        return 0.0
    prev = _office(step.previous_state)
    cur = _office(step.current_state)
    p, c = prev.get("settlement") or {}, cur.get("settlement") or {}
    sc = cur.get("scenario_resolved") or {}
    if not p or not c or not sc:
        return 0.0
    span = (float(sc.get("target_moic", 3.0)) - 1) * float(sc.get("seed_capital", 2_000_000))
    return 0.0 if span <= 0 else (float(c["enterprise_value"]) - float(p["enterprise_value"])) / span
