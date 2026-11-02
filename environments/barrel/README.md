# barrel

A craft whiskey distillery's desk for 40 quarters (10 years), as one Python App over the
deterministic simulator in `barrel_sim/`.

- **Hidden per batch:** peak maturity (5-9 effective years) and peak quality. Floors age at
  different speeds (F1 0.85x, F2 1x, F3 1.25x), new wood faster than refill. Past its peak a
  batch declines (over-oaked).
- **Visible:** paperwork age, lab samples (noisy score, oak note), orders and prices by age
  statement, broker offers, the bank's borrowing base.
- **World path by seed:** a craft boom (index up to ~1.6) then a glut, a cooperage shortage
  (new casks 3x for ~6 quarters), a heat wave that over-ages the top floor, a celebrity brand
  dumping sourced 2-6-year whiskey, a bank that cuts its advance rate from 50% to 30% (22% in
  `glut`) through the glut, and broker lots that are sometimes younger or worse than stated.
- **Outcome:** cash - debt + 45% of list x quality multiplier for casks + 60% for bottles.
- **Vetoes:** bottling under a false age statement; selling casks above their true grade
  without a supporting lab read from the last year.

`playbook.py` holds the scripted policies (vendored into `harnesses/barrel-scripted/vendor`);
`policies.py` holds the hindsight oracle and the per-world anchors.
