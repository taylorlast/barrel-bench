"""A model-driven Harness for long Barrel episodes with pluggable context management.

Nothing here decides for the Agent: every Environment action comes from the model's tool
calls. The Harness only decides what the model sees each turn (config ``context``):

- ``window``   system prompt + the last ``window_messages`` messages (cut on turn bounds).
- ``summary``  full history until it passes ``summarize_at_chars``, then the model itself
               writes a running summary that replaces the old turns.
- ``notebook`` each simulated week starts a fresh context: system prompt, the Agent's own
               notebook (notebook_write/read/delete), and the new briefing. Turns within a
               week are kept. This is how a real operator works: notes, inbox, calendar.

With ``briefing: true`` the Harness inserts the office briefing after every week closes.
``model_client: mock`` swaps in tests' MockModel (no key, no gateway) for smoke runs only.
"""

from __future__ import annotations

import json
import time
from typing import Any

from plural import Harness, HarnessResult

DEFAULTS: dict[str, Any] = {
    "context": "notebook", "window_messages": 40, "briefing": True, "notebook_max_chars": 12000,
    "summarize_at_chars": 60000, "max_observation_chars": 6000, "max_idle_replies": 3,
    "max_model_turns": None, "temperature": None, "max_tokens": None, "model_client": "agent",
}

NOTEBOOK_TOOLS = [
    {"type": "function", "function": {"name": "notebook_write", "description":
        "Save or overwrite a note under a key (plans, commitments, prices, who owes what). "
        "Notes persist across weeks; in notebook mode they are the only memory you keep.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
                       "required": ["key", "text"]}}},
    {"type": "function", "function": {"name": "notebook_read", "description": "Read all notes, or one key.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "notebook_delete", "description": "Delete a note.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
]

STRATEGY_TEXT = {
    "notebook": "Your context is reset every simulated week. Only your notebook (notebook_* tools), "
                "the inbox and the briefing carry over, so write down plans and commitments.",
    "summary": "Older turns are periodically replaced with a summary you write.",
    "window": "You only see your most recent messages; use reminders and the inbox to remember.",
}


def _dump(obj: Any, limit: int) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, default=str, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit] + f"... [truncated {len(text) - limit} chars]"


def _chars(msgs: list[dict[str, Any]]) -> int:
    return sum(len(str(m.get("content") or "")) + len(json.dumps(m.get("tool_calls") or [])) for m in msgs)


class Notebook:
    def __init__(self, max_chars: int) -> None:
        self.notes: dict[str, str] = {}
        self.max_chars = max_chars

    def text(self) -> str:
        return "\n".join(f"## {k}\n{v}" for k, v in self.notes.items()) or "(empty)"

    def call(self, name: str, args: dict[str, Any]) -> str:
        key = str(args.get("key") or "")
        if name == "notebook_write":
            old = self.notes.get(key)
            self.notes[key] = str(args.get("text") or "")
            if len(self.text()) > self.max_chars:
                if old is None:
                    del self.notes[key]
                else:
                    self.notes[key] = old
                return f"Refused: notebook would exceed {self.max_chars} chars; delete or shorten notes."
            return f"Saved '{key}' ({len(self.text())}/{self.max_chars} chars used)."
        if name == "notebook_read":
            return self.notes.get(key, f"(no note '{key}')") if key else self.text()
        self.notes.pop(key, None)
        return f"Deleted '{key}'."


