import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "environments" / "barrel", ROOT / "harnesses" / "distillery-operator",
          ROOT / "verifiers" / "enterprise-value", ROOT / "tests"):
    sys.path.insert(0, str(p))
