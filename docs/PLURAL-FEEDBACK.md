# Plural SDK feedback from building Barrel

These are friction points we hit while turning Barrel into a long-horizon environment
where the *other people* in the world are not a fixed cast. Each item is a real
workaround in this repo, plus a proposed Plural API that would have made the same
design cheaper, safer, or more reproducible. Written against Plural **0.25.0**
(still the latest on PyPI as of 6 November 2026).

---

## 1. No first-class simulated-user / counterparty LLM primitive

**What we wanted.** A whiskey operator deals with dozens of other parties
(distributors, TTB specialists, farmers, brokers, bankers). Those parties should
actually negotiate — accept, counter, reject, propose terms, initiate asks —
while a seeded hidden type still caps what they are allowed to do, so a trial
stays gradeable and the evaluated agent never operates the other chairs.

**What we did.** `barrel_sim/negotiate.py` calls `plural.Client().chat(...)` itself,
with `write_trace=False`, and asks for `{decision, terms, subject, message}`. The
World clamps every proposal to hidden bounds (reservation, budget, capacity, legal
constraints). Versioned prompts live in `prompts/counterparties/`. Tests and CI
use `counterparties.mode: rule` (also forced by `BARREL_FORCE_RULE=1`) so no API
key is required; failed LLM calls fall back to that same labeled path.
`barrel_sim/voice.py` still phrases non-decision mail. There is still no first-class
seat for these operators, so we reinvented mode / clamp / transcript / replay /
per-role models around `Client.chat`.

**Proposed API.** Something like:

```python
env.counterparty_chat(
    party_id="D-001",
    role="counterparty",          # billed and traced separately from the Agent
    messages=[...],
    temperature=0.6,
    seed=env.seed.derive("parties", "D-001", week),
    allowed_facts=["$12.50", "2028-03-14", "PO#012"],  # rewrite rejected if any vanish
    record="transcripts/D-001.jsonl",
)
```

A first-class `SimulatedUser` / `Counterparty` type, with its own seed stream,
transcript, and cost center, would stop every long-horizon env from reinventing this.

---

## 2. No way to seed the LLM side separately from the trial

**What we wanted.** `Random(f"{master_seed}|parties|{counterparties.seed}")` already
isolates party *identities* from the 17 exogenous-factor streams. We also wanted the
optional wording model to be pin-able (`counterparties.model`, `temperature`, a
voice seed) without reshuffling corn prices or fires.

**What we did.** Scenario knobs under `counterparties:` (`seed`, `mode`, `model`,
`models`, `temperature`, `voice`, `replay_path`). The gateway still does not honor
a seed on `Client.chat`; `rule` / `replay` modes are how we get bit-exact
decisions, and `temperature: 0` is how we reduce sampling noise (see DESIGN.md).

**Proposed API.** `Client.chat(..., seed=...)` honored by the gateway, plus a
documented `derive_stream(master, *parts) -> seed` so environment authors do not
invent string-key RNGs. Allow an Environment to declare *named RNG streams*
(`factors.corn`, `parties`) that Plural binds to the trial seed unless overridden.

---

## 3. No built-in transcript log or replay

**What we wanted.** A trial that used `mode: llm` should be inspectable (every
prompt, raw response, clamped decision and operator tag) and replayable later
with `mode: replay` so a published result can be re-scored without calling the
model again.

**What we did.** `Negotiator` (and `Voice` for leftover phrasing) write JSONL
(`record_type`, `cache_key`, prompt, raw, decision, terms, operator, cost,
fallback). Replay loads that file and returns the stored decision for the same
key, falling back to the rule-based path on a miss. Operator metadata is also
stamped on every email the founder reads.

**Proposed API.**

```yaml
# environment.yaml
counterparties:
  transcripts: persist     # written next to the trial
  replay: allow            # a later run can point at that file
```

```python
episode.transcripts["environment"]   # alongside the Agent trace
Client.chat(..., replay_from=path)   # hit cache, else call, else error
```

---

## 4. Environment-side LLM cost is invisible to scoring

**What we wanted.** When the *world* calls a model to write a distributor's email,
that spend should show up somewhere the Verifier can see — either on
`episode.usage.cost_usd` or as a clearly named env-side total — so “net EV minus
model cost” does not silently ignore half the bill.

**What we did.** We pass `write_trace=False` so counterparty calls do not
pollute the Agent trace. `Usage.cost` is accumulated on `World.negotiator.cost_usd`
plus `World.voice.cost_usd` and exposed as `finance.counterparty_llm_cost_usd`. The
Verifier still subtracts only the Agent's `episode.usage.cost_usd`, because there
is no supported place to add environment-side spend without pretending the Agent
said those words.

