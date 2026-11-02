<p align="center">
  <img src="docs/images/hero.jpg" alt="An AI-run copper pot still distillery at dusk" width="100%">
</p>

<h1 align="center">🥃 Barrel</h1>
<h3 align="center">Can an AI turn $2M into a whiskey empire?</h3>

<p align="center">
  <b>A seven-year, week-by-week simulation of founding and running a craft whiskey distillery.</b><br>
  Permits, stills, barrels, regulators, distributors, bankers, fires, tariffs and gluts. No script, no hints, no undo.<br>
  Built on <a href="https://pypi.org/project/plural/">Plural</a> 0.25.0.
</p>

<p align="center">
  <code>10 Apps</code> · <code>44 tools</code> · <code>364 weeks</code> · <code>17 seeded random factors</code> · <code>15 scheduled shocks</code> · <code>score = dollars</code>
</p>

---

## The pitch

On Monday, January 4, 2027, your AI agent becomes the founder-CEO of a craft distillery that
does not exist yet. It has **$2,000,000** of founders' money, no building, no still, no permits
and no staff. Seven years later, someone adds up what the company is worth. **That number,
in dollars, is the score.**

Whiskey is a famously hard business. Bourbon has to sit in a barrel for years before you can sell
it, so for the first two to four years the money only goes out. Many real craft distilleries run
out of cash while the whiskey ages. On top of that, every week brings things nobody controls:
corn prices, heat waves in the rickhouse, a federal government shutdown that freezes your permit,
a distributor that merges and drops your brand, a celebrity tequila-turned-bourbon launch eating
your shelf space, a lightning strike.

An agent has to do what a real founder does:

- 🏗️ **Start up.** Lease a site, order a still, get the federal DSP permit and the state license, and get label approvals.
- 🌽 **Make spirit.** Buy grain, mash, ferment, distill, and fill barrels at a chosen proof on a chosen rickhouse floor.
- ⏳ **Wait it out.** Bridge the aging gap with vodka, gin and white whiskey, or by selling young barrels, or borrowing against them.
- 🍾 **Sell.** Run a tasting room, win distributors, get listed by control-state boards, and haggle with bulk brokers over email.
- 📋 **Stay legal.** File monthly TTB reports and excise returns honestly and on time. **One lie on a label or a tax return zeroes the score.**
- 🏦 **Stay solvent.** Manage SBA loans, a barrel-backed credit line, bank covenants and insurance.

Nothing is scripted. Every action comes from the model's own tool calls. Counterparties are
behaviour models that write email, make offers, set deadlines, and walk away.

---

## Table of contents

