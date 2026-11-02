# Barrel: a 10-year whiskey-distillery benchmark for Plural

The Agent runs a craft distillery for **40 quarters (10 years)**. Whiskey made today
sells years from now, so every quarter it has to balance:
- **production**: what to fill, on which warehouse floor, in new or refill wood;
- **cellar**: when to sample and when to bottle, and under which age statement;
- **distributors**: which orders to promise;
- **brokers**: buying bulk lots, some with false paperwork, and selling casks honestly;
- **the bank**: a borrowing-base covenant on a $9M line that tightens in a glut.

It also faces a boom-then-glut demand cycle, a cooperage shortage, a heat wave on F3,
and a celebrity brand dumping cheap whiskey.
The outcome is **dollars**: cash − debt + 0.45 × the mark on casks + 0.60 × the mark on
finished goods. Model spend (`usage.cost_usd`) is subtracted.
Two acts score the whole run 0:
- a **false age statement** (a label older than the spirit's true age);
- **misdescribed casks** (sold above their true grade without a lab read from the last 4 quarters).

Built against **plural 0.25.0** (latest on PyPI, released 2026-10-29). It is pinned in `pyproject.toml`.

## Layout
```
environments/barrel/          Barrel(App[BarrelState]), 15 actions; environment.yaml (max_turns: null)
  barrel_sim/                 deterministic seeded sim: params, core, desk, playbook, policies, voice
verifiers/distillery-outcome/ score = clamp((raw-baseline)/(oracle-baseline),0,1), 0 if vetoed; reward() shaping
harnesses/barrel-scripted/    ONE scripted Harness; policy picked by Agent harness_config (new in 0.25)
agents/idle-bot|baseline-bot|cellar-bot   harness_config.policy = do_nothing|baseline|cellar
agents/native-model           built-in model loop (needs a model key, not run here)
tasks/                        barrel-dev-{1,2,glut-3}, barrel-test-{101,102,103,glut-104,mature-105}; expected = anchors
benchmarks/barrel, barrel-dev scripts/make_tasks.py regenerates tasks + expected
tests/                        pytest, 38 tests
```

## Policies and anchors
- **do-nothing:** fills nothing and sells nothing. The interest and covenant breaches eat it.
- **baseline:** fills 200 new casks on F2 every quarter, bottles everything at 4 years,
  ships orders, and repays any cash above $500k. It anchors score 0.
- **cellar (the smarter policy):**
  - samples and ladders bottling by estimated potential;
  - sells over-oaked casks honestly;
  - buys only inspected lots;
  - sizes fills to its borrowing headroom.
- **oracle:** the best of an 18-setting grid of the cellar policy, run with and without
  perfect information (`Peek`). It anchors score 1.

Do-nothing scores below 0 and is clamped to 0.

## Results (raw $M; score in brackets)
Raw dollars come from `references()`. Scores come from real offline `plural run`s.

| Task | do-nothing | baseline | cellar | oracle |
|---|---|---|---|---|
| dev-1 | −0.29 | 9.48 (0.00) | 19.08 (0.664) | 23.93 |
| dev-2 | −0.44 | 10.86 (0.00) | 18.04 (0.700) | 21.12 |
| dev-glut-3 | −0.44 | 12.24 (0.00) | 20.68 (0.839) | 22.29 |
| test-101 | −0.24 | 10.25 | 20.64 (0.741) | 24.26 |
| test-102 | −0.36 | 9.37 | 17.33 (0.670) | 21.25 |
| test-103 | −0.46 | 9.44 | 19.06 (0.732) | 22.58 |
| test-glut-104 | −0.60 | 11.47 | 19.19 (0.750) | 21.76 |
| test-mature-105 | 0.05 | 13.38 | 22.44 (0.621) | 27.97 |

The ordering do-nothing < baseline < cellar ≤ oracle holds on **all 8 seeds** (this is tested).
Do-nothing breaches the covenant about 25 times per run and is force-sold 12 times. Baseline and cellar never breach.

Plural jobs:
- dev, idle-bot: `job_d6d05ba2…`, mean 0.000
- dev, baseline-bot: `job_45884936…`, mean 0.000
- dev, cellar-bot: `job_b62e85f7…`, mean 0.735
- test, cellar-bot: `job_659e188f…`, mean 0.703

## What's new in the SDK
**0.25.0** (used here):
- An Agent's `harness_config` now overrides a custom Harness's config. Hangar needed one Harness copy per policy; Barrel uses one Harness for three Agents.
- A Harness can have a `readme` (in harness.yaml and as a class attribute).
- `rubric_score` was added.
- `job record --push-pinned` and `push --bump patch` were added.
- `job list` shows each Job's Agent and mean score.
- validate, show and push accept a path.
- The model-call deadline follows `max_seconds` instead of a fixed 120 s.
- An AgentVerifier's score now follows its rubric.

**0.24.0 / 0.24.1:**
- local model fingerprinting;
- `allow_local_models`;
- $0 cost for local endpoints.

**0.23.1:**
- `max_turns` is uncapped by default (`null` means no cap);
- default limits are 600 s, and the Runtime timeout defaults to 900;
- project push is atomic;
- title vs. name is fixed.

**Used from 0.23.x:** Task `expected` (the Verifier prefers it and warns if it differs from the App's anchors) and per-Trial seeds.

## SDK friction
1. **The `click` dependency is undeclared.** The plural 0.25.0 CLI imports `click`, but the package doesn't declare it (typer 0.27.3 no longer brings it in). `plural --version` crashes until it's installed. Workaround: `click>=8.1` in our dependencies.
2. **Argument names fail silently.** A tool call with wrong argument names is refused, and a custom Harness sees only an empty observation plus `info["error"]`. The Trial still "succeeds". In our first run every bottle call was refused (`batch=` vs `batch_id=`) and all policies scored 0 without any visible failure. It's fixed in the harness (`_APP_ARGS`) with a regression test. It would help if a Trial could flag a high refusal rate.
3. **Local runs are slow.** A run of about 400–1,500 actions takes 2–10 minutes locally, while the bare sim plays 16 full runs in 0.24 s. Per-step overhead (state snapshots, settlement, and trajectory files) dominates.
4. **One Agent per run.** `plural run` accepts only one `--agent`, so comparing Agents takes one Job per Agent.
5. **No multi-agent Tasks.** Benchmarks can't hold them, so brokers are scripted. There's an optional LLM pitch voice (`broker_voice: llm`) that falls back to the script.

## Limitations
- The oracle is the best of a grid, not a true optimum. The grid includes the cellar policy's own blind default, so oracle ≥ cellar by construction.
- The baseline never trips the covenant, so the bank only bites careless or idle play.

## Run
```
uv venv && uv pip install -e .   # or: pip install plural==0.25.0 click pytest pyyaml
pytest -q
plural run -b barrel-dev -a cellar-bot -n 3
```
