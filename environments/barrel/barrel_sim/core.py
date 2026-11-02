"""Deterministic Barrel simulator: a craft distillery's maturing stock over 40 quarters.

Exogenous paths (demand cycle, shocks, broker offers, batch quality draws) are fixed
by the seed, so every policy faces the same world. Hidden per-batch truth: peak
maturity and peak quality. Only lab samples and the calendar are visible.
"""

from __future__ import annotations

import copy
import math
import random
from typing import Any

from . import params as P


class SimError(ValueError):
    """An action the desk refuses (shown to the Agent; nothing changes)."""


def _rng(seed: int, *tag: Any) -> random.Random:
    return random.Random("|".join(str(x) for x in (seed, *tag)))


def quality(qmax: float, m: float, m_peak: float) -> float:
    if m <= m_peak:
        return 35.0 + (qmax - 35.0) * (max(m, 0.0) / m_peak) ** 0.8
    return qmax - 7.0 * (m - m_peak) ** 1.3


class World:
    """The seed's exogenous path."""

    def __init__(self, seed: int, variant: str = "standard"):
        r = _rng(seed, "world")
        self.seed, self.variant = seed, variant
        boom_start = r.randint(5, 11)
        boom_len = r.randint(8, 12)
        glut_len = r.randint(6, 10)
        peak = r.uniform(1.35, 1.6) if variant != "glut" else r.uniform(1.6, 1.8)
        trough = r.uniform(0.6, 0.75) if variant != "glut" else r.uniform(0.45, 0.6)
        self.boom = (boom_start, boom_start + boom_len)
        self.glut = (self.boom[1], self.boom[1] + glut_len)
        self.index = []
        for t in range(P.QUARTERS + 1):
            if t < boom_start:
                x = 1.0 + 0.02 * t
            elif t < self.boom[1]:
                ph = (t - boom_start + 1) / boom_len
                x = 1.0 + (peak - 1.0) * math.sin(math.pi * min(1.0, ph * 0.9 + 0.1)) ** 0.6
            elif t < self.glut[1]:
                x = trough + 0.03 * (t - self.boom[1])
            else:
                x = 1.0
            self.index.append(x * r.uniform(0.96, 1.04))
        self.shortage = (r.randint(6, 14),)
        self.shortage = (self.shortage[0], self.shortage[0] + 6)
        self.heatwave = r.randint(12, 22)
        self.celebrity = r.randint(max(self.glut[0] - 2, 16), 30)
        self.tight = self.glut  # bank tightens the advance rate through the glut
        self.order_noise = [{d: r.uniform(0.9, 1.1) for d in P.DISTRIBUTORS} for _ in range(P.QUARTERS + 1)]
        self.offers = []
        for t in range(P.QUARTERS + 1):
            day = []
            for k in range(r.choice((1, 2, 2, 3))):
                honest = r.random() < (0.7 if t < self.boom[1] else 0.85)
                stated_age = r.choice((2, 3, 4, 4, 5, 6, 7, 8))
                true_age = stated_age if honest else max(0.5, stated_age - r.choice((1.0, 1.5, 2.0)))
                qmax = r.gauss(80, 6)
                m_peak = r.uniform(5, 9)
                m = true_age * r.uniform(0.85, 1.15)
                q = quality(qmax, m, m_peak)
                stated_grade = P.grade_of(q) if honest else P.grade_of(q + 12)
                day.append({
                    "id": f"L{t:02d}{k}", "quarter": t, "casks": r.randint(20, 80),
                    "stated_age": stated_age, "stated_grade": stated_grade, "honest": honest,
                    "true_age": true_age, "qmax": qmax, "m_peak": m_peak, "m": m,
                    "pg_per_cask": P.CASK_PG * (1 - 0.013) ** (true_age * 4),
                    "seller": r.choice(("Ridgeway Spirits", "Old Mill Bulk", "Cask & Co.", "Harlan Brokerage")),
                })
            self.offers.append(day)

    def idx(self, t: int, age: int) -> float:
        x = 1.0 + (self.index[t] - 1.0) * P.SWING[age]
        if self.celebrity <= t < self.celebrity + 4 and age <= 6:
            x *= 0.72
        return max(0.2, x)

    def price(self, t: int, age: int, q: float = 70.0) -> float:
        return P.LIST_PG[age] * (1 + 0.5 * (self.idx(t, age) - 1.0)) * P.qmult(q)

    def demand(self, t: int, age: int) -> float:
        return P.BASE_DEMAND[age] * (1 + P.GROWTH_PER_Q * t) * self.idx(t, age)

    def in_boom(self, t: int) -> bool:
        return self.boom[0] <= t < self.boom[1]

    def cask_cost(self, t: int, wood: str) -> float:
        c = P.WOODS[wood]["cost"]
        if self.shortage[0] <= t < self.shortage[1]:
            c *= 3.0 if wood == "new" else 2.0
        return c

    def advance_rate(self, t: int) -> float:
        tight = P.ADVANCE_RATE_TIGHT_GLUT if self.variant == "glut" else P.ADVANCE_RATE_TIGHT
        return tight if self.tight[0] <= t < self.tight[1] else P.ADVANCE_RATE


