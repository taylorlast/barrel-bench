import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "environments" / "barrel", ROOT / "harnesses" / "distillery-operator",
          ROOT / "verifiers" / "enterprise-value", ROOT / "tests"):
    sys.path.insert(0, str(p))


import os

# Keep counterparties on the labeled rule-based fallback during the suite so a
# present Plural key cannot change economic outcomes. Tests that want an LLM
# set counterparties.mode to "llm" explicitly and inject a mock chat_fn.
os.environ.setdefault("BARREL_FORCE_RULE", "1")
