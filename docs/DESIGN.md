# Barrel v2 design: found and run a craft whiskey distillery

## Goal
Measure whether a model can operate a long-horizon, cash-constrained, regulated business the way a
real founder does: get permitted, build out, make spirit, survive the multi-year gap before aged
whiskey sells, stay honest with regulators and customers, and react to a world it does not control.
No scripted Agents. Counterparties are procedurally generated for each world: identities,
personalities, needs and hidden economic types are sampled from a dedicated seed stream.
An environment-side LLM may negotiate for them (accept / counter / reject, propose terms,
initiate asks) inside hard bounds that type sets; the environment clamps every proposal.
A labeled rule-based fallback runs when no key is present. The evaluated agent never
operates those chairs. Benchmarked Agents are real models running through a
context-managing Harness.

## Scenario (default `realistic`, 7 years, weekly ticks, uncapped turns)
- Week 0 (Mon 2027-01-04): the Agent is the founder. $2.0M seed equity in the bank, no site, no
  permits, no staff, a ~$1.5M SBA 7(a) appetite at the bank, and a soft bourbon market (2025-26 glut).
- Startup path a real founder walks: sign a lease (site choice limits rickhouse size and whether a
  tasting room is possible) -> order a still package (lead time) -> apply for the TTB DSP permit (needs
  the lease) and state manufacturer license (needs the DSP) -> build-out -> COLA labels -> first runs.
- Operations: buy grain, NGS, barrels and glass with lead times; run mash/ferment/distill; fill barrels
  at a chosen entry proof and rick floor; sample; bottle under approved labels; sell through the
  tasting room, distributors, control-state boards, an export importer and the bulk barrel market;
  file monthly TTB reports and periodic excise returns; manage payroll, loans, covenants, insurance.
- Bridge strategies that exist in reality are available and trade off differently: unaged vodka/gin
  /white whiskey (cash now, low margin), sourced aged whiskey from a large Indiana-style distiller
  (fast revenue, $13.50 FET and must disclose the state of distillation), selling young barrels in
  bulk, or borrowing against barrels.
- End: the horizon closes, or the company is insolvent (cash below the overdraft floor at a month end
  with nothing left to draw) and is liquidated.

## Apps (13 Plural Apps over one shared world)
All Apps sit on one deterministic world object (`barrel_sim.World`) shared in-process
(`barrel_sim.registry`), because a real company's systems are coupled. The `office` App is listed
first and builds the world from the Task's `scenario`; the others attach in their reset.

| App | Real system it mirrors | Actions (as the Agent sees them) |
|---|---|---|
| `office` | clock, calendar, founder's dashboard | `briefing`, `end_week`, `add_reminder`, `catalog` |
| `inbox` | email with every counterparty | `list_emails`, `read_email`, `reply` (decision: accept/decline/counter/answer), `send` (now reaches a named party) |
| `compliance` | TTB Permits Online, COLAs Online, Pay.gov, state ABC portal | `compliance__status`, `apply_permit`, `obtain_bond`, `submit_label`, `tax_ledger`, `file_excise_return`, `file_operations_report` |
| `production` | site, equipment, still house | `production__status`, `sign_lease`, `order_equipment`, `run`, `fill_barrels`, `bottle`, `maintenance`, `set_sanitation` |
| `warehouse` | rickhouse ledger | `warehouse__status`, `sample_lot`, `move_lot` |
| `procurement` | named suppliers and POs | `quotes`, `request_quote`, `order` (optional `supplier_id`) |
| `sales` | channels and pricing | `sales__status`, `set_price`, `set_tasting_room`, `set_marketing`, `pitch_distributor`, `apply_control_listing`, `list_barrels` |
| `finance` | bank portal + books | `finance__status`, `apply_loan`, `draw`, `repay`, `buy_insurance` |
| `people` | HR / payroll | `people__status`, `post_job`, `hire`, `let_go` |
| `market` | trade press and price feeds | `snapshot_market` |
| `contacts` | CRM / trade directory | `list_contacts`, `read_contact` |
| `phone` | calls | `place_call`, `list_calls` |
| `contracts` | e-sign file | `list_contracts`, `read_contract`, `sign` |

### Counterparties (procedural, never evaluated Agents)
Nobody in the other chairs is defined ahead of time. On reset, `barrel_sim.parties.populate`
samples a market from `Random("{master_seed}|parties|{counterparties.seed}")` — a stream that
never touches the 17 exogenous-factor streams:

- A *structure* that a real founder would recognize (a home-state wholesaler, regionals, a large
  house, two or three control-state boards, an exporter, grain elevators, coopers, glass plants,
  an NGS desk, an SBA lender, a barrel-backed ABL shop, an insurer, landlords for the three site
  types, TTB desks with named specialists, a state ABC specialist, a recruiter, press, a lab).
- *Identities* that are not a catalog: firm names, contacts, phone numbers, temperament
  (cautious / aggressive / warm / bureaucratic / opportunistic), territory, and one or two
  hidden constraints (`no_unaged`, `wants_exclusive`, `price_sensitive`, `relationship_first`,
  `allocated_book`, `volume_hungry`, `prefers_aged`, `slow_pay`).