**Proposed API.** `Client.chat(..., bill_to="environment"|"agent")`. Surface
`episode.usage.agent_cost_usd` and `episode.usage.environment_cost_usd` (and keep
`cost_usd` as the sum). Let a Verifier opt into counting either or both.

---

## 5. `click` is imported by the CLI but not declared

**What we hit.** `plural` 0.25.0 imports `click`. Typer 0.27 no longer pulls `click`
in, so a fresh install of `plural` alone breaks `plural env validate`.

**What we did.** `pyproject.toml` pins `click>=8.1`.

**Proposed API.** Declare `click` (or stop importing it) in plural's own package
metadata. This is a one-line packaging fix.

---

## 6. A wrong argument name fails silently

**What we hit.** If the Agent calls `sales.set_price(label="COLA-001")` instead of
`label_id=...`, Plural does not raise into the tool result unless the Harness reads
`info["error"]`. The `distillery-operator` Harness does; the built-in loop is easy
to misconfigure.

**Proposed API.** Always echo a structured tool error (`unknown parameter 'label';
expected label_id, channel, price`) as the observation, and flag it on
`step.info["error"]`. An Environment-level `strict_params: true` would help.

---

## 7. Apps in one Environment cannot share state

**What we wanted.** A real company is one set of books: the inbox, the rickhouse,
the bank portal and the CRM all see the same week and the same cash.

**What we did.** `barrel_sim/registry.py`. The `office` App is listed first, builds
the `World`, and publishes it; every other App attaches on reset. This relies on
AppHost resetting Apps in order in a single process.

**Proposed API.** `Environment.shared: dict` or an official `env.store` that every
App of one trial can read/write, with a documented reset order (or an explicit
`depends_on: [office]`). Without it, every multi-app business sim invents a process
global.

---

## 8. Reserved App hook names silently steal action names

**What we hit.** We added a `phone` App with an action named `call`. 
`plural env validate` rejected it: `Phone.call is an App hook; do not mark it with @action`.
Renaming to `place_call` fixed it, but the reserved set is not listed next to `@action`.

**Proposed API.** Document the reserved hook names (`reset`, `snapshot`, `call`, …)
in the `@action` docs and in the validation error (already decent). A
`plural env reserved-names` snippet, or allowing `@action(name="call")` to bind a
method that is not literally `def call`, would have saved a validation cycle.

---

## 9. No top-level `plural validate`

**What we hit.** Validating a project means `plural env validate`, `plural harness validate`,
`plural verifier validate`, `plural benchmark validate`, `plural agent validate`
separately. Easy to forget one.

**Proposed API.** `plural validate` (project-wide) that walks every resource.

---

## 10. `score_range` is a hard infrastructure check

This is documented in the README and is the right default — out-of-range scores
should be bugs. For dollar-valued benchmarks it means the Environment author must
pick a wide explicit range (`[0, 100_000_000]`) and cap in the Verifier. A
`score_range: dollars` convenience, or allowing `null` to mean “any finite float”,
would make EV-style scores less surprising.

---

## 11. Harness objects are frozen pydantic models

Per-run settings have to travel through `agent.harness_config`. That works, but it
overrides a custom Harness's own config in a way that is easy to miss when you are
debugging why `context: notebook` did not apply. A merged view in
`harness.run` logs (`applied_config=...`) would help.

---

## 12. One evaluated Agent per run, no co-party seats

Barrel's counterparties must not be scored, but they *are* conversational. Plural
has no seat for “environment-owned speakers” next to the Agent, so they live
entirely inside the Environment. A supported `participants:` block on a Benchmark
(one evaluated Agent, N unevaluated simulated users with their own model/seed/cost)
is the feature this design is reaching for.

---


## 13. No structured output for environment-side models

**What we wanted.** A counterparty turn is naturally a tool-shaped object
(`decision`, `terms`, `message`). We want the gateway to guarantee that shape
the way a tool call would.

**What we did.** We ask for JSON in the prompt, parse fences / first object
ourselves, and treat a parse failure as a rule-based fallback. Clamping then
has to happen in the Environment rather than as schema validation on the
gateway.

**Proposed API.** `Client.chat(..., response_format={"decision": str, "terms": dict, "message": str})`
(or a tool-call schema) that either returns a parsed object or raises a typed
error the Environment can catch and fall back from.

---

## What worked well

- `@action` plus `ValueError` (`Refused`) coming back as feedback, with no state
  change, is the right shape for a sim this size.
- Task `initial_state` as the scenario surface (preset, seeds, shocks) is clean.
- `score_range` / `success_threshold: null` let us score in dollars without a
  pass/fail line.
- `Client.chat` is easy to call from inside an Environment once you accept you are
  off the paved path (items 1–4 above).
