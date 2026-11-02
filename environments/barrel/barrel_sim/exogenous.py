"""Exogenous factor paths, one independent RNG stream per factor.

Each generator draws a fixed number of values in a fixed order for MAX_WEEKS, from its own
``random.Random``. A disabled factor still consumes nothing from anyone else's stream and
returns its mean path. Scheduled shocks are layered on afterwards and consume no randomness.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from .scenario import MAX_WEEKS, Scenario

N = MAX_WEEKS
REGIMES = {"boom": 1.18, "normal": 1.0, "soft": 0.88, "glut": 0.76}
REGIME_ORDER = ("glut", "soft", "normal", "boom")


def _season(week: int) -> float:
    return math.sin(2 * math.pi * ((week % 52) - 15) / 52)


def _poisson_events(r: random.Random, rate_per_year: float, n: int = N) -> list[int]:
    p = min(0.5, rate_per_year / 52)
    return [w for w in range(n) if r.random() < p]


@dataclass
class Paths:
    corn: list[float] = field(default_factory=list)          # $/bushel
    energy: list[float] = field(default_factory=list)        # index ~1
    temp_f: list[float] = field(default_factory=list)        # rickhouse mid-floor deg F
    humidity: list[float] = field(default_factory=list)      # %
    demand: list[float] = field(default_factory=list)        # category index ~1
    regime: list[str] = field(default_factory=list)
    consumer_noise: list[float] = field(default_factory=list)
    bulk_new_fill: list[float] = field(default_factory=list)  # $/barrel new fill
    prime: list[float] = field(default_factory=list)         # annual rate
    cooperage_index: list[float] = field(default_factory=list)
    cooperage_lead: list[int] = field(default_factory=list)  # weeks for an order placed this week
    glass_index: list[float] = field(default_factory=list)
    glass_lead: list[int] = field(default_factory=list)
    dsp_days: list[float] = field(default_factory=list)
    state_days: list[float] = field(default_factory=list)
    cola_days: list[float] = field(default_factory=list)
    bank_days: list[float] = field(default_factory=list)
    shutdown: list[bool] = field(default_factory=list)
    inspection_u: list[float] = field(default_factory=list)
    export_tariff: list[float] = field(default_factory=list)
    consolidation_weeks: list[int] = field(default_factory=list)
    consolidation_u: list[float] = field(default_factory=list)
    equip_u: list[float] = field(default_factory=list)
    equip_sev: list[float] = field(default_factory=list)
    contam_u: list[float] = field(default_factory=list)
    fire_u: list[float] = field(default_factory=list)
    fire_share: list[float] = field(default_factory=list)
    celebrity: list[float] = field(default_factory=list)     # share of your tier taken (0..)
    labor_quit_u: list[float] = field(default_factory=list)
    labor_pool: list[float] = field(default_factory=list)    # candidate skill mean shift
    tourism: list[float] = field(default_factory=list)
    news: list[tuple[int, str, str]] = field(default_factory=list)  # (week, factor, headline)
    forced: dict[str, list[int]] = field(default_factory=dict)      # scheduled one-off events

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def _ou_log(r, mu, sigma, k, vol, enabled, start=None):
    x = math.log(start or mu)
    out = []
    for _ in range(N):
        e = r.gauss(0, 1)
        if enabled:
            x += k * (math.log(mu) - x) + sigma * vol * e
        out.append(math.exp(x) if enabled else mu)
    return out


def generate(sc: Scenario) -> Paths:
    P = Paths()
    R = {name: random.Random(sc.stream_key(name)) for name in sc.factors}
    f = sc.factors

    c = f["corn"]
    P.corn = _ou_log(R["corn"], c.extra.get("mean", 4.40), 0.035, 0.02, c.volatility, c.enabled)
    e = f["energy"]
    P.energy = _ou_log(R["energy"], 1.0, 0.03, 0.03, e.volatility, e.enabled)

    w = f["weather"]; r = R["weather"]
    ar = 0.0
    heat = _poisson_events(r, 1.2 * w.event_rate)
    hum_noise = 0.0
    for t in range(N):
        a, b = r.gauss(0, 1), r.gauss(0, 1)
        ar = 0.7 * ar + 3.0 * w.volatility * a
        hum_noise = 0.7 * hum_noise + 4.0 * w.volatility * b
        base = 57 + 24 * _season(t)
        P.temp_f.append(base + (ar if w.enabled else 0.0))
        P.humidity.append(66 + 8 * _season(t + 6) + (hum_noise if w.enabled else 0.0))
    if w.enabled:
        for t0 in heat:
            if 0 < _season(t0):  # summer half only
                for t in range(t0, min(N, t0 + 3)):
                    P.temp_f[t] += 9
                P.news.append((t0, "weather", "Heat wave bakes Kentucky and Tennessee rickhouses"))

    d = f["demand"]; r = R["demand"]
    idx = REGIME_ORDER.index(sc.start_regime)
    level = REGIMES[sc.start_regime]
    p_switch = min(0.2, 1 / 90 * d.event_rate)
    for t in range(N):
        u, mv, ns = r.random(), r.random(), r.gauss(0, 1)
        if d.enabled and t > 0 and u < p_switch:
            step = 1 if mv < (0.62 if idx < 2 else 0.4) else -1
            new = max(0, min(3, idx + step))
            if new != idx:
                idx = new
                P.news.append((t, "demand", f"Category report: American whiskey moving into a {REGIME_ORDER[idx]} phase"))
        target = REGIMES[REGIME_ORDER[idx]] if d.enabled else 1.0
        level += 0.06 * (target - level)
        P.regime.append(REGIME_ORDER[idx] if d.enabled else "normal")
        P.demand.append(level)
        P.consumer_noise.append(math.exp(0.08 * d.volatility * ns) if d.enabled else 1.0)

    b = f["bulk_market"]; r = R["bulk_market"]
    beta = float(b.extra.get("demand_beta", 0.8))
    x = 0.0
    for t in range(N):
        g = r.gauss(0, 1)
        x = 0.96 * x + 0.03 * b.volatility * g
        lag = P.demand[max(0, t - 26)]
        base = 640 * (lag ** (beta * 2.2))
        P.bulk_new_fill.append(base * math.exp(x) if b.enabled else 640.0)

    i = f["interest"]; r = R["interest"]
    rate = float(i.extra.get("start_prime", 0.0725))
    for t in range(N):
        u, s = r.random(), r.random()
        if i.enabled and t % 6 == 0 and u < 0.25 * i.event_rate:
            rate += 0.0025 * (1 if s < 0.5 else -1) * (2 if i.volatility > 1.4 else 1)
            rate = min(0.12, max(0.03, rate))
        P.prime.append(rate)

    for name, base_lead, price_sigma, short_rate in (("cooperage", 8, 0.02, 0.35), ("glass", 4, 0.015, 0.3)):
        fc = f[name]; r = R[name]
        idxs = _ou_log(r, 1.0, price_sigma, 0.04, fc.volatility, fc.enabled)
        shortage = [0] * N
        for t0 in _poisson_events(r, short_rate * fc.event_rate):
            dur = 8 + int(r.random() * 14)
            if fc.enabled:
                for t in range(t0, min(N, t0 + dur)):
                    shortage[t] = 1
                P.news.append((t0, name, f"{'Cooperages' if name == 'cooperage' else 'Glass plants'} report allocation; lead times stretch"))
        leads = []
        for t in range(N):
            u = r.random()
            jitter = int(u * 4) if fc.enabled else 2
            leads.append(base_lead + jitter + (8 if shortage[t] else 0))
            if shortage[t]:
                idxs[t] *= 1.35
        setattr(P, f"{name}_index", idxs)
        setattr(P, f"{name}_lead", leads)

    g = f["regulatory"]; r = R["regulatory"]
    def lognorm(median, sd):
        return median * math.exp(sd * g.volatility * r.gauss(0, 1)) if g.enabled else median
    for t in range(N):
        P.dsp_days.append(lognorm(47, 0.30))
        P.state_days.append(lognorm(45, 0.35))
        P.cola_days.append(lognorm(6, 0.5))
        P.bank_days.append(lognorm(60, 0.25))
        P.inspection_u.append(r.random())
    P.shutdown = [False] * N
    for t0 in _poisson_events(r, 0.15 * g.event_rate):
        dur = 2 + int(r.random() * 5)
        if g.enabled:
            for t in range(t0, min(N, t0 + dur)):
                P.shutdown[t] = True
            P.news.append((t0, "regulatory", "Federal shutdown: TTB stops processing permits and labels"))

    tf = f["tariffs"]; r = R["tariffs"]
    P.export_tariff = [0.0] * N
    for t0 in _poisson_events(r, 0.25 * tf.event_rate):
        rate_ = 0.25 if r.random() < 0.6 else 0.5
        dur = 26 + int(r.random() * 78)
        if tf.enabled:
            for t in range(t0, min(N, t0 + dur)):
                P.export_tariff[t] = max(P.export_tariff[t], rate_)
            P.news.append((t0, "tariffs", f"Retaliatory {int(rate_ * 100)}% tariff on American whiskey announced"))

    dc = f["distributor"]; r = R["distributor"]
    ev = _poisson_events(r, 0.3 * dc.event_rate)
    P.consolidation_u = [r.random() for _ in range(N)]
    P.consolidation_weeks = ev if dc.enabled else []
    for t0 in P.consolidation_weeks:
        P.news.append((t0, "distributor", "Wholesaler merger announced; suppliers brace for portfolio cuts"))

    for name, attrs in (("equipment", ("equip_u", "equip_sev")), ("contamination", ("contam_u",)),
                        ("fire", ("fire_u", "fire_share")), ("labor", ("labor_quit_u", "labor_pool")),):
        fc = f[name]; r = R[name]
        for a in attrs:
            vals = []
            for _ in range(N):
                u = r.random()
                if a == "labor_pool":
                    u = (u - 0.5) * 20 * fc.volatility
                elif not fc.enabled and a in ("equip_u", "contam_u", "fire_u", "labor_quit_u"):
                    u = 1.0  # never triggers
                elif a in ("equip_u", "contam_u", "fire_u", "labor_quit_u"):
                    u = u / max(0.05, fc.event_rate)  # higher rate -> smaller u -> more events
                vals.append(u)
            setattr(P, a, vals)

    P.fire_share = [0.1 + 0.5 * v for v in P.fire_share]

    ce = f["celebrity"]; r = R["celebrity"]
    P.celebrity = [0.0] * N
    for t0 in _poisson_events(r, 0.35 * ce.event_rate):
        hit = 0.05 + 0.12 * r.random() * ce.volatility
        dur = 26 + int(r.random() * 52)
        if ce.enabled:
            for t in range(t0, min(N, t0 + dur)):
                decay = 1 - (t - t0) / dur
                P.celebrity[t] = max(P.celebrity[t], hit * decay)
            P.news.append((t0, "celebrity", "Celebrity-backed bourbon launches nationally at $39.99"))

    to = f["tourism"]; r = R["tourism"]
    for t in range(N):
        n = r.gauss(0, 1)
        seas = 1 + 0.35 * _season(t + 2)
        P.tourism.append(seas * (math.exp(0.15 * to.volatility * n) if to.enabled else 1.0))

    _apply_shocks(sc, P)
    P.news.sort()
    return P


def _apply_shocks(sc: Scenario, P: Paths) -> None:
    for s in sc.shocks:
        t0 = s["week"]
        if t0 >= N:
            continue
        ev = s["event"]
        dur = int(s.get("weeks", 26))
        span = range(t0, min(N, t0 + dur))
        if ev == "government_shutdown":
            for t in range(t0, min(N, t0 + int(s.get("weeks", 4)))):
                P.shutdown[t] = True
            P.news.append((t0, "shock", "Federal shutdown: TTB stops processing permits and labels"))
        elif ev == "demand_regime":
            target = REGIMES[s.get("regime", "glut")]
            for t in range(t0, N):
                P.demand[t] = P.demand[t] + (target - P.demand[t]) * min(1.0, (t - t0 + 1) / 26)
                P.regime[t] = s.get("regime", "glut")
            P.news.append((t0, "shock", f"Category turns: analysts call a {s.get('regime', 'glut')}"))
        elif ev in ("corn_spike", "energy_spike"):
            arr = P.corn if ev == "corn_spike" else P.energy
            mult = float(s.get("mult", 1.6))
            for t in span:
                arr[t] *= 1 + (mult - 1) * (1 - (t - t0) / max(1, dur))
            P.news.append((t0, "shock", "Drought sends corn futures soaring" if ev == "corn_spike" else "Natural gas price spike"))
        elif ev in ("cooperage_shortage", "glass_shortage"):
            name = ev.split("_")[0]
            idx, lead = getattr(P, f"{name}_index"), getattr(P, f"{name}_lead")
            for t in span:
                idx[t] *= 1.4
                lead[t] += 10
            P.news.append((t0, "shock", f"{name.title()} supply crunch: allocations and long lead times"))
        elif ev == "tariff":
            for t in range(t0, min(N, t0 + int(s.get("weeks", 52)))):
                P.export_tariff[t] = float(s.get("rate", 0.5))
            P.news.append((t0, "shock", f"{int(float(s.get('rate', 0.5)) * 100)}% retaliatory tariff hits American whiskey"))
        elif ev == "rate_hike":
            bp = float(s.get("bp", 150)) / 10000
            for t in range(t0, N):
                P.prime[t] += bp
            P.news.append((t0, "shock", "Fed hikes sharply; prime rate jumps"))
        elif ev == "celebrity_launch":
            hit = float(s.get("share", 0.15))
            for t in span:
                P.celebrity[t] = max(P.celebrity[t], hit * (1 - (t - t0) / max(1, dur)))
            P.news.append((t0, "shock", "Celebrity bourbon launch floods your price tier"))
        elif ev == "heat_wave":
            for t in range(t0, min(N, t0 + int(s.get("weeks", 3)))):
                P.temp_f[t] += float(s.get("deg", 10))
            P.news.append((t0, "shock", "Record heat wave"))
        elif ev == "distributor_consolidation":
            P.consolidation_weeks = sorted(set(P.consolidation_weeks) | {t0})
            P.news.append((t0, "shock", "Major wholesaler merger; portfolio review underway"))
        else:  # warehouse_fire, still_failure, contamination, key_staff_quit: one-off forced events
            P.forced.setdefault(ev, []).append(t0)
            if ev == "warehouse_fire":
                P.fire_share[t0] = float(s.get("share", 0.3))