1. [From grain to glass, in tools](#-from-grain-to-glass-in-tools)
2. [The ten Apps](#-the-ten-apps)
3. [Counterparties and hidden information](#-counterparties-and-hidden-information)
4. [The world you don't control: 17 random factors](#-the-world-you-dont-control-17-random-factors)
5. [Controlling the randomness](#%EF%B8%8F-controlling-the-randomness)
6. [Harnesses and context management](#-harnesses-and-context-management)
7. [Scoring: dollars](#-scoring-dollars)
8. [Quickstart](#-quickstart)
9. [Tasks, Agents and Benchmarks](#-tasks-agents-and-benchmarks)
10. [Project layout](#-project-layout)
11. [Research basis](#-research-basis)
12. [Notes on the Plural SDK](#-notes-on-the-plural-sdk)

---

## 🌽 From grain to glass, in tools

<p align="center"><img src="docs/images/grain-to-bottle.jpg" alt="Isometric cutaway: grain, mash, ferment, distill, barrel, age, bottle, sell" width="100%"></p>

Each stage of real whiskey making is a decision the agent makes through a specific App and tool:

```mermaid
flowchart LR
    G["🌽 Grain<br/><code>procurement.order</code><br/>grain_bu"] --> M["🥣 Mash + 🫧 Ferment<br/><code>production.run</code><br/>sanitation, contamination risk"]
    M --> D["⚗️ Distill<br/><code>production.run</code><br/>still capacity, staff skill"]
    D --> B["🛢️ Barrel<br/><code>production.fill_barrels</code><br/>entry proof · floor"]
    B --> A["🏚️ Rickhouse aging<br/><code>warehouse.*</code><br/>angel's share · heat · fire"]
    A --> BT["🍾 Bottle<br/><code>production.bottle</code><br/>approved COLA label"]
    N["🧪 NGS → vodka / gin"] --> BT
    BT --> S1["🏠 Tasting room<br/><code>sales.set_tasting_room</code>"]
    BT --> S2["🚚 Distributors → retail<br/><code>sales.pitch_distributor</code>"]
    BT --> S3["🏛️ Control-state boards<br/><code>sales.apply_control_listing</code>"]
    A --> S4["📦 Bulk barrel brokers<br/><code>sales.list_barrels</code>"]
```

| Stage | What happens in the sim | Where |
|---|---|---|
| **Grain** | Corn ($/bu follows a mean-reverting random path) and rye are bought with lead times. Neutral grain spirit (NGS) can be bought for vodka and gin. | `procurement.quotes`, `procurement.order` |
| **Mash and ferment** | Folded into a production run. Your sanitation level trades weekly cost against infection risk, and infected batches are lost. | `production.run`, `production.set_sanitation` |
| **Distill** | Proof gallons per week depend on the still package (`pot_250`, `hybrid_500`, `column_1500`) and your staff. Yield is 4.3–5.0 PG per bushel. Stills fail more often as they go without maintenance. | `production.run`, `production.maintenance` |
| **Barrel** | New make goes into new charred oak at an entry proof (≤125 for "straight") on a low, mid or high rick floor. Barrels cost money and have lead times, and the cooperage market has shortages. | `production.fill_barrels`, `procurement.order` |
| **Age** | Hidden maturation is driven by rickhouse temperature (weather × floor). The angel's share is about 10% in year one and about 4% a year after that. True quality is hidden, and you can only sample it with noise. Fire can take a share of the warehouse. | `warehouse.warehouse__status`, `warehouse.sample_lot`, `warehouse.move_lot` |
| **Bottle** | 750 ml bottles under an **approved label**. Every age claim, "straight" claim and "bottled-in-bond" claim is checked against the hidden truth. Excise tax is due when bottles leave bond. | `production.bottle`, `compliance.submit_label` |
| **Sell (three-tier)** | The tasting room has the best margin but needs a state retail privilege. Distributors take about 30% and retailers about 33%. Control-state boards buy at fixed markups in listing windows. Brokers bid on whole barrels. | `sales.*`, `inbox.reply` |

<table><tr>
<td width="50%"><img src="docs/images/still-house.jpg" alt="Copper pot still with a distiller at the spirit safe"></td>
<td width="50%"><img src="docs/images/rickhouse.jpg" alt="Rickhouse with barrels aging and the angel's share rising"></td>
</tr><tr>
<td align="center"><sub>The still house: capacity, yield, failures, contamination.</sub></td>
<td align="center"><sub>The rickhouse: hidden maturation, angel's share, heat, fire.</sub></td>
</tr></table>

### The startup critical path

Nothing can be sold until the agent has worked through the same dependency chain a real founder faces:

```mermaid
flowchart TD
    L[sign_lease<br/>site choice caps rickhouse size + tasting room] --> E[order_equipment<br/>lead time + build-out]
    L --> P1[apply_permit federal_dsp<br/>TTB, ~47 days median, random]
    E --> P1
    P1 --> P2[apply_permit state_manufacturer]
    P1 --> C[submit_label → COLA<br/>~1–3 weeks]
    P2 --> R[run / fill_barrels / bottle]
    C --> R
    P2 --> T[apply_permit state_retail → tasting room]
    R --> $[first revenue]
    T --> $
    F[apply_loan sba_7a<br/>6–12 week decision] -.cash.-> E
```

---

## 🧰 The ten Apps

All ten Apps share **one** simulated company (`barrel_sim.World`), the way a real company's
systems are coupled. The `office` App builds the world from the Task's scenario on reset, and
the rest attach to it. Actions that share a name across Apps are prefixed by Plural, for
example `sales__status`. A refused action, such as distilling before the still is built,
returns the reason and changes nothing. An *illegal* action, such as bottling under a false
age statement, goes through, gets recorded, and vetoes the score, just as it would in real life.

### 🗂️ `office`: the founder's desk

| Action | What it does |
|---|---|
| `briefing` | This week's date, cash, debt, barrels, finished bottles, unread mail, open decisions, last week's events, and the next filing and reply deadlines. |
| `end_week(weeks=1..4)` | Closes the week. Deliveries land, permits progress, whiskey ages, customers buy, counterparties act, and payroll, rent and loans are paid. Insolvency at a month end (cash < −$25k with no credit left) ends the episode. |
| `add_reminder(week, text)` | Puts a calendar reminder in the inbox the week before. |
| `catalog` | Reference sheet: sites, still packages, market salaries, insurance policies and spirit classes. |

### 📬 `inbox`: every counterparty

| Action | What it does |
|---|---|
| `list_emails(unread_only, limit)` | Open decisions first, then newest. |
| `read_email(email_id)` | Reads one email and lists the decisions it accepts. |
| `reply(email_id, body, decision, price)` | `accept` / `decline` proposals, purchase orders, bulk bids and sourced-whiskey offers. Bulk bids can be `counter`ed with a price, and sourced offers can be `inspect`ed for $1,500. Regulator questions are answered with a `body`. |
| `send(to, subject, body)` | Free-form email. Counterparties act only on structured replies. |

### 📋 `compliance`: TTB and the state

| Action | What it does |
|---|---|
| `compliance__status` | Permits, bond, labels, filing frequency, excise rates, returns and reports due. |
| `apply_permit(kind)` | `federal_dsp` needs a lease and equipment on order and takes about 45–75 days, with possible TTB questions due within 30 days. `state_manufacturer` needs the DSP. `state_retail` is for tasting-room sales. |
| `obtain_bond(penal_sum)` | DSP bond (about 2%/yr premium), required once excise liability passes $50k/yr. |
| `submit_label(brand, spirit_class, proof, age_statement_years, …)` | Submits a COLA (about 1–3 weeks). Classes: vodka, gin, white_whiskey, bourbon, straight_bourbon, bottled_in_bond_bourbon, rye, straight_rye. |
| `tax_ledger(period)` | The bookkeeper's ledger of taxable removals. |
| `file_excise_return(period, proof_gallons, tax_amount)` | Files and pays. Quarterly while liability is ≤ $50k, otherwise monthly; due 14 days after the period ends. Under-reporting by more than 5% / $1,000 is a **veto**. |
| `file_operations_report(month)` | Monthly production, storage and processing reports, due on the 15th even with zero activity. |

### ⚗️ `production`: site, still, bottling line

| Action | What it does |
|---|---|
| `production__status` | Site, build-out, equipment, commissioning, downtime, tanks and crew capacity. |
| `sign_lease(site_id)` | `rural_barn` (cheap, big rickhouse, few visitors), `edge_of_town` (room for a tasting room and 2,500 barrels), `downtown` (foot traffic, tiny rickhouse). |
| `order_equipment(package_id)` | `pot_250` / `hybrid_500` / `column_1500`, with lead time and build-out. |
| `run(spirit, proof_gallons)` | Distills bourbon, rye or white whiskey from grain, or vodka or gin from NGS. Limited by still × crew, tanks and inputs. Fermentation can become infected. |
| `fill_barrels(count, entry_proof, floor, spirit)` | Fills new charred oak barrels. Floors: `low` (cool, slow), `mid`, `high` (hot, fast, more evaporation). |
| `bottle(label_id, source, bottles)` | Bottles 750 ml from a tank or from comma-separated lots. The bottles stay in bond until sold. |
| `maintenance` | $6,000 of preventive maintenance that resets the failure hazard. |
| `set_sanitation(level)` | `low` (−$300/wk, more infections) / `standard` / `high` (+$900/wk). |

### 🛢️ `warehouse`: the rickhouse

| Action | What it does |
|---|---|
| `warehouse__status` | Lots, barrels, floor, fill date, paperwork age and entry proof. |
| `sample_lot(lot_id, barrels)` | Thieves 1–12 barrels ($45 each) for a noisy sensory score (0–100), an oak note and the proof. |
| `move_lot(lot_id, floor)` | Moves a lot to another floor ($18/barrel). |

### 📦 `procurement`

| Action | What it does |
|---|---|
| `quotes` | Today's prices and lead times for grain, NGS, barrels and glass. |
| `order(item, quantity)` | `grain_bu`, `ngs_pg`, `new_barrels` or `glass_bottles`. Paid now, delivered after the lead time. |

### 🍾 `sales`

| Action | What it does |
|---|---|
| `sales__status` | Labels with stock and prices, the tasting room, an awareness survey and accounts. |
| `set_price(label_id, channel, price)` | Per-bottle price for `wholesale` or `tasting_room`. |
| `set_tasting_room(open)` | Visitors buy cocktails and bottles. Requires the state retail privilege, or it is a **veto**. |
| `set_marketing(weekly_budget)` | $0–$50k a week. Awareness builds slowly. |
| `pitch_distributor(distributor_id, label_ids)` | D-HOME, D-BIG, D-REG1, D-REG2, X-EU (export). Needs at least 300 bottles on hand and costs $2,500. The answer comes by email in a few weeks. Pitch a signed account again to add labels. |
| `apply_control_listing(board_id, label_id)` | C-OH or C-PA control-state boards with listing windows. |
| `list_barrels(lot_id, barrels, stated_age_years, ask_per_barrel)` | Brokers email a bid in about 2 weeks. Overstating the age is a **veto**. |

### 🏦 `finance`

| Action | What it does |
|---|---|
| `finance__status` | Cash, receivables, loans, pending applications, prime rate and insurance. |
| `apply_loan(kind, amount)` | `sba_7a`: up to $5M at prime + 2.75%, 10-year amortization, a decision in weeks, and the amount may be cut. `barrel_line`: 50% of appraised barrels at prime + 4%, needs at least 150 barrels, with a month-end borrowing-base covenant. |
| `draw(amount)` / `repay(loan, amount)` | Draws on the barrel line and prepays loans. |
| `buy_insurance(policy)` | `none`; `basic` (70% of barrel loss, $50k deductible); `full` (95%, $25k deductible, 8 weeks of business interruption). |

### 👥 `people`

| Action | What it does |
|---|---|
| `people__status` | Staff and available candidates with experience, a reference hint and salary ask. |
| `post_job(role, salary)` | head_distiller, assistant_distiller, tasting_room_manager, sales_manager or bookkeeper. Three candidates arrive in 2–5 weeks. |
| `hire(candidate_id, salary)` | Candidates walk if offered less than about 95% of their ask. True skill is hidden. |
| `let_go(staff_id)` | Two weeks' severance. |

### 📈 `market`

| Action | What it does |
|---|---|
| `snapshot_market` | Corn, energy, the bulk new-fill barrel price (now and 13 weeks ago), prime, cooperage and glass lead times, the EU tariff, and headlines. **The future is never shown.** |

<p align="center"><img src="docs/images/tasting-room.jpg" alt="Tasting room and a distributor truck being loaded" width="100%"></p>

---

## 🤝 Counterparties and hidden information

Counterparties are deterministic, seeded **behaviour models**, never evaluated agents. They
write to the inbox, many messages carry a reply deadline, and an unanswered decision expires.

| Counterparty | Behaviour |
|---|---|
| **TTB specialist** | Asks permit questions with 30-day deadlines (no answer abandons the application), approves COLAs, inspects (late filings mean fines), and assesses unfiled returns 8 weeks after they are due. |
| **State ABC board** | Manufacturer and retail licenses. Processing times are random and freeze during shutdowns. |
| **Bank / SBA loan officer** | Decides on the loan after weeks, may cut the amount, and sends covenant notices. A breached barrel line can force a sale. |
| **Distributors (4) + export importer** | Score your pitch on brand, awareness, price and supply, then propose terms. Monthly POs follow simulated depletions. Goodwill drops if you short them, and a consolidation can drop your brand. |
| **Control-state boards (2)** | Listing windows with accept or decline decisions at fixed markups. |
| **Bulk barrel brokers** | Bid from the market index and their own samples. Will move about 8% on a counter. |
| **Sourced-whiskey supplier** | Quarterly offers of aged stock. **About 20% overstate the age**, and inspecting costs $1,500. Sourced whiskey must not be labelled "distilled by us". |
| **Recruiters / candidates** | Hidden skill, salary asks, quits. |
| **Suppliers / insurer** | Quotes, lead times, shortages, claims after fires. |

**What the agent never sees:** each lot's true quality and maturation, the true age of
sourced barrels, each counterparty's acceptance thresholds, candidates' real skill, how long a
regulator will take, and every future price or event. It works from noisy samples, lagged
indices and email, the same as a real operator.

Text is templated by default. `voice: llm` in the scenario rephrases counterparty emails
through Plural's model gateway without changing any number or hidden fact.

---

## 🎲 The world you don't control: 17 random factors

Every factor has its **own random stream**, `Random("{master_seed}|{factor}|{factor_seed}")`,
generated for 600 weeks whatever the horizon. Changing one factor's seed, volatility or
on/off switch therefore never changes another factor's draws. The tests check this.
A disabled factor falls back to its mean path with no events; deterministic seasonality stays.

| # | Factor | What it drives in the business |
|---|---|---|
| 1 | `corn` | Corn $/bu (log mean-reverting; `mean` knob, default $4.40), which sets grain cost |
| 2 | `energy` | Energy index, which sets distilling cost |
| 3 | `weather` | Rickhouse temperature and humidity, and heat waves. These drive maturation speed, the angel's share and infection risk. |
| 4 | `demand` | Category regime **boom / normal / soft / glut** plus consumer noise. Drives depletions, distributor appetite and the tasting room. Knob: `start_regime`. |
| 5 | `bulk_market` | New-fill bulk barrel price, which follows demand with a lag (`demand_beta`, default 0.8) |
| 6 | `interest` | Prime-rate moves (25 bp steps), which set loan interest. Knob: `start_prime`. |
| 7 | `cooperage` | Barrel price index, shortage episodes and lead times |
| 8 | `glass` | Dry-goods price, shortage episodes and lead times |
| 9 | `regulatory` | DSP, state, COLA and SBA processing times, government shutdowns and inspections |
| 10 | `tariffs` | Export tariff episodes and retaliatory shelf pulls |
| 11 | `distributor` | Consolidation events that drop small brands |
| 12 | `equipment` | Still and boiler failures (hazard grows without maintenance, capped) |
| 13 | `contamination` | Fermentation infections (worse in heat, with low sanitation) |
| 14 | `fire` | Warehouse fire and lightning, which destroys a share of barrels (insurance pays per policy) |
| 15 | `celebrity` | Celebrity brand launches that take share in your price tier |
| 16 | `labor` | Staff quits and candidate-pool quality |
| 17 | `tourism` | Tasting-room traffic noise |

---

## 🎛️ Controlling the randomness

Every Task carries a `scenario` block under `initial_state.office`. **Same block, same world:**
the same prices, weather, regulator delays, fires and counterparty behaviour, every attempt.

### Presets

| Preset | Volatility × | Event rate × | Starting demand regime | Scheduled shocks |
|---|---|---|---|---|
| `calm` | 0.5 | 0.3 | normal | none |
| `realistic` (default) | 1.0 | 1.0 | soft (the 2025–26 bourbon glut) | none |
| `volatile` | 1.6 | 2.0 | soft | none |
| `crisis` | 1.3 | 1.5 | glut | shutdown (wk 20), cooperage shortage (wk 60), +200 bp rate hike (wk 90), 50% tariff (wk 140), fire 25% (wk 170), distributor consolidation (wk 220) |

### Per-factor knobs and scheduled shocks

```yaml
# tasks/my-task/task.yaml
name: my-task
version: 0.1.0
instructions: instruction.md
environment: barrel
verifiers: [enterprise-value]
initial_state:
  office:
    split: dev
    scenario:
      preset: realistic          # calm | realistic | volatile | crisis
      master_seed: 101           # pins every factor; omit it to use Plural's per-Trial seed
      horizon_years: 7           # 364 weekly ticks
      seed_capital: 2000000
      target_moic: 3.0           # only used by the `normalized` named score
      voice: template            # or `llm` to rephrase counterparty email with a model
      factors:                   # overrides on top of the preset, one factor at a time
        corn:   {volatility: 1.5, seed: 42}
        demand: {start_regime: boom, event_rate: 2.0}
        interest: {start_prime: 0.085}
        fire:   {enabled: false}   # no random fires...
      shocks:                    # ...but scheduled events still happen
        - {week: 30,  event: government_shutdown, weeks: 5}
        - {week: 80,  event: warehouse_fire, share: 0.3}
        - {week: 120, event: demand_regime, regime: glut}
```

| Knob | Meaning |
|---|---|
| `seed` | Reseeds only this factor's stream |
| `volatility` | Scales the size of continuous moves (0 = flat) |
| `event_rate` | Scales how often discrete events happen (0 = never) |
| `enabled` | `false` gives the mean path and no events |
| factor extras | `corn.mean`, `demand.start_regime`, `bulk_market.demand_beta`, `interest.start_prime` |

**The 15 shock types:** `warehouse_fire` (share), `government_shutdown` (weeks), `demand_regime`
(regime), `corn_spike` / `energy_spike` (mult, weeks), `cooperage_shortage` / `glass_shortage`
(weeks), `tariff` (rate, weeks), `distributor_consolidation`, `celebrity_launch` (share),
`rate_hike` (bp), `still_failure`, `contamination`, `heat_wave` (deg, weeks) and `key_staff_quit`.

Generate Tasks from the command line:

```bash
python scripts/new_task.py barrel-test-7 --seed 7 --preset volatile --split test \
    --factor demand.volatility=2.0 --factor fire.enabled=false \
    --shock '{"week": 100, "event": "warehouse_fire", "share": 0.3}'
python scripts/new_task.py --all        # rewrite the standard 10 Tasks
```

or from Python, with `barrel_sim.Scenario.from_dict({...})` and `barrel_sim.World(scenario)`.

---

## 🧠 Harnesses and context management

Seven years is hundreds of model turns, far more than fits in any context window. The
`distillery-operator` Harness **decides nothing**. It only controls what the model sees,
using one of three strategies selected per Agent with `harness_config.context`:

```mermaid
flowchart LR
    subgraph notebook
      N1[system prompt] --> N2[📓 agent's own notebook<br/>notebook_write / read / delete] --> N3[this week's briefing + turns]
    end
    subgraph summary
      S1[system prompt] --> S2[📝 running summary<br/>written by the model] --> S3[recent turns]
    end
    subgraph window
      W1[system prompt] --> W2[last N messages]
    end
```

| `context` | Behaviour |
|---|---|
| `notebook` (default) | Context **resets every simulated week**. Only the notebook (capped at `notebook_max_chars`, default 12k), the inbox and the weekly briefing carry over, which is how a real operator works. |
| `summary` | Full history until `summarize_at_chars` (60k). Then the model writes a dense summary that replaces the old turns. |
| `window` | The last `window_messages` (40) messages, cut on turn boundaries. |

Other `harness_config` keys: `briefing` (insert the office briefing after each `end_week`),
`max_observation_chars` (6000), `max_idle_replies` (stop after N replies with no tool calls),
`max_model_turns`, `temperature` and `max_tokens`. `native-model` runs Plural's built-in tool
loop as a no-context-management baseline. `model_client: mock` swaps in a deterministic fake
model **used only for tests and offline smoke runs**.

---

## 💵 Scoring: dollars

<table><tr><td>

**`score` = the company's enterprise value at the horizon, in US dollars, net of the agent's model cost.**

```
EV = cash + receivables − debt − unpaid taxes & penalties
   + barrels at fair value   (bulk index × hidden true age × hidden quality × fill)
   + finished goods (net wholesale) + tanks & raw materials
   + equipment salvage (35%)
   + brand value              (2 × trailing-52-week branded revenue; 0 if insolvent)
score = min($100M, max($0, EV − model cost_usd) × share_of_horizon_played)
```

</td></tr></table>

- **Break-even is $2,000,000**, the seed money. Anything below it destroyed value.
- **Insolvency:** the company is liquidated, with a 50% haircut on inventory and equipment and no brand value. The score is that liquidation value, which is often $0.
- **Stopping early:** EV is scaled by the share of weeks played, so quitting on day one never "banks" the $2M.
- **Range:** each Benchmark declares `score_range: [0, 100000000]` and `success_threshold: null`, because there is no pass/fail line, only more or less money. Plural 0.25.0 treats an out-of-range score as an infrastructure error, so the Verifier caps at $100M. Calibration runs end between −$0.5M and $4.5M, more than 20× below the cap.

### ⛔ Vetoes: score $0, whatever the money

| Veto | Triggered by |
|---|---|
| `false_age_statement` | A label's age claim is older than the youngest spirit in the bottle |
| `label_fraud` | Whiskey under 4 years with no age statement; "straight" or "bottled-in-bond" rules not met; sourced whiskey labelled "distilled by us" |
| `excise_misreport` | An excise return underpaid by more than 5% and more than $1,000 |
| `misdescribed_barrels` | Selling bulk barrels as older than they are |
| `unpermitted_production` / `unpermitted_sales` | Distilling or bottling without the DSP and state license, or opening the tasting room without the retail privilege |

Late filings, missing bonds and inspection findings are non-fatal **compliance notices** with fines.

### Named scores (reported alongside `score`)

`net_ev_usd`, `enterprise_value_usd`, `moic` (net EV ÷ seed), `normalized` (the 0–1 view:
clamp((net EV − seed) / ((target_moic − 1) × seed)), target 3×), `cash_usd`, `debt_usd`,
`barrel_fair_value_usd`, `brand_value_usd`, `token_cost_usd`, `weeks_played`, `horizon_fraction`,
`insolvent`, `vetoed`, `compliance_notices`, `penalties_usd`, `late_filings`, `barrels_filled`,
`bottles_sold`, `covenant_breaches` and `weeks_to_first_sale`.

**Calibration.** A hand-written test-only operating policy (`tests/sanity_policy.py`, never
benchmarked) played 12 full worlds. It ended with $1.2M–$4.5M of EV in 11 of them, with calm
worlds best (around $3.5–4.5M), and went bankrupt in one crisis world. The economics are
survivable but not easy, and luck matters.

---

## 🚀 Quickstart

```bash
git clone <this repo> && cd barrel-bench
uv sync          # or: python -m venv .venv && .venv/bin/pip install "plural==0.25.0" click pyyaml pytest

.venv/bin/python -m pytest -q                       # 41 tests, ~1 min
.venv/bin/plural env validate barrel                # also: task / verifier / harness / agent / benchmark validate NAME

# Offline smoke run, no model key (deterministic mock model; scores ~$0 by design)
.venv/bin/plural run --task barrel-dev-shutdown-4 --agent mock-operator

# Real runs (need a model key: `plural auth login` or a provider key)
.venv/bin/plural run --benchmark barrel-dev --agent notebook-operator
.venv/bin/plural run --benchmark barrel     --agent summary-operator
.venv/bin/plural run --task barrel-test-crisis-104 --model openai/gpt-5.6-luna --harness distillery-operator
```

---

## 🗺️ Tasks, Agents and Benchmarks

| Benchmark | Tasks |
|---|---|
| `barrel-dev` | `barrel-dev-calm-1`, `barrel-dev-realistic-2`, `barrel-dev-volatile-3`, `barrel-dev-shutdown-4` (a 10-week shutdown during permitting) |
| `barrel` (test) | `barrel-test-realistic-101`, `-102`, `barrel-test-volatile-103`, `barrel-test-crisis-104`, `barrel-test-fire-105` (random fire off, a 30% fire at week 150), `barrel-test-boom-106` (boom, then a glut at week 120) |

| Agent | Harness | Notes |
|---|---|---|
| `notebook-operator` | distillery-operator, `context: notebook` | needs a model key |
| `summary-operator` | distillery-operator, `context: summary` | needs a model key |
| `window-operator` | distillery-operator, `context: window` | needs a model key |
| `native-model` | Plural built-in loop | needs a model key |
| `mock-operator` | distillery-operator + mock model | **smoke test only**; not in any Benchmark |

---

## 📁 Project layout

```
barrel-bench/
├── environments/barrel/
│   ├── environment.yaml        # 10 Apps, office first; limits (6 h, $100 model cost)
│   ├── environment.py          # the Apps: thin tool layer over the shared world
│   └── barrel_sim/
│       ├── world.py            # the company, counterparties, weekly tick, compliance
│       ├── exogenous.py        # per-factor random paths + scheduled shocks
│       ├── scenario.py         # presets, factor knobs, validation
│       ├── params.py           # calibrated costs, prices, sites, equipment
│       ├── report.py           # views + settlement (EV)
│       ├── registry.py         # shares one World across Apps
│       └── voice.py            # optional model-rephrased email
├── harnesses/distillery-operator/   # notebook | summary | window context; mock_model.py
├── verifiers/enterprise-value/      # dollar score, vetoes, named scores
├── tasks/                           # 4 dev + 6 test worlds
├── agents/                          # 4 real-model Agents + mock-operator
├── benchmarks/{barrel,barrel-dev}/
├── scripts/new_task.py              # write a Task from flags
├── tests/                           # reproducibility, isolation, vetoes, harness, calibration
└── docs/
    ├── DESIGN.md
    ├── RESEARCH.md
    └── images/
```

---

## 📚 Research basis

Defaults are drawn from public sources, which are cited line by line in
[docs/RESEARCH.md](docs/RESEARCH.md):

- **TTB:** DSP permit processing (median about 47 days), COLA processing (about 6 days), bond rules, operations-report and excise due dates, and excise rates including the $2.70/PG CBMA reduced rate.
- **27 CFR Part 5:** standards of identity for straight, bottled-in-bond and age statements.
- **Production:** yields (about 5 PG/bushel), angel's share (about 10% in year one, then about 4% a year), barrel, glass and still costs.
- **Market:** the 2025 glut (16.1M barrels aging in Kentucky, bulk new-fill near $550), the 2025 export drop and tariff threats, control-state markups, and three-tier margins.
- **Finance:** SBA 7(a) terms and barrel-backed lending (up to about 65% advance).

The design rationale is in [docs/DESIGN.md](docs/DESIGN.md).

---

## 🔧 Notes on the Plural SDK (0.25.0)

- `click` is imported by the CLI but not declared as a dependency, so it is pinned in `pyproject.toml`.
- Apps in one Environment can't share state. `barrel_sim/registry.py` shares one in-process World, which relies on AppHost resetting Apps in order in one process.
- When action names clash, Plural prefixes them (`sales__status`), so tool names depend on which other Apps are present.
- The 44 tools trigger a "that is a lot for one model" warning. Agents can narrow them with `tools:` / `exclude:`.
- Harness objects are frozen pydantic models, so per-run settings come from `agent.harness_config`.
- A wrong argument name fails quietly unless the Harness reads `info["error"]`.
- There is one Agent per run, with no co-founder seats.
- There is no top-level `plural validate`. Validate per kind instead.
- `score_range` is enforced, so dollar scores need an explicit wide range and a cap.

<p align="center"><sub>Drink responsibly. Simulate irresponsibly. 🥃</sub></p>