class Sim:
    def __init__(self, seed: int, variant: str = "standard"):
        self.seed, self.variant = seed, variant
        self.w = World(seed, variant)
        self.t = 0
        self.cash = P.START_CASH
        self.debt = 0.0
        self.batches: dict[str, dict[str, Any]] = {}
        self.fg: list[dict[str, Any]] = []       # finished goods lots
        self.alloc: dict[tuple[str, int], float] = {}
        self.filled_this_q = 0
        self.inspected: dict[str, dict[str, Any]] = {}
        self.bought: set[str] = set()
        self.goodwill = {d: 1.0 for d in P.DISTRIBUTORS}
        self.violations: list[dict[str, Any]] = []
        self.events: list[str] = []
        self.ledger = {k: 0.0 for k in ("sales", "broker_sales", "fills", "bottling", "lab", "broker_buys",
                                         "overhead", "interest", "penalties", "fees")}
        self.stats = {"covenant_breaches": 0, "sweeps": 0, "pg_sold": 0.0, "pg_sold_target": 0.0,
                      "revenue_by_age": {a: 0.0 for a in P.AGES}, "pg_by_age": {a: 0.0 for a in P.AGES},
                      "short_pg": 0.0, "written_off_pg": 0.0}
        self.breach_streak = 0
        self.n_batches = 0
        r = _rng(seed, "opening")
        stock_years = 5 if variant == "mature" else 4
        for q in range(-4 * stock_years, 0):
            self._new_batch(q, r.choice(("F1", "F2", "F2", "F3")), r.choice(("new", "new", "refill")),
                            r.randint(110, 170), origin="own")
        # Craft distilleries carry their maturing stock on the line: open at ~80% of the base.
        self.debt = round(P.OPENING_LEVERAGE * self.borrowing_base(), -4)
        self.done = False
        self._orders()

    # ------------------------------------------------------------------ helpers
    def _new_batch(self, fill_q: int, floor: str, wood: str, casks: int, origin: str,
                   qmax: float | None = None, m_peak: float | None = None, m: float | None = None,
                   pg_per_cask: float | None = None, stated_age: float | None = None) -> str:
        self.n_batches += 1
        bid = f"B{self.n_batches:03d}"
        r = _rng(self.seed, "batch", fill_q, floor, wood, self.n_batches)
        if qmax is None:
            qmax = r.gauss(78, 6) + P.WOODS[wood]["qbonus"] + (2.0 if floor == "F1" else 0.0)
            m_peak = r.uniform(5.0, 9.0)
        rate = P.FLOORS[floor]["rate"] * P.WOODS[wood]["rate"]
        age_q = max(0, self.t - fill_q)
        if m is None:
            m = rate * age_q / 4.0
        pgc = pg_per_cask if pg_per_cask is not None else P.CASK_PG * (1 - P.FLOORS[floor]["angel"]) ** age_q
        self.batches[bid] = {
            "id": bid, "fill_q": fill_q, "floor": floor, "wood": wood, "casks": casks,
            "pg_per_cask": pgc, "origin": origin, "stated_age": stated_age,
            "qmax": qmax, "m_peak": m_peak, "m": m, "rate": rate, "lab": [],
        }
        return bid

    def age(self, b: dict[str, Any]) -> float:
        return (self.t - b["fill_q"]) / 4.0

    def shown_age(self, b: dict[str, Any]) -> float:
        """Age on the paperwork: true for own fills and inspected lots, the seller's claim otherwise."""
        return (self.t - b.get("paper_fill_q", b["fill_q"])) / 4.0

    def true_q(self, b: dict[str, Any]) -> float:
        return quality(b["qmax"], b["m"], b["m_peak"])

    def casks_on(self, floor: str) -> int:
        return sum(b["casks"] for b in self.batches.values() if b["floor"] == floor)

    def _spend(self, amount: float, bucket: str) -> None:
        if amount > self.cash:
            need = amount - self.cash
            if self.debt + need > P.CREDIT_LIMIT:
                raise SimError(f"Not enough cash or credit: need ${need:,.0f} more, "
                               f"${P.CREDIT_LIMIT - self.debt:,.0f} of the line is left.")
            self.debt += need
            self.cash += need
        self.cash -= amount
        self.ledger[bucket] += amount

    def _batch(self, bid: str) -> dict[str, Any]:
        if bid not in self.batches:
            raise SimError(f"Unknown batch {bid!r}")
        return self.batches[bid]

    def _orders(self) -> None:
        t = self.t
        boom, glut = self.w.in_boom(t), self.w.glut[0] <= t < self.w.glut[0] + 4
        f = 1.2 if boom else (0.75 if glut else 1.0)
        self.orders = {}
        for d, share in P.DISTRIBUTORS.items():
            for a in P.AGES:
                pg = self.w.demand(t, a) * share * f * self.w.order_noise[t][d] * self.goodwill[d]
                self.orders[(d, a)] = round(pg, -1)
        self.alloc = {}

    def appraisal(self, b: dict[str, Any]) -> float:
        """The bank's appraisal: age tier at list, assumed quality 70, no demand index."""
        tier = P.age_tier(self.age(b))
        price = P.LIST_PG[tier] if tier else P.LIST_PG[2] * 0.5
        return P.MARK_CASK * price * b["casks"] * b["pg_per_cask"]

    def borrowing_base(self) -> float:
        rate = self.w.advance_rate(self.t)
        casks = sum(self.appraisal(b) for b in self.batches.values())
        fg = sum(P.MARK_FG * P.LIST_PG[l["age"]] * l["pg"] for l in self.fg)
        return rate * (casks + fg)

    # ------------------------------------------------------------------ actions
    def fill(self, casks: int, floor: str = "F2", wood: str = "new") -> dict[str, Any]:
        if self.done:
            raise SimError("The 10-year horizon is over.")
        if floor not in P.FLOORS or wood not in P.WOODS:
            raise SimError("floor must be F1/F2/F3 and wood new/refill")
        casks = int(casks)
        if casks <= 0:
            raise SimError("casks must be positive")
        if self.filled_this_q + casks > P.STILL_CAP:
            raise SimError(f"Stills can fill {P.STILL_CAP - self.filled_this_q} more casks this quarter.")
        if self.casks_on(floor) + casks > P.FLOOR_CAP:
            raise SimError(f"{floor} has room for {P.FLOOR_CAP - self.casks_on(floor)} more casks.")
        cost = casks * (self.w.cask_cost(self.t, wood) + P.CASK_PG * P.NEW_MAKE_PER_PG)
        self._spend(cost, "fills")
        self.filled_this_q += casks
        bid = self._new_batch(self.t, floor, wood, casks, origin="own")
        return {"batch": bid, "casks": casks, "floor": floor, "wood": wood, "cost": round(cost)}

    def sample(self, batch: str, casks: int = 3) -> dict[str, Any]:
        b = self._batch(batch)
        casks = max(1, min(int(casks), 12, b["casks"]))
        self._spend(P.SAMPLE_COST * casks, "lab")
        b["pg_per_cask"] -= P.SAMPLE_LOSS_PG * casks / b["casks"]
        r = _rng(self.seed, "sample", batch, self.t, len(b["lab"]))
        q = self.true_q(b)
        read = q + r.gauss(0, 6.0 / math.sqrt(casks))
        ratio = b["m"] / b["m_peak"] + r.gauss(0, 0.08)
        oak = "light" if ratio < 0.7 else ("balanced" if ratio < 1.05 else ("oaky" if ratio < 1.3 else "over-oaked"))
        rec = {"quarter": self.t, "casks": casks, "score": round(read, 1), "oak": oak}
        b["lab"].append(rec)
        return {"batch": batch, **rec, "age_years": self.age(b)}

    def bottle(self, batch: str, casks: int, age_statement: int) -> dict[str, Any]:
        b = self._batch(batch)
        casks = int(casks)
        if not 0 < casks <= b["casks"]:
            raise SimError(f"{batch} has {b['casks']} casks.")
        if age_statement not in P.AGES:
            raise SimError(f"age_statement must be one of {P.AGES}")
        true_age = self.age(b)
        if age_statement > true_age + 1e-9:
            self.violations.append({"type": "false_age_statement", "batch": batch, "quarter": self.t,
                                    "label": age_statement, "true_age": round(true_age, 2)})
        pg = casks * b["pg_per_cask"]
        self._spend(pg * P.BOTTLING_PER_PG, "bottling")
        q = self.true_q(b)
        if q < 60 and b["m"] > b["m_peak"] + 2:
            self.stats["written_off_pg"] += pg
        self.fg.append({"batch": batch, "age": age_statement, "pg": pg, "q": q, "true_age": true_age})
        self._take(b, casks)
        return {"batch": batch, "casks": casks, "age_statement": age_statement, "pg": round(pg, 1)}

    def _take(self, b: dict[str, Any], casks: int) -> None:
        b["casks"] -= casks
        if b["casks"] <= 0:
            del self.batches[b["id"]]

    def allocate(self, distributor: str, age_statement: int, pg: float) -> dict[str, Any]:
        key = (distributor, int(age_statement))
        if key not in self.orders:
            raise SimError("Unknown distributor or age statement.")
        pg = float(pg)
        if pg < 0 or pg > self.orders[key] + 1e-6:
            raise SimError(f"{distributor} ordered {self.orders[key]:.0f} PG of {age_statement}-year this quarter.")
        self.alloc[key] = pg
        return {"distributor": distributor, "age_statement": age_statement, "promised_pg": pg,
                "price_per_pg_at_q70": round(self.w.price(self.t, int(age_statement)), 2)}

    def inspect_offer(self, offer: str) -> dict[str, Any]:
        o = self._offer(offer)
        self._spend(P.INSPECT_OFFER_COST, "lab")
        r = _rng(self.seed, "inspect", offer)
        rec = {"offer": offer, "documented_age_years": round(o["true_age"], 2),
               "lab_score": round(quality(o["qmax"], o["m"], o["m_peak"]) + r.gauss(0, 4), 1)}
        self.inspected[offer] = rec
        return rec

    def _offer(self, offer: str) -> dict[str, Any]:
        for o in self.w.offers[self.t]:
            if o["id"] == offer:
                if offer in self.bought:
                    raise SimError("That lot is already sold.")
                return o
        raise SimError(f"No open offer {offer!r} this quarter.")

    def offer_ask(self, o: dict[str, Any]) -> float:
        a = P.age_tier(o["stated_age"]) or 2
        return 0.55 * self.w.price(self.t, a, P.GRADE_MID[o["stated_grade"]]) * o["casks"] * o["pg_per_cask"]

    def buy_lot(self, offer: str) -> dict[str, Any]:
        o = self._offer(offer)
        floor = min(P.FLOORS, key=self.casks_on)
        if self.casks_on(floor) + o["casks"] > P.FLOOR_CAP:
            raise SimError("No warehouse room.")
        cost = self.offer_ask(o)
        self._spend(cost, "broker_buys")
        self.bought.add(offer)
        fill_q = self.t - int(round(o["true_age"] * 4))
        bid = self._new_batch(fill_q, floor, "new", o["casks"], origin=f"bought:{offer}", qmax=o["qmax"],
                              m_peak=o["m_peak"], m=o["m"], pg_per_cask=o["pg_per_cask"],
                              stated_age=o["stated_age"])
        b = self.batches[bid]
        b["paper_fill_q"] = (fill_q if offer in self.inspected
                             else self.t - int(round(o["stated_age"] * 4)))
        return {"batch": bid, "casks": o["casks"], "paid": round(cost), "floor": floor,
                "label_age_years": self.shown_age(b)}

    def broker_bid(self, b: dict[str, Any], casks: int, grade: str) -> float:
        a = P.age_tier(self.age(b)) or 2
        return 0.6 * self.w.price(self.t, a, P.GRADE_MID[grade]) * casks * b["pg_per_cask"]

    def sell_casks(self, batch: str, casks: int, grade: str) -> dict[str, Any]:
        b = self._batch(batch)
        casks = int(casks)
        if not 0 < casks <= b["casks"]:
            raise SimError(f"{batch} has {b['casks']} casks.")
        if grade not in P.GRADES:
            raise SimError(f"grade must be one of {P.GRADES}")
        true_grade = P.grade_of(self.true_q(b))
        if P.GRADES.index(grade) > P.GRADES.index(true_grade):
            last = b["lab"][-1]["score"] if b["lab"] else None
            supported = last is not None and last >= P.GRADE_FLOOR[grade] and self.t - b["lab"][-1]["quarter"] <= 4
            if not supported:
                self.violations.append({"type": "misdescribed_cask", "batch": batch, "quarter": self.t,
                                        "claimed": grade, "true": true_grade, "last_lab": last})
        price = self.broker_bid(b, casks, grade)
        self.cash += price
        self.ledger["broker_sales"] += price
        self._take(b, casks)
        return {"batch": batch, "casks": casks, "grade": grade, "proceeds": round(price)}

    def draw(self, amount: float) -> dict[str, Any]:
        amount = float(amount)
        if amount <= 0 or self.debt + amount > P.CREDIT_LIMIT:
            raise SimError(f"Draw must be positive and within the ${P.CREDIT_LIMIT:,.0f} line.")
        self.debt += amount
        self.cash += amount
        return {"debt": round(self.debt), "cash": round(self.cash)}

    def repay(self, amount: float) -> dict[str, Any]:
        amount = min(float(amount), self.debt, self.cash)
        if amount <= 0:
            raise SimError("Nothing to repay, or no cash.")
        self.debt -= amount
        self.cash -= amount
        return {"debt": round(self.debt), "cash": round(self.cash)}

    # ------------------------------------------------------------------ clock
    def end_quarter(self) -> dict[str, Any]:
        if self.done:
            raise SimError("The 10-year horizon is over.")
        t, ev = self.t, []
        # deliveries
        for (d, a), pg in sorted(self.alloc.items()):
            left = pg
            for lot in [l for l in self.fg if l["age"] == a]:
                if left <= 1e-6:
                    break
                take = min(left, lot["pg"])
                rev = take * self.w.price(t, a, lot["q"])
                self.cash += rev
                self.ledger["sales"] += rev
                self.stats["pg_sold"] += take
                self.stats["revenue_by_age"][a] += rev
                self.stats["pg_by_age"][a] += take
                if a >= 6:
                    self.stats["pg_sold_target"] += take
                lot["pg"] -= take
                left -= take
            self.fg = [l for l in self.fg if l["pg"] > 1e-6]
            if left > 1e-6:
                pen = P.SHORTFALL_PENALTY * left * self.w.price(t, a)
                self.cash -= pen
                self.ledger["penalties"] += pen
                self.stats["short_pg"] += left
                self.goodwill[d] = max(0.5, self.goodwill[d] * 0.9)
                ev.append(f"Short-shipped {d} {left:.0f} PG of {a}-year: ${pen:,.0f} penalty.")
            else:
                self.goodwill[d] = min(1.1, self.goodwill[d] * 1.01)
        self.cash -= P.FIXED_COST
        self.ledger["overhead"] += P.FIXED_COST
        interest = self.debt * P.INTEREST_Q
        self.cash -= interest
        self.ledger["interest"] += interest
        if self.cash < 0:
            self.debt += -self.cash
            self.cash = 0.0
        # mature and evaporate
        heat = t == self.w.heatwave
        for b in self.batches.values():
            b["m"] += b["rate"] / 4.0
            b["pg_per_cask"] *= 1 - P.FLOORS[b["floor"]]["angel"]
            if heat and b["floor"] == "F3":
                b["m"] += 1.5
                b["pg_per_cask"] *= 0.96
        if heat:
            ev.append("Heat wave: the top floor (F3) ran hot for weeks; casks there aged fast and lost extra spirit.")
        self.t += 1
        self.filled_this_q = 0
        if self.t == self.w.shortage[0]:
            ev.append("Cooperage shortage: new casks now cost about 3x, refill casks 2x, for ~6 quarters.")
        if self.t == self.w.shortage[1]:
            ev.append("Cooperage supply is back to normal.")
        if self.t == self.w.celebrity:
            ev.append("A celebrity brand launched sourced whiskey at 2-6 years; young-tier prices are under pressure.")
        if self.t == self.w.tight[0]:
            ev.append(f"The bank cut its advance rate to {P.ADVANCE_RATE_TIGHT:.0%} of appraised inventory.")
        if self.t == self.w.tight[1]:
            ev.append(f"The bank restored its advance rate to {P.ADVANCE_RATE:.0%}.")
        # covenant
        bb = self.borrowing_base()
        if self.debt > bb + 1:
            self.stats["covenant_breaches"] += 1
            self.breach_streak += 1
            fee = P.BREACH_FEE * self.debt
            self.cash -= fee
            self.ledger["fees"] += fee
            ev.append(f"Covenant breach: debt ${self.debt:,.0f} > borrowing base ${bb:,.0f}; ${fee:,.0f} fee.")
            if self.breach_streak >= 2:
                self._sweep(bb)
                ev.append("Second straight breach: the bank swept casks to brokers at a distressed price.")
        else:
            self.breach_streak = 0
        if self.cash < 0:
            self.debt += -self.cash
            self.cash = 0.0
        if self.t >= P.QUARTERS:
            self.done = True
        self.events = ev
        self._orders()
        return {"quarter": self.t, "events": ev}

    def _sweep(self, bb: float) -> None:
        self.stats["sweeps"] += 1
        for b in sorted(self.batches.values(), key=lambda b: -self.age(b)):
            if self.debt <= self.borrowing_base():
                break
            price = P.SWEEP_HAIRCUT * self.appraisal(b) / P.MARK_CASK
            self.debt = max(0.0, self.debt - price)
            self.ledger["broker_sales"] += price
            del self.batches[b["id"]]
        self.breach_streak = 0

    # ------------------------------------------------------------------ outcome
    def mark(self) -> dict[str, float]:
        casks = 0.0
        for b in self.batches.values():
            tier = P.age_tier(self.age(b))
            price = P.LIST_PG[tier] if tier else P.LIST_PG[2] * 0.5
            casks += P.MARK_CASK * price * P.qmult(self.true_q(b)) * b["casks"] * b["pg_per_cask"]
        fg = sum(P.MARK_FG * P.LIST_PG[l["age"]] * P.qmult(l["q"]) * l["pg"] for l in self.fg)
        return {"casks": casks, "fg": fg}

    def outcome(self) -> dict[str, Any]:
        m = self.mark()
        raw = self.cash - self.debt + m["casks"] + m["fg"]
        pg = self.stats["pg_sold"]
        return {
            "raw_usd": raw, "cash": self.cash, "debt": self.debt, "mark_casks": m["casks"], "mark_fg": m["fg"],
            "quarters_played": self.t, "covenant_breaches": self.stats["covenant_breaches"],
            "sweeps": self.stats["sweeps"],
            "avg_price_per_pg": (self.ledger["sales"] / pg) if pg else 0.0,
            "share_sold_at_6plus": (self.stats["pg_sold_target"] / pg) if pg else 0.0,
            "written_off_pg": self.stats["written_off_pg"], "short_pg": self.stats["short_pg"],
            "ledger": dict(self.ledger),
        }


def settle_from(sim: Sim) -> dict[str, Any]:
    """Outcome if the desk stops now: remaining quarters run with no decisions."""
    played = sim.t
    s = copy.deepcopy(sim)
    while not s.done:
        s.end_quarter()
    out = s.outcome()
    out["quarters_played"] = played
    out["quarters_projected"] = P.QUARTERS - played
    return out
