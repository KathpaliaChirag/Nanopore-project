#!/usr/bin/env python3
"""
plot_s10.py — grouped bar chart of S10 (parallel hash-table load) vs stock
kraken2 (S0), wall-clock seconds across the project's 4 standard database
sizes, at 1,872,777 reads / 32 threads / Luna.

Data is hard-coded from the raw interleaved benchmark log:
  plan_paper/data/s6plus/s10_full.log  (mean of 3 reps per cell)

Run on Luna (matplotlib already present in the snn venv):
  ~/snn/venv/bin/python3 plot_s10.py

Or anywhere with matplotlib installed:
  pip install matplotlib
  python3 plot_s10.py

Writes s10_parallel_load.png next to this script.
"""

import os
import matplotlib.pyplot as plt
import numpy as np

# db name -> (stock seconds, S10 seconds), mean of 3 interleaved reps
DATA = {
    "50MB":  (16.45, 11.61),
    "8GB":   (20.73, 11.96),
    "16GB":  (25.42, 13.80),
    "103GB": (90.47, 34.46),
}

dbs = list(DATA.keys())
stock = [DATA[d][0] for d in dbs]
s10 = [DATA[d][1] for d in dbs]
speedup = [s0 / s1 for s0, s1 in zip(stock, s10)]

x = np.arange(len(dbs))
bar_w = 0.36

fig, ax = plt.subplots(figsize=(8, 5), dpi=150)

bars0 = ax.bar(x - bar_w / 2, stock, width=bar_w, label="Stock (S0)", color="#2a78d6")
bars1 = ax.bar(x + bar_w / 2, s10, width=bar_w, label="Parallel load (S10)", color="#eb6834")

# value labels on top of each bar
for bars in (bars0, bars1):
    for b in bars:
        h = b.get_height()
        ax.annotate(f"{h:.1f}s", xy=(b.get_x() + b.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, color="#333333")

# speedup badge above each db's pair of bars
for i, sp in enumerate(speedup):
    top = max(stock[i], s10[i])
    ax.annotate(f"{sp:.2f}× faster", xy=(x[i], top),
                xytext=(0, 20), textcoords="offset points",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color="#111111")

ax.set_xticks(x)
ax.set_xticklabels(dbs)
ax.set_ylabel("Wall-clock time (seconds, lower is better)")
ax.set_title("Hash-table load: stock vs 32-thread parallel pread (S10)\n"
              "1,872,777 reads · 32 threads · Luna · mean of 3 interleaved reps")
ax.legend(loc="upper left", frameon=False)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(stock) * 1.25)
ax.grid(axis="y", linestyle="-", linewidth=0.5, color="#e0e0e0", zorder=0)
ax.set_axisbelow(True)

fig.tight_layout()

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s10_parallel_load.png")
fig.savefig(out_path)
print(f"wrote {out_path}")
