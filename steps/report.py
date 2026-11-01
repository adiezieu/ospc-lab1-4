"""Revenue by region and month (revenue_by_region_month.csv)."""

import os

import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
os.makedirs(OUT, exist_ok=True)

orders = pd.read_csv(DATA)
size = orders.memory_usage(deep=True).sum() / 2**20
print(f"report: loaded {len(orders):,} orders ({size:.0f} MiB)")

orders["order_date"] = pd.to_datetime(orders["order_date"])
orders["revenue"] = orders["quantity"] * orders["unit_price"]

# Calculate monthly revenue directly without creating separate monthly tables
month = orders["order_date"].dt.month  # Extract each order's month (1–12)
table = orders.groupby(["region", month])["revenue"].sum().unstack()  # Sum revenue by region and month

table.round(2).to_csv(os.path.join(OUT, "revenue_by_region_month.csv"))
print("report: done")
