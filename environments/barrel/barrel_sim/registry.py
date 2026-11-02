"""Shared-world registry.

Plural Apps cannot call each other or share State, but AppHost resets every App of one
Environment sequentially in one process. The ``office`` App (listed first) builds the
World and publishes it here; every other App attaches to the current World on reset.
See README "SDK friction".
"""

from __future__ import annotations

from .world import World

_current: World | None = None


def publish(world: World) -> None:
    global _current
    _current = world


def current() -> World:
    if _current is None:
        raise RuntimeError("No world: the 'office' App must be listed first and reset before the others.")
    return _current
