"""distillery-operator context strategies with the mock model, plus project validation."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from barrel_sim import Refused, Scenario, World
from barrel_sim import report as R
from harness import DistilleryOperatorHarness
from mock_model import MockModel

ROOT = Path(__file__).resolve().parents[1]


class FakeEnv:
    """A minimal HarnessEnvironment over a World (briefing, list_emails, bottle, end_week)."""
    overview = "test"

    def __init__(self):
        self.w = World(Scenario.from_dict({"master_seed": 1, "horizon_years": 1}))
        self.calls = []

    def tools(self):
        return [{"type": "function", "function": {"name": n, "description": n, "parameters": {"type": "object"}}}
                for n in ("briefing", "list_emails", "bottle", "end_week")]

    def reset(self):
        return R.briefing(self.w)

    def step(self, name, **args):
        self.calls.append(name)
        try:
            obs = {"briefing": lambda: R.briefing(self.w), "list_emails": lambda: R.inbox(self.w),
                   "bottle": lambda: self.w.bottle(args.get("lot_id", "x"), "x", 1),
                   "end_week": lambda: self.w.end_week(int(args.get("weeks", 1)))}[name]()
            return SimpleNamespace(observation=obs, info={}, done=self.w.done)
        except Refused as e:
            return SimpleNamespace(observation=None, info={"error": str(e)}, done=False)


def run(context, **cfg):
    h = DistilleryOperatorHarness()
    env = FakeEnv()
    agent = SimpleNamespace(instructions="run it",
                            harness_config={"model_client": "mock", "context": context, **cfg})
    task = SimpleNamespace(instructions="do well")
    res = h.run(task, agent, env)
    return res, env


@pytest.mark.parametrize("context", ["notebook", "summary", "window"])
def test_context_strategies_play_to_the_end(context):
    res, env = run(context, summarize_at_chars=4000, window_messages=8)
    t = res.trajectory[0]
    assert env.w.done and res.metadata["stop_reason"] == "environment_done"
    assert t["refused"] > 0  # the mock's bad bottle call came back as feedback
    assert (t["notebook"] != {}) == (context == "notebook")


def test_unknown_context_rejected():
    with pytest.raises(ValueError):
        run("telepathy")


def test_window_context_is_bounded():
    seen = []
    orig = MockModel.complete

    def spy(self, messages, **kw):
        seen.append(len(messages))
        return orig(self, messages, **kw)
    MockModel.complete = spy
    try:
        run("window", window_messages=6, max_model_turns=40)
    finally:
        MockModel.complete = orig
    assert max(seen) <= 7


def _plural():
    exe = shutil.which("plural") or str(Path(sys.executable).parent / "plural")
    return exe if os.path.exists(exe) else None


@pytest.mark.skipif(_plural() is None, reason="plural CLI not installed")
@pytest.mark.parametrize("kind,name", [("env", "barrel"), ("harness", "distillery-operator"),
                                       ("verifier", "enterprise-value"), ("benchmark", "barrel"),
                                       ("benchmark", "barrel-dev"), ("agent", "mock-operator")])
def test_plural_validate(kind, name):
    r = subprocess.run([_plural(), kind, "validate", name], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "is valid" in r.stdout, r.stdout + r.stderr
