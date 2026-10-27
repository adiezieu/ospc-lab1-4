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

# The monthly tables first, then the whole year
months = [orders[orders["order_date"].dt.month == m] for m in range(1, 13)]
year = pd.concat(months)

table = year.groupby(["region", year["order_date"].dt.month])["revenue"].sum().unstack()
table.round(2).to_csv(os.path.join(OUT, "revenue_by_region_month.csv"))
print("report: done")
