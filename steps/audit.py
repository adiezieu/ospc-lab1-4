"""Audit trail: one line per order with its revenue (audit_2025.csv)."""

import os

import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "audit_2025.csv")

orders = pd.read_csv(DATA, usecols=["order_id", "region", "quantity", "unit_price"])
orders["revenue"] = orders["quantity"] * orders["unit_price"]

# GenAI note: this fix was written with Claude (Anthropic). Prompt: 'walk me through Task 3 of Lab 1 and fix audit.py'.
# Open the file once and let Python buffer the lines: a few large
# write() calls instead of one open/write/close per order.
with open(path, "w") as f:
    for order in orders.itertuples():
        f.write(f"{order.order_id},{order.region},{order.revenue:.2f}\n")
print(f"audit: {len(orders):,} lines written")
