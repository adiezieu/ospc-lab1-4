"""Worker K of N: bootstrap confidence intervals for its share of the region-months."""

import os
import sys

import numpy as np

RESAMPLES = 1000

k, n = int(sys.argv[1]), int(sys.argv[2])
OUT = os.environ.get("OUT", os.path.expanduser("~/data/out"))
folder = os.path.join(OUT, "stats_input")
names = sorted(os.listdir(folder))[k::n]

rng = np.random.default_rng(2025 + k)
lines = []
for name in names:
    values = np.load(os.path.join(folder, name))
    means = np.empty(RESAMPLES)
    for b in range(RESAMPLES):
        means[b] = values[rng.integers(0, len(values), len(values))].mean()
    low, high = np.percentile(means, [2.5, 97.5])
    region, month = name[:-4].rsplit("_", 1)
    lines.append(f"{region},{month},{values.mean():.2f},{low:.2f},{high:.2f}\n")

with open(os.path.join(OUT, "stats", f"part_{k:02d}.csv"), "w") as f:
    f.writelines(lines)
