"""
Generates a dark-terminal-style table of approximate Sniper simulation run time
by read count, extrapolated from the real fixed+variable cost model derived
from actual measured 10/50-read Luna runs this week.

IMPORTANT: only the 10-read and 50-read rows are REAL MEASURED data. 2,000 reads
is a live, still-running job (not finished after 11+ hours as of writing) shown
as an in-progress lower bound, not a completed measurement. 10,000 reads and the
full 104,832-read file were never run - those rows are ESTIMATES ONLY, computed
from: fixed_cost (~96s, DB load) + total_bases * per_base_rate, where
per_base_rate = (188s - 96s) / 91,372 bases, from the real 50-read Luna/50MB run.
"""

import matplotlib.pyplot as plt
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

BG = "#0d0d0d"
FG = "#d6d6d6"
HEAD_BG = "#1a1a1a"
BORDER = "#3a3a3a"
WARN = "#e0a030"

rows = [
    ("10 reads",             "~15K",   "111s",      "MEASURED"),
    ("50 reads",             "91K",    "188s",      "MEASURED"),
    ("2,000 reads",          "35.1M",  "~9.8 hrs",  "IN PROGRESS\n(>11 hrs, not done)"),
    ("10,000 reads",         "60.2M",  "~16.9 hrs", "ESTIMATED\n(not run)"),
    ("104,832 reads\n(full file)", "357.6M", "~4.2 days", "ESTIMATED\n(not run)"),
]

fig, ax = plt.subplots(figsize=(11.5, 4.6))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.axis("off")
ax.set_position([0.02, 0.20, 0.96, 0.76])

col_labels = ["Workload", "Total\nbases", "Sim. run time\n(S0, Luna, 50MB DB)", "Status"]
cell_text = [list(r) for r in rows]
col_widths = [0.22, 0.16, 0.30, 0.32]

tbl = ax.table(cellText=cell_text, colLabels=col_labels, loc="center",
               cellLoc="left", colWidths=col_widths)
tbl.auto_set_font_size(False)
tbl.set_fontsize(10.5)
tbl.scale(1, 2.6)

for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor(BORDER)
    cell.set_linewidth(0.8)
    cell.PAD = 0.02
    cell.set_text_props(fontfamily="monospace", color=FG)
    if r == 0:
        cell.set_facecolor(HEAD_BG)
        cell.set_text_props(fontfamily="monospace", color=FG, fontweight="bold")
    else:
        cell.set_facecolor(BG)
    # color the status column
    if c == 3 and r > 0:
        status = rows[r - 1][3]
        color = "#7fd97f" if status == "MEASURED" else WARN
        cell.set_text_props(fontfamily="monospace", color=color)

fig.text(0.02, 0.035,
          "Only 10/50-read rows are measured. 2,000-read is a live job still running past 11 hours\n"
          "(not yet complete). 10,000-read and the full file are extrapolated from the real fixed+\n"
          "variable cost model (fixed ~96s DB load + ~1.007ms/base), not actually run - treat as\n"
          "rough estimates, not measurements, until confirmed.",
          fontsize=7.3, color="#999999", fontfamily="monospace")

for ext in ("png", "pdf"):
    path = os.path.join(OUT_DIR, f"fig8_readcount_time_estimate.{ext}")
    fig.savefig(path, dpi=300, facecolor=BG)
    print(f"wrote {path}")
