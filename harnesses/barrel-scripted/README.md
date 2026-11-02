# barrel-scripted

Plays one of the scripted distillery policies in `vendor/playbook.py` (a copy of
`environments/barrel/barrel_sim/playbook.py`) through the Environment's own actions,
with JSON output and no model calls.

| `harness_config.policy` | What it does |
|---|---|
| `do_nothing` | Calls `end_quarter` 40 times. Floor reference. |
| `baseline` | Fill 200 new casks on F2 a quarter, bottle everything at 4 years, ship what is ordered. Score 0 by construction. |
| `cellar` | Samples, ladders bottling across age statements to orders, holds promising spirit, sells over-oaked casks honestly, buys only inspected bulk lots, sizes fills to the bank's headroom. No hidden information. |

Refused actions come back as an empty observation with `info["error"]`; the Harness
turns them into `ValueError` so the policy can skip them.
