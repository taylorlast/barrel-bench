"""Procedural counterparties: identities, personalities and hidden economic types.

Nothing in this module is an evaluated Agent. Parties are sampled from the world's
``parties`` RNG stream (``{master_seed}|parties|{counterparties.seed}``), independent of
the 17 exogenous-factor streams. A hidden, deterministic economic model (reservation
prices, thresholds, memory, reputation) decides every accept/reject and every number
that appears in a message. The Voice layer only phrases those facts.

The *structure* of the three-tier market is realistic and stable (there is always a
home-state wholesaler, some regionals, a large house, control-state boards and an
exporter) so a competent operator still has a path. The *people and firms* occupying
those seats — names, temperament, hidden constraints, when they enter or leave — are
not defined ahead of time.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- name banks
# Fictional firms on purpose: we do not simulate Southern Glazer's, RNDC, or any
# named government liquor board as itself.

FIRST = (
    "Avery", "Jordan", "Sam", "Riley", "Casey", "Morgan", "Drew", "Quinn", "Harper",
    "Reese", "Skyler", "Cameron", "Rowan", "Finley", "Parker", "Elliot", "Hayden",
    "Jamie", "Alex", "Taylor", "Chris", "Pat", "Dana", "Lee", "Robin", "Shannon",
    "Marlow", "Sasha", "Kai", "Eden", "Blake", "Sydney", "Frankie", "Jesse",
    "Nic", "Remy", "Wren", "Sol", "Arden", "Lake",
)

LAST = (
    "Hale", "Vargas", "Nguyen", "Patel", "Okafor", "Brennan", "Sato", "Keller",
    "Ibarra", "Cohen", "Duffy", "Bergstrom", "Cho", "Moreau", "Alvarez", "Singh",
    "Whitaker", "Rosso", "Kaur", "Madsen", "Okada", "Tremblay", "Nwosu", "Petrov",
    "McRae", "Yilmaz", "Costa", "Berg", "Fontaine", "Shah", "Horowitz", "Lindqvist",
    "Abebe", "Carmichael", "Dubois", "Ellis", "Farouk", "Gupta", "Huang", "Inoue",
)

FIRM_A = (
    "Iron Gate", "Riverbend", "Hickory Ridge", "Summit", "Lake Country", "Oak & Rye",
    "Frontier", "Commonwealth", "Copperline", "Red Clover", "Whispering Fork",
    "Blackland", "Millstone", "Cedar Post", "Blue Heron", "Saltlick", "Two Rivers",
    "Hazelwood", "Foxhollow", "Grand Portage", "Painted Horse", "North Fork",
    "Ember Hill", "Whetstone", "Silver Maples", "Caney Fork", "Dry Creek",
)

FIRM_B = {
    "distributor": ("Wine & Spirits", "Beverage Co.", "Craft Distributors", "Fine Spirits",
                    "Wholesale", "Hospitality Partners", "Spirits Division"),
    "export": ("Imports", "Export Agency", "Cask & Bottle Ltd.", "International Spirits"),
    "broker": ("Barrel Brokers", "Cask Exchange", "Warehouse Receipts", "Bulk Spirits Desk"),
    "grain": ("Grain Elevator", "Farms", "Milling & Feed", "Cash Grain"),
    "cooperage": ("Cooperage", "Barrel Works", "Oak Mill", "Stave & Hoop"),
    "glass": ("Glass", "Container Co.", "Bottling Supplies", "Closures & Glass"),
    "ngs": ("Neutral Spirits", "Grain Alcohol", "Industrial Alcohol Desk"),
    "bank": ("Bank", "Community Bank", "National Bank", "Credit Union", "Bancorp"),
    "lender": ("Capital", "ABL Desk", "Barrel Finance", "Inventory Lending"),
    "insurer": ("Mutual", "Assurance", "Underwriters", "Farm & Distillery Ins."),
    "recruiter": ("Staffing", "Talent", "Search Partners"),
    "landlord": ("Properties", "Holdings", "Realty", "Land Trust"),
    "press": ("Daily", "Review", "Sip Magazine", "Trade Journal"),
    "fabricator": ("Stills", "Coppersmiths", "Process Equipment"),
    "retailer": ("Tavern", "Bottle Shop", "Cocktail Bar", "Inn"),
    "contract_client": ("Distilling Co.", "Private Label", "Hotel Group"),
    "investor": ("Partners", "Holdings", "Ventures"),
    "lab": ("Laboratory", "Cask Analysis", "Independent Lab"),
}

HOME_STATES = (
    "Kentucky", "Tennessee", "Indiana", "Texas", "Colorado", "New York", "Oregon",
    "Missouri", "North Carolina", "Illinois", "Ohio", "Pennsylvania", "Washington",
)

# Control jurisdictions (real tier-1 / control states). Agency titles are lightly
# fictionalized so we are not claiming to simulate a named commission's actual process.
CONTROL_STATES = (
    "Ohio", "Pennsylvania", "Alabama", "Virginia", "New Hampshire", "Utah", "Maine",
    "Vermont", "Montana", "Wyoming", "Idaho", "Mississippi", "North Carolina",
)

CONTROL_TITLES = (
    "Liquor Control Board", "ABC Commission", "Spirits Authority",
    "Beverage Control Board", "State Stores Commission",
)

TEMPERAMENTS = ("cautious", "aggressive", "warm", "bureaucratic", "opportunistic")
DEFAULT_TEMPERAMENT_WEIGHTS = {
    "cautious": 0.25, "aggressive": 0.15, "warm": 0.25, "bureaucratic": 0.20, "opportunistic": 0.15,
}

STYLE = {
    "cautious": "measured, asks a lot of questions",
    "aggressive": "direct and in a hurry",
    "warm": "friendly and relationship-oriented",
    "bureaucratic": "formal and process-heavy",
    "opportunistic": "deal-focused",
}

CONSTRAINTS = (
    "no_unaged", "wants_exclusive", "price_sensitive", "relationship_first",
    "allocated_book", "volume_hungry", "prefers_aged", "slow_pay",
)

# Channel seats that exist at week 0 so a competent founder has a path. Identities
# sitting in those seats are still sampled. Extra firms (above this count) may enter later.
CHANNEL_SEATS = (
    {"kind": "distributor", "tier": "home", "size": (0.95, 1.15), "threshold": (0.28, 0.34), "margin": (0.27, 0.29)},
    {"kind": "distributor", "tier": "regional", "size": (1.10, 1.35), "threshold": (0.40, 0.46), "margin": (0.27, 0.29)},
    {"kind": "distributor", "tier": "regional", "size": (1.25, 1.55), "threshold": (0.46, 0.52), "margin": (0.28, 0.30)},
    {"kind": "distributor", "tier": "national", "size": (2.80, 3.50), "threshold": (0.58, 0.66), "margin": (0.29, 0.31)},
)

DEFAULT_POPS = {
    "distributor": {"min": 4, "max": 7},
    "control_board": {"min": 2, "max": 3},
    "exporter": {"min": 1, "max": 2},
    "broker": {"min": 2, "max": 4},
    "grain": {"min": 2, "max": 4},
    "cooperage": {"min": 2, "max": 3},
    "glass": {"min": 1, "max": 3},
    "ngs": {"min": 1, "max": 2},
    "bank": {"min": 1, "max": 2},
    "lender": {"min": 1, "max": 2},
    "insurer": {"min": 1, "max": 2},
    "recruiter": {"min": 1, "max": 1},
    "press": {"min": 1, "max": 3},
    "fabricator": {"min": 1, "max": 2},
    "lab": {"min": 1, "max": 1},
    "retailer": {"min": 0, "max": 0},
    "contract_client": {"min": 0, "max": 0},
}

PREFIX = {
    "distributor": "D-", "control": "C-", "export": "X-", "broker": "BKR-",
    "grain": "GRN-", "cooperage": "COP-", "glass": "GLS-", "ngs": "NGS-",
    "bank": "BNK-", "lender": "LNDR-", "insurer": "INS-", "recruiter": "REC-",
    "landlord": "LL-", "regulator": "REG-", "press": "PRS-", "fabricator": "STL-",
    "retailer": "RTL-", "contract_client": "CDC-", "investor": "BD-", "lab": "LAB-",
    "candidate": "CAND-",
}

HIDDEN_KEYS = (
    "threshold", "reservation_mult", "hidden_constraints", "price_mult", "lead_extra",
    "skill", "true_age_offset", "personality", "pickup", "counter_room",
)


def _n(lo: float, hi: float, r: random.Random) -> float:
    return lo + (hi - lo) * r.random()


def _pick_temp(r: random.Random, weights: dict[str, float]) -> str:
    names = [t for t in TEMPERAMENTS if t in weights]
    w = [max(0.0, float(weights[t])) for t in names]
    s = sum(w) or 1.0
    x, acc = r.random(), 0.0
    for name, wi in zip(names, w):
        acc += wi / s
        if x <= acc:
            return name
    return names[-1]


def person(r: random.Random) -> str:
    return f"{r.choice(FIRST)} {r.choice(LAST)}"


def firm_name(r: random.Random, kind: str, used: set[str]) -> str:
    suffixes = FIRM_B.get(kind, ("Co.", "Group", "LLC"))
    for _ in range(40):
        name = f"{r.choice(FIRM_A)} {r.choice(suffixes)}"
        if name not in used:
            used.add(name)
            return name
    name = f"{r.choice(FIRM_A)} {r.choice(suffixes)} {r.randint(2, 99)}"
    used.add(name)
    return name


def _email(contact: str, firm: str) -> str:
    left = ".".join(contact.lower().split())
    dom = "".join(ch for ch in firm.lower() if ch.isalnum() or ch.isspace())
    dom = "-".join(dom.split())[:28] or "firm"
    return f"{left}@{dom}.example"


def _phone(r: random.Random) -> str:
    return f"{200 + r.randint(0, 599):03d}-555-{r.randint(1000, 9899):04d}"


def remember(party: dict[str, Any], week: int, kind: str, text: str, delta: float = 0.0) -> None:
    party.setdefault("memory", []).append({"week": week, "kind": kind, "text": text[:240], "delta": delta})
    if len(party["memory"]) > 40:
        party["memory"] = party["memory"][-40:]
    if delta:
        party["goodwill"] = max(0.25, min(1.15, party.get("goodwill", 1.0) + delta))


def display_from(party: dict[str, Any]) -> str:
    contact = party.get("contact")
    name = party.get("name", "Unknown")
    return f"{contact}, {name}" if contact else name


def public_card(party: dict[str, Any], week: int = 0) -> dict[str, Any]:
    """What the operator is allowed to see. Hidden economic type is omitted."""
    last = party.get("memory") or []
    vibe = party.get("goodwill", 1.0)
    relationship = "strained" if vibe < 0.6 else "ok" if vibe < 0.9 else "good"
    active = bool(party.get("active", True)) and (party.get("exit_week") is None or week < party["exit_week"])
    entered = party.get("enter_week", 0) <= week
    return {
        "id": party["id"],
        "kind": party["kind"],
        "name": party["name"],
        "contact": party.get("contact"),
        "title": party.get("title"),
        "email": party.get("email"),
        "phone": party.get("phone"),
        "territory": party.get("territory"),
        "specialty": party.get("specialty"),
        "style": STYLE.get(party.get("temperament", "warm"), "professional"),
        "relationship": relationship if last else "new",
        "last_contact_week": last[-1]["week"] if last else None,
        "notes_count": len(last),
        "in_market": bool(active and entered),
        "entered_week": party.get("enter_week", 0),
        "left_week": None if active else party.get("exit_week"),
        "channel_status": party.get("status") if party["kind"] in ("distributor", "control", "export") else None,
    }


def reputation(parties: dict[str, dict[str, Any]], kinds: tuple[str, ...] = ("distributor", "export", "control")) -> float:
    vals = [p.get("goodwill", 1.0) for p in parties.values()
            if p.get("kind") in kinds and p.get("memory")]
    return sum(vals) / len(vals) if vals else 1.0


@dataclass
class Market:
    parties: dict[str, dict[str, Any]] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    home_state: str = "Kentucky"
    site_landlords: dict[str, str] = field(default_factory=dict)
    used_names: set[str] = field(default_factory=set)

    def of(self, role: str) -> dict[str, Any]:
        return self.parties[self.roles[role]]

    def by_kind(self, *kinds: str, week: int | None = None) -> list[dict[str, Any]]:
        out = []
        for p in self.parties.values():
            if p["kind"] not in kinds:
                continue
            if week is not None:
                if p.get("enter_week", 0) > week:
                    continue
                if p.get("exit_week") is not None and p["exit_week"] <= week:
                    continue
            out.append(p)
        return out


class _Gen:
    def __init__(self, r: random.Random, weights: dict[str, float]):
        self.r = r
        self.weights = weights
        self.ids: dict[str, int] = {}
        self.used: set[str] = set()

    def id(self, kind: str) -> str:
        prefix = PREFIX.get(kind, "P-")
        self.ids[prefix] = self.ids.get(prefix, 0) + 1
        return f"{prefix}{self.ids[prefix]:03d}"

    def base(self, kind: str, **extra: Any) -> dict[str, Any]:
        pid = extra.pop("id", None) or self.id(kind)
        name = extra.pop("name", None) or firm_name(self.r, kind, self.used)
        contact = extra.pop("contact", None) or person(self.r)
        temperament = extra.pop("temperament", None) or _pick_temp(self.r, self.weights)
        title = extra.pop("title", None) or {
            "distributor": "Portfolio manager", "control": "Listing analyst",
            "export": "Buyer", "broker": "Broker", "grain": "Origination",
            "cooperage": "Allocations", "glass": "Account manager", "ngs": "Sales",
            "bank": "SBA relationship officer", "lender": "ABL officer",
            "insurer": "Commercial underwriter", "recruiter": "Recruiter",
            "landlord": "Property manager", "regulator": "Specialist",
            "press": "Writer", "fabricator": "Project engineer",
            "retailer": "Beverage director", "contract_client": "Founder",
            "investor": "Board chair", "lab": "Chemist",
        }.get(kind, "Contact")
        p = {
            "id": pid, "kind": kind, "name": name, "contact": contact, "title": title,
            "email": _email(contact, name), "phone": _phone(self.r),
            "temperament": temperament, "personality": _personality(temperament, name, contact, kind),
            "territory": extra.pop("territory", None), "specialty": extra.pop("specialty", None),
            "size": extra.pop("size", 1.0), "threshold": extra.pop("threshold", 0.5),
            "margin": extra.pop("margin", 0.28), "price_mult": extra.pop("price_mult", 1.0),
            "lead_extra": extra.pop("lead_extra", 0), "reservation_mult": extra.pop("reservation_mult", 0.88),
            "counter_room": extra.pop("counter_room", 0.08),
            "goodwill": extra.pop("goodwill", 1.0), "trust": extra.pop("trust", 0.5),
            "hidden_constraints": extra.pop("hidden_constraints", []),
            "pickup": extra.pop("pickup", {"warm": 0.9, "aggressive": 0.72, "cautious": 0.58,
                                           "bureaucratic": 0.32, "opportunistic": 0.8}[temperament]),
            "status": extra.pop("status", "none"),
            "inventory": extra.pop("inventory", {}), "listed": extra.pop("listed", []),
            "memory": extra.pop("memory", []),
            "enter_week": extra.pop("enter_week", 0), "exit_week": extra.pop("exit_week", None),
            "active": extra.pop("active", True),
            "item": extra.pop("item", None),
        }
        p.update(extra)
        return p


def _personality(temperament: str, firm: str, contact: str, kind: str) -> str:
    return (f"{contact} at {firm} ({kind.replace('_', ' ')}). Temperament: {temperament} "
            f"({STYLE[temperament]}). Writes like a real {kind.replace('_', ' ')} counterpart "
            "in the American whiskey trade. Never invents numbers, dates, SKUs or terms.")


def _constraints(r: random.Random, tier: str | None) -> list[str]:
    if tier == "home":
        return ["relationship_first"] if r.random() < 0.5 else []
    n = 1 if r.random() < 0.7 else (2 if r.random() < 0.4 else 0)
    pool = list(CONSTRAINTS)
    r.shuffle(pool)
    return pool[:n]


def populate(sc: Any) -> Market:
    """Build the opening cast from the scenario's counterparties config."""
    r = random.Random(sc.party_stream_key())
    cp = sc.counterparties
    weights = dict(DEFAULT_TEMPERAMENT_WEIGHTS)
    if cp.temperament:
        weights.update({k: float(v) for k, v in cp.temperament.items()})
    g = _Gen(r, weights)
    pops = {k: dict(v) for k, v in DEFAULT_POPS.items()}
    for k, v in (cp.populations or {}).items():
        pops.setdefault(k, {})
        pops[k].update(v if isinstance(v, dict) else {})

    m = Market(home_state=r.choice(HOME_STATES), used_names=g.used)

    board = g.base("investor", specialty="founders' board", territory=m.home_state,
                   name=f"{r.choice(FIRM_A)} {r.choice(FIRM_B['investor'])}")
    m.parties[board["id"]] = board
    m.roles["board"] = board["id"]

    # TTB is a real federal bureau; the *specialists* assigned to the file are sampled.
    for role, desk, title in (
        ("ttb", "TTB National Revenue Center", "Permit specialist"),
        ("ttb_labels", "TTB COLAs Online", "Label specialist"),
        ("ttb_field", "TTB Field Operations", "Investigator"),
    ):
        p = g.base("regulator", name=desk, title=title, territory="United States",
                   specialty=role, temperament="bureaucratic")
        m.parties[p["id"]] = p
        m.roles[role] = p["id"]

    abc_name = f"{m.home_state} Alcoholic Beverage Control"
    abc = g.base("regulator", name=abc_name, title="Licensing specialist",
                 territory=m.home_state, specialty="state_abc", temperament="bureaucratic")
    m.parties[abc["id"]] = abc
    m.roles["abc"] = abc["id"]

    for site, specialty in (
        ("rural_barn", "converted barn / acreage"),
        ("edge_of_town", "industrial flex / interstate"),
        ("downtown", "historic warehouse"),
    ):
        p = g.base("landlord", specialty=specialty, territory=m.home_state)
        m.parties[p["id"]] = p
        m.site_landlords[site] = p["id"]
    m.roles["landlord_rural"] = m.site_landlords["rural_barn"]
    m.roles["landlord_edge"] = m.site_landlords["edge_of_town"]
    m.roles["landlord_downtown"] = m.site_landlords["downtown"]

    n_dist = int(pops["distributor"].get("min", 4))
    n_dist_max = max(n_dist, int(pops["distributor"].get("max", 7)))
    n_dist = n_dist + (r.randint(0, n_dist_max - n_dist) if n_dist_max > n_dist else 0)
    for i in range(n_dist):
        if i < len(CHANNEL_SEATS):
            seat = CHANNEL_SEATS[i]
            p = g.base(
                "distributor",
                size=_n(*seat["size"], r),
                threshold=_n(*seat["threshold"], r),
                margin=_n(*seat["margin"], r),
                territory={"home": m.home_state, "regional": "regional", "national": "multi-state"}[seat["tier"]],
                specialty=f"{seat['tier']} wholesaler",
                hidden_constraints=_constraints(r, seat["tier"]),
                enter_week=0,
            )
        else:
            p = g.base(
                "distributor",
                size=_n(0.8, 2.2, r),
                threshold=_n(0.52, 0.72, r),  # extras are pickier, so the opening path stays intact
                margin=_n(0.27, 0.32, r),
                territory=r.choice(("regional", "adjacent-state", "metro")),
                specialty="wholesaler",
                hidden_constraints=_constraints(r, "extra"),
                enter_week=0 if i < n_dist_max else 26 + int(r.random() * 160),
            )
        if p["enter_week"] > 0:
            p["status"] = "pending_entry"
        m.parties[p["id"]] = p

    used_states = {m.home_state}
    n_ctrl = int(pops["control_board"].get("min", 2))
    n_ctrl = max(n_ctrl, min(int(pops["control_board"].get("max", 3)), n_ctrl + (1 if r.random() < 0.45 else 0)))
    states = [s for s in CONTROL_STATES if s not in used_states]
    r.shuffle(states)
    for i, st in enumerate(states[:n_ctrl]):
        title = r.choice(CONTROL_TITLES)
        p = g.base(
            "control",
            name=f"{st} {title}",
            territory=st,
            specialty="control-state listing board",
            size=_n(1.15, 1.7, r),
            threshold=_n(0.42, 0.55, r),
            margin=0.0,
            temperament="bureaucratic",
            hidden_constraints=["prefers_aged"] if r.random() < 0.4 else [],
            contact=person(r),
            title="Listing analyst",
        )
        m.parties[p["id"]] = p

    n_exp = int(pops["exporter"].get("min", 1))
    n_exp = max(n_exp, min(int(pops["exporter"].get("max", 2)), n_exp + (1 if r.random() < 0.4 else 0)))
    for i in range(n_exp):
        region = r.choice(("EU", "UK", "Japan", "Australia", "Canada"))
        p = g.base(
            "export",
            territory=region,
            specialty=f"{region} importer",
            size=_n(0.9, 1.4, r),
            threshold=_n(0.46, 0.58, r),
            margin=_n(0.22, 0.28, r),
            hidden_constraints=_constraints(r, "export"),
            enter_week=0 if i == 0 else (0 if r.random() < 0.5 else 40 + int(r.random() * 80)),
        )
        if p["enter_week"] > 0:
            p["status"] = "pending_entry"
        m.parties[p["id"]] = p

    def _many(kind: str, item: str | None, specialty: str, price=(0.94, 1.10), lead=(-1, 2),
              reservation=(0.82, 0.94)) -> None:
        cfg = pops.get(kind, {"min": 1, "max": 1})
        n = int(cfg.get("min", 1))
        mx = max(n, int(cfg.get("max", n)))
        n = n + (r.randint(0, mx - n) if mx > n else 0)
        for i in range(n):
            p = g.base(
                kind, item=item, specialty=specialty,
                price_mult=_n(*price, r),
                lead_extra=int(round(_n(*lead, r))),
                reservation_mult=_n(*reservation, r),
                territory=m.home_state if kind in ("grain", "landlord") else r.choice(
                    (m.home_state, "regional", "national")),
            )
            m.parties[p["id"]] = p
            if i == 0:
                m.roles[kind] = p["id"]

    _many("broker", None, "bulk whiskey broker", reservation=(0.80, 0.92))
    _many("grain", "grain_bu", "cash grain / elevator")
    _many("cooperage", "new_barrels", "new charred oak barrels", price=(0.96, 1.14), lead=(0, 3))
    _many("glass", "glass_bottles", "glass, closures, labels", price=(0.95, 1.12), lead=(0, 2))
    _many("ngs", "ngs_pg", "190-proof grain neutral spirits", price=(0.97, 1.08))
    _many("bank", None, "SBA 7(a) preferred lender")
    _many("lender", None, "barrel-backed ABL")
    _many("insurer", None, "distillery package policy")
    _many("recruiter", None, "beverage-alcohol staffing")
    _many("press", None, "trade or lifestyle press")
    _many("fabricator", None, "still and process equipment")
    _many("lab", None, "independent cask analysis")

    # Role aliases used by the World when a single "the bank" / "the insurer" writes.
    for role, kind in (("sba", "bank"), ("barrel_lender", "lender"), ("insurer", "insurer"),
                       ("recruiter", "recruiter"), ("lab", "lab"), ("fabricator", "fabricator")):
        if role not in m.roles:
            found = next((p for p in m.parties.values() if p["kind"] == kind), None)
            if found:
                m.roles[role] = found["id"]

    return m


