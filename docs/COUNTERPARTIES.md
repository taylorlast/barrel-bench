# Who operates the counterparties

The evaluated agent is the founder. **It never operates a counterparty.** Every
distributor, exporter, control board, broker, farmer, cooper, banker, regulator,
journalist, retailer, landlord and recruiter is owned by the environment.

This document is the operator log: who sits in each chair, what they can see,
what they cannot, which prompt file they use, and how the environment stops
them from exceeding hidden economic limits.

## Modes

`counterparties.mode` (default **`auto`**):

| Mode | Who decides accept / counter / reject / asks | When it is used |
|---|---|---|
| `auto` | LLM if a Plural (or provider) key is present; otherwise the labeled **rule-based fallback** | Default for a Task |
| `llm` | Environment-side model through Plural's `Client.chat` (`write_trace=False`) | Explicit; needs a key or a mock |
| `rule` | Deterministic hidden economic model. Every transcript and email is tagged **`rule-based fallback`** | CI, tests (`BARREL_FORCE_RULE=1`), and any LLM failure |
| `replay` | Prior trial's JSONL (`counterparties.replay_path`). A cache miss falls back to the rule-based path and is logged as such | Re-scoring a published trial |

`counterparties.voice` (`template` / `llm` / `replay`) still controls *phrasing* of
non-decision mail (reminders, POs, system notes). Decision mail is written by
the negotiator, not re-phrased afterwards.

The pytest suite sets `BARREL_FORCE_RULE=1` so `auto` always resolves to `rule`
even if a key is in the environment. Tests that exercise the LLM path set
`counterparties.mode: llm` and inject a mock `chat_fn`.

## What the economic model hides (and still enforces)

On reset, `barrel_sim.parties.populate` samples identities from
`Random("{master_seed}|parties|{counterparties.seed}")`. That stream never
touches the 17 exogenous-factor streams. Each party gets a hidden type:
`threshold`, `margin`, `reservation_mult`, `price_mult`, `counter_room`,
`pickup`, and zero or more constraints (`no_unaged`, `wants_exclusive`,
`price_sensitive`, `relationship_first`, `allocated_book`, `volume_hungry`,
`prefers_aged`, `slow_pay`). Those numbers never appear on
`contacts.read_contact`.

When it is time to act, the environment:

1. Draws any randomness that decides *whether* an event happens (inbound
   rate, pitch score noise, broker selection) from the seeded counterparty
   stream.
2. Turns the hidden type plus current world state into **hard bounds**:
   allowed decisions and `[min, max]` for every numeric term (reservation,
   budget, capacity, legal constraints).
3. Asks the operator (LLM or rule-based fallback) for
   `{decision, terms, subject, message}`.
4. **Clamps** the proposal: illegal decisions are rewritten to an allowed
   one; terms outside the range are projected onto it; unknown term keys
   are dropped; language that would leak reservation/threshold/“I am an LLM”
   is stripped. The model cannot exceed the limits.
5. Logs the full prompt, raw response, clamped decision, operator metadata
   and cost on `World.negotiator.transcripts` (and optionally
   `counterparties.transcript_path`).
6. Sends the email with an operator tag in the body and on the record
   (`read_email` exposes `operator`).

Party **memory** and **goodwill** are fed into the LLM prompt as recent
history and a qualitative relationship (frosty / cautious / cordial / warm).
They already feed the rule-based score (relationship-first houses, word of
mouth when new firms enter).

## Operator table (every role)

Default model when `counterparties.models` does not override a role:
`counterparties.model`, or `$BARREL_COUNTERPARTY_MODEL`, or
`openai/gpt-5.6-luna`. In `rule` mode the model column is unused and the
operator label is always `rule-based fallback`.

| Role | Kind key(s) | Who operates it | Prompt file | What it sees | What is hidden from it | What the env enforces |
|---|---|---|---|---|---|---|
| Home / regional / national wholesaler | `distributor` | Env LLM or rule-based fallback | `prompts/counterparties/distributor.md` | Persona, temperament, memory, goodwill, the labels pitched, a band on awareness and relative wholesale | Raw `threshold` / score internals; other parties' types; true spirit quality; future factor paths; the founder's system prompt | Allowed: `accept` / `counter` / `decline` when the score clears the bar; only `decline` well below it or when `no_unaged` meets an all-unaged pitch. `margin` clamped to the hidden type ± a few points |
| Export importer | `export` | same | `prompts/counterparties/exporter.md` | Same as a distributor, plus that tariffs weigh on the (already computed) score | Same + the tariff path itself | Same decision/margin clamp; score already subtracted export-tariff pressure |
| Control-state board | `control` | same | `prompts/counterparties/control_board.md` | Persona, the filed label, listing-window context | Raw threshold, other applicants, future windows | `accept` only if the listing score clears the bar; otherwise `decline` only. No margin to set |
| Bulk broker / sourced seller | `broker` | same | `prompts/counterparties/broker.md` | Listing (barrels, ask, stated age), relationship | Reservation multiplier as a raw field; true lot quality/age they have not paid to inspect; future bulk index | Bid in `[reservation × fair value, reservation+0.14 × FV]`, never above the ask. A counter from the founder above `bid × (1+counter_room)` can only be `decline` (walk). Age claims they sell are env-authored (including the 20% shady flag) |
| Grain elevator, cooperage, glass, NGS | `grain`, `cooperage`, `glass`, `ngs` | same | `prompts/counterparties/supplier.md` | Spot context, persona, whether they are on allocation | Raw `price_mult`; future corn/cooperage/glass paths | Harvest `price` / `qty` / `due` clamped around the seeded lock; they may `offer` or `pass`. Quotes around the posted index stay on the named-supplier card (spot orders ignore them) |
| SBA officer / barrel lender | `bank`, `lender` | same | `prompts/counterparties/lender.md` | Requested amount, product (7(a) vs barrel line) | Full credit box formula | `amount` cannot exceed the cap (budget). They may cut it down to a floor or `decline`. Rule-based fallback always accepts at `min(requested, cap)` |
| TTB / state ABC specialist | `regulator` | same (usually rule-authored info mail) | `prompts/counterparties/regulator.md` | The file they are writing about | Processing-time draws, inspection RNG, future shutdowns | They cannot grant a permit the compliance engine has not approved, or shorten a statutory wait |
| Trade press | `press` | same | `prompts/counterparties/press.md` | Founder's public story so far | Circulation, unpublished scoops | `offer` an interview or `pass`. No prices to set |
| Retailer / bar | `retailer` | same | `prompts/counterparties/retailer.md` | Allocation or tasting context | Distributor inventories they should not see | Tasting `fee` is fixed at $600. They cannot bypass three-tier |
| Landlord | `landlord` | same (usually rule-authored notes) | `prompts/counterparties/landlord.md` | The signed site | The option to raise rent | Anniversary notes cannot change the recorded rent |
| Insurer, recruiter, fabricator, lab, board, contract client | `insurer`, `recruiter`, `fabricator`, `lab`, `board`, `contract_client` | same | `prompts/counterparties/generic.md` | The situation the env authored | Anything not in that situation | Contract-distill `pg` / `weeks` / `rate` clamped around the seeded ask; they may `pass` |

