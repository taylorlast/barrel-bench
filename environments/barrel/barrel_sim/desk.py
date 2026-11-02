"""What the Agent sees: compact views over the Sim, and one dispatch table for actions."""

from __future__ import annotations

import json
from typing import Any

from . import params as P
from .core import Sim, SimError

ACTIONS = ("fill", "sample", "bottle", "allocate", "inspect_offer", "buy_lot", "sell_casks",
           "draw", "repay", "end_quarter")


def _r(x: float) -> float:
    return round(float(x), 1)


class Desk:
    def __init__(self, sim: Sim):
        self.sim = sim

    # ------------------------------------------------------------------ views
    def brief_data(self) -> dict[str, Any]:
        s = self.sim
        fg: dict[int, float] = {}
        for l in s.fg:
            fg[l["age"]] = fg.get(l["age"], 0.0) + l["pg"]
        return {
            "quarter": s.t, "year": s.t // 4 + 1, "q_of_year": s.t % 4 + 1, "done": s.done,
            "cash": round(s.cash), "debt": round(s.debt), "borrowing_base": round(s.borrowing_base()),
            "advance_rate": s.w.advance_rate(s.t), "credit_left": round(P.CREDIT_LIMIT - s.debt),
            "stills_left": P.STILL_CAP - s.filled_this_q,
            "cask_cost": {w: s.w.cask_cost(s.t, w) for w in P.WOODS},
            "floor_casks": {f: s.casks_on(f) for f in P.FLOORS},
            "events": list(s.events),
            "orders": [{"distributor": d, "age": a, "pg": pg, "price_q70": _r(s.w.price(s.t, a)),
                        "promised": s.alloc.get((d, a), 0.0)}
                       for (d, a), pg in sorted(s.orders.items()) if pg > 0],
            "finished_goods": {str(a): _r(v) for a, v in sorted(fg.items())},
            "offers": [{"id": o["id"], "seller": o["seller"], "casks": o["casks"], "stated_age": o["stated_age"],
                        "stated_grade": o["stated_grade"], "ask": round(s.offer_ask(o)),
                        "inspected": s.inspected.get(o["id"])}
                       for o in (s.w.offers[s.t] if s.t <= P.QUARTERS else []) if o["id"] not in s.bought],
        }

    def batch_row(self, b: dict[str, Any]) -> dict[str, Any]:
        last = b["lab"][-1] if b["lab"] else None
        return {"id": b["id"], "age": self.sim.shown_age(b), "floor": b["floor"], "wood": b["wood"],
                "casks": b["casks"], "pg": _r(b["casks"] * b["pg_per_cask"]), "origin": b["origin"],
                "lab": last}

    def cellar_data(self) -> dict[str, Any]:
        rows = [self.batch_row(b) for b in sorted(self.sim.batches.values(), key=lambda b: b["fill_q"])]
        return {"quarter": self.sim.t, "batches": rows,
                "total_casks": sum(r["casks"] for r in rows), "total_pg": _r(sum(r["pg"] for r in rows))}

    def batch_data(self, batch: str) -> dict[str, Any]:
        if batch not in self.sim.batches:
            raise SimError(f"Unknown batch {batch!r}")
        b = self.sim.batches[batch]
        return {**self.batch_row(b), "lab_history": b["lab"], "stated_age_at_purchase": b["stated_age"],
                "broker_bid_per_cask": {g: round(self.sim.broker_bid(b, 1, g)) for g in P.GRADES}}

    # ------------------------------------------------------------------ text
    def brief_text(self) -> str:
        d = self.brief_data()
        lines = [f"Q{d['quarter'] + 1}/40 (year {d['year']} Q{d['q_of_year']})" + (" DONE" if d["done"] else ""),
                 f"cash ${d['cash']:,} debt ${d['debt']:,} borrowing base ${d['borrowing_base']:,} "
                 f"(advance {d['advance_rate']:.0%}) line left ${d['credit_left']:,}",
                 f"stills left {d['stills_left']} casks; cask cost new ${d['cask_cost']['new']:.0f} "
                 f"refill ${d['cask_cost']['refill']:.0f}; floors " +
                 " ".join(f"{f}:{n}" for f, n in d["floor_casks"].items())]
        for e in d["events"]:
            lines.append("EVENT " + e)
        lines.append("orders (distributor age PG @ $/PG at q70):")
        for o in d["orders"]:
            lines.append(f"  {o['distributor']} {o['age']}y {o['pg']:.0f} @ {o['price_q70']}"
                         + (f" promised {o['promised']:.0f}" if o["promised"] else ""))
        lines.append("finished goods PG: " + (", ".join(f"{a}y {v}" for a, v in d["finished_goods"].items()) or "none"))
        for o in d["offers"]:
            lines.append(f"offer {o['id']} {o['seller']}: {o['casks']} casks, said {o['stated_age']}y "
                         f"{o['stated_grade']}, ask ${o['ask']:,}" + (f" inspected {o['inspected']}" if o["inspected"] else ""))
        return "\n".join(lines)

    def cellar_text(self) -> str:
        d = self.cellar_data()
        out = [f"{d['total_casks']} casks, {d['total_pg']} PG"]
        for r in d["batches"]:
            lab = f" lab q{r['lab']['quarter'] + 1} {r['lab']['score']} {r['lab']['oak']}" if r["lab"] else ""
            out.append(f"{r['id']} {r['age']:.2f}y {r['floor']} {r['wood']} {r['casks']}c {r['pg']}PG {r['origin']}{lab}")
        return "\n".join(out)

    def view(self, name: str, fmt: str, **kw: Any) -> Any:
        if name == "brief":
            return self.brief_data() if fmt == "json" else self.brief_text()
        if name == "cellar":
            return self.cellar_data() if fmt == "json" else self.cellar_text()
        if name == "batch":
            data = self.batch_data(**kw)
            return data if fmt == "json" else json.dumps(data, separators=(",", ":"))
        raise SimError(f"unknown view {name}")

    # ------------------------------------------------------------------ dispatch
    def call(self, name: str, **kw: Any) -> Any:
        """Policy-facing entry point: JSON views and actions, as through the App."""
        kw.pop("fmt", None)
        if name in ("brief", "cellar", "batch"):
            return self.view(name, "json", **kw)
        if name in ("write_note", "read_notes"):
            return "ok"
        if name not in ACTIONS:
            raise SimError(f"unknown action {name}")
        out = getattr(self.sim, name)(**kw)
        if name == "end_quarter":
            return self.brief_data()
        return out
