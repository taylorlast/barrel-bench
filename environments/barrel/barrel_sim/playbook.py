"""Scripted distillery policies that act only through Environment actions (JSON output).

``call(name, **kw)`` runs one action and returns its JSON; a refused action raises
ValueError. This file is vendored into the Harnesses, so it imports nothing from the
simulator. ``peek`` (oracle only) exposes hidden truth; scripted Agents never get it.
"""

from __future__ import annotations

import math
from typing import Any, Callable

AGES = (2, 4, 6, 8, 10, 12)
GRADE_FLOOR = {"standard": 0.0, "good": 65.0, "premium": 78.0}

Call = Callable[..., Any]


def tier(age: float) -> int:
    return max([a for a in AGES if age + 1e-9 >= a], default=0)


def grade_for(score: float) -> str:
    return "premium" if score >= 78 else ("good" if score >= 65 else "standard")


def _try(call: Call, name: str, **kw: Any) -> Any:
    try:
        return call(name, **kw)
    except ValueError:
        return None


def do_nothing_quarter(call: Call) -> None:
    call("end_quarter")


# ---------------------------------------------------------------- baseline
def baseline_quarter(call: Call) -> None:
    """Fixed rule: fill 200 new casks on F2, bottle everything at 4 years, ship whatever is ordered."""
    for b in call("cellar")["batches"]:
        if b["age"] >= 4:
            _try(call, "bottle", batch=b["id"], casks=b["casks"], age_statement=4)
    _ship_all(call)
    _try(call, "fill", casks=200, floor="F2", wood="new")
    brief = call("brief")
    if brief["debt"] > 0 and brief["cash"] > 500_000:
        _try(call, "repay", amount=brief["cash"] - 500_000)
    call("end_quarter")


def _ship_all(call: Call) -> None:
    brief = call("brief")
    fg = {int(a): v for a, v in brief["finished_goods"].items()}
    by_age: dict[int, list[dict[str, Any]]] = {}
    for o in brief["orders"]:
        by_age.setdefault(o["age"], []).append(o)
    for a, orders in by_age.items():
        have = fg.get(a, 0.0)
        total = sum(o["pg"] for o in orders)
        if have <= 0 or total <= 0:
            continue
        frac = min(1.0, have / total) * 0.999
        for o in orders:
            pg = math.floor(o["pg"] * frac)
            if pg > 0:
                _try(call, "allocate", distributor=o["distributor"], age_statement=a, pg=pg)


# ---------------------------------------------------------------- cellar master
DEFAULT_KNOBS = {"fill": 260, "mix": (0.45, 0.4, 0.15), "buffer": 400_000, "hold_q": 80.0,
                 "headroom": 0.85, "buy": True, "max_samples": 8, "young_q": 64.0}


