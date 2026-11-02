"""A hand-written operating policy used ONLY by tests to calibrate and smoke-test the world.

It is not an evaluated Agent and is not exposed in any Benchmark track. It drives the World
object directly (no LLM) so tests can check the economics are survivable but not trivial.
"""

from __future__ import annotations

from barrel_sim.world import Refused, World


def _try(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Refused:
        return None


def step(w: World) -> None:
    for e in list(w.emails):
        if e["status"] != "open":
            continue
        k = e["kind"]
        if k == "ttb_question":
            _try(w.reply_email, e["id"], "Diagram and funding letter attached.")
        elif k in ("purchase_order", "distributor_proposal", "bulk_bid"):
            _try(w.reply_email, e["id"], "", decision="accept")
        elif k == "sourced_offer":
            _try(w.reply_email, e["id"], "", decision="decline")
    for c in list(w.candidates.values()):
        if c["status"] == "available" and not any(s["role"] == c["role"] for s in w.staff.values()):
            _try(w.hire, c["id"], c["ask"])
    P = w.permits
    st = lambda k: P.get(k, {}).get("status")  # noqa: E731
    if w.t == 0:
        w.sign_lease("edge_of_town")
        w.order_equipment("hybrid_500")
        w.apply_permit("federal_dsp")
        w.apply_loan("sba_7a", 1_200_000)
        for role in ("head_distiller", "assistant_distiller", "tasting_room_manager"):
            w.post_job(role, 0)
        w.buy_insurance("basic")
    for k in ("federal_dsp", "state_manufacturer", "state_retail"):
        if st(k) == "abandoned":
            _try(w.apply_permit, k)
    if st("federal_dsp") == "approved" and "state_manufacturer" not in P:
        _try(w.apply_permit, "state_manufacturer")
    if st("state_manufacturer") == "approved" and "state_retail" not in P:
        _try(w.apply_permit, "state_retail")
    if st("state_retail") == "approved" and not w.tasting_room_open:
        _try(w.set_tasting_room, True)
    if st("federal_dsp") == "approved" and not w.labels:
        w.submit_label("Test Vodka", "vodka", 80)
        w.submit_label("Test Gin", "gin", 90)
        w.submit_label("Test Bourbon 2", "bourbon", 92, 2)
        w.obtain_bond(60_000)
        w.set_marketing(1_000)
    if w.t % 4 == 0 and w.t > 4:
        for item, q in (("grain_bu", 300), ("new_barrels", 20), ("glass_bottles", 6_000), ("ngs_pg", 2_000)):
            if w.inventory[item] < q * 2:
                _try(w.place_order, item, q)
    if w.permitted and w.equipment_ready():
        unaged = [l for l in w.labels.values() if l["class"] in ("vodka", "gin") and l["status"] == "approved"]
        for l in unaged:
            fgb = w.fg.get(l["id"], {}).get("bottles", 0)
            if fgb < 2_500:
                _try(w.run_production, l["class"], 300)
                _try(w.bottle, l["id"], l["class"], 1_500)
        _try(w.run_production, "bourbon", max(0.0, min(w._room(True), w.inventory["grain_bu"] * 4.6)))
        n = min(int(w.tanks.get("bourbon", {"pg": 0})["pg"] // 63.6), int(w.inventory["new_barrels"]))
        liquidity = w.cash + ((w.loans['barrel_line']['limit'] - w.loans['barrel_line']['balance']) if 'barrel_line' in w.loans else 0)
        if n and liquidity > 400_000:
            _try(w.fill_barrels, n, 120, "mid")
        aged = [l for l in w.labels.values() if l["class"] == "bourbon" and l["status"] == "approved"]
        old = [x for x in w.lots.values() if w.true_age(x) >= 2.05]
        if aged and old and w.fg.get(aged[0]["id"], {}).get("bottles", 0) < 3_000:
            _try(w.bottle, aged[0]["id"], old[0]["id"], 2_000)
        ids = [l["id"] for l in unaged + aged if w.fg.get(l["id"], {}).get("bottles", 0) > 0]
        for did in ("D-HOME", "D-REG1", "D-REG2"):
            if w.distributors[did]["status"] in ("none", "declined", "dropped", "signed") and ids:
                _try(w.pitch_distributor, did, ",".join(ids))
    if w.barrels_on_hand() >= 150 and "barrel_line" not in w.loans:
        _try(w.apply_loan, "barrel_line", 1_500_000)
    line = w.loans.get("barrel_line")
    if line and w.cash < 150_000:
        _try(w.draw, min(250_000, line["limit"] - line["balance"]))
    if line and w.cash > 600_000 and line["balance"] > 0:
        _try(w.repay, "barrel_line", min(line["balance"], w.cash - 500_000))
    liq = w.cash + ((line["limit"] - line["balance"]) if line else 0)
    if liq < 350_000 and w.lots and not any(b["status"] == "open" for b in w.bulk_listings.values()):
        lot = max(w.lots.values(), key=lambda x: w.true_age(x))
        n = min(40, int(lot["barrels"]))
        if n >= 5:
            _try(w.list_barrels_for_sale, lot["id"], n, int(w.true_age(lot) * 10) / 10, w.barrel_fair_value(lot) * 0.9)
    for p in w.periods_due(w.t):
        if p not in w.returns:
            tr = w.period_truth(p)
            _try(w.file_excise_return, p, tr["proof_gallons"], tr["tax"])
    for m in w.months_due(w.t):
        if m not in w.ops_reports:
            _try(w.file_operations_report, m)


def play(w: World, max_weeks: int | None = None) -> World:
    while not w.done and (max_weeks is None or w.t < max_weeks):
        step(w)
        if not w.done:
            w.end_week(1)
    return w
