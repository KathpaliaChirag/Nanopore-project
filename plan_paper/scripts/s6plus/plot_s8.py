#!/usr/bin/env python3
"""
plot_s8.py — grouped bar chart of S8 (stream all input files through one
reader instead of one parallel region per file) vs stock kraken2 (S0),
wall-clock seconds, at 1,872,777 reads (16 FASTQ files, see legend caption
for the combined input size) / 32 threads / Luna.

All 4 standard databases benchmarked. 16GB/103GB were re-measured 2026-10-07
on request to complete the table (50MB/8GB are the original 2026-09-24 run).
On 103GB the speedup shrinks to near 1x: that database's wall time is
dominated by loading the hash table (S10 fixes that separately), not by
file-switching overhead, so S8 has little left to save there.

Data is hard-coded from the raw interleaved benchmark logs:
  plan_paper/data/s6plus/s8_vs.log         (50MB, 8GB, mean of 3 reps)
  plan_paper/data/s6plus/s8_full16_103.log (16GB, 103GB, mean of 3 reps)

Run on Luna (matplotlib already present in the snn venv):
  ~/snn/venv/bin/python3 plot_s8.py

Or anywhere with matplotlib installed:
  pip install matplotlib
  python3 plot_s8.py

Writes s8_file_streaming.png next to this script.
"""

import os
import matplotlib.pyplot as plt
import numpy as np

# db name -> (stock seconds, S8 seconds), mean of 3 interleaved reps
DATA = {
    "50MB":  (15.61, 11.07),
    "8GB":   (19.69, 14.62),
    "16GB":  (25.13, 19.11),
    "103GB": (89.92, 85.34),
}

# pod5 input: 16 separate FASTQ files (not one combined file), total reads
# and combined size shown in the chart's legend/caption
TOTAL_READS = "1,872,777"
TOTAL_INPUT_SIZE = "~12.3GB across 16 pod5-derived FASTQ files (189MB-1.04GB each)"

dbs = list(DATA.keys())
stock = [DATA[d][0] for d in dbs]
s8 = [DATA[d][1] for d in dbs]
speedup = [s0 / s1 for s0, s1 in zip(stock, s8)]

x = np.arange(len(dbs))
bar_w = 0.36

fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)

bars0 = ax.bar(x - bar_w / 2, stock, width=bar_w, label="Stock (S0)", color="#2a78d6")
bars1 = ax.bar(x + bar_w / 2, s8, width=bar_w, label="One-stream input (S8)", color="#eb6834")

for bars in (bars0, bars1):
    for b in bars:
        h = b.get_height()
        ax.annotate(f"{h:.1f}s", xy=(b.get_x() + b.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, color="#333333")

for i, sp in enumerate(speedup):
    top = max(stock[i], s8[i])
    ax.annotate(f"{sp:.2f}× faster", xy=(x[i], top),
                xytext=(0, 20), textcoords="offset points",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color="#111111")

ax.set_xticks(x)
ax.set_xticklabels(dbs)
ax.set_ylabel("Wall-clock time (seconds, lower is better)")
ax.set_title("16 input files as one stream vs stock's one-region-per-file (S8)\n"
              f"{TOTAL_READS} reads · 32 threads · Luna · mean of 3 interleaved reps")
ax.legend(loc="upper left", frameon=False,
          title=f"Input: {TOTAL_INPUT_SIZE}", title_fontsize=8)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.set_ylim(0, max(stock) * 1.3)
ax.grid(axis="y", linestyle="-", linewidth=0.5, color="#e0e0e0", zorder=0)
ax.set_axisbelow(True)

fig.tight_layout()

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s8_file_streaming.png")
fig.savefig(out_path)
print(f"wrote {out_path}")
