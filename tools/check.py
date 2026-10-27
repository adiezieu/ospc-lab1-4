"""Checks the outputs of the pipeline and the members' folders.

Usage, inside the container, from the repository folder:
    python3 tools/check.py
"""

import glob
import os
import re
import subprocess

import numpy as np
import pandas as pd

DATA = os.environ.get("DATA", os.path.expanduser("~/data/sales_2025.csv"))
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
REGIONS = ["Benelux", "DACH", "France", "Iberia", "Italy", "Nordics"]


def result(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


# Reference values, computed in chunks so that they fit in memory
revenue = None
rows = None
segments = None
total_revenue, n_orders = 0.0, 0
for chunk in pd.read_csv(DATA, usecols=["order_date", "region", "quantity", "unit_price"], chunksize=1_000_000):
    value = chunk["quantity"] * chunk["unit_price"]
    month = chunk["order_date"].str[5:7].astype(int).rename("month")
    by_month = value.groupby([chunk["region"], month]).sum()
    revenue = by_month if revenue is None else revenue.add(by_month, fill_value=0)
    by_region = chunk["region"].value_counts()
    rows = by_region if rows is None else rows.add(by_region, fill_value=0)
    size = np.select([value >= 500, value >= 100], ["large", "medium"], "small")
    seg = "Q" + ((month - 1) // 3 + 1).astype(str) + " " + size
    counts = pd.crosstab(chunk["region"], seg)
    segments = counts if segments is None else segments.add(counts, fill_value=0)
    total_revenue += value.sum()
    n_orders += len(chunk)

# Revenue by region and month
path = os.path.join(OUT, "revenue_by_region_month.csv")
if os.path.exists(path):
    table = pd.read_csv(path, index_col=0)
    table.columns = table.columns.astype(int)
    expected = revenue.unstack()
    ok = table.shape == expected.shape and np.allclose(table.loc[expected.index, expected.columns], expected, atol=0.01)
    result("revenue_by_region_month.csv", ok)
else:
    result("revenue_by_region_month.csv", False, "missing")

# Extracts
for region in REGIONS:
    path = os.path.join(OUT, "extracts", f"{region}.csv")
    n = sum(1 for _ in open(path)) if os.path.exists(path) else 0
    result(f"extracts/{region}.csv", n == rows[region], f"{n:,} rows, expected {int(rows[region]):,}")

# Audit trail
path = os.path.join(OUT, "audit_2025.csv")
if os.path.exists(path):
    audit = pd.read_csv(path, header=None, names=["order_id", "region", "revenue"])
    ok = len(audit) == n_orders and abs(audit["revenue"].sum() - total_revenue) < 0.01 * n_orders
    result("audit_2025.csv", ok, f"{len(audit):,} lines, expected {n_orders:,}")
else:
    result("audit_2025.csv", False, "missing")

# Segments
path = os.path.join(OUT, "segments.csv")
if os.path.exists(path):
    table = pd.read_csv(path, index_col=0)
    ok = table.reindex_like(segments).fillna(0).astype(int).equals(segments.astype(int))
    result("segments.csv", ok)
else:
    result("segments.csv", False, "missing")

# Stats
path = os.path.join(OUT, "stats.csv")
if os.path.exists(path):
    stats = pd.read_csv(path, header=None, names=["region", "month", "mean", "low", "high"])
    ok = len(stats) == 72 and ((stats["low"] <= stats["mean"]) & (stats["mean"] <= stats["high"])).all()
    result("stats.csv", ok, f"{len(stats)} region-months, expected 72")
else:
    result("stats.csv", False, "missing")

# Members
print()
users = []
if os.path.exists("TEAM.md"):
    for line in open("TEAM.md"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) > 1:
            users += re.findall(r"^@([A-Za-z0-9-]+)$", cells[1])
for user in users:
    folder = os.path.join("members", user)
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, "*")))
    authors = subprocess.run(["git", "log", "--format=%an <%ae>", "--", folder],
                             capture_output=True, text=True).stdout.split("\n")
    authors = sorted({a for a in authors if a})
    has_all = {"machine.txt", "measurements.md", "sweep.csv"} <= set(files)
    result(f"members/{user}", has_all, f"files: {', '.join(files) or 'none'}; committed by: {', '.join(authors) or 'nobody yet'}")
if not users:
    print("TEAM.md lists no GitHub usernames yet (write them as @username in the second column).")
