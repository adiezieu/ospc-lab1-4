"""Splits the order values by region and month, one file each, for the stats workers."""

import os

import numpy as np
import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
folder = os.path.join(OUT, "stats_input")

if os.path.isdir(folder) and len(os.listdir(folder)) == 72:
    print("stats: input ready")
else:
    os.makedirs(folder, exist_ok=True)
    orders = pd.read_csv(DATA, usecols=["order_date", "region", "quantity", "unit_price"],
                         dtype={"region": "category", "quantity": "int16"})
    orders["month"] = orders["order_date"].str[5:7].astype("int8")
    value = (orders["quantity"] * orders["unit_price"]).to_numpy()
    for (region, month), rows in orders.groupby(["region", "month"], observed=True).indices.items():
        np.save(os.path.join(folder, f"{region}_{month:02d}.npy"), value[rows])
    print(f"stats: input ready ({len(os.listdir(folder))} files)")
