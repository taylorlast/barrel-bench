"""Real-ish constants for Barrel v2. Sources are listed in docs/RESEARCH.md."""

START_DATE = (2027, 1, 4)  # a Monday

SITES = {
    "rural_barn": {"desc": "Converted barn on 6 acres, 40 min from the city. Cheap, big rickhouse, few visitors.",
                   "rent_month": 6_500, "buildout_cost": 180_000, "buildout_weeks": 14, "rick_capacity": 1_800,
                   "traffic": 0.45, "deposit": 13_000},
    "edge_of_town": {"desc": "Industrial flex building by the interstate. Room for a tasting room and 2,500 barrels.",
                     "rent_month": 11_000, "buildout_cost": 260_000, "buildout_weeks": 16, "rick_capacity": 2_500,
                     "traffic": 1.0, "deposit": 22_000},
    "downtown": {"desc": "Historic warehouse in the bar district. Heavy foot traffic, tiny rickhouse.",
                 "rent_month": 19_000, "buildout_cost": 380_000, "buildout_weeks": 20, "rick_capacity": 600,
                 "traffic": 2.1, "deposit": 38_000},
}

EQUIPMENT = {
    "pot_250": {"desc": "250-gal copper pot still, 2 fermenters, small mash tun", "cost": 140_000, "lead_weeks": 8,
                "whiskey_pg_week": 140, "neutral_pg_week": 420, "pg_per_bushel": 4.4, "quality": 54},
    "hybrid_500": {"desc": "500-gal hybrid pot/column with 4 fermenters and 1,500 gal cooker", "cost": 320_000,
                   "lead_weeks": 14, "whiskey_pg_week": 380, "neutral_pg_week": 900, "pg_per_bushel": 4.7,
                   "quality": 56},
    "column_1500": {"desc": "18-inch continuous column, 6 fermenters, automated cook", "cost": 780_000,
                    "lead_weeks": 22, "whiskey_pg_week": 1_100, "neutral_pg_week": 2_200, "pg_per_bushel": 5.0,
                    "quality": 50},
}

ROLES = {
    "head_distiller": 88_000, "assistant_distiller": 52_000, "tasting_room_manager": 55_000,
    "sales_manager": 82_000, "bookkeeper": 58_000,
}

SPIRITS = ("bourbon", "rye", "vodka", "gin", "white_whiskey")
WHISKEY = ("bourbon", "rye")
CLASSES = ("vodka", "gin", "white_whiskey", "bourbon", "straight_bourbon", "bottled_in_bond_bourbon",
           "rye", "straight_rye")
# reference FOB wholesale $/750ml bottle at a "fair" quality of 60
REF_WHOLESALE = {"vodka": 9.0, "gin": 12.0, "white_whiskey": 14.0, "bourbon": 22.0, "straight_bourbon": 27.0,
                 "bottled_in_bond_bourbon": 33.0, "rye": 23.0, "straight_rye": 28.0}
BOTTLE_GAL = 0.198129  # 750 ml in US gallons
BARREL_GAL = 53.0
FET_GENERAL = 13.50
FET_CBMA_LOW = 2.70
FET_CBMA_HIGH = 13.34
CBMA_TIER_PG = 100_000
BOND_THRESHOLD = 50_000

GRAIN_PER_PG_COST_MULT = {"bourbon": 1.25, "rye": 1.6}
ENERGY_PER_PG = 0.55
YEAST_PER_PG = 0.35
GIN_BOTANICALS_PER_PG = 0.80
NGS_PER_PG = 3.40
BARREL_BASE_PRICE = 380.0
DRY_GOODS_PER_BOTTLE = 3.20
G_AND_A_WEEK = 900.0
UTILITIES_WEEK = 1_100.0
PAYROLL_BURDEN = 1.20
TANK_CAPACITY_PG = 4_000

INSURANCE = {
    "none": {"premium_year": 0, "cover": 0.0, "deductible": 0, "bi_weekly": 0},
    "basic": {"premium_year": 26_000, "cover": 0.70, "deductible": 50_000, "bi_weekly": 0},
    "full": {"premium_year": 48_000, "cover": 0.95, "deductible": 25_000, "bi_weekly": 6_000},
}

DISTRIBUTORS = {
    "D-HOME": {"name": "Bluegrass Beverage Co. (home state)", "kind": "distributor", "size": 1.0, "threshold": 0.30,
               "margin": 0.28},
    "D-BIG": {"name": "Continental Wine & Spirits (5 states)", "kind": "distributor", "size": 3.2, "threshold": 0.62,
              "margin": 0.30},
    "D-REG1": {"name": "Ohio Valley Craft Distributors", "kind": "distributor", "size": 1.2, "threshold": 0.42,
               "margin": 0.28},
    "D-REG2": {"name": "Great Lakes Fine Spirits", "kind": "distributor", "size": 1.4, "threshold": 0.48,
               "margin": 0.29},
    "C-OH": {"name": "Buckeye State Liquor Board (control)", "kind": "control", "size": 1.3, "threshold": 0.45,
             "margin": 0.0},
    "C-PA": {"name": "Keystone Liquor Control Board (control)", "kind": "control", "size": 1.6, "threshold": 0.52,
             "margin": 0.0},
    "X-EU": {"name": "EuroCask Imports (EU export)", "kind": "export", "size": 1.1, "threshold": 0.50, "margin": 0.25},
}