Every role file is concatenated after `prompts/counterparties/_shared.md`
(JSON schema, “you are not the evaluated agent”, no leaking hidden limits).
Prompt files are versioned in-header (`barrel-counterparty-prompt 1.0`).

## Example transcript (one pitch)

What the LLM is asked (abridged):

```
system: <_shared.md + distributor.md>
user:
  You are Maya Chen at Green River Wholesale (distributor, warm).
  Relationship: cordial (goodwill 0.88 of 1.00).
  Recent history with this operator:
  - week 40: pitch — Samples of COLA-001 left with the sales manager
  Intent: pitch_response
  Situation: {"labels": ["COLA-001"], "awareness_band": 0.21, "relative_wholesale": 0.97}
  Allowed decisions: accept, counter, decline
  Term ranges: margin between 0.22 and 0.31
```

What it returned:

```json
{
  "decision": "accept",
  "terms": {"margin": 0.40},
  "subject": "Distribution proposal",
  "message": "We'd like to carry COLA-001 at a 40% program allowance..."
}
```

What the environment did:

- `0.40` is above `0.31` → clamped to `0.31`. `clamped: true` is logged.
- Email body includes the clamped term if the prose still said 40%.
- Operator footer:

```
—
[Counterparty operator: openai/gpt-5.6-luna · prompts/counterparties/distributor.md]
```

A rule-based turn of the same event (CI, no key, or a failed call) looks
like this instead:

```
—
[Counterparty operator: rule-based fallback]
```

The founder (`inbox.read_email`) sees `operator.model` or
`operator.label: "rule-based fallback"`. They cannot change it.

## How to swap models

```yaml
initial_state:
  office:
    scenario:
      counterparties:
        mode: llm                 # or auto / rule / replay
        model: openai/gpt-5.6-luna
        models:                   # optional per-role overrides
          distributor: anthropic/claude-sonnet-4
          broker: openai/gpt-5.6-luna
          lender: openai/gpt-5.6-luna
        temperature: 0.2          # 0 for less sampling noise
        seed: 7                   # reshuffles identities, not corn or fires
        transcript_path: /tmp/barrel-cp.jsonl
```

Or set `BARREL_COUNTERPARTY_MODEL` for the default id. Changing a role's
model never reseeds the 17 factor streams.

## How to reproduce / replay

1. Run a trial with `counterparties.transcript_path` set (or collect
   `World.negotiator.transcripts` and `World.voice.transcripts` at the end).
2. Re-run the same scenario (`master_seed`, `counterparties.seed`, factor
   knobs, shocks) with:

```yaml
counterparties:
  mode: replay
  replay_path: /tmp/barrel-cp.jsonl
  model: openai/gpt-5.6-luna   # must match; it is part of the cache key
  temperature: 0.2             # must match
```

3. Each decision looks up `sha256(master_seed|party_id|week|intent|situation|model|temperature)`.
   A hit replays the stored decision and terms exactly and tags the message
   `replay of <model>`. A miss uses the rule-based fallback and logs
   `fallback: true`.

Bit-exact economic reproduction without any model: `counterparties.mode: rule`
(what CI runs). Bit-exact wording of a prior LLM trial: `mode: replay` plus
the transcript file.

## The evaluated agent never controls counterparties

- The agent's tools (`inbox.send`, `inbox.reply`, `phone.place_call`,
  `sales.pitch_distributor`, …) talk *to* counterparties. They cannot set
  `operator`, choose a counterparty model, edit a prompt file, or loosen
  bounds.
- Counterparty `Client.chat` calls use `write_trace=False` so those tokens
  do not appear as the agent's words.
- `finance.counterparty_llm_cost_usd` reports environment-side spend
  (`voice` + `negotiator`); the Verifier still subtracts only the agent's
  `episode.usage.cost_usd` (see `PLURAL-FEEDBACK.md`).
- A message that asked the counterparty to “accept regardless of your
  limits” is still clamped. Legal constraints such as `no_unaged` force
  `decline`.

## Related

- [DESIGN.md](DESIGN.md) — score-variance tradeoff and mitigations
- [PLURAL-FEEDBACK.md](PLURAL-FEEDBACK.md) — SDK friction this design hits
- [README.md](../README.md#who-operates-the-counterparties) — short version
