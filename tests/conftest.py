import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "environments" / "barrel"))
sys.path.insert(0, str(ROOT / "verifiers" / "distillery-outcome"))
sys.path.insert(0, str(ROOT / "harnesses" / "barrel-scripted"))
