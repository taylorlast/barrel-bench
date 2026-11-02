"""A Harness that plays a scripted Barrel policy (config.policy) through Environment actions."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from plural import Harness, HarnessResult

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
from playbook import POLICIES  # noqa: E402  (vendored copy of barrel_sim/playbook.py)


_APP_ARGS = {"batch": "batch_id", "offer": "offer_id"}


def _error_text(observation: Any) -> str | None:
    if isinstance(observation, dict) and observation.get("error"):
        return str(observation["error"])
    return None


class BarrelScriptedHarness(Harness):
    auth = ("none",)
    readme = "README.md"

    def run(self, task, agent, environment):
        """Play 40 quarters with the configured policy using JSON tool output."""
        name = str(self.config.get("policy", "baseline"))
        policy = POLICIES[name]
        environment.reset()
        steps = errors = 0

        def call(action: str, **kw: Any) -> Any:
            nonlocal steps, errors
            # The vendored playbook speaks the sim's argument names; the App's tools use *_id.
            kw = {_APP_ARGS.get(k, k): v for k, v in kw.items()}
            if action not in ("write_note", "read_notes"):
                kw = {**kw, "fmt": "json"}
            try:
                step = environment.step(action, **kw)
            except RuntimeError as exc:  # an action the App refused
                errors += 1
                raise ValueError(str(exc)) from None
            steps += 1
            obs = step.observation
            if isinstance(obs, str):
                try:
                    obs = json.loads(obs)
                except json.JSONDecodeError:
                    pass
            # A refused action comes back as observation None with info["error"].
            err = (step.info or {}).get("error") or _error_text(obs)
            if err:
                errors += 1
                raise ValueError(err)
            return obs

        for _ in range(40):
            if call("brief").get("done"):
                break
            policy(call)
        final = call("brief")
        return HarnessResult(
            response=f"[{name}] played to quarter {final.get('quarter')} (done={final.get('done')}); "
            f"{steps} actions, {errors} refused.",
            trajectory=({"type": "summary", "policy": name, "steps": steps, "refused": errors},),
            metadata={"stop_reason": "agent_response"},
        )
