"""Agent-facing views of the world, and the final settlement used by the verifier.

Views never reveal hidden truth: no lot quality, no candidate skill, no future paths,
no true age of sourced lots beyond what paperwork claims.
"""

from __future__ import annotations

from typing import Any

from . import params as K
from .world import World, _r


def _money(x: float) -> float:
    return round(float(x), 2)


def deadlines(w: World) -> list[dict[str, Any]]:
    import datetime as dt
    out = []
    for p in w.periods_due(w.t + 6):
        if p in w.returns:
            continue
        _, end = w.period_end_week(p)
        out.append({"what": f"Excise return {p} (TTB F 5000.24)", "due": (end + dt.timedelta(days=14)).isoformat(),
                    "due_week": w.week_of(end + dt.timedelta(days=14))})
    for m in w.months_due(w.t + 6):
        if m in w.ops_reports:
            continue
        y, mo = int(m[:4]), int(m[5:])
        end = dt.date(y + (mo == 12), 1 if mo == 12 else mo + 1, 1)
        due = end + dt.timedelta(days=14)
        out.append({"what": f"Monthly operations reports {m}", "due": due.isoformat(), "due_week": w.week_of(due)})
    for e in w.emails:
        if e["status"] == "open" and e["deadline_week"] is not None:
            out.append({"what": f"Reply to {e['id']} ({e['subject']})", "due": w.date(e["deadline_week"]).isoformat(),
                        "due_week": e["deadline_week"]})
    return sorted(out, key=lambda x: x["due_week"])


def briefing(w: World) -> dict[str, Any]:
    unread = [e for e in w.emails if not e["read"]]
    return {"week": w.t, "date": w.date().isoformat(), "weeks_left": max(0, w.H - w.t), "cash": _money(w.cash),
            "debt": _money(w.debt()), "barrels": w.barrels_on_hand(),
            "finished_bottles": int(sum(f["bottles"] for f in w.fg.values())),
            "unread_emails": len(unread), "open_decisions": sum(1 for e in w.emails if e["status"] == "open"),
            "this_week": list(w.events)[-12:], "upcoming_deadlines": deadlines(w)[:8], "episode_over": w.done,
            "insolvent": w.insolvent}


