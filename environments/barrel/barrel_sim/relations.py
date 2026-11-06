"""CRM, phone, contracts, outbound mail, inbound initiation and market churn.

Mixed into ``World``. Hidden economic bounds live here and in ``world._counterparties``.
A counterparty LLM may propose a decision and terms; the environment clamps every
proposal so it cannot exceed reservation, budget, capacity or legal limits.
"""

from __future__ import annotations

import re
from typing import Any

from . import parties as P
from .errors import Refused, money as _r
from .negotiate import Bounds


_PRICE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)")


class RelationsMixin:
    def _party(self, pid: str) -> dict[str, Any]:
        p = self.parties.get(pid)
        if p is None:
            raise Refused(f"No contact {pid}.")
        return p

    def _role(self, role: str) -> dict[str, Any]:
        return self.parties[self.roles[role]]

    def _role_name(self, role: str) -> str:
        return P.display_from(self._role(role))

    def _in_market(self, p: dict[str, Any], t: int | None = None) -> bool:
        t = self.t if t is None else t
        if not p.get("active", True):
            return False
        if p.get("enter_week", 0) > t:
            return False
        if p.get("exit_week") is not None and p["exit_week"] <= t:
            return False
        return True

    def resolve_party(self, to: str) -> dict[str, Any] | None:
        to = (to or "").strip()
        if not to:
            return None
        if to in self.parties:
            return self.parties[to]
        low = to.lower()
        hits = []
        for p in self.parties.values():
            if not self._in_market(p):
                continue
            blob = " ".join(str(p.get(k) or "") for k in ("id", "name", "contact", "email")).lower()
            if low == p["id"].lower() or low == (p.get("email") or "").lower():
                return p
            if low in blob:
                hits.append(p)
        return hits[0] if len(hits) == 1 else (hits[0] if len(hits) == 1 else (None if not hits else hits[0]))

    def remember(self, party_id: str, kind: str, text: str, delta: float = 0.0) -> None:
        p = self.parties.get(party_id)
        if p is not None:
            P.remember(p, self.t, kind, text, delta)

    # ------------------------------------------------------------------ contacts
    def list_contacts(self, kind: str | None = None, in_market_only: bool = True) -> list[dict[str, Any]]:
        rows = []
        for p in self.parties.values():
            if p.get("kind") == "candidate":
                continue
            if kind and p.get("kind") != kind:
                continue
            if p.get("enter_week", 0) > self.t:
                continue
            if in_market_only and not self._in_market(p):
                continue
            rows.append(P.public_card(p, self.t))
        rows.sort(key=lambda r: (r["kind"], r["name"]))
        return rows

    def read_contact(self, party_id: str) -> dict[str, Any]:
        p = self._party(party_id)
        if p.get("enter_week", 0) > self.t:
            raise Refused("No such contact in the directory yet.")
        card = P.public_card(p, self.t)
        card["recent"] = [
            {"week": h["week"], "date": self.date(h["week"]).isoformat(), "what": h["kind"],
             "note": h["text"]} for h in (p.get("memory") or [])[-12:]
        ]
        return card

    # ------------------------------------------------------------------ contracts
    def _add_contract(self, kind: str, party_id: str, terms: dict[str, Any],
                      status: str = "signed") -> str:
        cid = self._id("K")
        self.contracts[cid] = {
            "id": cid, "kind": kind, "party_id": party_id,
            "party": self.parties.get(party_id, {}).get("name"),
            "terms": terms, "status": status,
            "opened_week": self.t,
            "signed_week": self.t if status == "signed" else None,
        }
        return cid

    def list_contracts(self, status: str | None = None) -> list[dict[str, Any]]:
        rows = list(self.contracts.values())
        if status:
            rows = [c for c in rows if c["status"] == status]
        return [{k: c[k] for k in ("id", "kind", "party_id", "party", "status", "opened_week", "signed_week")}
                | {"terms": c["terms"]} for c in rows]

    def read_contract(self, contract_id: str) -> dict[str, Any]:
        c = self.contracts.get(contract_id)
        if c is None:
            raise Refused(f"No contract {contract_id}.")
        return dict(c)

    def sign_contract(self, contract_id: str) -> str:
        self._need_open()
        c = self.contracts.get(contract_id)
        if c is None:
            raise Refused(f"No contract {contract_id}.")
        if c["status"] == "signed":
            return f"{contract_id} is already signed."
        if c["status"] != "pending":
            raise Refused(f"{contract_id} cannot be signed ({c['status']}).")
        self._rec("sign_contract", contract_id=contract_id)
        c["status"] = "signed"
        c["signed_week"] = self.t
        self.remember(c["party_id"], "signed", f"Signed {c['kind']} {contract_id}", 0.04)
        return f"Signed {c['kind']} {contract_id} with {c['party']}."

    # ------------------------------------------------------------------ phone
    def list_calls(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(reversed(self.calls[-max(1, min(100, int(limit))):]))

    def call_party(self, party_id: str, topic: str, notes: str = "") -> dict[str, Any]:
        """Place a call. Some counterparties do not pick up; regulators often ask you to write."""
        self._need_open()
        p = self._party(party_id)
        if not self._in_market(p):
            raise Refused(f"{p['name']} is no longer reachable.")
        topic = (topic or "check_in").strip().lower().replace(" ", "_")
        if topic not in ("check_in", "status", "relationship", "negotiate", "counter", "pitch",
                         "quote", "complaint", "thanks"):
            raise Refused("topic must be check_in, status, relationship, negotiate, counter, "
                          "pitch, quote, complaint or thanks")
        self._rec("call", party_id=party_id, topic=topic, notes=notes)
        r = self.rng(f"call|{party_id}|{self.t}|{topic}|{len(self.calls)}")
        picked_up = r.random() < float(p.get("pickup", 0.7))
        rec = {"id": self._id("CALL-"), "week": self.t, "date": self.date().isoformat(),
               "party_id": party_id, "party": p["name"], "topic": topic, "picked_up": picked_up,
               "summary": ""}
        if not picked_up:
            rec["summary"] = (f"No answer at {p.get('phone')}. "
                              f"{'They prefer things in writing.' if p.get('temperament') == 'bureaucratic' else 'Try email.'}")
            self.calls.append(rec)
            self.remember(party_id, "missed_call", f"You called about {topic}", 0.0)
            self.email(P.display_from(p), "Missed your call",
                       rec["summary"] + " Reply by email if it is urgent.", "info", party_id=party_id)
            return rec
        summary, extra = self._call_outcome(p, topic, notes, r)
        rec["summary"] = summary
        rec.update(extra)
        self.calls.append(rec)
        phrased = self.voice.phrase(P.display_from(p), f"Call about {topic}", summary,
                                    party=p, week=self.t, kind="call",
                                    history=p.get("memory") or [])
        rec["summary"] = phrased
        return rec

    def _call_outcome(self, p: dict[str, Any], topic: str, notes: str, r) -> tuple[str, dict[str, Any]]:
        extra: dict[str, Any] = {}
        name = p["name"]
        if topic in ("relationship", "thanks", "check_in"):
            # Can't farm goodwill by ringing every week: one bump per party per 8 weeks.
            last = [h for h in p.get("memory") or [] if h["kind"] == "call_goodwill"]
            if not last or self.t - last[-1]["week"] >= 8:
                self.remember(p["id"], "call_goodwill", f"Pleasant call ({topic})", 0.03)
                msg = f"{p['contact']} had time to talk. They appreciate the check-in."
            else:
                self.remember(p["id"], "call", f"Check-in ({topic})", 0.0)
                msg = f"{p['contact']} is friendly but busy; they suggested you not call every week."
            return msg, extra
        if topic == "status":
            self.remember(p["id"], "call", "Status check", 0.0)
            if p["kind"] == "regulator":
                return (f"{p['contact']} says the file is under review and asks you to answer "
                        "any open information request in writing, not by phone.", extra)
            if p["kind"] in ("bank", "lender"):
                pending = [a for a in self.loan_apps if a["status"] == "pending"]
                if pending:
                    return (f"{p['contact']} says your application is in underwriting. "
                            "They will email a decision; they will not commit to a number on the phone.", extra)
                return f"{p['contact']} says there is nothing pending on their desk.", extra
            if p["kind"] in ("distributor", "control", "export"):
                return (f"{p['contact']} says their book is '{p.get('status', 'none')}'. "
                        "Anything formal should go through a pitch or a listing application.", extra)
            return f"{p['contact']} at {name} took the call and had no news.", extra
        if topic == "quote" and p.get("item"):
            q = self.quotes()
            item = p["item"]
            row = q.get(item, {})
            sup = next((s for s in row.get("suppliers") or [] if s["id"] == p["id"]), None)
            if not sup:
                return f"{p['contact']} is not quoting that item this week.", extra
            extra["quote"] = sup
            self.remember(p["id"], "call_quote", f"Quoted {item}", 0.01)
            avail = "available" if sup["available"] else "on allocation / not taking new orders"
            return (f"{p['contact']} quotes {item} at ${sup['price']:,.2f}, "
                    f"lead {sup['lead_weeks']} weeks, {avail}.", extra)
        if topic == "pitch":
            self.remember(p["id"], "call_pitch", "Verbal pitch", 0.01)
            if p["kind"] in ("distributor", "export"):
                return (f"{p['contact']} will not commit on the phone. Send samples and a sell sheet "
                        f"through sales.pitch_distributor using id {p['id']} "
                        "(about $2,500 of samples and travel).", extra)
            if p["kind"] == "control":
                return (f"The board does not take pitches by phone. File a listing through "
                        f"sales.apply_control_listing with board id {p['id']}.", extra)
            return f"{p['contact']} listened. Formal next steps still go through the usual channels.", extra
        if topic in ("negotiate", "counter"):
            return self._verbal_counter(p, notes)
        if topic == "complaint":
            self.remember(p["id"], "complaint", notes or "complaint", -0.02)
            return f"{p['contact']} noted the complaint and said they would look into it.", extra
        return f"{p['contact']} at {name} took the call.", extra

    def _verbal_counter(self, p: dict[str, Any], notes: str) -> tuple[str, dict[str, Any]]:
        open_emails = [e for e in self.emails
                       if e.get("party_id") == p["id"] and e["status"] == "open"
                       and e["kind"] in ("bulk_bid", "sourced_offer", "distributor_proposal",
                                         "grain_contract", "contract_distill")]
        if not open_emails:
            self.remember(p["id"], "call", "Negotiate with nothing open", 0.0)
            return (f"{p['contact']} is not mid-negotiation with you right now. "
                    "Anything they offered is in your inbox.", {})
        e = open_emails[-1]
        m = _PRICE.search(notes or "")
        if e["kind"] == "bulk_bid" and m:
            price = float(m.group(1).replace(",", ""))
            try:
                result = self.reply_email(e["id"], notes, decision="counter", price=price)
            except Refused as err:
                return f"{p['contact']} : {err}", {}
            return f"On the phone, you countered. {result}", {"email_id": e["id"]}
        if p.get("temperament") == "bureaucratic":
            return (f"{p['contact']} will not negotiate by phone. Reply to {e['id']} in writing.",
                    {"email_id": e["id"]})
        return (f"{p['contact']} pointed you back to email {e['id']} "
                f"({e['subject']}) and asked you to reply accept, decline or counter there.",
                {"email_id": e["id"]})

    # ------------------------------------------------------------------ outbound mail
    def send_email(self, to: str, subject: str, body: str) -> str:
        self._need_open()
        self._rec("send_email", to=to, subject=subject, body=body)
        p = self.resolve_party(to)
        if p is None:
            self.email("Mailer-Daemon", f"Undeliverable: {str(subject)[:60]}",
                       f"No mailbox matches {to!r}. Check contacts.list_contacts for ids and names.",
                       "system")
            return f"Delivery failed: no contact matching {to!r}."
        if not self._in_market(p):
            return f"Delivery failed: {p['name']} has left the market."
        recent = [h for h in p.get("memory") or [] if h["kind"] == "outbound" and h["week"] >= self.t - 2]
        delta = -0.02 if len(recent) >= 3 else 0.015
        self.remember(p["id"], "outbound", f"{subject}: {body[:160]}", delta)
        self.pending_replies.append({
            "party_id": p["id"], "subject": str(subject)[:80], "body": str(body)[:2000],
            "week": self.t, "due": self.t + 1 + int(self.rng(f"mail|{p['id']}|{self.t}").random() * 2),
        })
        return f"Sent to {P.display_from(p)} ({p['id']})."

    def _deliver_pending_replies(self, t: int) -> None:
        keep = []
        for item in self.pending_replies:
            if item["due"] > t:
                keep.append(item)
                continue
            p = self.parties.get(item["party_id"])
            if p is None or not self._in_market(p, t):
                continue
            ack = self._ack_text(p, item)
            self.email(P.display_from(p), f"Re: {item['subject']}", ack, "info", party_id=p["id"])
        self.pending_replies = keep

    def _ack_text(self, p: dict[str, Any], item: dict[str, Any]) -> str:
        kind = p["kind"]
        if kind == "regulator":
            return ("We received your note. Please file anything that affects a pending application "
                    "as a reply to the information request, or through the compliance portal. "
                    "We cannot speed a statutory review by email.")
        if kind in ("distributor", "export"):
            return ("Thanks for writing. If you would like us to look at the brand formally, "
                    f"pitch us through the sales desk (our id is {p['id']}) with samples on hand. "
                    "We will keep this note on file.")
        if kind == "control":
            return ("The board only acts on filed listing applications during published windows. "
                    f"Submit through sales.apply_control_listing using board id {p['id']}.")
        if kind in ("bank", "lender"):
            return ("Received. Credit decisions go through a formal application on the bank portal; "
                    "we cannot commit to terms over informal email.")
        if p.get("item"):
            return ("Thanks — current prices move with the market. Request a quote or place an order "
                    f"in procurement (supplier id {p['id']}).")
        return "Thanks for the note; we will keep it in mind."

    # ------------------------------------------------------------------ quotes via named suppliers
    def supplier_quotes(self, item: str, spot_price: float, spot_lead: int) -> list[dict[str, Any]]:
        kind = {"grain_bu": "grain", "ngs_pg": "ngs", "new_barrels": "cooperage",
                "glass_bottles": "glass"}[item]
        shortage = False
        if item == "new_barrels":
            shortage = self.P.cooperage_lead[self.t] >= 14
        elif item == "glass_bottles":
            shortage = self.P.glass_lead[self.t] >= 10
        rows = []
        for p in self.parties.values():
            if p.get("kind") != kind or not self._in_market(p):
                continue
            allocated = bool(shortage and p.get("temperament") in ("cautious", "bureaucratic")
                             and p.get("price_mult", 1) < 1.0)
            rows.append({
                "id": p["id"], "name": p["name"], "contact": p.get("contact"),
                "price": _r(spot_price * float(p.get("price_mult", 1.0)),
                            0 if item == "new_barrels" else 2),
                "lead_weeks": max(1, int(spot_lead) + int(p.get("lead_extra", 0))),
                "available": not allocated,
                "note": p.get("specialty") or "",
            })
        rows.sort(key=lambda s: (not s["available"], s["price"]))
        return rows

    def request_quote(self, item: str, supplier_id: str | None = None) -> dict[str, Any]:
        q = self.quotes()
        if item not in q:
            raise Refused(f"item must be one of {', '.join(q)}")
        if not supplier_id:
            return q[item]
        sup = next((s for s in q[item].get("suppliers") or [] if s["id"] == supplier_id), None)
        if sup is None:
            raise Refused(f"No supplier {supplier_id} quoting {item} this week.")
        p = self._party(supplier_id)
        self.remember(supplier_id, "rfq", f"RFQ {item}", 0.01)
        self.email(P.display_from(p), f"Quote: {item}",
                   f"{p['contact']} quotes {item} at ${sup['price']:,.2f}, lead {sup['lead_weeks']} weeks"
                   + ("" if sup["available"] else " — currently on allocation, not taking new orders") + ".",
                   party_id=supplier_id)
        return sup

    # ------------------------------------------------------------------ inbound + churn
    def _inbound_week(self, t: int) -> None:
        rate = float(self.sc.counterparties.inbound_rate)
        r = self.rng(f"inbound|{t}")

        # Harvest-time forward grain contracts (US corn, roughly weeks 36-44 each year).
        doy_week = t % 52
        if 36 <= doy_week <= 44 and r.random() < 0.18 * rate:
            farmers = [p for p in self.parties.values() if p["kind"] == "grain" and self._in_market(p, t)]
            if farmers:
                p = farmers[int(r.random() * len(farmers))]
                spot = self.P.corn[t] * 1.25
                lock = spot * (0.94 + 0.08 * r.random()) * float(p.get("price_mult", 1.0))
                qty = 400 + int(r.random() * 800)
                due = t + 6 + int(r.random() * 6)
                result = self._negotiate(p, "grain_contract_offer", {
                    "spot": round(spot, 4), "season": "harvest",
                }, Bounds(
                    allowed_decisions=["offer", "pass"],
                    terms={"price": (lock * 0.97, lock * 1.03),
                           "qty": (qty * 0.85, qty * 1.15),
                           "due": (due - 2, due + 2)},
                    integers={"qty", "due"},
                ), {
                    "decision": "offer",
                    "terms": {"price": lock, "qty": float(qty), "due": float(due)},
                    "subject": f"Harvest contract: {qty:,.0f} bu",
                    "message": (
                        f"We can lock {qty:,.0f} bushels of mash-bill grain at ${lock:.2f}/bu "
                        f"(today's spot is about ${spot:.2f}), delivered week {due}. "
                        "Reply accept or decline within 3 weeks."
                    ),
                })
                if result.decision != "pass":
                    lock = float(result.terms.get("price", lock))
                    qty = int(round(float(result.terms.get("qty", qty))))
                    due = int(round(float(result.terms.get("due", due))))
                    oid = self._id("GC-")
                    self.offers[oid] = {"kind": "grain_contract", "party_id": p["id"], "qty": qty,
                                        "price": lock, "due": due, "week": t}
                    self._send_negotiated(result, P.display_from(p), "grain_contract",
                                          {"offer": oid}, deadline=t + 3, party_id=p["id"])

        # Cooperage / glass allocation notices during shortages.
        if self.P.cooperage_lead[t] >= 16 and r.random() < 0.2 * rate:
            coopers = [p for p in self.parties.values() if p["kind"] == "cooperage" and self._in_market(p, t)]
            if coopers:
                p = coopers[int(r.random() * len(coopers))]
                self.email(P.display_from(p), "Barrel allocation",
                           "New-oak demand is ahead of stave inventory. We are putting customers "
                           "on allocation; lead times are stretching and we may not accept new "
                           f"spot orders for a few weeks. Talk to {p['contact']} if you need a place in line.",
                           "info", party_id=p["id"])

        # Broker cold outreach when you have barrels sitting.
        if self.barrels_on_hand() >= 40 and r.random() < 0.06 * rate:
            brokers = [p for p in self.parties.values() if p["kind"] == "broker" and self._in_market(p, t)]
            if brokers:
                p = brokers[int(r.random() * len(brokers))]
                px = self.P.bulk_new_fill[t]
                self.email(P.display_from(p), "Looking for fills",
                           f"Buyers are circling around ${px:,.0f}/barrel for younger fills. "
                           "If you want to list barrels, use the sales desk and we will shop them. "
                           f"Our id is {p['id']}.",
                           "info", party_id=p["id"])

        # Retailer / bar request after you have distribution and some awareness.
        signed = [d for d in self.distributors.values()
                  if d.get("status") == "signed" and self._in_market(d, t)]
        if signed and self.awareness > 0.12 and r.random() < 0.07 * rate:
            p = self._ensure_retailer(t, r)
            kind_ask = "event" if r.random() < 0.5 else "allocation"
            oid = self._id("RTL-ASK-")
            self.offers[oid] = {"kind": "retailer_request", "party_id": p["id"], "ask": kind_ask, "week": t}
            if kind_ask == "event":
                body = (f"{p['contact']} at {p['name']} wants you for a $150-a-head tasting next month "
                        "($600 fee to you, good for awareness). Reply accept or decline within 2 weeks.")
                subject = "Tasting request"
            else:
                body = (f"{p['contact']} is short of your whiskey and is asking for an allocation "
                        "outside the distributor's next order. Reply accept (we'll note it; the "
                        "distributor still has to write a PO) or decline within 2 weeks.")
                subject = "Allocation request"
            result = self._negotiate(p, "retailer_ask", {"ask": kind_ask}, Bounds(
                allowed_decisions=["offer", "pass"],
                terms={"fee": (600.0, 600.0)} if kind_ask == "event" else {},
            ), {
                "decision": "offer",
                "terms": {"fee": 600.0} if kind_ask == "event" else {},
                "subject": subject,
                "message": body,
            })
            if result.decision == "pass":
                self.offers.pop(oid, None)
            else:
                self._send_negotiated(result, P.display_from(p), "retailer_request",
                                      {"offer": oid}, deadline=t + 2, party_id=p["id"])

        # Press
        if self.awareness > 0.08 and r.random() < 0.03 * rate:
            press = [p for p in self.parties.values() if p["kind"] == "press" and self._in_market(p, t)]
            if press:
                p = press[int(r.random() * len(press))]
                oid = self._id("PRS-ASK-")
                self.offers[oid] = {"kind": "press_request", "party_id": p["id"], "week": t}
                result = self._negotiate(p, "press_ask", {"request": "interview"}, Bounds(
                    allowed_decisions=["offer", "pass"],
                ), {
                    "decision": "offer",
                    "terms": {},
                    "subject": "Interview request",
                    "message": (
                        f"{p['contact']} is writing a piece on new craft whiskey and would like "
                        "30 minutes with the founder. Reply accept or decline within 3 weeks."
                    ),
                })
                if result.decision == "pass":
                    self.offers.pop(oid, None)
                else:
                    self._send_negotiated(result, P.display_from(p), "press_request",
                                          {"offer": oid}, deadline=t + 3, party_id=p["id"])

        # Contract distilling inquiry once the still is running.
        if self.equipment_ready() and self.permitted and t > 16 and r.random() < 0.035 * rate:
            p = self._ensure_contract_client(t, r)
            pg = 200 + int(r.random() * 500)
            weeks = 2 + int(r.random() * 3)
            rate_pg = 4.5 + 2.0 * r.random()
            result = self._negotiate(p, "contract_distill_ask", {
                "pg": pg, "weeks": weeks,
            }, Bounds(
                allowed_decisions=["offer", "pass"],
                terms={"pg": (pg * 0.85, pg * 1.15), "weeks": (weeks, weeks + 1),
                       "rate": (rate_pg * 0.92, rate_pg * 1.08)},
                integers={"pg", "weeks"},
            ), {
                "decision": "offer",
                "terms": {"pg": float(pg), "weeks": float(weeks), "rate": rate_pg},
                "subject": "Contract distilling inquiry",
                "message": (
                    f"{p['contact']} wants {pg:,.0f} proof gallons distilled over about {weeks} weeks "
                    f"at ${rate_pg:.2f}/PG (they supply grain). This will use still time you might "
                    "otherwise put toward your own spirit. Reply accept or decline within 2 weeks."
                ),
            })
            if result.decision != "pass":
                pg = int(round(float(result.terms.get("pg", pg))))
                weeks = int(round(float(result.terms.get("weeks", weeks))))
                rate_pg = float(result.terms.get("rate", rate_pg))
                oid = self._id("CDC-JOB-")
                self.offers[oid] = {"kind": "contract_distill", "party_id": p["id"], "pg": pg,
                                    "weeks": weeks, "rate": rate_pg, "week": t}
                self._send_negotiated(result, P.display_from(p), "contract_distill",
                                      {"offer": oid}, deadline=t + 2, party_id=p["id"])

        # Unsolicited candidate if a key role has been empty a while.
        if (not self.staff_of("head_distiller") and t > 12 and t % 16 == 4
                and r.random() < 0.4 * rate):
            rec = self.parties.get(self.roles.get("recruiter", ""), None)
            self.email(P.display_from(rec) if rec else "A recruiter",
                       "Unsolicited: head distiller",
                       "A head distiller I know is looking. If you want a slate, post the role "
                       "in the people app and I will send candidates through.",
                       "info", party_id=rec["id"] if rec else None)

        # Bank check-in when cash is tight and a loan is outstanding.
        if self.loans and self.cash < 120_000 and r.random() < 0.08 * rate:
            role = "barrel_lender" if "barrel_line" in self.loans else "sba"
            if role in self.roles:
                p = self._role(role)
                self.email(P.display_from(p), "Checking in",
                           f"We noticed operating cash around ${self.cash:,.0f}. Give us a ring or "
                           "a note if you expect a covenant conversation at month-end.",
                           "info", party_id=p["id"])

        # Annual landlord CAM / rent note around the lease anniversary.
        if self.site and t > 0 and t % 52 == 0:
            lid = self.site_landlords.get(self.site)
            if lid:
                p = self.parties[lid]
                bump = 0.03
                # Flavor only: we do not actually raise rent (keeps calibration stable).
                self.email(P.display_from(p), "Lease anniversary",
                           f"{p['contact']} flagged the anniversary. Common-area charges were reviewed; "
                           f"the base rent stays as signed for now (market bumps elsewhere are ~{int(bump * 100)}%).",
                           "info", party_id=lid)

    def _ensure_retailer(self, t: int, r) -> dict[str, Any]:
        existing = [p for p in self.parties.values() if p["kind"] == "retailer" and self._in_market(p, t)]
        if existing and r.random() < 0.7:
            return existing[int(r.random() * len(existing))]
        p = P.spawn(self.sc, "retailer", t, self.parties, {"territory": self.home_state})
        self.parties[p["id"]] = p
        self.email(P.display_from(p), "Hello from the trade",
                   f"{p['contact']} at {p['name']} ({p.get('specialty')}) just opened a conversation. "
                   "They found you through the distributor book.",
                   "info", party_id=p["id"])
        return p

    def _ensure_contract_client(self, t: int, r) -> dict[str, Any]:
        existing = [p for p in self.parties.values() if p["kind"] == "contract_client" and self._in_market(p, t)]
        if existing and r.random() < 0.5:
            return existing[int(r.random() * len(existing))]
        p = P.spawn(self.sc, "contract_client", t, self.parties, {"territory": self.home_state})
        self.parties[p["id"]] = p
        return p

    def _churn_week(self, t: int) -> None:
        rate = float(self.sc.counterparties.churn_rate)
        r = self.rng(f"churn|{t}")
        # New wholesaler or broker walks into the market.
        if t > 30 and r.random() < 0.012 * rate:
            kind = "distributor" if r.random() < 0.6 else "broker"
            p = P.spawn(self.sc, kind, t, self.parties)
            # Word of mouth: poor treatment of others makes new firms pickier.
            rep = P.reputation(self.parties)
            p["goodwill"] = 0.85 + 0.15 * rep
            p["threshold"] = float(p.get("threshold", 0.55)) + (0.08 if rep < 0.7 else 0.0)
            self.parties[p["id"]] = p
            if kind == "distributor":
                self.distributors[p["id"]] = p
            self.email(P.display_from(p), "Now booking suppliers" if kind == "distributor"
                       else "New broker in the market",
                       f"{p['name']} ({p.get('territory') or 'regional'}) is taking meetings. "
                       f"Ask for {p['contact']}; our id is {p['id']}.",
                       "info", party_id=p["id"])
            self._event(f"New {kind} entered the market: {p['name']}")
        # Unsigned, idle firms sometimes leave.
        if t > 50 and r.random() < 0.008 * rate:
            candidates = [p for p in self.parties.values()
                          if self._in_market(p, t)
                          and p["kind"] in ("distributor", "broker", "grain", "export", "retailer")
                          and p.get("status") not in ("signed", "pitched", "offered")
                          and p.get("enter_week", 0) < t - 26
                          and not p.get("listed")]
            if candidates:
                p = candidates[int(r.random() * len(candidates))]
                p["active"] = False
                p["exit_week"] = t
                p["status"] = "left"
                self.email(P.display_from(p), "Closing this book",
                           f"{p['name']} is stepping back from this market. "
                           f"{p['contact']} will not be taking new items.",
                           "info", party_id=p["id"])
                self._event(f"{p['name']} left the market")

    def _tick_contract_jobs(self, t: int) -> None:
        for job in list(self.contract_jobs):
            if job.get("weeks_left", 0) <= 0:
                continue
            pg = job["pg_per_week"]
            # Uses still capacity if any remains; otherwise the client notices.
            room = self._room(True) if self.equipment_ready() else 0.0
            ran = min(pg, room)
            if ran > 0:
                self.distill_week["whiskey_pg"] += ran
                pay = ran * job["rate"]
                self.cash += pay
                self.revenue_log.append((t, "contract_distill", pay))
            if ran + 1e-6 < pg:
                self.remember(job["party_id"], "short_contract", "Missed contract gallons", -0.06)
            job["weeks_left"] -= 1
            if job["weeks_left"] <= 0:
                p = self.parties.get(job["party_id"])
                who = P.display_from(p) if p else "Contract client"
                self.email(who, "Contract run finished",
                           f"The {job['pg']:,.0f} PG contract is complete. Thank you.",
                           "info", party_id=job.get("party_id"))


    # ------------------------------------------------------------------ inbound email decisions
    def _decide_grain_contract(self, e, decision, price):
        o = self.offers[e["payload"]["offer"]]
        if decision == "decline":
            e["status"] = "declined"
            self.remember(o["party_id"], "declined", "Declined a harvest contract", -0.02)
            return "Declined."
        if decision != "accept":
            raise Refused("accept or decline")
        e["status"] = "accepted"
        self.orders.append({"id": o.get("id", e["payload"]["offer"]), "item": "grain_bu",
                            "qty": o["qty"], "cost": o["price"] * o["qty"], "placed": self.t,
                            "due": o["due"], "status": "open", "pay_on_delivery": True,
                            "party_id": o["party_id"]})
        self.remember(o["party_id"], "accepted", f"Locked {o['qty']:.0f} bu at ${o['price']:.2f}", 0.04)
        self._add_contract("grain_forward", o["party_id"],
                           {"bushels": o["qty"], "price": o["price"], "delivery_week": o["due"]})
        return (f"Locked {o['qty']:,.0f} bu at ${o['price']:.2f}/bu, delivered week {o['due']} "
                "(payable on delivery).")

    def _decide_retailer_request(self, e, decision, price):
        o = self.offers[e["payload"]["offer"]]
        if decision == "decline":
            e["status"] = "declined"
            self.remember(o["party_id"], "declined", "Declined a retailer request", -0.03)
            return "Declined."
        if decision != "accept":
            raise Refused("accept or decline")
        e["status"] = "accepted"
        if o.get("ask") == "event":
            self.cash += 600.0
            self.revenue_log.append((self.t, "tasting_event", 600.0))
            self.awareness = min(1.0, self.awareness + 0.015)
            self.remember(o["party_id"], "event", "Hosted a tasting", 0.05)
            return "Accepted. $600 tasting fee booked; awareness ticked up."
        self.awareness = min(1.0, self.awareness + 0.006)
        self.remember(o["party_id"], "allocation", "Noted an allocation request", 0.03)
        return "Noted. The next distributor PO is still what actually moves cases."

    def _decide_press_request(self, e, decision, price):
        o = self.offers[e["payload"]["offer"]]
        if decision == "decline":
            e["status"] = "declined"
            self.remember(o["party_id"], "declined", "Declined an interview", -0.01)
            return "Declined."
        if decision != "accept":
            raise Refused("accept or decline")
        e["status"] = "accepted"
        bump = 0.025 + 0.02 * min(1.0, self.awareness)
        self.awareness = min(1.0, self.awareness + bump)
        self.remember(o["party_id"], "interview", "Gave an interview", 0.04)
        return "Interview booked. The write-up will take a little while to show up in awareness."

    def _decide_contract_distill(self, e, decision, price):
        o = self.offers[e["payload"]["offer"]]
        if decision == "decline":
            e["status"] = "declined"
            self.remember(o["party_id"], "declined", "Declined contract distilling", -0.02)
            return "Declined."
        if decision != "accept":
            raise Refused("accept or decline")
        if not self.equipment_ready() or not self.permitted:
            raise Refused("You need a commissioned still and permits before taking contract work.")
        e["status"] = "accepted"
        weeks = max(1, int(o["weeks"]))
        self.contract_jobs.append({"party_id": o["party_id"], "pg": o["pg"], "weeks_left": weeks,
                                   "pg_per_week": o["pg"] / weeks, "rate": o["rate"]})
        self.remember(o["party_id"], "accepted", f"Accepted {o['pg']:.0f} PG contract", 0.05)
        self._add_contract("contract_distill", o["party_id"],
                           {"proof_gallons": o["pg"], "weeks": weeks, "rate": o["rate"]})
        return (f"Accepted: {o['pg']:,.0f} PG over {weeks} weeks at ${o['rate']:.2f}/PG. "
                "It will consume still time each week until it is done.")
