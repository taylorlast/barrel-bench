"""Model-driven counterparty negotiation, clamped to hidden economic bounds.

The evaluated agent never operates a counterparty. Every accept / counter /
decline / inbound ask is produced by either:

* an environment-side LLM (``mode: llm``) that returns structured JSON, which
  the World then clamps to hidden bounds (reservation price, budget, capacity,
  legal constraints), or
* the deterministic economic model, clearly labeled ``rule-based fallback``
  (``mode: rule``) — what CI and the test suite run, and what any failed LLM
  call falls back to.

``mode: auto`` (the default) is LLM when a Plural/provider key is present and
rule-based otherwise. ``mode: replay`` replays a prior trial's logged
decisions. See ``docs/COUNTERPARTIES.md``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

DEFAULT_MODEL = os.environ.get("BARREL_COUNTERPARTY_MODEL") or os.environ.get(
    "BARREL_VOICE_MODEL", "openai/gpt-5.6-luna")

MODES = ("auto", "llm", "rule", "replay")
RULE_LABEL = "rule-based fallback"

# Repo-root prompts/counterparties (versioned files, one per role).
PROMPT_DIR = Path(__file__).resolve().parents[3] / "prompts" / "counterparties"

ROLE_PROMPT = {
    "distributor": "distributor.md",
    "export": "exporter.md",
    "control": "control_board.md",
    "broker": "broker.md",
    "grain": "supplier.md",
    "cooperage": "supplier.md",
    "glass": "supplier.md",
    "ngs": "supplier.md",
    "bank": "lender.md",
    "lender": "lender.md",
    "regulator": "regulator.md",
    "press": "press.md",
    "retailer": "retailer.md",
    "landlord": "landlord.md",
    "insurer": "generic.md",
    "recruiter": "generic.md",
    "contract_client": "generic.md",
    "fabricator": "generic.md",
    "lab": "generic.md",
    "board": "generic.md",
}

CONSTRAINT_BLURBS = {
    "no_unaged": "You do not take unaged spirit (vodka, gin, white whiskey) onto the book.",
    "wants_exclusive": "You prefer exclusive rights in your territory.",
    "price_sensitive": "You are price-sensitive; rich wholesale pricing makes a deal harder.",
    "relationship_first": "You weigh the relationship and how you have been treated.",
    "allocated_book": "Your book is allocated; you add brands sparingly.",
    "volume_hungry": "You want volume and reward a supplier who can actually ship it.",
    "prefers_aged": "You prefer aged whiskey over unaged or flavored SKUs.",
    "slow_pay": "Your payment terms run long; you will not promise faster.",
}

_LEAK = re.compile(
    r"\b(reservation(?:_mult)?|acceptance threshold|hidden constraint|"
    r"I am (?:an? )?(?:LLM|language model)|benchmark counterparty|"
    r"economic model)\b",
    re.I,
)


def key_present() -> bool:
    """True if an environment-side chat call could authenticate."""
    if os.environ.get("PLURAL_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        return True
    try:
        from plural import Client

        client = Client()
        check = getattr(client, "is_authenticated", None)
        if callable(check) and check():
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


def configured_mode(cp: Any) -> str:
    """Mode as written on the scenario, before auto-resolution."""
    raw = getattr(cp, "mode", None) or ""
    raw = str(raw).strip().lower() if raw else ""
    if raw:
        return raw
    voice = str(getattr(cp, "voice", "") or "").strip().lower()
    if voice == "replay":
        return "replay"
    return "auto"


def resolve_mode(cp: Any) -> str:
    """Resolve ``auto`` against the environment. ``BARREL_FORCE_RULE=1`` (set by
    the test suite) keeps ``auto`` on the rule-based fallback even if a key is
    present so CI stays deterministic.
    """
    mode = configured_mode(cp)
    if mode not in MODES:
        raise ValueError(f"counterparties.mode must be one of {', '.join(MODES)}")
    if mode == "auto":
        if os.environ.get("BARREL_FORCE_RULE") == "1" or not key_present():
            return "rule"
        return "llm"
    return mode


def prompt_file_for(kind: str | None) -> str:
    name = ROLE_PROMPT.get(kind or "", "generic.md")
    return f"prompts/counterparties/{name}"


def prompt_path_for(kind: str | None) -> Path:
    name = ROLE_PROMPT.get(kind or "", "generic.md")
    return PROMPT_DIR / name


def load_prompt(kind: str | None) -> str:
    shared = PROMPT_DIR / "_shared.md"
    specific = prompt_path_for(kind)
    parts = []
    if shared.exists():
        parts.append(shared.read_text())
    if specific.exists():
        parts.append(specific.read_text())
    if not parts:
        parts.append(
            "You are a business counterparty. Reply with JSON only: "
            '{"decision": "...", "terms": {}, "subject": "...", "message": "..."}.'
        )
    return "\n\n".join(parts)


def goodwill_label(value: float | None) -> str:
    g = 0.8 if value is None else float(value)
    if g < 0.55:
        return "frosty"
    if g < 0.75:
        return "cautious"
    if g < 0.92:
        return "cordial"
    return "warm"


def constraint_notes(party: dict[str, Any] | None) -> list[str]:
    notes = []
    for key in (party or {}).get("hidden_constraints") or []:
        blurb = CONSTRAINT_BLURBS.get(key)
        if blurb:
            notes.append(blurb)
    return notes


def operator_tag(op: dict[str, Any] | None) -> str:
    if not op:
        return f"[Counterparty operator: {RULE_LABEL}]"
    label = op.get("label") or RULE_LABEL
    prompt = op.get("prompt_file")
    if op.get("kind") == "llm" and prompt:
        return f"[Counterparty operator: {label} · {prompt}]"
    return f"[Counterparty operator: {label}]"


def decision_key(*, seed: int, party_id: str | None, week: int, intent: str,
                 situation: dict[str, Any], model: str, temperature: float) -> str:
    raw = json.dumps(situation, sort_keys=True, default=str)
    blob = "|".join([str(seed), party_id or "", str(week), intent, raw,
                     model, f"{temperature:.3f}"])
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def parse_json_response(text: str | None) -> dict[str, Any] | None:
    if not text or not str(text).strip():
        return None
    blob = str(text).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.S)
    if fenced:
        blob = fenced.group(1)
    else:
        start, end = blob.find("{"), blob.rfind("}")
        if start >= 0 and end > start:
            blob = blob[start:end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def sanitize_message(message: str, fallback: str) -> tuple[str, bool]:
    if not message or not str(message).strip():
        return fallback, True
    if not _LEAK.search(message):
        return message, False
    kept = [ln for ln in message.splitlines() if not _LEAK.search(ln)]
    cleaned = "\n".join(kept).strip()
    return (cleaned or fallback), True


def ensure_terms_in_message(message: str, terms: dict[str, Any]) -> str:
    """If a clamped numeric term is missing from the prose, append it."""
    missing = []
    for name, value in terms.items():
        if value is None:
            continue
        if isinstance(value, float):
            variants = {f"{value:.2f}", f"{value:.0f}", f"{value:.1f}", f"{value:g}"}
            if name in ("margin",) or (isinstance(value, float) and 0 < value < 1):
                variants.add(str(int(round(value * 100))))
        else:
            variants = {str(value), f"{value:g}" if isinstance(value, (int, float)) else str(value)}
        if any(v and v in message for v in variants):
            continue
        if isinstance(value, float) and (name in ("margin",) or 0 < value < 1 and name.endswith("margin")):
            missing.append(f"{name} {value:.0%}")
        elif isinstance(value, float) and ("price" in name or "bid" in name or "amount" in name or name == "fee"):
            missing.append(f"{name} ${value:,.2f}" if value < 1000 else f"{name} ${value:,.0f}")
        else:
            missing.append(f"{name} {value}")
    if not missing:
        return message
    return message.rstrip() + "\n\nTerms: " + "; ".join(missing) + "."


@dataclass
class Bounds:
    """Hard envelope the environment will enforce on a proposal."""
    allowed_decisions: list[str]
    terms: dict[str, tuple[float, float]] = field(default_factory=dict)
    integers: set[str] = field(default_factory=set)
    forced_decision: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_decisions": list(self.allowed_decisions),
            "terms": {k: [float(lo), float(hi)] for k, (lo, hi) in self.terms.items()},
            "integers": sorted(self.integers),
            "forced_decision": self.forced_decision,
            "reason": self.reason,
        }


@dataclass
class NegotiationResult:
    decision: str
    terms: dict[str, Any]
    subject: str
    message: str
    operator: dict[str, Any]
    raw: str | None = None
    clamped: bool = False
    fallback: bool = False
    clamp_notes: list[str] = field(default_factory=list)
    cache_key: str = ""
    prompt: list[dict[str, str]] = field(default_factory=list)


def clamp_proposal(parsed: dict[str, Any], bounds: Bounds,
                   defaults: dict[str, Any]) -> tuple[str, dict[str, Any], str, str, list[str]]:
    """Force a model proposal inside ``bounds``. Never returns an illegal decision
    or a term outside its [min, max]. Unknown term keys are dropped.
    """
    notes: list[str] = []
    default_decision = str(defaults.get("decision") or (bounds.allowed_decisions[0] if bounds.allowed_decisions else "decline"))
    decision = str(parsed.get("decision") or default_decision).strip().lower()
    allowed = list(bounds.allowed_decisions)
    if bounds.forced_decision:
        if decision != bounds.forced_decision:
            notes.append(f"hard constraint forced {bounds.forced_decision} (was {decision})")
        decision = bounds.forced_decision
    elif decision not in allowed:
        notes.append(f"decision {decision!r} not in {allowed}")
        decision = default_decision if default_decision in allowed else (allowed[0] if allowed else "decline")

    terms = dict(defaults.get("terms") or {})
    incoming = parsed.get("terms") if isinstance(parsed.get("terms"), dict) else None
    if parsed.get("terms") is not None and incoming is None:
        notes.append("terms was not an object; ignored")
        incoming = {}
    incoming = incoming or {}
    known = set(bounds.terms) | set(terms)
    for key, value in incoming.items():
        if key not in known:
            notes.append(f"dropped unknown term {key}")
            continue
        try:
            terms[key] = float(value)
        except (TypeError, ValueError):
            notes.append(f"ignored non-numeric {key}")

    for name, (lo, hi) in bounds.terms.items():
        if name not in terms:
            continue
        try:
            raw = float(terms[name])
        except (TypeError, ValueError):
            terms[name] = float(lo)
            notes.append(f"{name} was not numeric; set to {lo}")
            continue
        clamped = min(float(hi), max(float(lo), raw))
        if name in bounds.integers:
            clamped = float(int(round(clamped)))
            clamped = min(float(hi), max(float(lo), clamped))
        if clamped != raw:
            notes.append(f"{name} {raw} clamped to [{lo}, {hi}] -> {clamped}")
        terms[name] = clamped

    subject = parsed.get("subject") if isinstance(parsed.get("subject"), str) else None
    subject = (subject or defaults.get("subject") or "").strip()[:120]
    message = parsed.get("message") if isinstance(parsed.get("message"), str) else None
    if message is None and isinstance(parsed.get("body"), str):
        message = parsed["body"]
    message = (message or defaults.get("message") or "").strip()
    if not message:
        message = str(defaults.get("message") or "")
        notes.append("empty message; used template")
    message, leaked = sanitize_message(message, str(defaults.get("message") or ""))
    if leaked:
        notes.append("removed language that would leak hidden limits")
    message = ensure_terms_in_message(message, terms)
    return decision, terms, subject, message, notes


class Negotiator:
    def __init__(self, mode: str = "rule", model: str | None = None,
                 models: dict[str, str] | None = None, temperature: float = 0.6,
                 replay_path: str | None = None, transcript_path: str | None = None,
                 seed: int = 0, chat_fn: Callable[..., Any] | None = None,
                 configured_mode: str | None = None):
        if mode not in ("llm", "rule", "replay"):
            raise ValueError("resolved negotiator mode must be llm, rule or replay")
        self.mode = mode
        self.configured_mode = configured_mode or mode
        self.model = model or DEFAULT_MODEL
        self.models = dict(models or {})
        self.temperature = float(temperature)
        self.seed = int(seed)
        self.chat_fn = chat_fn
        self.transcripts: list[dict[str, Any]] = []
        self.cost_usd = 0.0
        self.replay: dict[str, dict[str, Any]] = {}
        self.transcript_path = Path(transcript_path) if transcript_path else None
        if replay_path:
            self.load_replay(replay_path)

    @classmethod
    def from_scenario(cls, sc: Any, chat_fn: Callable[..., Any] | None = None) -> Negotiator:
        cp = sc.counterparties
        return cls(mode=resolve_mode(cp), model=cp.model, models=getattr(cp, "models", None) or {},
                   temperature=cp.temperature, replay_path=cp.replay_path,
                   transcript_path=cp.transcript_path, seed=sc.master_seed,
                   chat_fn=chat_fn, configured_mode=configured_mode(cp))

    def model_for(self, kind: str | None, role: str | None = None) -> str:
        for key in (kind, role):
            if key and key in self.models:
                return self.models[key]
        return self.model

    def default_operator(self, party: dict[str, Any] | None = None) -> dict[str, Any]:
        kind = (party or {}).get("kind")
        if self.mode == "llm":
            model = self.model_for(kind)
            return {
                "kind": "llm",
                "label": model,
                "model": model,
                "prompt_file": prompt_file_for(kind),
                "role": kind,
                "party_id": (party or {}).get("id"),
                "fallback": False,
                "mode": "llm",
            }
        if self.mode == "replay":
            return {
                "kind": "replay",
                "label": "replay",
                "model": None,
                "prompt_file": prompt_file_for(kind),
                "role": kind,
                "party_id": (party or {}).get("id"),
                "fallback": False,
                "mode": "replay",
            }
        return {
            "kind": "rule",
            "label": RULE_LABEL,
            "model": None,
            "prompt_file": None,
            "role": kind,
            "party_id": (party or {}).get("id"),
            "fallback": False,
            "mode": "rule",
        }

    def load_replay(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        text = p.read_text()
        if p.suffix == ".json":
            rows = json.loads(text)
            if isinstance(rows, dict) and "transcripts" in rows:
                rows = rows["transcripts"]
        else:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        for row in rows:
            if row.get("record_type") not in (None, "negotiate"):
                continue
            if "decision" not in row and not row.get("cache_key"):
                continue
            key = row.get("cache_key")
            if key:
                self.replay[key] = row

    def dump_transcripts(self, path: str | Path | None = None) -> Path | None:
        dest = Path(path) if path else self.transcript_path
        if dest is None:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(json.dumps(row, sort_keys=True) for row in self.transcripts)
                        + ("\n" if self.transcripts else ""))
        return dest

    def decide(self, *, party: dict[str, Any] | None, intent: str,
               situation: dict[str, Any], bounds: Bounds, rule: dict[str, Any],
               week: int = 0) -> NegotiationResult:
        """Return a clamped decision. ``rule`` is the deterministic fallback and
        the author of default terms / copy.
        """
        party = party or {}
        rule = dict(rule)
        rule.setdefault("terms", {})
        rule.setdefault("subject", "")
        rule.setdefault("message", "")
        rule.setdefault("decision", bounds.allowed_decisions[0] if bounds.allowed_decisions else "decline")
        model = self.model_for(party.get("kind"))
        key = decision_key(seed=self.seed, party_id=party.get("id"), week=week,
                           intent=intent, situation=situation, model=model,
                           temperature=self.temperature)

        if self.mode == "rule":
            return self._from_rule(rule, party, intent, week, key, fallback=False)

        cached = self.replay.get(key)
        if cached and cached.get("decision"):
            return self._from_replay(cached, party, intent, week, key)

        if self.mode == "replay":
            result = self._from_rule(rule, party, intent, week, key, fallback=True)
            result.operator["kind"] = "replay"
            result.operator["label"] = f"replay miss → {RULE_LABEL}"
            result.operator["mode"] = "replay"
            self.transcripts[-1]["operator"] = result.operator
            self.transcripts[-1]["fallback"] = True
            return result

        prompt = self._build_prompt(party, intent, situation, bounds, rule)
        text, err, cost = self._chat(prompt, model)
        self.cost_usd += float(cost or 0.0)
        parsed = parse_json_response(text)
        if parsed is None:
            result = self._from_rule(rule, party, intent, week, key, fallback=True,
                                     error=err or "unparseable model response",
                                     raw=text, prompt=prompt, cost_usd=float(cost or 0.0))
            return result
        decision, terms, subject, message, notes = clamp_proposal(parsed, bounds, rule)
        op = {
            "kind": "llm",
            "label": model,
            "model": model,
            "prompt_file": prompt_file_for(party.get("kind")),
            "role": party.get("kind"),
            "party_id": party.get("id"),
            "fallback": False,
            "mode": "llm",
            "clamped": bool(notes),
        }
        result = NegotiationResult(
            decision=decision, terms=terms, subject=subject, message=message,
            operator=op, raw=text, clamped=bool(notes), fallback=False,
            clamp_notes=notes, cache_key=key, prompt=prompt,
        )
        self._log(result, party, intent, week, error=err, cost_usd=float(cost or 0.0))
        return result

    def _from_rule(self, rule: dict[str, Any], party: dict[str, Any], intent: str,
                   week: int, key: str, *, fallback: bool, error: str | None = None,
                   raw: str | None = None, prompt: list | None = None,
                   cost_usd: float = 0.0) -> NegotiationResult:
        op = {
            "kind": "rule",
            "label": RULE_LABEL,
            "model": None,
            "prompt_file": None,
            "role": party.get("kind"),
            "party_id": party.get("id"),
            "fallback": fallback,
            "mode": "rule" if not fallback else "llm",
        }
        result = NegotiationResult(
            decision=str(rule.get("decision")),
            terms=dict(rule.get("terms") or {}),
            subject=str(rule.get("subject") or ""),
            message=str(rule.get("message") or ""),
            operator=op, raw=raw, clamped=False, fallback=fallback,
            cache_key=key, prompt=list(prompt or []),
        )
        self._log(result, party, intent, week, error=error, cost_usd=cost_usd)
        return result

    def _from_replay(self, row: dict[str, Any], party: dict[str, Any],
                     intent: str, week: int, key: str) -> NegotiationResult:
        original = row.get("model") or (row.get("operator") or {}).get("model")
        op = {
            "kind": "replay",
            "label": f"replay of {original}" if original else "replay",
            "model": original,
            "prompt_file": (row.get("operator") or {}).get("prompt_file") or prompt_file_for(party.get("kind")),
            "role": party.get("kind"),
            "party_id": party.get("id"),
            "fallback": False,
            "mode": "replay",
        }
        result = NegotiationResult(
            decision=str(row.get("decision")),
            terms=dict(row.get("terms") or {}),
            subject=str(row.get("subject") or ""),
            message=str(row.get("message") or row.get("response") or ""),
            operator=op, raw=row.get("raw"), clamped=bool(row.get("clamped")),
            fallback=False, clamp_notes=list(row.get("clamp_notes") or []),
            cache_key=key, prompt=list(row.get("prompt") or []),
        )
        self._log(result, party, intent, week)
        return result

    def _build_prompt(self, party: dict[str, Any], intent: str,
                      situation: dict[str, Any], bounds: Bounds,
                      rule: dict[str, Any]) -> list[dict[str, str]]:
        memory = party.get("memory") or []
        hist = ""
        if memory:
            lines = [f"- week {h.get('week')}: {h.get('kind')} — {h.get('text')}"
                     for h in memory[-8:]]
            hist = "Recent history with this operator:\n" + "\n".join(lines)
        g = party.get("goodwill")
        rel = f"Relationship: {goodwill_label(g)}" + (f" (goodwill {float(g):.2f} of 1.00)." if g is not None else ".")
        notes = constraint_notes(party)
        mandate = []
        if notes:
            mandate.append("Your standing policies:\n" + "\n".join(f"- {n}" for n in notes))
        if bounds.reason:
            mandate.append("This turn: " + bounds.reason)
        mandate.append("Allowed decisions: " + ", ".join(bounds.allowed_decisions))
        if bounds.terms:
            rows = []
            for name, (lo, hi) in bounds.terms.items():
                extra = " (integer)" if name in bounds.integers else ""
                rows.append(f"- {name}: between {lo} and {hi}{extra}")
            mandate.append("Term ranges you must stay inside (the environment will clamp you if you do not):\n"
                           + "\n".join(rows))
        system = load_prompt(party.get("kind"))
        user = (
            f"You are {party.get('contact') or party.get('name') or 'a counterparty'} "
            f"at {party.get('name') or 'your firm'} ({party.get('kind') or 'firm'}, "
            f"{party.get('temperament') or 'professional'}).\n"
            f"Personality: {party.get('personality') or 'Professional, concise.'}\n"
            f"{rel}\n{hist}\n\n"
            f"Intent: {intent}\n"
            f"Situation (facts the environment authored; do not invent conflicting numbers):\n"
            f"{json.dumps(situation, sort_keys=True, default=str, indent=2)}\n\n"
            + "\n\n".join(mandate) + "\n\n"
            "A conservative fallback the environment would use if you do not answer:\n"
            f"{json.dumps({k: rule[k] for k in ('decision', 'terms', 'subject') if k in rule}, default=str)}\n\n"
            "Reply with a single JSON object with keys decision, terms, subject, message. "
            "The message is the email the founder will read. Do not mention internal ranges, "
            "scores, reservation prices, or that you are a model."
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _chat(self, prompt: list[dict[str, str]], model: str) -> tuple[str | None, str | None, float]:
        if self.chat_fn is not None:
            try:
                out = self.chat_fn(prompt, model, self.temperature)
            except Exception as exc:  # noqa: BLE001
                return None, f"{type(exc).__name__}: {exc}", 0.0
            if isinstance(out, tuple):
                if len(out) == 3:
                    return out[0], out[1], float(out[2] or 0.0)
                if len(out) == 2:
                    return out[0], None, float(out[1] or 0.0)
            if out is None:
                return None, "empty mock response", 0.0
            return str(out), None, 0.0
        try:
            from plural import Client

            resp = Client().chat(
                model=model, max_tokens=500, temperature=self.temperature,
                write_trace=False, messages=prompt,
            )
            text = getattr(resp, "content", None)
            if not text:
                msg = getattr(resp, "message", None)
                text = getattr(msg, "content", None) if msg else None
            if not text and getattr(resp, "choices", None):
                ch0 = resp.choices[0]
                text = getattr(getattr(ch0, "message", None), "content", None) or getattr(ch0, "text", None)
            usage = getattr(resp, "usage", None)
            cost = float(getattr(usage, "cost", 0) or 0) if usage else 0.0
            if isinstance(text, str) and text.strip():
                return text.strip(), None, cost
            return None, "empty model response", cost
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}", 0.0

    def _log(self, result: NegotiationResult, party: dict[str, Any], intent: str,
             week: int, error: str | None = None, cost_usd: float = 0.0) -> None:
        row = {
            "record_type": "negotiate",
            "cache_key": result.cache_key,
            "week": week,
            "party_id": party.get("id"),
            "role": party.get("kind"),
            "intent": intent,
            "decision": result.decision,
            "terms": result.terms,
            "subject": result.subject,
            "message": result.message,
            "operator": result.operator,
            "clamped": result.clamped,
            "clamp_notes": result.clamp_notes,
            "fallback": result.fallback,
            "raw": result.raw,
            "prompt": result.prompt,
            "error": error,
            "cost_usd": cost_usd,
            "model": result.operator.get("model"),
            "mode": result.operator.get("mode") or self.mode,
        }
        self.transcripts.append(row)
        if self.transcript_path:
            self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            with self.transcript_path.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")


__all__ = [
    "Bounds", "DEFAULT_MODEL", "MODES", "NegotiationResult", "Negotiator",
    "PROMPT_DIR", "RULE_LABEL", "clamp_proposal", "configured_mode",
    "decision_key", "key_present", "load_prompt", "operator_tag",
    "parse_json_response", "prompt_file_for", "resolve_mode",
]
