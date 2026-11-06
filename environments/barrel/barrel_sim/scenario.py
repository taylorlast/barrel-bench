"""Scenario config: master seed, presets, per-factor overrides and scheduled shocks.

Every exogenous factor draws from its own stream, ``Random(f"{master_seed}|{factor}|{seed}")``,
so changing one factor's seed, volatility or enable flag never reshuffles another factor.
Counterparties draw from a separate stream, ``Random(f"{master_seed}|parties|{seed}")``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

FACTORS = ("corn", "energy", "weather", "demand", "bulk_market", "interest", "cooperage", "glass",
           "regulatory", "tariffs", "distributor", "equipment", "contamination", "fire", "celebrity",
           "labor", "tourism")

SHOCKS = ("warehouse_fire", "government_shutdown", "demand_regime", "corn_spike", "energy_spike",
          "cooperage_shortage", "glass_shortage", "tariff", "distributor_consolidation",
          "celebrity_launch", "rate_hike", "still_failure", "contamination", "heat_wave", "key_staff_quit")

PRESETS: dict[str, dict[str, Any]] = {
    "calm": {"volatility": 0.5, "event_rate": 0.3, "start_regime": "normal"},
    "realistic": {"volatility": 1.0, "event_rate": 1.0, "start_regime": "soft"},
    "volatile": {"volatility": 1.6, "event_rate": 2.0, "start_regime": "soft"},
    "crisis": {"volatility": 1.3, "event_rate": 1.5, "start_regime": "glut",
               "shocks": [
                   {"week": 20, "event": "government_shutdown", "weeks": 6},
                   {"week": 60, "event": "cooperage_shortage", "weeks": 20},
                   {"week": 90, "event": "rate_hike", "bp": 200},
                   {"week": 140, "event": "tariff", "rate": 0.5, "weeks": 80},
                   {"week": 170, "event": "warehouse_fire", "share": 0.25},
                   {"week": 220, "event": "distributor_consolidation"},
               ]},
}

MAX_WEEKS = 600  # paths are always generated this long, so the horizon never reshuffles draws


@dataclass
class FactorConfig:
    enabled: bool = True
    volatility: float = 1.0
    event_rate: float = 1.0
    seed: int | str | None = None
    extra: dict[str, Any] = field(default_factory=dict)



CP_KEYS = ("seed", "voice", "model", "models", "mode", "temperature", "replay_path",
           "transcript_path", "inbound_rate", "churn_rate", "populations", "temperament")
CP_MODES = ("auto", "llm", "rule", "replay")


@dataclass
class CounterpartyConfig:
    """Knobs for the procedural counterparty market. Independent of the 17 factor streams."""
    seed: int | str | None = None
    voice: str = "template"
    model: str | None = None
    models: dict[str, str] = field(default_factory=dict)
    mode: str = "auto"
    temperature: float = 0.6
    replay_path: str | None = None
    transcript_path: str | None = None
    inbound_rate: float = 1.0
    churn_rate: float = 1.0
    populations: dict[str, Any] = field(default_factory=dict)
    temperament: dict[str, float] = field(default_factory=dict)


def _parse_counterparties(raw: dict[str, Any], *, default_voice: str) -> CounterpartyConfig:
    bad = set(raw) - set(CP_KEYS)
    if bad:
        raise ValueError(f"unknown counterparties keys: {sorted(bad)}; known: {', '.join(CP_KEYS)}")
    voice = str(raw.get("voice", default_voice))
    if voice not in ("template", "llm", "replay"):
        raise ValueError("counterparties.voice must be 'template', 'llm' or 'replay'")
    mode = str(raw.get("mode", "auto")).strip().lower()
    if mode not in CP_MODES:
        raise ValueError("counterparties.mode must be 'auto', 'llm', 'rule' or 'replay'")
    models = dict(raw.get("models") or {})
    for role, mid in models.items():
        if not isinstance(role, str) or not isinstance(mid, str) or not mid.strip():
            raise ValueError(f"counterparties.models.{role} must be a model id string")
    temp = float(raw.get("temperature", 0.6))
    if not 0.0 <= temp <= 1.5:
        raise ValueError("counterparties.temperature must be 0-1.5")
    pops = dict(raw.get("populations") or {})
    for name, spec in pops.items():
        if not isinstance(spec, dict):
            raise ValueError(f"counterparties.populations.{name} must be a mapping of min/max")
    temper = dict(raw.get("temperament") or {})
    for k, v in temper.items():
        try:
            float(v)
        except (TypeError, ValueError):
            raise ValueError(f"counterparties.temperament.{k} must be a number") from None
    return CounterpartyConfig(
        seed=raw.get("seed"), voice=voice, model=raw.get("model"),
        models=models, mode=mode,
        temperature=temp, replay_path=raw.get("replay_path"),
        transcript_path=raw.get("transcript_path"),
        inbound_rate=float(raw.get("inbound_rate", 1.0)),
        churn_rate=float(raw.get("churn_rate", 1.0)),
        populations=pops, temperament=temper,
    )


@dataclass
class Scenario:
    master_seed: int = 0
    preset: str = "realistic"
    horizon_years: float = 7.0
    start_regime: str = "soft"
    seed_capital: float = 2_000_000.0
    target_moic: float = 3.0
    voice: str = "template"
    counterparties: CounterpartyConfig = field(default_factory=lambda: CounterpartyConfig())
    factors: dict[str, FactorConfig] = field(default_factory=dict)
    shocks: list[dict[str, Any]] = field(default_factory=list)

    def party_stream_key(self) -> str:
        s = self.counterparties.seed
        return f"{self.master_seed}|parties|{'' if s is None else s}"

    @property
    def horizon_weeks(self) -> int:
        return max(4, min(MAX_WEEKS - 10, int(round(self.horizon_years * 52))))

    def factor(self, name: str) -> FactorConfig:
        return self.factors[name]

    def stream_key(self, name: str) -> str:
        f = self.factors[name]
        return f"{self.master_seed}|{name}|{'' if f.seed is None else f.seed}"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, default_seed: int = 0) -> Scenario:
        data = copy.deepcopy(dict(data or {}))
        preset = str(data.get("preset", "realistic"))
        if preset not in PRESETS:
            raise ValueError(f"scenario.preset must be one of {sorted(PRESETS)}")
        p = PRESETS[preset]
        unknown = set(data) - {"preset", "master_seed", "seed", "horizon_years", "start_regime", "factors",
                               "shocks", "seed_capital", "target_moic", "voice", "counterparties"}
        if unknown:
            raise ValueError(f"unknown scenario keys: {sorted(unknown)}")
        seed = data.get("master_seed", data.get("seed", default_seed))
        sc = cls(master_seed=int(seed), preset=preset,
                 horizon_years=float(data.get("horizon_years", 7.0)),
                 start_regime=str(data.get("start_regime", p["start_regime"])),
                 seed_capital=float(data.get("seed_capital", 2_000_000.0)),
                 target_moic=float(data.get("target_moic", 3.0)),
                 voice=str(data.get("voice", "template")))
        if sc.voice not in ("template", "llm", "replay"):
            raise ValueError("scenario.voice must be 'template', 'llm' or 'replay'")
        sc.counterparties = _parse_counterparties(data.get("counterparties") or {}, default_voice=sc.voice)
        sc.voice = sc.counterparties.voice
        overrides = data.get("factors") or {}
        bad = set(overrides) - set(FACTORS)
        if bad:
            raise ValueError(f"unknown factors {sorted(bad)}; known: {', '.join(FACTORS)}")
        for name in FACTORS:
            o = dict(overrides.get(name) or {})
            fc = FactorConfig(enabled=bool(o.pop("enabled", True)),
                              volatility=float(o.pop("volatility", p["volatility"])),
                              event_rate=float(o.pop("event_rate", p["event_rate"])),
                              seed=o.pop("seed", None), extra=o)
            sc.factors[name] = fc
        if "start_regime" in (overrides.get("demand") or {}):
            sc.start_regime = str(overrides["demand"]["start_regime"])
        if sc.start_regime not in ("boom", "normal", "soft", "glut"):
            raise ValueError("start_regime must be boom, normal, soft or glut")
        shocks = list(p.get("shocks", [])) + list(data.get("shocks") or [])
        for s in shocks:
            if s.get("event") not in SHOCKS:
                raise ValueError(f"unknown shock {s.get('event')!r}; known: {', '.join(SHOCKS)}")
            if not isinstance(s.get("week"), int) or s["week"] < 0:
                raise ValueError("each shock needs an integer week >= 0")
        sc.shocks = sorted(shocks, key=lambda s: s["week"])
        return sc

    def summary(self) -> dict[str, Any]:
        return {"preset": self.preset, "master_seed": self.master_seed, "horizon_weeks": self.horizon_weeks,
                "start_regime": self.start_regime,
                "disabled": [k for k, f in self.factors.items() if not f.enabled],
                "shocks": len(self.shocks),
                "voice": self.voice,
                "counterparties_seed": self.counterparties.seed,
                "inbound_rate": self.counterparties.inbound_rate,
                "churn_rate": self.counterparties.churn_rate}
