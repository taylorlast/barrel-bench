# Barrel v2 design: found and run a craft whiskey distillery

## Goal
Measure whether a model can operate a long-horizon, cash-constrained, regulated business the way a
real founder does: get permitted, build out, make spirit, survive the multi-year gap before aged
whiskey sells, stay honest with regulators and customers, and react to a world it does not control.
No scripted Agents. Counterparties are environment-side behaviour models. Benchmarked Agents are real
models running through a context-managing Harness.

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

## Apps (10 Plural Apps over one shared world)
All Apps sit on one deterministic world object (`barrel_sim.World`) shared in-process
(`barrel_sim.registry`), because a real company's systems are coupled. The `office` App is listed
first and builds the world from the Task's `scenario`; the others attach in their reset.

| App | Real system it mirrors | Actions (as the Agent sees them) |
|---|---|---|
| `office` | clock, calendar, founder's dashboard | `briefing`, `end_week`, `add_reminder`, `catalog` |
| `inbox` | email with every counterparty | `list_emails`, `read_email`, `reply` (decision: accept/decline/counter/answer), `send` |
| `compliance` | TTB Permits Online, COLAs Online, Pay.gov, state ABC portal | `compliance__status`, `apply_permit`, `obtain_bond`, `submit_label`, `tax_ledger`, `file_excise_return`, `file_operations_report` |
| `production` | site, equipment, still house | `production__status`, `sign_lease`, `order_equipment`, `run`, `fill_barrels`, `bottle`, `maintenance`, `set_sanitation` |
| `warehouse` | rickhouse ledger | `warehouse__status`, `sample_lot`, `move_lot` |
| `procurement` | suppliers and POs | `quotes`, `order` |
| `sales` | channels and pricing | `sales__status`, `set_price`, `set_tasting_room`, `set_marketing`, `pitch_distributor`, `apply_control_listing`, `list_barrels` |
| `finance` | bank portal + books | `finance__status`, `apply_loan`, `draw`, `repay`, `buy_insurance` |
| `people` | HR / payroll | `people__status`, `post_job`, `hire`, `let_go` |
| `market` | trade press and price feeds | `snapshot_market` |

### Counterparties (environment-side behaviour models, never evaluated Agents)
TTB specialist (permit questions with 30-day answer deadlines, inspections), state ABC board, bank
loan officer (SBA decision, covenant notices), barrel-line lender, distributor reps (proposals, monthly
POs driven by simulated depletions, brand drops after consolidation), control-state boards (listing
windows), export importer, bulk barrel brokers (bids from market index and their own samples),
a sourced-whiskey supplier (offers), cooperage/glass/grain vendors (quotes, delays), recruiters
(candidates with hidden skill), insurer. Each writes email into `inbox`; decisions come back through
`reply_email(decision=...)`. Text is templated; `voice: llm` rewrites it with a model through Plural's
gateway without changing any number or hidden fact.

### Hidden state
True spirit quality per run, barrel maturation (temperature-driven), true age of every lot, candidate
skill, distributor appetite, future exogenous paths. The Agent sees only noisy samples, lagged indices
and email.

## Exogenous randomness (and how to control it)
Seventeen factors, each with its own RNG stream `Random("{master_seed}|{factor}|{factor_seed}")`,
pre-generated for 600 weeks regardless of horizon. Changing one factor's seed, volatility or enable
flag never changes another factor's draws. Disabled factors fall back to their mean path / no events
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