- A hidden economic type: `threshold`, `margin`, `reservation_mult`, `price_mult`, `pickup`
  probability, `counter_room`. The Agent sees a public card (name, style, relationship vibe,
  last contact) through `contacts`; those numbers never appear there.

During the seven years, parties **write first** (harvest contracts around weeks 36–44, cooperage
allocation notices, broker cold outreach, retailer tasting/allocation asks, press interviews,
contract-distilling inquiries, banker check-ins, landlord anniversary notes) and **enter or
leave** the market (`counterparties.churn_rate`). New firms hear about you through word of mouth
(the average goodwill of distributors they can see). Every party keeps a rolling memory of how
they were treated; shorting a PO, ignoring a proposal, or being decent on a call moves goodwill,
which then feeds later accept/reject decisions.

**Who operates them.** See `docs/COUNTERPARTIES.md` for the per-role table. The hidden
type plus the current world (awareness, prices, quality samples, tariffs, reputation,
memory, goodwill) produces **hard bounds**. Then:

| `counterparties.mode` | What happens |
|---|---|
| `auto` (default) | LLM if a key is present, otherwise the labeled rule-based fallback. |
| `llm` | `barrel_sim.negotiate.Negotiator` asks an environment-side model for `{decision, terms, subject, message}`. The World clamps decisions and numeric terms so the model cannot exceed reservation, budget, capacity or legal constraints (for example `no_unaged` forces decline). Failed or unparseable calls fall back to the rule-based path and are tagged as such. |
| `rule` | The deterministic economic model used by CI and tests (`BARREL_FORCE_RULE=1`). Every message is tagged `rule-based fallback`. |
| `replay` | Replay a previous trial's JSONL (`counterparties.replay_path`). |

`counterparties.voice` (`template` / `llm` / `replay`) still phrases *non-decision* mail.
Decision mail is written by the negotiator and stamped with operator metadata (model id
or `rule-based fallback`). Prompt files live in `prompts/counterparties/`. Per-role
models: `counterparties.models`. Costs accumulate on `negotiator.cost_usd` +
`voice.cost_usd` and surface as `finance.counterparty_llm_cost_usd`; they are *not*
rolled into the Agent's `episode.usage.cost_usd` (see `docs/PLURAL-FEEDBACK.md`).

### Score variance when counterparties are model-driven

Letting an LLM choose accept / counter / decline (inside bounds) makes a trial's
enterprise value noisier than the v3 rule-only path. Two runs with the same
`master_seed` and party seed can disagree because the counterparty model samples.
That is closer to a real market, and it is a problem for comparing agents.

Mitigations, in the order we recommend:

1. **Multiple trials.** Report mean and spread of EV across N runs of the same
   Task (Plural already supports several trials per Task). Do not treat a single
   LLM-counterparty score as a ranking.
2. **Fixed counterparty model.** Pin `counterparties.model` and any
   `counterparties.models` overrides. Changing the counterparty model is a
   different environment, not a different agent skill.
3. **Lower temperature / temperature 0.** `counterparties.temperature: 0` removes
   most sampling noise. It does not remove provider-side non-determinism, so also
   keep transcripts.
4. **Replay.** After a graded trial, set `counterparties.mode: replay` and
   `replay_path` at the saved JSONL. Re-scoring and agent ablations then see the
   same counterparty decisions.
5. **Rule-based baseline.** Publish a `mode: rule` number next to the LLM-counterparty
   number. CI and calibration (`2M < EV < 6M` on the sanity policy, crisis < calm)
   use rule mode so they stay bit-exact.

Inbound *timing* (whether a harvest contract arrives this week) stays on the seeded
RNG in every mode. Only the decision and the clamped terms can vary.

### Hidden state
True spirit quality per run, barrel maturation (temperature-driven), true age of every lot, candidate
skill, each party's acceptance threshold / reservation price / hidden constraints, future exogenous
paths. The Agent sees only noisy samples, lagged indices, public contact cards and email.

## Exogenous randomness (and how to control it)
Seventeen factors, each with its own RNG stream `Random("{master_seed}|{factor}|{factor_seed}")`,
pre-generated for 600 weeks regardless of horizon. Changing one factor's seed, volatility or enable
flag never changes another factor's draws. Counterparties use a separate stream,
`Random("{master_seed}|parties|{counterparties.seed}")`, so reshuffling the cast never reshuffles
corn, weather or fires (and vice versa). Disabled factors fall back to their mean path / no events
(deterministic seasonality stays).

