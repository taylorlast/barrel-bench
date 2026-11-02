"""Barrel v2: start up and run a craft whiskey distillery, as ten Plural Apps.

Each App mirrors a system a real founder uses (calendar/briefing, email, TTB/state
compliance portals, production log, rickhouse inventory, purchasing, sales/CRM, bank,
HR, market data). They all act on one shared ``barrel_sim.World``: the ``office`` App
builds it from the Task's ``scenario`` and publishes it; the others attach on reset
(see barrel_sim/registry.py). Counterparties (TTB, state board, distributors, control
boards, brokers, suppliers, bank, recruiter, staff) are behaviour models inside the
World whose messages arrive in the ``inbox`` App. Exogenous randomness (17 factors,
each with its own seeded stream, presets and scheduled shocks) lives in
barrel_sim/exogenous.py and is configured by the Task's ``scenario`` block.

An action that the World refuses raises ValueError, which Plural returns to the Agent
as feedback, and nothing changes.
"""

from __future__ import annotations

from typing import Any

from plural import App, State, action, initial

from barrel_sim import report as R
from barrel_sim import registry
from barrel_sim.scenario import Scenario
from barrel_sim.world import World


# ============================================================================ office
class OfficeState(State):
    seed: int = initial(0, description="Per-Trial seed. Used as scenario.master_seed when the scenario sets none.")
    scenario: dict[str, Any] = initial({}, description="Scenario block: preset, master_seed, horizon_years, "
                                       "factors (per-factor enabled/volatility/event_rate/seed), shocks. "
                                       "See docs/DESIGN.md.")
    split: str = initial("dev", description="Bookkeeping only: dev or test.")
    week: int = 0
    done: bool = False
    insolvent: bool = False
    actions_taken: int = 0
    scenario_resolved: dict[str, Any] = {}
    settlement: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    horizon_weeks: int = 0
    log_length: int = 0


class Office(App[OfficeState]):
    """Founder's desk: weekly briefing, calendar and the clock. Ending the week advances the whole world."""

    def reset(self, initial_state):
        """Build the World from the Task's scenario and publish it for the other Apps."""
        super().reset(initial_state)
        sc = Scenario.from_dict(self.state.scenario, default_seed=self.state.seed)
        self._world = World(sc)
        registry.publish(self._world)
        self.state.scenario_resolved = sc.summary()
        self._sync()
        b = R.briefing(self._world)
        return ("You are the founder and CEO of a new craft whiskey distillery. It is Monday "
                f"{b['date']}. You have ${b['cash']:,.0f} of seed equity and {sc.horizon_weeks} weeks "
                "until the board values the company. Nothing is leased, licensed, built or hired yet. "
                "Read your inbox and the office briefing, then run the company one week at a time "
                "with office.end_week.")

    def _w(self) -> World:
        w = getattr(self, "_world", None)
        if w is None:
            raise ValueError("World not initialised; reset the environment.")
        return w

    def _sync(self) -> None:
        w = self._world
        self.state.week = w.t
        self.state.done = w.done
        self.state.insolvent = w.insolvent
        self.state.violations = list(w.violations)
        self.state.stats = dict(w.stats)
        self.state.horizon_weeks = w.H
        self.state.actions_taken = len(w.log)
        self.state.log_length = len(w.log)
        self.state.settlement = R.settle(w)

    def snapshot(self):
        """State for Verifiers: always re-settled from the live World."""
        if getattr(self, "_world", None) is not None:
            self._sync()
        return self.state.model_dump(mode="json")

    def terminated(self) -> bool:
        w = getattr(self, "_world", None)
        return bool(w and w.done)

    def step_info(self) -> dict[str, Any]:
        w = getattr(self, "_world", None)
        return {"week": w.t if w else 0}

    @action
    def briefing(self) -> dict[str, Any]:
        """This week's briefing: date, cash, debt, barrels, finished bottles, unread email count,
        open decisions, what happened last week, and the next filing and reply deadlines."""
        return R.briefing(self._w())

    @action
    def end_week(self, weeks: int = 1) -> dict[str, Any]:
        """Close the week (1-4 weeks at once). Deliveries land, permits progress, whiskey ages,
        customers buy, counterparties act, payroll/rent/loans are paid, then the next briefing is
        returned. Insolvency at a month-end (cash < -$25k with no credit) ends the episode."""
        w = self._w()
        w.end_week(weeks)
        self._sync()
        return R.briefing(w)

    @action
    def add_reminder(self, week: int, text: str) -> str:
        """Calendar: put a reminder in your inbox the week before `week` (an absolute week number)."""
        return self._w().add_reminder(week, text)

    @action
    def catalog(self) -> dict[str, Any]:
        """Reference sheet: sites you can lease, still packages, market salaries, insurance
        policies and the spirit classes you can label."""
        return R.catalog()


