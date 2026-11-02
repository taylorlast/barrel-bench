"""Reference policies on a world: do-nothing, the fixed baseline (score 0), the
scripted cellar master, and the hindsight oracle (score 1).

The oracle is the best of a grid of cellar-master settings, each run both blind and
with perfect information (true quality and peak per batch, honest/dishonest brokers,
the demand path and the bank's tightening). It is a strong reference, not a proven
optimum; the Verifier clamps scores at 1.
"""

from __future__ import annotations

import itertools
from functools import lru_cache
from typing import Any

from . import params as P
from .core import Sim
from .desk import Desk
from .playbook import DEFAULT_KNOBS, POLICIES, cellar_quarter


class Peek:
    def __init__(self, sim: Sim):
        self.sim = sim

    def batch(self, bid: str) -> dict[str, Any]:
        b = self.sim.batches[bid]
        r = b["m"] / b["m_peak"]
        oak = "light" if r < 0.7 else ("balanced" if r < 1.05 else ("oaky" if r < 1.3 else "over-oaked"))
        return {"q": self.sim.true_q(b), "oak": oak, "potential": b["qmax"]}

    def offer(self, oid: str) -> dict[str, Any]:
        o = next(o for o in self.sim.w.offers[self.sim.t] if o["id"] == oid)
        return {"honest": o["honest"]}

    def fill_size(self, t: int, n: int) -> int:
        # Spirit filled now sells in 4-10 years: lean on the demand index then.
        w = self.sim.w
        fut = [w.index[min(P.QUARTERS, t + d)] for d in range(16, 33, 4)]
        return int(min(P.STILL_CAP, n * max(0.5, sum(fut) / len(fut))))

    def buffer(self, t: int, base: float) -> float:
        w = self.sim.w
        return base * 0.5 if w.tight[0] - 3 <= t < w.tight[1] else base


def play(seed: int, variant: str, policy: str, knobs: dict[str, Any] | None = None,
         oracle: bool = False) -> Sim:
    sim = Sim(seed, variant)
    desk = Desk(sim)
    peek = Peek(sim) if oracle else None
    while not sim.done:
        if policy == "cellar":
            cellar_quarter(desk.call, knobs, peek)
        else:
            POLICIES[policy](desk.call)
    return sim


GRID = [{"fill": f, "mix": m, "hold_q": h}
        for f, m, h in itertools.product((200, 260, 300), ((0.45, 0.4, 0.15), (0.6, 0.35, 0.05), (0.25, 0.45, 0.3)),
                                         (76.0, 84.0))]


@lru_cache(maxsize=64)
def references(seed: int, variant: str = "standard") -> dict[str, float]:
    do_nothing = play(seed, variant, "do_nothing").outcome()["raw_usd"]
    baseline = play(seed, variant, "baseline").outcome()["raw_usd"]
    cellar = play(seed, variant, "cellar").outcome()["raw_usd"]
    best = cellar
    for knobs in GRID:
        for oracle in (True, False):
            best = max(best, play(seed, variant, "cellar", knobs, oracle).outcome()["raw_usd"])
    return {"do_nothing_usd": do_nothing, "baseline_usd": baseline, "cellar_usd": cellar,
            "oracle_usd": max(best, baseline)}