def cellar_quarter(call: Call, knobs: dict[str, Any] | None = None, peek: Any = None) -> None:
    """Demand-laddered policy: sample, bottle each tier to its orders, hold good spirit
    for older labels, dump over-oaked casks honestly, buy only verified bulk lots,
    fill counter to the bank's headroom."""
    k = {**DEFAULT_KNOBS, **(knobs or {})}
    brief = call("brief")
    t = brief["quarter"]
    cellar = call("cellar")["batches"]

    # 1. what we believe about each batch
    est: dict[str, dict[str, Any]] = {}
    samples = 0
    for b in sorted(cellar, key=lambda b: -b["age"]):
        if peek is not None:
            est[b["id"]] = peek.batch(b["id"])
            continue
        lab = b["lab"]
        if b["age"] >= 3.75 and (lab is None or t - lab["quarter"] >= 4) and samples < k["max_samples"]:
            lab = _try(call, "sample", batch=b["id"], casks=2) or lab
            samples += 1
        if lab:
            lift = {"light": 12.0, "balanced": 3.0}.get(lab["oak"], 0.0)
            est[b["id"]] = {"q": lab["score"], "oak": lab["oak"], "potential": lab["score"] + lift}

    def q_of(b: dict[str, Any]) -> float:
        return est.get(b["id"], {}).get("q", 70.0)

    def potential(b: dict[str, Any]) -> float:
        return est.get(b["id"], {}).get("potential", 75.0)

    def oaky(b: dict[str, Any]) -> bool:
        return est.get(b["id"], {}).get("oak") in ("oaky", "over-oaked")

    # 2. bottle to orders, oldest labels first
    need: dict[int, float] = {a: 0.0 for a in AGES}
    for o in brief["orders"]:
        need[o["age"]] += o["pg"]
    for a, v in brief["finished_goods"].items():
        need[int(a)] -= v
    pool = {b["id"]: dict(b) for b in cellar if tier(b["age"]) >= 2}
    for a in sorted(AGES, reverse=True):
        def rank(b: dict[str, Any]) -> tuple:
            return (not oaky(b), tier(b["age"]) != a, -b["age"])
        cands = [b for b in pool.values() if tier(b["age"]) >= a]
        if a == 2:
            cands = [b for b in cands if potential(b) < k["young_q"] or (oaky(b) and tier(b["age"]) == 2)]
        elif a in (4, 6):
            cands = [b for b in cands if oaky(b) or potential(b) < k["hold_q"] or tier(b["age"]) > a]
        for b in sorted(cands, key=rank):
            if need[a] <= 0:
                break
            per = b["pg"] / max(b["casks"], 1)
            n = min(b["casks"], math.ceil(need[a] / per))
            if n <= 0:
                continue
            if _try(call, "bottle", batch=b["id"], casks=n, age_statement=a) is not None:
                need[a] -= n * per
                b["casks"] -= n
                b["pg"] -= n * per
                if b["casks"] <= 0:
                    del pool[b["id"]]

    # 3. over-oaked casks we can't place go to brokers, described by our own lab read
    for b in list(pool.values()):
        e = est.get(b["id"], {})
        if e.get("oak") == "over-oaked" and b["casks"] > 0:
            _try(call, "sell_casks", batch=b["id"], casks=b["casks"], grade=grade_for(e["q"] - 3))

    _ship_all(call)

    # 4. bulk lots: buy only what the paperwork and lab confirm
    brief = call("brief")
    room = brief["borrowing_base"] * k["headroom"] - brief["debt"]
    if k["buy"]:
        for o in brief["offers"]:
            if o["stated_age"] < 4 or o["ask"] > room * 0.5:
                continue
            if peek is not None:
                ok = peek.offer(o["id"])["honest"]
            else:
                rep = _try(call, "inspect_offer", offer=o["id"])
                ok = bool(rep) and rep["documented_age_years"] >= o["stated_age"] - 0.01 and \
                    rep["lab_score"] >= GRADE_FLOOR[o["stated_grade"]]
            if ok and _try(call, "buy_lot", offer=o["id"]) is not None:
                room -= o["ask"]

    # 5. fill new make, sized to the bank's headroom and cask prices
    brief = call("brief")
    room = brief["borrowing_base"] * k["headroom"] - brief["debt"]
    wood = "refill" if brief["cask_cost"]["new"] > 400 else "new"
    n = k["fill"]
    if peek is not None:
        n = peek.fill_size(t, n)
    if room < 0:
        n = int(n * 0.4)
    n = min(n, brief["stills_left"])
    for floor, share in zip(("F1", "F2", "F3"), k["mix"]):
        m = int(n * share)
        if m > 0:
            _try(call, "fill", casks=m, floor=floor, wood=wood)

    # 6. finance
    brief = call("brief")
    buf = k["buffer"] if peek is None else peek.buffer(t, k["buffer"])
    if brief["debt"] > 0 and brief["cash"] > buf:
        _try(call, "repay", amount=brief["cash"] - buf)
    call("end_quarter")


POLICIES = {"do_nothing": do_nothing_quarter, "baseline": baseline_quarter, "cellar": cellar_quarter}