# ============================================================================ attached Apps
class _AttachedState(State):
    attached: bool = False


class _Attached(App[_AttachedState]):
    def reset(self, initial_state):
        super().reset(initial_state)
        self._world = registry.current()
        self.state.attached = True
        return None

    def _w(self) -> World:
        w = getattr(self, "_world", None)
        if w is None:
            raise ValueError("World not initialised; reset the environment.")
        return w


class Inbox(_Attached):
    """Email. Regulators, distributors, control boards, brokers, suppliers, the bank, the recruiter
    and your staff write here; some emails need a decision by a reply-by date."""

    @action
    def list_emails(self, unread_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        """List emails, open decisions first then newest: id, date, from, subject, status, reply_by."""
        return R.inbox(self._w(), unread_only, limit)

    @action
    def read_email(self, email_id: str) -> dict[str, Any]:
        """Read one email (marks it read). `decisions` lists the decisions it accepts, if any."""
        return R.read_email(self._w(), email_id)

    @action
    def reply(self, email_id: str, body: str = "", decision: str | None = None, price: float | None = None) -> str:
        """Reply to an email. Answer regulator information requests with a body. Proposals, purchase
        orders, bulk bids and sourced-whiskey offers need decision='accept'|'decline' (bulk bids also
        'counter' with price; sourced offers also 'inspect')."""
        return self._w().reply_email(email_id, body, decision, price)

    @action
    def send(self, to: str, subject: str, body: str) -> str:
        """Send a free-form email. Counterparties act on structured replies, not on free-form mail."""
        return self._w().send_email(to, subject, body)


class Compliance(_Attached):
    """TTB Permits Online / COLAs Online / Pay.gov and the state ABC portal."""

    @action
    def status(self) -> dict[str, Any]:
        """Permits, bond, labels, filing frequency, excise rates, returns and reports filed,
        notices, outstanding penalties and deadlines."""
        return R.compliance(self._w())

    @action
    def apply_permit(self, kind: str) -> str:
        """Apply for 'federal_dsp' (needs a lease and equipment on order; TTB takes ~45-75 days
        and may email questions you must answer within 30 days), then 'state_manufacturer' (needs the
        DSP), then 'state_retail' (tasting room sales; needs the state license). Producing, bottling
        or selling before you hold the licenses is a fatal violation."""
        return self._w().apply_permit(kind)

    @action
    def obtain_bond(self, penal_sum: float) -> str:
        """Buy a DSP bond (premium ~2%/yr of penal_sum). Required once excise liability exceeds
        $50,000 a year."""
        return self._w().obtain_bond(penal_sum)

    @action
    def submit_label(self, brand: str, spirit_class: str, proof: float, age_statement_years: int | None = None,
                     distilled_by: str = "us") -> str:
        """Submit a COLA (needs the DSP; ~1-3 weeks). spirit_class: vodka, gin, white_whiskey,
        bourbon, straight_bourbon, bottled_in_bond_bourbon, rye, straight_rye. Whiskey under 4 years
        must carry an age statement; 'straight' needs >= 2 years and entry proof <= 125; bottled in
        bond needs 100 proof, >= 4 years, one season, distilled by us. Bottling spirit that does not
        meet the label is label fraud (fatal)."""
        return self._w().submit_label(brand, spirit_class, proof, age_statement_years, distilled_by)

    @action
    def tax_ledger(self, period: str | None = None) -> dict[str, Any]:
        """Your bookkeeper's ledger of taxable removals (bottles leaving bond), optionally for a
        period 'YYYY-Qn' or 'YYYY-MM': proof gallons and excise owed by label."""
        return R.tax_ledger(self._w(), period)

    @action
    def file_excise_return(self, period: str, proof_gallons: float, tax_amount: float) -> str:
        """File and pay an excise return for a period that has ended: 'YYYY-Qn' if last year's
        liability was <= $50k, else 'YYYY-MM'. Due 14 days after period end. Under-reporting by more
        than 5% (and $1,000) is excise fraud (fatal); late filing draws penalties."""
        return self._w().file_excise_return(period, proof_gallons, tax_amount)

    @action
    def file_operations_report(self, month: str) -> str:
        """File the monthly production/storage/processing reports for 'YYYY-MM' (due the 15th of the
        next month once you hold a DSP permit)."""
        return self._w().file_operations_report(month)


class Production(_Attached):
    """Still house: site, equipment, crew capacity, tanks and the production log."""

    @action
    def status(self) -> dict[str, Any]:
        """Site and build-out, equipment and commissioning date, downtime, crew capacity left this
        week, tanks, raw materials and finished goods."""
        return R.production(self._w())

    @action
    def sign_lease(self, site_id: str) -> str:
        """Lease a site (see office.catalog): rural_barn, edge_of_town or downtown. Pays the deposit
        and 40% of the build-out; the rest is due on completion."""
        return self._w().sign_lease(site_id)

    @action
    def order_equipment(self, package_id: str) -> str:
        """Order a still package: pot_250, hybrid_500 or column_1500. 50% deposit now, 50% on
        commissioning."""
        return self._w().order_equipment(package_id)

    @action
    def run(self, spirit: str, proof_gallons: float) -> str:
        """Distill this week: bourbon, rye or white_whiskey from grain; vodka or gin from purchased
        NGS. Limited by still capacity x crew (a head distiller matters), tank space and inputs.
        Fermentation can get infected (worse in heat and with low sanitation)."""
        return self._w().run_production(spirit, proof_gallons)

    @action
    def fill_barrels(self, count: int, entry_proof: float = 120.0, floor: str = "mid", spirit: str = "bourbon") -> str:
        """Barrel new make from the bourbon or rye tank into new charred oak (53 gal). Floors: low
        (cool, slow), mid, high (hot, fast, more evaporation)."""
        return self._w().fill_barrels(count, entry_proof, floor, spirit)

    @action
    def bottle(self, label_id: str, source: str, bottles: int) -> str:
        """Bottle 750ml under an approved label from a tank (vodka, gin, white_whiskey) or from
        comma-separated lot ids. Needs dry goods and crew. Bottles stay in bond until sold."""
        return self._w().bottle(label_id, source, bottles)

    @action
    def maintenance(self) -> str:
        """Preventive maintenance ($6,000; the still is offline for the rest of this week). Failure
        risk climbs with weeks since the last service."""
        return self._w().maintenance()

    @action
    def set_sanitation(self, level: str) -> str:
        """Sanitation program: low (saves $300/wk, more infections), standard, high (+$900/wk)."""
        return self._w().set_sanitation(level)


class Warehouse(_Attached):
    """Rickhouse inventory: lots, floors, climate, and the lab."""

    @action
    def status(self) -> dict[str, Any]:
        """Lots with barrels, floor, fill date, paperwork age, entry proof, estimated PG per barrel and
        last lab sample; capacity; floor temperatures and humidity this week."""
        return R.warehouse(self._w())

    @action
    def sample_lot(self, lot_id: str, barrels: int = 3) -> dict[str, Any]:
        """Thief 1-12 barrels ($45 each): a noisy sensory score (0-100; more barrels, less noise), oak
        note (light, balanced, oak-forward, over-oaked) and proof."""
        return self._w().sample_lot(lot_id, barrels)

    @action
    def move_lot(self, lot_id: str, floor: str) -> str:
        """Move a lot to another floor ($18/barrel)."""
        return self._w().move_lot(lot_id, floor)


class Procurement(_Attached):
    """Purchasing: supplier quotes and purchase orders (paid on order)."""

    @action
    def quotes(self) -> dict[str, Any]:
        """Today's prices and lead times: grain (bushels), NGS (PG), new barrels, glass/dry goods
        sets; plus open orders and stock on hand."""
        return R.procurement(self._w())

    @action
    def order(self, item: str, quantity: float) -> str:
        """Place a PO: grain_bu, ngs_pg, new_barrels or glass_bottles. Paid now, delivered after the
        quoted lead time (cooperage and glass lead times swing with supply shocks)."""
        return self._w().place_order(item, quantity)


class Sales(_Attached):
    """Sales and CRM: labels and prices, tasting room, marketing, distributor and control-state
    accounts, bulk barrel listings."""

    @action
    def status(self) -> dict[str, Any]:
        """Labels with stock and prices, tasting room, awareness survey, accounts and their
        depletions/inventory, recent revenue by channel, open POs and bulk listings."""
        return R.sales(self._w())

    @action
    def set_price(self, label_id: str, channel: str, price: float) -> str:
        """Set a label's per-bottle price for 'wholesale' (to distributors/boards) or 'tasting_room'."""
        return self._w().set_price(label_id, channel, price)

    @action
    def set_tasting_room(self, open: bool) -> str:  # noqa: A002
        """Open or close the tasting room (needs a finished build-out; selling without the state
        retail privilege is a fatal violation). Cocktails and bottles sell to visitors."""
        return self._w().set_tasting_room(open)

    @action
    def set_marketing(self, weekly_budget: float) -> str:
        """Weekly marketing spend ($0-$50,000), which builds awareness slowly."""
        return self._w().set_marketing(weekly_budget)

    @action
    def pitch_distributor(self, distributor_id: str, label_ids: str) -> str:
        """Pitch a distributor or importer (D-HOME, D-BIG, D-REG1, D-REG2, X-EU) with comma-separated
        approved labels (>= 300 bottles on hand; $2,500 of samples and travel). They answer by email
        in a few weeks. Pitch a signed account to add new labels."""
        return self._w().pitch_distributor(distributor_id, label_ids)

    @action
    def apply_control_listing(self, board_id: str, label_id: str) -> str:
        """Submit a label to a control-state board (C-OH, C-PA). Boards decide quarterly."""
        return self._w().apply_control_listing(board_id, label_id)

    @action
    def list_barrels(self, lot_id: str, barrels: int, stated_age_years: float, ask_per_barrel: float) -> str:
        """List whole barrels with a broker. A bid arrives by email in ~2 weeks. Describing barrels
        as older than they are is fraud (fatal)."""
        return self._w().list_barrels_for_sale(lot_id, barrels, stated_age_years, ask_per_barrel)


class Finance(_Attached):
    """Bank portal: cash, loans, lines and insurance."""

    @action
    def status(self) -> dict[str, Any]:
        """Cash, receivables, loans, pending applications, prime rate, insurance and estimated
        monthly fixed costs."""
        return R.finance(self._w())

    @action
    def apply_loan(self, kind: str, amount: float) -> str:
        """Apply for 'sba_7a' (up to $5M at prime+2.75%, 10-year amortization; needs a lease and
        equipment on order) or 'barrel_line' (revolver at 50% of appraised barrels, prime+4%; needs
        150+ barrels; month-end borrowing-base covenant). Decisions take weeks; amounts may be cut."""
        return self._w().apply_loan(kind, amount)

    @action
    def draw(self, amount: float) -> str:
        """Draw on the barrel line up to availability."""
        return self._w().draw(amount)

    @action
    def repay(self, loan: str, amount: float) -> str:
        """Prepay principal on 'sba_7a' or 'barrel_line'."""
        return self._w().repay(loan, amount)

    @action
    def buy_insurance(self, policy: str) -> str:
        """Bind a 12-month policy: none, basic (70% of barrel loss, $50k deductible) or full (95%,
        $25k deductible, 8 weeks business interruption). Auto-renews."""
        return self._w().buy_insurance(policy)


class People(_Attached):
    """HR: staff, job postings and candidates."""

    @action
    def status(self) -> dict[str, Any]:
        """Staff, available candidates (experience, reference hint, salary ask), open postings and
        market salaries."""
        return R.people(self._w())

    @action
    def post_job(self, role: str, salary: float) -> str:
        """Post a role (head_distiller, assistant_distiller, tasting_room_manager, sales_manager,
        bookkeeper); the recruiter emails three candidates in 2-5 weeks."""
        return self._w().post_job(role, salary)

    @action
    def hire(self, candidate_id: str, salary: float) -> str:
        """Offer a candidate a salary; below ~95% of their ask they walk. Starts in 2 weeks. Paying
        under market raises the chance they quit later."""
        return self._w().hire(candidate_id, salary)

    @action
    def let_go(self, staff_id: str) -> str:
        """Let someone go with two weeks' severance."""
        return self._w().let_go(staff_id)


class Market(_Attached):
    """Market data terminal: commodities, bulk whiskey, rates, lead times, tariffs and headlines."""

    @action
    def snapshot_market(self) -> dict[str, Any]:
        """Corn, energy, bulk new-fill barrel price (now and 13 weeks ago), prime rate, cooperage and
        glass lead times, EU tariff, and recent industry headlines. The future is not shown."""
        return R.market(self._w())
