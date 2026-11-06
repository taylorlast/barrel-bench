"""Counterparty voice: template, LLM, or replay.

Every number, date, id and term in a message is authored by the World (or by the
hidden economic model) *before* this module runs. Voice only phrases those facts.

Modes
- ``template`` (default): the authored text is used as-is. Deterministic, no API key.
- ``llm``: a model rewrites the text in the sender's voice through Plural's gateway.
  If any authored number/id/date is dropped, or the call fails, the template is kept.
- ``replay``: return the body stored under the same cache key from a previous trial
  (loaded from ``replay_path``). Missing keys fall back to the template.

Every attempt — hit, miss, fallback — is appended to ``transcripts`` so a trial can
be inspected and replayed exactly. Environment-side model cost is tracked on
``cost_usd``; Plural's Agent ``cost_usd`` does not pick this up when ``write_trace``
is False (see docs/PLURAL-FEEDBACK.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_MODEL = os.environ.get("BARREL_COUNTERPARTY_MODEL") or os.environ.get(
    "BARREL_VOICE_MODEL", "openai/gpt-5.6-luna")

# Dollar amounts, bare decimals, ISO dates, and the ids this world issues.
_FACT = re.compile(
    r"\$[\d,]+(?:\.\d+)?|\b\d+\.\d+\b|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:PO#|COLA-|SRC-|BKR-|GRN-|COP-|GLS-|NGS-|BNK-|LNDR-|"
    r"INS-|REC-|LL-|REG-|PRS-|STL-|RTL-|CDC-|BD-|LAB-|CAND-|"
    r"D-|C-|X-|E|B|L|S|C|R|P)\d[\w-]*"
)


def facts_in(text: str) -> set[str]:
    return set(_FACT.findall(text or ""))


def facts_preserved(original: str, rewritten: str) -> bool:
    needed = facts_in(original)
    return True if not needed else needed <= facts_in(rewritten)


def cache_key(*, seed: int, party_id: str | None, week: int, kind: str,
              subject: str, body: str, model: str, temperature: float) -> str:
    raw = "|".join([str(seed), party_id or "", str(week), kind, subject, body,
                    model, f"{temperature:.3f}"])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class Voice:
    def __init__(self, mode: str = "template", model: str | None = None,
                 temperature: float = 0.6, replay_path: str | None = None,
                 transcript_path: str | None = None, seed: int = 0):
        if mode not in ("template", "llm", "replay"):
            raise ValueError("voice mode must be template, llm or replay")
        self.mode = mode
        self.model = model or DEFAULT_MODEL
        self.temperature = float(temperature)
        self.seed = int(seed)
        self.transcripts: list[dict[str, Any]] = []
        self.cost_usd = 0.0
        self.replay: dict[str, dict[str, Any]] = {}
        self.transcript_path = Path(transcript_path) if transcript_path else None
        if replay_path:
            self.load_replay(replay_path)

    @classmethod
    def from_scenario(cls, sc: Any) -> Voice:
        cp = sc.counterparties
        mode = cp.voice or sc.voice or "template"
        return cls(mode=mode, model=cp.model, temperature=cp.temperature,
                   replay_path=cp.replay_path, transcript_path=cp.transcript_path,
                   seed=sc.master_seed)

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
            key = row.get("cache_key")
            if key:
                self.replay[key] = row

    def dump_transcripts(self, path: str | Path | None = None) -> Path | None:
        dest = Path(path) if path else self.transcript_path
        if dest is None:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(json.dumps(row, sort_keys=True) for row in self.transcripts) +
                        ("\n" if self.transcripts else ""))
        return dest

    def phrase(self, sender: str, subject: str, body: str, *, party: dict[str, Any] | None = None,
               week: int = 0, kind: str = "info", history: list[dict[str, Any]] | None = None) -> str:
        """Return phrased body. Subject is never rewritten (agents match on it in tests/UI)."""
        if kind == "system" or self.mode == "template":
            self._log(sender, subject, body, body, party, week, kind, "template", fallback=False)
            return body
        key = cache_key(seed=self.seed, party_id=(party or {}).get("id"), week=week,
                        kind=kind, subject=subject, body=body,
                        model=self.model, temperature=self.temperature)
        cached = self.replay.get(key)
        if cached and cached.get("response"):
            text = cached["response"]
            self._log(sender, subject, body, text, party, week, kind, "replay",
                      fallback=False, cache_key=key, prompt=cached.get("prompt"))
            return text
        if self.mode == "replay":
            self._log(sender, subject, body, body, party, week, kind, "replay",
                      fallback=True, cache_key=key)
            return body
        text, err, usage_cost, prompt = self._rewrite(sender, subject, body, party, history)
        fallback = True
        used = body
        if text and facts_preserved(body, text):
            used, fallback = text, False
        elif text and not facts_preserved(body, text):
            err = (err or "") + " rewrite dropped authored facts; kept template"
        self.cost_usd += float(usage_cost or 0.0)
        self._log(sender, subject, body, used, party, week, kind, "llm",
                  fallback=fallback, cache_key=key, error=err, prompt=prompt,
                  cost_usd=float(usage_cost or 0.0))
        return used

    def _rewrite(self, sender: str, subject: str, body: str, party: dict[str, Any] | None,
                 history: list[dict[str, Any]] | None) -> tuple[str | None, str | None, float, list]:
        persona = (party or {}).get("personality") or f"You are {sender}."
        hist = ""
        if history:
            lines = [f"- week {h.get('week')}: {h.get('kind')} — {h.get('text')}" for h in history[-6:]]
            hist = "Recent history with this operator:\n" + "\n".join(lines)
        prompt = [
            {"role": "system", "content": (
                "Rewrite this business email in the voice of its sender. "
                "Keep every number, dollar amount, date, percent, id and instruction exactly; "
                "add no new facts, offers or terms. Plain text, under 180 words."
            )},
            {"role": "user", "content": (
                f"From: {sender}\nPersonality: {persona}\n{hist}\n"
                f"Subject: {subject}\n\n{body}"
            )},
        ]
        try:
            from plural import Client

            resp = Client().chat(
                model=self.model, max_tokens=320, temperature=self.temperature,
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
                return text.strip(), None, cost, prompt
            return None, "empty model response", cost, prompt
        except Exception as exc:  # noqa: BLE001 - any failure falls back to the template
            return None, f"{type(exc).__name__}: {exc}", 0.0, prompt

    def _log(self, sender, subject, original, response, party, week, kind, mode,
             fallback, cache_key=None, error=None, prompt=None, cost_usd=0.0) -> None:
        row = {
            "cache_key": cache_key or "",
            "week": week,
            "party_id": (party or {}).get("id"),
            "sender": sender,
            "kind": kind,
            "subject": subject,
            "original": original,
            "response": response,
            "mode": mode,
            "model": self.model if mode == "llm" else None,
            "fallback": fallback,
            "error": error,
            "prompt": prompt,
            "cost_usd": cost_usd,
        }
        self.transcripts.append(row)
        if self.transcript_path:
            self.transcript_path.parent.mkdir(parents=True, exist_ok=True)
            with self.transcript_path.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")


# Back-compat function used by older call sites.
MODEL = DEFAULT_MODEL


def rewrite(sender: str, subject: str, body: str) -> str:
    return Voice(mode="llm", model=MODEL).phrase(sender, subject, body)
