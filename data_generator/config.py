"""
Configuration and static reference data for the synthetic data generator.

All business-realism numbers in this file (city weights, product prices,
stage-duration ranges, cancellation rates, etc.) are DESIGNED / ASSUMED
values chosen to make the generated dataset behave like a plausible
delivery business. They are configuration, not measured facts about any
real company, and are documented here so they can be pointed to directly
in an interview ("this rate is a config value I chose, here's why").
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class GeneratorConfig:
    number_of_customers: int = 50_000
    number_of_orders: int = 100_000
    number_of_riders: int = 2_000
    number_of_days: int = 90
    cities: List[str] = field(default_factory=lambda: list(CITY_META.keys()))
    random_seed: int = 42
    # Fixed reference "now" for the dataset snapshot, so re-running the
    # generator on a different calendar day still produces the same content.
    end_date: datetime = datetime(2025, 6, 30, 23, 59, 59)
    output_dir: str = "output"  # relative to the working directory generate_data.py is run from

    # Data-quality issue injection (all five issue types requested).
    inject_data_quality_issues: bool = True
    quality_issue_rate: float = 0.02  # base rate; each issue function uses this unless noted


# ----------------------------------------------------------------------------
# City reference data: state, approximate coordinates for jitter, zip prefix,
# and a relative order-volume weight. Weights are an assumed distribution for
# scenario variety (e.g. "Austin is our biggest market"), not real
# demographic or company data.
# ----------------------------------------------------------------------------
CITY_META: Dict[str, dict] = {
    "Austin":   {"state": "TX", "lat": 30.2672, "lon": -97.7431, "zip_prefix": "787", "weight": 0.22},
    "Denver":   {"state": "CO", "lat": 39.7392, "lon": -104.9903, "zip_prefix": "802", "weight": 0.18},
    "Portland": {"state": "OR", "lat": 45.5152, "lon": -122.6784, "zip_prefix": "972", "weight": 0.12},
    "Chicago":  {"state": "IL", "lat": 41.8781, "lon": -87.6298, "zip_prefix": "606", "weight": 0.20},
    "Miami":    {"state": "FL", "lat": 25.7617, "lon": -80.1918, "zip_prefix": "331", "weight": 0.16},
    "Seattle":  {"state": "WA", "lat": 47.6062, "lon": -122.3321, "zip_prefix": "981", "weight": 0.12},
}

FIRST_NAMES = [
    "Alice", "Bob", "Carla", "David", "Emma", "Frank", "Grace", "Hassan", "Irene", "Jack",
    "Karen", "Liam", "Maria", "Noah", "Olivia", "Paul", "Quinn", "Rachel", "Sam", "Tara",
    "Umar", "Vera", "Will", "Xena", "Yusuf", "Zoe", "Aaron", "Bella", "Chris", "Dana",
]

LAST_NAMES = [
    "Johnson", "Smith", "Diaz", "Lee", "Wilson", "Miller", "Kim", "Ali", "Chen", "Brown",
    "Nguyen", "Garcia", "Patel", "Clark", "Lewis", "Walker", "Young", "King", "Wright", "Scott",
    "Torres", "Reed", "Cook", "Bell", "Murphy", "Bailey", "Rivera", "Cooper", "Hughes", "Price",
]

STREET_NAMES = [
    "Congress Ave", "6th St", "Larimer St", "16th St", "Broadway", "Main St",
    "Market St", "5th Ave", "Union St", "Pine St", "Oak St", "Cedar Ave",
    "Maple Dr", "Lakeview Rd", "Riverside Dr", "Highland Ave",
]

# (product_name, category, unit_price) — a small fictitious menu.
PRODUCT_CATALOG = [
    ("Cheeseburger", "main", 8.50), ("Veggie Burger", "main", 7.75),
    ("Pizza Slice", "main", 4.25), ("Taco Plate", "main", 10.00),
    ("Chicken Bowl", "main", 11.50), ("Sandwich", "main", 7.50),
    ("Bagel", "main", 3.00), ("Garden Salad", "main", 9.00),
    ("Fries", "side", 4.00), ("Chicken Wings", "side", 6.50),
    ("Chips", "side", 2.00), ("Onion Rings", "side", 4.50),
    ("Soda", "drink", 2.50), ("Coffee", "drink", 2.75),
    ("Iced Tea", "drink", 2.25), ("Bottled Water", "drink", 1.50),
    ("Churros", "dessert", 3.50), ("Brownie", "dessert", 3.25),
]

PAYMENT_METHODS = ["card", "upi", "cash", "wallet"]
PAYMENT_WEIGHTS = [0.45, 0.25, 0.15, 0.15]

VEHICLE_TYPES = ["bike", "scooter", "car"]
VEHICLE_WEIGHTS = [0.45, 0.35, 0.20]

# Order lifecycle stages, in order — must match database/schema.sql CHECK constraints.
ORDER_STAGES = ["placed", "confirmed", "preparing", "ready_for_pickup", "out_for_delivery", "delivered"]

# Outcome probabilities for a generated order. Assumed/configured, not measured.
P_CANCELLED_EARLY = 0.05   # cancelled right after placed/confirmed, before preparing
P_CANCELLED_MID = 0.02     # cancelled during preparing, before a rider is involved
P_FAILED_DELIVERY = 0.01   # rider picked up but delivery ultimately failed
# remainder (~0.92) completes normally, subject to the in-progress snapshot window below

# Rider city distribution is deliberately NOT identical to the customer/order
# city distribution above — it's shaped to create a supply/demand imbalance
# (e.g. Portland and Miami relatively understaffed) so that a later analytics
# phase has a genuine "is rider supply sufficient?" question to answer from
# the data. This is a designed characteristic of the synthetic dataset, not
# a claimed real-world finding.
RIDER_CITY_WEIGHTS: Dict[str, float] = {
    "Austin": 0.28,
    "Denver": 0.18,
    "Portland": 0.08,
    "Chicago": 0.20,
    "Miami": 0.10,
    "Seattle": 0.16,
}

# Orders placed within this many hours of end_date are treated as "still in
# progress" (order lifecycle truncated) to simulate a live operational
# snapshot rather than a fully closed-out historical dataset.
IN_PROGRESS_WINDOW_HOURS = 6
