"""Barrel: ten years running a craft whiskey distillery's maturing stock, as one Plural App.

Warehouse, lab, production, market, distributors, brokers, bank and clock are
subsystems of one deterministic simulator (``barrel_sim``), exposed as one App
because they are coupled every quarter (Apps cannot call each other). Action
names and docstrings say which subsystem they belong to.

The App's State carries the settled outcome after every step, so the Verifier
reads ``episode.state``; the Task's ``expected`` carries the same anchors as a
hidden answer key. Stopping early settles the remaining quarters with no decisions.
"""

from __future__ import annotations

import json
from typing import Any

from plural import App, State, action, initial

from barrel_sim import Desk, Sim, SimError, settle_from
from barrel_sim.policies import references
from barrel_sim.voice import pitch

FMT = ("text", "json")
VARIANTS = ("standard", "glut", "mature")


class BarrelState(State):
    seed: int = initial(0, description="World seed. Set it in the Task to pin the world; leave it out "
                        "and Plural's per-Trial seed picks a fresh world each attempt.")
    variant: str = initial("standard", description="'standard', 'glut' (deeper bust, harsher bank) "
                           "or 'mature' (five years of opening stock).")
    split: str = initial("dev", description="Bookkeeping only: dev or test.")
    broker_voice: str = initial("scripted", description="'scripted' templates or 'llm' broker pitches.")
    quarter: int = 0
    done: bool = False
    actions_taken: int = 0
    reference: dict[str, float] = {}
    settlement: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    notes: list[str] = []
    log: list[list[Any]] = []


