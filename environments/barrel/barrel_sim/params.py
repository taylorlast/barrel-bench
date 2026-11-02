"""Barrel world constants. All money in USD, volume in proof gallons (PG)."""

QUARTERS = 40                      # 10 years
CASK_PG = 60.0                     # proof gallons in a freshly filled 53-gal barrel
NEW_MAKE_PER_PG = 9.0              # grain, energy, labor to distill
STILL_CAP = 300                    # casks the stills can fill per quarter
FLOOR_CAP = 2500                   # casks per warehouse floor
FIXED_COST = 140_000.0             # overhead per quarter
BOTTLING_PER_PG = 12.0             # glass, labels, labor
SAMPLE_COST = 60.0                 # lab cost per cask thiefed
SAMPLE_LOSS_PG = 0.5               # spirit used per sample
INSPECT_OFFER_COST = 1_500.0       # paperwork audit + lab on a broker lot

FLOORS = {
    # maturity years gained per calendar year, angel's share per quarter
    "F1": {"rate": 0.85, "angel": 0.010, "desc": "ground floor, cool and slow"},
    "F2": {"rate": 1.00, "angel": 0.013, "desc": "middle floor"},
    "F3": {"rate": 1.25, "angel": 0.018, "desc": "top floor, hot and fast"},
}
WOODS = {
    "new": {"cost": 260.0, "rate": 1.15, "qbonus": 4.0},
    "refill": {"cost": 110.0, "rate": 0.80, "qbonus": -4.0},
}

AGES = (2, 4, 6, 8, 10, 12)        # legal age statements on the label
LIST_PG = {2: 55.0, 4: 85.0, 6: 125.0, 8: 170.0, 10: 230.0, 12: 300.0}  # at quality 70, index 1
BASE_DEMAND = {2: 5000.0, 4: 4200.0, 6: 3000.0, 8: 1900.0, 10: 1000.0, 12: 500.0}  # PG/quarter
SWING = {2: 1.4, 4: 1.2, 6: 1.0, 8: 0.8, 10: 0.6, 12: 0.5}  # sensitivity to the craft cycle
GROWTH_PER_Q = 0.0075
DISTRIBUTORS = {"northline": 0.55, "coastal": 0.45}
SHORTFALL_PENALTY = 0.25           # of list value, per PG promised and not shipped

GRADES = ("standard", "good", "premium")
GRADE_FLOOR = {"standard": 0.0, "good": 65.0, "premium": 78.0}
GRADE_MID = {"standard": 58.0, "good": 71.0, "premium": 84.0}

# Bank: borrowing base = advance rate x bank's appraisal of casks + 0.6 x finished goods at list.
ADVANCE_RATE = 0.50
ADVANCE_RATE_TIGHT = 0.30
ADVANCE_RATE_TIGHT_GLUT = 0.22
CREDIT_LIMIT = 9_000_000.0
INTEREST_Q = 0.02
BREACH_FEE = 0.01
SWEEP_HAIRCUT = 0.55

# End-of-horizon marks (conservative, fixed schedule)
MARK_CASK = 0.45                   # x list(age tier) x quality mult x PG
MARK_FG = 0.60

START_CASH = 600_000.0
OPENING_LEVERAGE = 0.8


def age_tier(years: float) -> int:
    """Highest legal age statement a cask of this calendar age can carry (0 = too young)."""
    best = 0
    for a in AGES:
        if years + 1e-9 >= a:
            best = a
    return best


def qmult(q: float) -> float:
    return max(0.25, min(1.8, (max(q, 1.0) / 70.0) ** 1.5))


def grade_of(q: float) -> str:
    g = "standard"
    for name in GRADES:
        if q >= GRADE_FLOOR[name]:
            g = name
    return g