class DistilleryOperatorHarness(Harness):
    auth = ("none",)
    readme = "README.md"

    def _client(self, agent: Any, cfg: dict[str, Any]) -> Any:
        if cfg["model_client"] == "mock":
            from mock_model import MockModel  # type: ignore[import-not-found]
            return MockModel(seed=int(cfg.get("mock_seed", 0)))
        return agent

    def run(self, task, agent, environment):
        cfg = {**DEFAULTS, **(self.config or {}), **(getattr(agent, "harness_config", {}) or {})}
        if cfg["model_client"] == "mock":
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent))
        client = self._client(agent, cfg)
        mode = str(cfg["context"])
        if mode not in STRATEGY_TEXT:
            raise ValueError(f"context must be one of {sorted(STRATEGY_TEXT)}, got {mode!r}")
        limit = int(cfg["max_observation_chars"])
        notebook = Notebook(int(cfg["notebook_max_chars"]))
        env_tools = environment.tools()
        names = {t["function"]["name"] for t in env_tools}
        tools = env_tools + (NOTEBOOK_TOOLS if mode == "notebook" else [])
        system = "\n\n".join(x for x in [
            agent.instructions, task.instructions,
            f"Environment overview: {environment.overview}" if environment.overview else "",
            "Each tool call is a real business action with consequences. Advance time with end_week. "
            + STRATEGY_TEXT[mode]] if x)
        first = environment.reset()
        history: list[dict[str, Any]] = [{"role": "user", "content": "Day one.\n" + _dump(first, limit)}]
        if cfg["briefing"] and "briefing" in names:
            history.append({"role": "user", "content": "Briefing: " + _dump(environment.step("briefing").observation, limit)})
        summary = ""
        opts = {k: cfg[k] for k in ("temperature", "max_tokens") if cfg[k] is not None}
        turns = idle = actions = refused = weeks_closed = 0
        done = False
        stop = "agent_response"
        usage_tokens = 0
        t0 = time.monotonic()

        def context() -> list[dict[str, Any]]:
            sys_msg = {"role": "system", "content": system}
            if mode == "window":
                tail = history[-int(cfg["window_messages"]):]
                while tail and tail[0].get("role") == "tool":
                    tail = tail[1:]
                return [sys_msg] + tail
            if mode == "summary":
                pre = [{"role": "user", "content": "Summary of earlier play:\n" + summary}] if summary else []
                return [sys_msg] + pre + history
            return [sys_msg, {"role": "user", "content": "Your notebook:\n" + notebook.text()}] + history

        while not done:
            if cfg["max_model_turns"] is not None and turns >= int(cfg["max_model_turns"]):
                stop = "max_model_turns"
                break
            if mode == "summary" and _chars(history) > int(cfg["summarize_at_chars"]):
                req = context() + [{"role": "user", "content": "Write a dense summary of everything you need "
                                    "to keep running the business: commitments, deadlines, plans, numbers."}]
                summary = client.complete(req, **opts).text[: int(cfg["summarize_at_chars"]) // 4]
                history = history[-2:] if history and history[-1].get("role") != "tool" else []
                while history and history[0].get("role") == "tool":
                    history = history[1:]
            reply = client.complete(context(), tools=tools, **opts)
            turns += 1
            usage_tokens += int((reply.usage or {}).get("total_tokens") or 0)
            msg: dict[str, Any] = {"role": "assistant", "content": reply.text or ""}
            if reply.tool_calls:
                msg["tool_calls"] = list(reply.tool_calls)
            history.append(msg)
            if not reply.tool_calls:
                idle += 1
                if idle > int(cfg["max_idle_replies"]):
                    stop = "idle"
                    break
                history.append({"role": "user", "content": "The business keeps running. Act with tools; "
                                "call end_week when this week's work is done."})
                continue
            idle = 0
            new_week = False
            for call in reply.tool_calls:
                fn = call.get("function") or {}
                name = str(fn.get("name") or "")
                try:
                    args = json.loads(fn.get("arguments") or "{}") if isinstance(fn.get("arguments"), str) else dict(fn.get("arguments") or {})
                except json.JSONDecodeError as exc:
                    args, out = None, f"Error: arguments were not valid JSON ({exc})."
                if args is not None:
                    if name.startswith("notebook_") and mode == "notebook":
                        out = notebook.call(name, args)
                    elif name not in names:
                        out = f"Error: unknown tool {name!r}."
                    elif done:
                        out = "Error: the episode has ended."
                    else:
                        try:
                            step = environment.step(name, **args)
                            err = (step.info or {}).get("error")
                            out = f"Refused: {err}" if err else _dump(step.observation, limit)
                            refused += bool(err)
                            actions += 1
                            done = step.done
                            if name == "end_week" and not err:
                                new_week, weeks_closed = True, weeks_closed + 1
                        except (RuntimeError, ValueError, TypeError) as exc:
                            refused += 1
                            out = f"Refused: {exc}"
                history.append({"role": "tool", "tool_call_id": call.get("id") or name, "content": out})
            if new_week and not done:
                if mode == "notebook":
                    history = []
                if cfg["briefing"] and "briefing" in names:
                    history.append({"role": "user", "content": "New week. Briefing: "
                                    + _dump(environment.step("briefing").observation, limit)})
        if done:
            stop = "environment_done"
        return HarnessResult(
            response=f"[{mode}] {turns} model turns, {actions} actions ({refused} refused), "
                     f"{weeks_closed} end_week calls; stop={stop}.",
            trajectory=({"type": "summary", "context": mode, "model_turns": turns, "actions": actions,
                         "refused": refused, "weeks_closed_calls": weeks_closed, "tokens": usage_tokens,
                         "seconds": round(time.monotonic() - t0, 1), "notebook": notebook.notes},),
            metadata={"stop_reason": stop},
        )
