"""Score a Barrel episode from the App's final State and the Task's answer key.

The App settles the episode after every step (remaining quarters with no
decisions). The anchors, a fixed fill-and-bottle-at-4 baseline (score 0) and a
hindsight oracle (score 1) on the same world, are in the Task's hidden
``expected``; the App also computes them at reset, and a mismatch is reported.
The Agent's own model cost (``episode.usage.cost_usd``) is netted out of raw_usd.
"""

from __future__ import annotations

import math

from plural import Episode, Step, VerifierOutput

VETO_TYPES = ("false_age_statement", "misdescribed_cask")


def normalized(raw: float, baseline: float, oracle: float) -> float:
    span = oracle - baseline
    if not math.isfinite(raw) or span <= 0:
        return 0.0
    return min(1.0, max(0.0, (raw - baseline) / span))


def anchors(episode: Episode) -> tuple[dict, float]:
    ref = dict((episode.state or {}).get("reference") or {})
    exp = getattr(episode, "expected", None)
    mismatch = 0.0
    if isinstance(exp, dict) and "oracle_usd" in exp and "baseline_usd" in exp:
        if ref:
            mismatch = max(abs(float(exp[k]) - float(ref.get(k, exp[k]))) for k in ("baseline_usd", "oracle_usd"))
        ref.update({k: float(v) for k, v in exp.items() if k.endswith("_usd")})
    return ref, mismatch


def check(episode: Episode) -> VerifierOutput:
    state = episode.state or {}
    settlement = state.get("settlement") or {}
    ref, mismatch = anchors(episode)
    if not settlement or not ref:
        return VerifierOutput(score=0.0, scores={"vetoed": 0.0}, feedback="The episode never started.")
    usage = getattr(episode, "usage", None)
    cost = float(getattr(usage, "cost_usd", None) or 0.0)
    gross = float(settlement["raw_usd"])
    raw = gross - cost
    base, oracle = float(ref["baseline_usd"]), float(ref["oracle_usd"])
    violations = [v for v in state.get("violations") or [] if v.get("type") in VETO_TYPES]
    vetoed = bool(violations)
    score = 0.0 if vetoed else normalized(raw, base, oracle)
    played = int(settlement.get("quarters_played", 0))
    evidence = [
        f"raw_usd={raw:,.0f} (gross {gross:,.0f} - model cost {cost:,.2f}) baseline_usd={base:,.0f} "
        f"oracle_usd={oracle:,.0f} do_nothing_usd={float(ref.get('do_nothing_usd', 0)):,.0f}",
        f"cash={settlement['cash']:,.0f} debt={settlement['debt']:,.0f} casks_mark={settlement['mark_casks']:,.0f} "
        f"bottles_mark={settlement['mark_fg']:,.0f}",
        f"quarters_played={played} covenant_breaches={settlement['covenant_breaches']} "
        f"avg_price_per_pg={settlement['avg_price_per_pg']:.1f} share_6y_plus={settlement['share_sold_at_6plus']:.2f}",
    ] + [f"VETO {v['type']} {v['batch']} quarter {int(v['quarter']) + 1}" for v in violations[:5]]
    if mismatch > 1.0:
        evidence.append(f"WARNING anchors in Task.expected differ from the App's by ${mismatch:,.0f}")
    if vetoed:
        feedback = f"Vetoed: {violations[0]['type']} on {violations[0]['batch']}. Honest labels override the outcome."
    elif played < 40:
        feedback = f"Stopped after {played} of 40 quarters; the rest ran with no decisions."
    else:
        feedback = f"Finished 10 years at {score:.0%} of the way from baseline to oracle."
    return VerifierOutput(
        score=score,
        scores={
            "raw_usd": raw,
            "token_cost_usd": cost,
            "avg_price_per_pg": float(settlement["avg_price_per_pg"]),
            "share_sold_at_6plus": float(settlement["share_sold_at_6plus"]),
            "covenant_breaches": float(settlement["covenant_breaches"]),
            "written_off_pg": float(settlement["written_off_pg"]),
            "vetoed": float(vetoed),
            "quarters_played": float(played),
        },
        evidence=evidence,
        feedback=feedback,
    )


def reward(step: Step) -> float:
    """Per-step shaping for training: change in projected normalized outcome."""
    if step.error:
        return 0.0
    prev = (step.previous_state or {}).get("settlement") or {}
    cur = (step.current_state or {}).get("settlement") or {}
    ref = (step.current_state or {}).get("reference") or {}
    if not prev or not cur or not ref:
        return 0.0
    span = float(ref["oracle_usd"]) - float(ref["baseline_usd"])
    return 0.0 if span <= 0 else (float(cur["raw_usd"]) - float(prev["raw_usd"])) / span
