"""Broker and distributor voices. Numbers always come from the Sim; voices only phrase them.

``scripted`` (default) is deterministic templates, so offline runs are reproducible.
``llm`` asks a model (through Plural's gateway) to write the broker's pitch in
character, falling back to the template on any error. The model never sees hidden
truth (honesty, true age), only the public offer, so it cannot leak the answer.
"""

from __future__ import annotations

import random
from typing import Any

OPENERS = ("Got a parcel you'll want to see.", "Quick one before this goes to the bigger houses.",
           "Clearing some space in our rickhouse.", "Estate lot, motivated seller.")


def scripted_pitch(seed: int, offer: dict[str, Any]) -> str:
    r = random.Random(f"{seed}|pitch|{offer['id']}")
    return (f"{offer['seller']}: \"{r.choice(OPENERS)} {offer['casks']} barrels, {offer['stated_age']} years, "
            f"{offer['stated_grade']} grade. ${offer['ask']:,} for the lot.\"")


def llm_pitch(seed: int, offer: dict[str, Any], model: str = "openai/gpt-5.6-luna") -> str:
    try:
        from plural import Client

        resp = Client().chat(
            model=model, max_tokens=120, temperature=0.7, write_trace=False,
            messages=[{"role": "system", "content": "You are a bulk whiskey cask broker. Write a two-sentence "
                       "pitch in character. Use exactly the numbers given; invent no facts about age or quality."},
                      {"role": "user", "content": str({k: offer[k] for k in
                                                       ("seller", "casks", "stated_age", "stated_grade", "ask")})}],
        )
        text = getattr(resp, "content", None) or getattr(getattr(resp, "message", None), "content", None)
        if isinstance(text, str) and text.strip():
            return f"{offer['seller']}: \"{text.strip()}\""
    except Exception:  # noqa: BLE001 - any failure falls back to the deterministic voice
        pass
    return scripted_pitch(seed, offer)


def pitch(voice: str, seed: int, offer: dict[str, Any]) -> str:
    return llm_pitch(seed, offer) if voice == "llm" else scripted_pitch(seed, offer)
