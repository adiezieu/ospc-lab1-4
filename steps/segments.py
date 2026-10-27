"""Number of orders per region, quarter and order size (segments.csv)."""

import os
from datetime import datetime

import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
os.makedirs(OUT, exist_ok=True)

orders = pd.read_csv(DATA, usecols=["order_date", "region", "quantity", "unit_price"])


def segment(order):
    quarter = (datetime.strptime(order.order_date, "%Y-%m-%d").month - 1) // 3 + 1
    value = order.quantity * order.unit_price
    if value >= 500:
        size = "large"
    elif value >= 100:
        size = "medium"
    else:
        size = "small"
    return f"Q{quarter} {size}"


counts = {}
for order in orders.itertuples(index=False):
    key = (order.region, segment(order))
    counts[key] = counts.get(key, 0) + 1

table = pd.Series(counts).rename_axis(["region", "segment"]).unstack(fill_value=0)
table.to_csv(os.path.join(OUT, "segments.csv"))
print("segments: done")