def inbox(w: World, unread_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    rows = [e for e in w.emails if (not unread_only or not e["read"])]
    rows = sorted(rows, key=lambda e: (e["status"] != "open", -e["week"]))[: max(1, min(100, int(limit)))]
    return [{"id": e["id"], "date": e["date"], "from": e["from"], "subject": e["subject"], "status": e["status"],
             "needs_decision": e["status"] == "open",
             "reply_by": None if e["deadline_week"] is None else w.date(e["deadline_week"]).isoformat(),
             "read": e["read"],
             "operator": (e.get("operator") or {}).get("label")} for e in rows]


def read_email(w: World, email_id: str) -> dict[str, Any]:
    e = next((x for x in w.emails if x["id"] == email_id), None)
    if e is None:
        raise ValueError(f"No email {email_id}.")
    e["read"] = True
    out = {k: e[k] for k in ("id", "date", "from", "subject", "body", "status")} | {
        "reply_by": None if e["deadline_week"] is None else w.date(e["deadline_week"]).isoformat(),
        "operator": e.get("operator") or {"kind": "rule", "label": "rule-based fallback"},
        "decisions": {"distributor_proposal": ["accept", "decline"], "purchase_order": ["accept", "decline"],
                      "bulk_bid": ["accept", "decline", "counter"],
                      "sourced_offer": ["accept", "decline", "inspect"],
                      "grain_contract": ["accept", "decline"],
                      "retailer_request": ["accept", "decline"],
                      "press_request": ["accept", "decline"],
                      "contract_distill": ["accept", "decline"]}.get(e["kind"], [])}
    return out


def compliance(w: World) -> dict[str, Any]:
    return {"permits": {k: {"status": v["status"], "applied": w.date(v["applied_week"]).isoformat(),
                            "waiting_on_you": bool(v.get("question_open"))} for k, v in w.permits.items()},
            "bond": w.bond,
            "labels": [{k: l[k] for k in ("id", "brand", "class", "proof", "age_statement", "distilled_by", "status")}
                       for l in w.labels.values()],
            "filing_frequency_this_year": w.frequency(w.date().year),
            "excise_rates_per_pg": {"cbma_first_100k_pg": K.FET_CBMA_LOW, "cbma_above": K.FET_CBMA_HIGH,
                                    "general_and_sourced": K.FET_GENERAL},
            "returns_filed": {k: {"tax": v["tax"], "late": v["late"]} for k, v in w.returns.items()},
            "operations_reports_filed": sorted(w.ops_reports),
            "notices": [v["detail"] for v in w.violations if not v["veto"]][-10:],
            "penalties_outstanding": _money(w.penalties_due),
            "deadlines": deadlines(w)}


def tax_ledger(w: World, period: str | None = None) -> dict[str, Any]:
    """Your own book of taxable removals (the bookkeeper's ledger). Accurate; it is your job to file from it."""
    rows = w.removals
    if period:
        rows = [r for r in rows if period in w._period_of(r["week"])]
    return {"period": period, "removals": len(rows), "proof_gallons": _r(sum(r["pg"] for r in rows), 3),
            "tax": _money(sum(r["tax"] for r in rows)),
            "by_label": {lid: {"bottles": sum(r["bottles"] for r in rows if r["label"] == lid),
                               "tax": _money(sum(r["tax"] for r in rows if r["label"] == lid))}
                         for lid in sorted({r["label"] for r in rows})}}


def production(w: World) -> dict[str, Any]:
    eq = K.EQUIPMENT.get(w.equipment) if w.equipment else None
    return {"site": w.site, "build_out_ready": w.buildout_done_week is not None and w.t >= w.buildout_done_week,
            "build_out_ready_week": w.buildout_done_week, "equipment": w.equipment,
            "equipment_ready_week": w.equipment_ready_week, "still_down_until_week":
                w.equipment_down_until if w.equipment_down_until > w.t else None,
            "weeks_since_maintenance": w.weeks_since_maint, "sanitation": w.sanitation,
            "crew_capacity_multiplier": _r(w.capacity_mult()),
            "capacity_left_this_week_pg": None if not w.equipment_ready() else
                {"whiskey": _r(w._room(True), 1), "neutral": _r(w._room(False), 1)},
            "equipment_specs": eq and {k: eq[k] for k in ("whiskey_pg_week", "neutral_pg_week", "pg_per_bushel")},
            "tanks_pg": {k: _r(v["pg"], 1) for k, v in w.tanks.items()}, "tank_capacity_pg": K.TANK_CAPACITY_PG,
            "raw_materials": {k: _r(v, 1) for k, v in w.inventory.items()},
            "finished_goods": {k: v["bottles"] for k, v in w.fg.items()}}


def catalog(w: World | None = None) -> dict[str, Any]:
    sites = {sid: dict(row) for sid, row in K.SITES.items()}
    if w is not None:
        for sid, lid in getattr(w, "site_landlords", {}).items():
            p = w.parties.get(lid)
            if p and sid in sites:
                sites[sid]["landlord"] = p["name"]
                sites[sid]["landlord_id"] = lid
                sites[sid]["landlord_contact"] = p.get("contact")
    banks = insurers = []
    if w is not None:
        banks = [{"id": p["id"], "name": p["name"], "contact": p.get("contact"), "kind": p["kind"]}
                 for p in w.parties.values() if p["kind"] in ("bank", "lender") and w._in_market(p)]
        insurers = [{"id": p["id"], "name": p["name"], "contact": p.get("contact")}
                    for p in w.parties.values() if p["kind"] == "insurer" and w._in_market(p)]
    return {"sites": sites, "equipment": K.EQUIPMENT, "roles_market_salary": K.ROLES,
            "insurance": K.INSURANCE, "spirit_classes": K.CLASSES,
            "home_state": getattr(w, "home_state", None),
            "lenders": banks, "insurers": insurers}


def warehouse(w: World) -> dict[str, Any]:
    lots = []
    for l in w.lots.values():
        lots.append({"lot": l["id"], "spirit": l["spirit"], "barrels": _r(l["barrels"], 2), "floor": l["floor"],
                     "filled": w.date(max(0, l["fill_week"])).isoformat(), "entry_proof": l["entry_proof"],
                     "paperwork_age_years": _r(l["stated_age"] + max(0, w.t - l["fill_week"]) / 52, 2)
                     if l["distilled_by"] != "us" else _r(w.true_age(l), 2),
                     "distilled_by": l["distilled_by"], "season": l["season"],
                     "pg_per_barrel_est": _r(l["pg_per_barrel"], 1),
                     "last_sample": l["samples"][-1] if l["samples"] else None})
    cap = K.SITES[w.site]["rick_capacity"] if w.site else 0
    return {"rick_capacity": cap, "barrels_on_hand": w.barrels_on_hand(),
            "floor_temps_f": {f: _r(w.floor_temp(f), 1) for f in ("low", "mid", "high")},
            "humidity_pct": _r(w.P.humidity[w.t], 0), "lots": lots, "empty_new_barrels": int(w.inventory["new_barrels"])}


def procurement(w: World) -> dict[str, Any]:
    return {"quotes": w.quotes(), "open_orders": [o for o in w.orders if o["status"] == "open"],
            "on_hand": {k: _r(v, 1) for k, v in w.inventory.items()}}


def sales(w: World) -> dict[str, Any]:
    dists = {}
    for k, d in w.distributors.items():
        dep = sum(x[2] for x in d.get("depletions", []) if x[0] > w.t - 13)
        dists[k] = {"name": d["name"], "kind": d["kind"], "status": d["status"], "carries": d["listed"],
                    "depletions_last_13w_bottles": int(dep),
                    "their_inventory_bottles": {l: int(v) for l, v in d["inventory"].items()},
                    "relationship": "strained" if d["goodwill"] < 0.6 else "ok" if d["goodwill"] < 0.9 else "good"}
    rev = {}
    for (t, ch, v) in w.revenue_log:
        if t > w.t - 13:
            rev[ch] = rev.get(ch, 0) + v
    return {"labels": {lid: {"brand": l["brand"], "class": l["class"], "status": l["status"],
                             "on_hand_bottles": w.fg.get(lid, {}).get("bottles", 0),
                             "wholesale_price": _r(w.price(lid, "wholesale")) if l["status"] == "approved" else None,
                             "tasting_room_price": _r(w.price(lid, "tasting_room")) if l["status"] == "approved" else None}
                       for lid, l in w.labels.items()},
            "tasting_room_open": w.tasting_room_open, "marketing_per_week": w.marketing_week,
            "brand_awareness_survey": "low" if w.awareness < 0.25 else "growing" if w.awareness < 0.6 else "strong",
            "accounts": dists, "revenue_last_13w": {k: _money(v) for k, v in rev.items()},
            "open_purchase_orders": [p for p in w.pos.values() if p["status"] in ("open", "accepted")],
            "bulk_listings": [b for b in w.bulk_listings.values() if b["status"] == "open"]}


def finance(w: World) -> dict[str, Any]:
    return {"cash": _money(w.cash), "receivables": _money(sum(a["amount"] for a in w.ar)),
            "loans": {k: {kk: _r(vv) for kk, vv in v.items() if kk in ("balance", "limit", "spread")}
                      for k, v in w.loans.items()},
            "loan_applications": [a for a in w.loan_apps if a["status"] == "pending"],
            "prime_rate": _r(w.P.prime[w.t], 4), "insurance": w.insurance,
            "insurance_paid_through": w.date(w.insurance_paid_until).isoformat() if w.insurance != "none" else None,
            "monthly_fixed_costs_est": _money(
                (K.SITES[w.site]["rent_month"] if w.site else 0) + 4.33 * (K.G_AND_A_WEEK + w.marketing_week) +
                sum(s["salary"] for s in w.staff.values()) / 12 * K.PAYROLL_BURDEN),
            "revenue_last_52w": _money(sum(v for (t, _c, v) in w.revenue_log if t > w.t - 52)),
            "claims": list(getattr(w, "claims", []) or []),
            "counterparty_llm_cost_usd": _money(
                (getattr(getattr(w, "voice", None), "cost_usd", 0) or 0)
                + (getattr(getattr(w, "negotiator", None), "cost_usd", 0) or 0)),
            "counterparty_mode": getattr(getattr(w, "negotiator", None), "mode", None)}


def people(w: World) -> dict[str, Any]:
    return {"staff": [{k: s[k] for k in ("id", "name", "role", "salary")} | {"started": s["start"] <= w.t}
                      for s in w.staff.values()],
            "candidates": [{k: c[k] for k in ("id", "name", "role", "years", "hint", "ask")}
                           for c in w.candidates.values() if c["status"] == "available"],
            "open_postings": [{"role": j["role"], "posted_week": j["week"]} for j in w.job_posts],
            "market_salaries": K.ROLES}


def market(w: World) -> dict[str, Any]:
    t = w.t
    back = max(0, t - 12)
    return {"corn_usd_bu": _r(w.P.corn[t]), "corn_13w_ago": _r(w.P.corn[back]),
            "energy_index": _r(w.P.energy[t]), "bulk_new_fill_usd_bbl": _r(w.P.bulk_new_fill[t], 0),
            "bulk_new_fill_13w_ago": _r(w.P.bulk_new_fill[back], 0), "prime_rate": _r(w.P.prime[t], 4),
            "cooperage_lead_weeks": int(w.P.cooperage_lead[t]), "glass_lead_weeks": int(w.P.glass_lead[t]),
            "eu_export_tariff": _r(w.P.export_tariff[t], 3),
            "headlines": [{"date": w.date(wk).isoformat(), "headline": h} for (wk, _f, h) in w.P.news
                          if back <= wk <= t][-8:]}


# ---------------------------------------------------------------------- settlement
def settle(w: World) -> dict[str, Any]:
    """Enterprise value at the current week, from hidden truth."""
    barrels = w.inventory_value()
    fg = 0.0
    for lid, f in w.fg.items():
        lab = w.labels[lid]
        pg = f["bottles"] * K.BOTTLE_GAL * lab["proof"] / 100
        fg += f["bottles"] * w.ref_wholesale(lab, f["q"]) * 0.6 - pg * K.FET_CBMA_HIGH
    tanks = sum(v["pg"] * 2.0 for v in w.tanks.values())
    raw = sum(w.inv_cost.values())
    equip = 0.35 * K.EQUIPMENT[w.equipment]["cost"] if w.equipment_ready() else 0.0
    ar = sum(a["amount"] for a in w.ar)
    brand = 0.0 if w.insolvent else 2.0 * w.ttm_brand_revenue()
    liab = w.debt() + w.penalties_due + sum(
        r["true_tax"] - r["tax"] for r in w.returns.values() if r["true_tax"] > r["tax"] and not r.get("assessed"))
    unfiled_tax = sum(w.period_truth(p)["tax"] for p in w.periods_due(w.t) if p not in w.returns)
    unfiled_tax += sum(r["tax"] for r in w.removals if not any(
        p in w._period_of(r["week"]) for p in w.periods_due(w.t)))  # current open period accrual
    haircut = 0.5 if w.insolvent else 1.0
    assets = w.cash + ar + haircut * (barrels + max(0.0, fg) + tanks + raw + equip)
    ev = assets + brand - liab - unfiled_tax
    return {"week": w.t, "cash": _money(w.cash), "receivables": _money(ar), "barrel_fair_value": _money(barrels),
            "finished_goods_value": _money(max(0.0, fg)), "tank_and_raw_value": _money(tanks + raw),
            "equipment_salvage": _money(equip), "brand_value": _money(brand), "debt": _money(w.debt()),
            "tax_and_penalties_owed": _money(liab - w.debt() + unfiled_tax), "liquidation_haircut": haircut,
            "enterprise_value": _money(ev), "insolvent": w.insolvent}
