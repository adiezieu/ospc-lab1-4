"""Audit trail: one line per order with its revenue (audit_2025.csv)."""

import os

import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "audit_2025.csv")

orders = pd.read_csv(DATA, usecols=["order_id", "region", "quantity", "unit_price"])
orders["revenue"] = orders["quantity"] * orders["unit_price"]

open(path, "w").close()
for order in orders.itertuples():
    # Open and close the file for every order, so that each line is
    # saved on disk even if the job crashes halfway.
    with open(path, "a") as f:
        f.write(f"{order.order_id},{order.region},{order.revenue:.2f}\n")
print(f"audit: {len(orders):,} lines written")
