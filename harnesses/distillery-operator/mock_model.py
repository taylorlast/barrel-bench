"""A deterministic stand-in model for smoke tests ONLY. It is not an evaluated Agent.

It exercises the Harness plumbing: read the briefing, write a note, occasionally make a
malformed call, then close the week. It makes no business decisions worth scoring.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace
from typing import Any


class MockModel:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        self.n = 0

    def complete(self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None = None, **_: Any):
        self.n += 1
        if not tools:
            return SimpleNamespace(text="Summary: nothing decided yet.", tool_calls=(), usage={"total_tokens": 10})
        names = {t["function"]["name"] for t in tools}
        calls = []
        if self.n % 3 == 1:
            calls.append(("briefing", {}))
            if "notebook_write" in names:
                calls.append(("notebook_write", {"key": "plan", "text": f"turn {self.n}: watching cash"}))
        elif self.n % 3 == 2:
            calls.append(("list_emails", {}) if "list_emails" in names else ("briefing", {}))
            calls.append(("bottle", {"lot_id": "nope"}) if "bottle" in names else ("briefing", {}))
        else:
            calls.append(("end_week", {"weeks": self.rng.choice([1, 2, 4])}))
        tc = tuple({"id": f"c{self.n}_{i}", "type": "function",
                    "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls) if n in names)
        return SimpleNamespace(text="", tool_calls=tc, usage={"total_tokens": 50})
