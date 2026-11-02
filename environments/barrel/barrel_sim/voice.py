"""Counterparty voice. Every number in an email comes from the World; voice only phrases it.

``template`` (default) keeps emails deterministic for reproducible offline runs.
``llm`` asks a model through Plural's gateway to rewrite the email in the sender's voice,
falling back to the template on any error. The model sees only the public email text, never
hidden truth, so it cannot leak quality or true ages.
"""

from __future__ import annotations

import os

MODEL = os.environ.get("BARREL_VOICE_MODEL", "openai/gpt-5.6-luna")


def rewrite(sender: str, subject: str, body: str) -> str:
    try:
        from plural import Client

        resp = Client().chat(
            model=MODEL, max_tokens=300, temperature=0.6, write_trace=False,
            messages=[{"role": "system", "content": "Rewrite this business email in the voice of its sender. Keep "
                       "every number, date, id and instruction exactly; add no new facts. Plain text, under 150 words."},
                      {"role": "user", "content": f"From: {sender}\nSubject: {subject}\n\n{body}"}])
        text = getattr(resp, "content", None) or getattr(getattr(resp, "message", None), "content", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:  # noqa: BLE001 - any failure falls back to the template
        pass
    return body