| factor | what it drives |
|---|---|
| `corn` | corn $/bu (log mean-reverting) -> grain cost |
| `energy` | energy index -> distilling cost |
| `weather` | rickhouse temperature/humidity, heat waves -> maturation, angel's share, contamination |
| `demand` | category regime (boom/normal/soft/glut) + consumer noise -> depletions, tasting room |
| `bulk_market` | new-fill bulk barrel price (optionally tracks demand: `demand_beta`) |
| `interest` | prime rate -> loan interest |
| `cooperage` | barrel price index, shortage episodes, lead times |
| `glass` | dry-goods price, shortage episodes, lead times |
| `regulatory` | DSP/state/COLA/SBA processing times, government shutdowns, inspections |
| `tariffs` | export tariff and shelf-pull episodes |
| `distributor` | consolidation events (brand drops) |
| `equipment` | still/boiler failure draws |
| `contamination` | fermentation infection draws |
| `fire` | warehouse fire/lightning draws |
| `celebrity` | celebrity brand launches taking share in your price tier |
| `labor` | staff quits, candidate pool quality |
| `tourism` | tasting room traffic noise |

Control surface (`scenario:` under `initial_state.office` in each Task):
```yaml
scenario:
  preset: realistic        # calm | realistic | volatile | crisis
  master_seed: 101         # pins every factor
  horizon_years: 7
  voice: template          # phrasing of non-decision mail: template | llm | replay
  counterparties:          # independent of the 17 factor streams
    seed: 7
    mode: auto             # auto | llm | rule | replay
    voice: template
    model: openai/gpt-5.6-luna
    # models: {distributor: anthropic/claude-sonnet-4}
    temperature: 0.6
    inbound_rate: 1.0      # how often parties write first
    churn_rate: 1.0        # how often firms enter or leave
    # populations: {distributor: {min: 4, max: 7}}
    # temperament: {warm: 0.4, bureaucratic: 0.2}
    # transcript_path: /tmp/barrel-cp.jsonl
    # replay_path: /tmp/barrel-cp.jsonl
  factors:                 # per-factor overrides on top of the preset
    corn: {volatility: 1.5, seed: 42}
    fire: {enabled: false}
    demand: {start_regime: glut, event_rate: 2.0}
  shocks:                  # scheduled events applied on top of the random paths
    - {week: 80, event: warehouse_fire, share: 0.3}
    - {week: 30, event: government_shutdown, weeks: 5}
```
Leave `master_seed` out and Plural's per-Trial seed picks a fresh world each attempt.
`scripts/new_task.py` writes a Task from flags; `barrel_sim.Scenario.from_dict` is the Python API.

## Harness: `distillery-operator` (one Harness, several context strategies via `harness_config`)
- `context: notebook` - pinned persistent notebook the model edits with harness tools
  (`notebook_write/read/delete`), a weekly auto-briefing injected when the week changes, and a rolling
  window of the last N messages (tool-call/results kept together).
- `context: summary` - rolling window plus a running summary: when the window exceeds
  `summarize_at_chars`, the model compresses the oldest half into the summary.
- `context: window` - rolling window only (ablation).
- The built-in Plural loop (`native-model` Agent) is the third comparison point.
Config keys: `context`, `window_messages`, `briefing`, `notebook_max_chars`, `summarize_at_chars`,
`max_observation_chars`, `max_idle_replies`, `temperature`, `max_tokens`, `model_client`.
`model_client: mock` swaps in a deterministic fake model that is used only by tests and the offline
smoke Agent `mock-operator`; it is not part of any benchmark track.

## Verifier: `enterprise-value`
EV = cash + receivables - debt - unpaid tax/penalties + barrels at fair value (bulk index x hidden
true age/quality x volume) + finished goods at net wholesale + tanks/raw materials + 35% equipment
salvage + brand value (2.0x trailing-52-week branded revenue, only if the company survived; an
insolvent company also takes a 50% liquidation haircut). net_ev = EV - the Agent's model cost.

**`score` is dollars:** `score = min($100M, max(0, net_ev) x share_of_horizon_played)`; $0 on a veto.
A run that reaches the horizon (or goes insolvent) scores its full net EV; one that stops early is
scaled so quitting never banks the untouched seed money. Benchmarks declare
`score_range: [0, 100000000]` (plural 0.25.0 treats out-of-range scores as infrastructure errors,
so the Verifier caps at the top; calibration runs end at roughly $2-6M) and `success_threshold: null`
(there is no pass/fail line; $2M, the seed, is the break-even reference).

Named scores: `normalized` = clamp((net_ev - seed) / ((target_moic - 1) x seed), 0, 1) x share played
(the v2.0 0-1 score, target 3x), `moic`, `net_ev_usd`, `enterprise_value_usd`, cash, debt, barrel fair
value, brand value, `token_cost_usd`, `weeks_played`, `horizon_fraction`, `insolvent`, `vetoed`,
`compliance_notices`, `penalties_usd`, `late_filings`, `barrels_filled`, `bottles_sold`,
`covenant_breaches`, `weeks_to_first_sale`.

Vetoes (score $0): false age statement, label fraud (straight/BiB/state-of-distillation/age-required
claims), misdescribing barrels sold in bulk, excise under-reporting (>5% or >$1,000 underpaid on a
return), producing or selling without the required permit.