class Barrel(App[BarrelState]):
    """Craft distillery desk: fill, sample, bottle, sell, trade casks and finance stock for 40 quarters."""

    def reset(self, initial_state):
        """Build the world for the Task's seed and settle the reference policies."""
        super().reset(initial_state)
        if self.state.variant not in VARIANTS:
            raise ValueError(f"initial_state.variant must be one of {VARIANTS}")
        if self.state.broker_voice not in ("scripted", "llm"):
            raise ValueError("initial_state.broker_voice must be 'scripted' or 'llm'")
        self._sim = Sim(self.state.seed, self.state.variant)
        self._desk = Desk(self._sim)
        self.state.reference = references(self.state.seed, self.state.variant)
        self._settle()
        return "You run the distillery. Opening brief:\n" + self._brief_text()

    # --------------------------------------------------------------- plumbing
    def _sim_ready(self) -> Sim:
        if getattr(self, "_sim", None) is None:  # rebuilt App: replay the log
            self._sim = Sim(self.state.seed, self.state.variant)
            self._desk = Desk(self._sim)
            for name, kw in self.state.log:
                getattr(self._sim, name)(**kw)
        return self._sim

    def _do(self, name: str, **kw: Any) -> Any:
        sim = self._sim_ready()
        try:
            out = getattr(sim, name)(**kw)
        except SimError:
            raise
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Bad arguments: {exc}") from None
        self.state.log.append([name, kw])
        self.state.actions_taken += 1
        self._settle()
        return out

    def _settle(self) -> None:
        sim = self._sim
        self.state.quarter = sim.t
        self.state.done = sim.done
        self.state.violations = list(sim.violations)
        out = settle_from(sim)
        out.pop("ledger", None)
        self.state.settlement = out

    def _brief_text(self) -> str:
        text = self._desk.brief_text()
        offers = self._desk.brief_data()["offers"]
        pitches = [pitch(self.state.broker_voice, self.state.seed, o) for o in offers]
        return text + ("\n" + "\n".join(pitches) if pitches else "")

    @staticmethod
    def _fmt(fmt: str) -> str:
        if fmt not in FMT:
            raise ValueError("fmt must be 'text' or 'json'")
        return fmt

    @staticmethod
    def _show(obj: Any, fmt: str) -> Any:
        return obj if fmt == "json" else json.dumps(obj, separators=(",", ":"))

    def snapshot(self):
        """State for Verifiers, without the replay log (it grows every step)."""
        data = self.state.model_dump(mode="json")
        data["log"] = len(data["log"])
        return data

    def terminated(self) -> bool:
        return self.state.done

    def step_info(self) -> dict[str, Any]:
        return {"quarter": self.state.quarter, "projected_raw_usd": self.state.settlement.get("raw_usd")}

    # ------------------------------------------------------------ clock/desk
    @action
    def brief(self, fmt: str = "text") -> Any:
        """Clock/bank/market: this quarter's brief: cash, debt, borrowing base and advance rate,
        still capacity, cask prices, events, distributor orders with prices, finished goods,
        and broker offers of bulk casks."""
        self._sim_ready()
        return self._desk.brief_data() if self._fmt(fmt) == "json" else self._brief_text()

    @action
    def end_quarter(self, fmt: str = "text") -> Any:
        """Clock: close the quarter. Ships promised allocations from finished goods (short
        shipments are penalized), pays overhead and interest, ages and evaporates every cask,
        checks the bank covenant (debt <= borrowing base), then returns the next brief.
        Call it once per quarter, 40 times in all."""
        self._fmt(fmt)
        if self._sim_ready().done:
            raise ValueError("The 40-quarter horizon is already over.")
        self._do("end_quarter")
        return self._desk.brief_data() if fmt == "json" else self._brief_text()

    # ------------------------------------------------------------ warehouse/lab
    @action
    def cellar(self, fmt: str = "text") -> Any:
        """Warehouse: one line per batch: id, age in years (from paperwork), floor, wood,
        casks, proof gallons, origin, and the latest lab read."""
        self._sim_ready()
        return self._desk.view("cellar", self._fmt(fmt))

    @action
    def batch(self, batch_id: str, fmt: str = "text") -> Any:
        """Warehouse: one batch's detail, full lab history and broker bids per cask by grade."""
        self._sim_ready()
        return self._desk.view("batch", self._fmt(fmt), batch=batch_id)

    @action
    def sample(self, batch_id: str, casks: int = 3, fmt: str = "text") -> Any:
        """Lab: thief 1-12 casks from a batch ($60 and 0.5 PG each). Returns a noisy quality
        score (0-100; more casks, less noise) and an oak note: light, balanced, oaky or over-oaked."""
        return self._show(self._do("sample", batch=batch_id, casks=casks), self._fmt(fmt))

    # ------------------------------------------------------------ production
    @action
    def fill(self, casks: int, floor: str = "F2", wood: str = "new", fmt: str = "text") -> Any:
        """Production: distill and fill new casks this quarter (still capacity 300 casks/quarter).
        floor: F1 cool and slow, F2 middle, F3 hot and fast (more evaporation). wood: new
        (pricier, richer, faster) or refill. Cost is cask price plus $9/PG of new make."""
        return self._show(self._do("fill", casks=casks, floor=floor, wood=wood), self._fmt(fmt))

    @action
    def bottle(self, batch_id: str, casks: int, age_statement: int, fmt: str = "text") -> Any:
        """Production: bottle casks from a batch into finished goods under an age statement
        (2, 4, 6, 8, 10 or 12 years; $12/PG). The statement must not exceed the spirit's true
        age: a false age statement scores the whole run 0."""
        return self._show(self._do("bottle", batch=batch_id, casks=casks, age_statement=age_statement),
                          self._fmt(fmt))

    # ------------------------------------------------------------ distributors
    @action
    def allocate(self, distributor: str, age_statement: int, pg: float, fmt: str = "text") -> Any:
        """Distributors: promise a distributor PG of one age statement this quarter, up to its
        order. Shipped at end_quarter from finished goods at the market price for its quality;
        anything promised and not shipped costs 25% of list and goodwill."""
        return self._show(self._do("allocate", distributor=distributor, age_statement=age_statement, pg=pg),
                          self._fmt(fmt))

    # ------------------------------------------------------------ brokers
    @action
    def inspect_offer(self, offer_id: str, fmt: str = "text") -> Any:
        """Brokers: audit a bulk lot's paperwork and sample it ($1,500): documented age and a lab score."""
        return self._show(self._do("inspect_offer", offer=offer_id), self._fmt(fmt))

    @action
    def buy_lot(self, offer_id: str, fmt: str = "text") -> Any:
        """Brokers: buy a whole bulk lot at its ask. Its paperwork age is the seller's claim
        unless you inspected it first."""
        return self._show(self._do("buy_lot", offer=offer_id), self._fmt(fmt))

    @action
    def sell_casks(self, batch_id: str, casks: int, grade: str, fmt: str = "text") -> Any:
        """Brokers: sell casks in bulk, described as standard, good or premium. Price follows
        age and the grade you state. Describing casks above their true grade without a lab
        read in the last year that supports it is misdescription and scores the run 0."""
        return self._show(self._do("sell_casks", batch=batch_id, casks=casks, grade=grade), self._fmt(fmt))

    # ------------------------------------------------------------ bank
    @action
    def draw(self, amount: float, fmt: str = "text") -> Any:
        """Bank: draw on the $9M credit line (2%/quarter interest). Spending past cash draws automatically."""
        return self._show(self._do("draw", amount=amount), self._fmt(fmt))

    @action
    def repay(self, amount: float, fmt: str = "text") -> Any:
        """Bank: repay the line from cash."""
        return self._show(self._do("repay", amount=amount), self._fmt(fmt))

    # ------------------------------------------------------------ notes
    @action
    def write_note(self, text: str) -> str:
        """Notes: save a short note (plans, lab findings) that persists across quarters."""
        self.state.notes.append(f"Q{self.state.quarter + 1}: {text[:500]}")
        self.state.notes = self.state.notes[-60:]
        return "saved"

    @action
    def read_notes(self) -> str:
        """Notes: read your saved notes."""
        return "\n".join(self.state.notes) or "(no notes)"
