"""Shared exceptions and tiny helpers (kept out of world.py to avoid circular imports)."""


class Refused(ValueError):
    """An action the world refuses (shown to the Agent as feedback)."""


def money(x: float, n: int = 2) -> float:
    return round(float(x), n)
