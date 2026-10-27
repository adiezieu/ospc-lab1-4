"""Plots the elapsed time of the stats step against the number of workers, one line per laptop.

Usage, inside the container, from the repository folder:
    python3 tools/plot_sweep.py
Reads members/*/sweep.csv and writes results/sweep.png (median of the runs).
"""

import csv
import glob
import os
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MARKERS = ["o", "s", "^", "D", "v", "h"]
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e5e4e0"
WORKERS = [1, 2, 4, 8, 16]


def load():
    laptops = []
    for path in sorted(glob.glob(os.path.join("members", "*", "sweep.csv"))):
        user = path.split(os.sep)[1]
        runs = {}
        with open(path) as f:
            for row in csv.DictReader(f):
                runs.setdefault(int(row["workers"]), []).append(float(row["elapsed_s"]))
        cpus = "?"
        info = os.path.join(os.path.dirname(path), "machine.txt")
        if os.path.exists(info):
            for line in open(info):
                if line.startswith("cpus_in_container:"):
                    cpus = line.split(":")[1].strip()
        laptops.append((user, cpus, {w: statistics.median(t) for w, t in runs.items()}))
    if len(laptops) > len(COLORS):
        print(f"Only the first {len(COLORS)} laptops are plotted.")
    return laptops[: len(COLORS)]


def main():
    laptops = load()
    if not laptops:
        raise SystemExit("No members/*/sweep.csv yet: run tools/sweep.sh first.")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2})
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    ends = []
    for i, (user, cpus, median) in enumerate(laptops):
        ws = [w for w in WORKERS if w in median]
        ax.plot(ws, [median[w] for w in ws], color=COLORS[i], marker=MARKERS[i], markersize=7, linewidth=2,
                markeredgecolor="white", markeredgewidth=1.5, label=f"{user} ({cpus} CPUs)", zorder=3)
        ends.append([median[ws[-1]], ws[-1], user])

    ax.set_xscale("log", base=2)
    ax.set_xticks(WORKERS, [str(w) for w in WORKERS])
    ax.minorticks_off()
    ax.set_xlim(0.85, 19)
    top = max(t for _, _, m in laptops for t in m.values())
    ax.set_ylim(0, top * 1.12)
    ax.set_xlabel("Workers")
    ax.set_ylabel("Seconds")
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(length=0)
    fig.text(0.07, 0.965, "Elapsed time of the stats step", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.07, 0.925, "Median of the runs on each laptop. Lower is faster.", fontsize=10, color=INK_2)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, fontsize=9, handlelength=2.5)

    # Up to four laptops: also a label at the end of each line, moved apart when they would overlap.
    if len(laptops) <= 4:
        ends.sort()
        gap = top * 0.05
        for k in range(1, len(ends)):
            ends[k][0] = max(ends[k][0], ends[k - 1][0] + gap)
        for y, w, user in ends:
            ax.annotate(user, (w, y), xytext=(10, 0), textcoords="offset points", va="center",
                        fontsize=9, color=INK_2, annotation_clip=False)

    fig.subplots_adjust(left=0.09, right=0.82 if len(laptops) <= 4 else 0.97, top=0.8, bottom=0.11)
    os.makedirs("results", exist_ok=True)
    fig.savefig(os.path.join("results", "sweep.png"), facecolor="white")
    print("Saved results/sweep.png")


if __name__ == "__main__":
    main()
