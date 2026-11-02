"""Number of orders per region, quarter and order size (segments.csv)."""
# GenAI note: this fix was done with the advice of Claude (Anthropic). Prompt: 'here is segments.py and its cProfile output, find where the time goes and fix it'.

import os

import numpy as np
import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
os.makedirs(OUT, exist_ok=True)

parts = []
for chunk in pd.read_csv(
    DATA,
    usecols=["order_date", "region", "quantity", "unit_price"],
    chunksize=1_000_000,
):
    # Whole-column operations: no Python loop over the rows.
    quarter = pd.to_datetime(chunk["order_date"], format="%Y-%m-%d").dt.quarter
    value = chunk["quantity"] * chunk["unit_price"]
    size = np.select([value >= 500, value >= 100], ["large", "medium"], default="small")
    segment = ("Q" + quarter.astype(str) + " " + pd.Series(size, index=chunk.index)).rename("segment")
    parts.append(chunk.groupby(["region", segment]).size())

counts = pd.concat(parts).groupby(level=["region", "segment"]).sum()
table = counts.unstack(fill_value=0)
table.to_csv(os.path.join(OUT, "segments.csv"))
print("segments: done")