def spawn(sc: Any, kind: str, week: int, parties: dict[str, dict[str, Any]],
          extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """A new party entering the market mid-episode (same stream family, keyed by week)."""
    r = random.Random(f"{sc.party_stream_key()}|spawn|{kind}|{week}|{len(parties)}")
    weights = dict(DEFAULT_TEMPERAMENT_WEIGHTS)
    if sc.counterparties.temperament:
        weights.update({k: float(v) for k, v in sc.counterparties.temperament.items()})
    g = _Gen(r, weights)
    # continue id sequence from what's already been issued of this prefix
    prefix = PREFIX.get(kind, "P-")
    existing = [int(pid[len(prefix):]) for pid in parties if pid.startswith(prefix) and pid[len(prefix):].isdigit()]
    g.ids[prefix] = max(existing, default=0)
    g.used = {p["name"] for p in parties.values()}
    kw = dict(extra or {})
    kw.setdefault("enter_week", week)
    if kind == "distributor":
        kw.setdefault("size", _n(0.8, 2.0, r))
        kw.setdefault("threshold", _n(0.50, 0.72, r))
        kw.setdefault("margin", _n(0.27, 0.32, r))
        kw.setdefault("hidden_constraints", _constraints(r, "extra"))
        kw.setdefault("specialty", "wholesaler")
        kw.setdefault("status", "none")
    elif kind == "retailer":
        kw.setdefault("specialty", r.choice(("cocktail bar", "independent bottle shop", "hotel bar", "restaurant")))
        kw.setdefault("threshold", _n(0.35, 0.6, r))
    elif kind == "contract_client":
        kw.setdefault("specialty", "contract distilling")
        kw.setdefault("reservation_mult", _n(0.9, 1.15, r))
    elif kind == "broker":
        kw.setdefault("reservation_mult", _n(0.80, 0.93, r))
        kw.setdefault("specialty", "bulk whiskey broker")
    p = g.base(kind, **kw)
    return p


def apply_constraints(score: float, party: dict[str, Any], *, labels: list[dict[str, Any]],
                      awareness: float, rel_price: float, bottles_on_hand: int,
                      already_has_home: bool) -> float:
    """Adjust a pitch/listing score from hidden constraints. Never leak them."""
    cs = set(party.get("hidden_constraints") or [])
    classes = {l.get("class") for l in labels}
    unaged = classes <= {"vodka", "gin", "white_whiskey"} and bool(classes)
    aged = bool(classes & {"bourbon", "straight_bourbon", "bottled_in_bond_bourbon", "rye", "straight_rye"})
    if "no_unaged" in cs and unaged:
        score -= 0.25
    elif "no_unaged" in cs and not aged:
        score -= 0.08
    if "wants_exclusive" in cs and already_has_home:
        score -= 0.12
    if "price_sensitive" in cs:
        score -= 0.18 * max(0.0, rel_price - 1.0)
    if "relationship_first" in cs:
        score += 0.08 * (party.get("goodwill", 1.0) - 0.8) + 0.06 * awareness
    if "allocated_book" in cs:
        score -= 0.10
    if "volume_hungry" in cs and bottles_on_hand >= 1500:
        score += 0.07
    if "prefers_aged" in cs:
        score += 0.08 if aged else -0.10
    return score
