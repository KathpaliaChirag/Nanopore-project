"""
Generates a dark-terminal-style table of approximate Sniper simulation run time
by read count, on Luna's S0 (no software cache) binary against the 50MB DB.

UPDATE (2026-09-11): the 2,000-read row is now REAL MEASURED data - the S0
variant of the 2000reads job finished at 44,716s (12.42 hrs). 10,000 reads and
the full 104,832-read file were never run - those rows are ESTIMATES ONLY, now
refit using BOTH real data points (50 reads @ 188s, 2000 reads @ 44,716s)
instead of just the tiny 50-read run: fixed_cost=71.78s, per_base_rate=
(44716-188)/(35,100,000-91,372)=0.0012719 s/base. This revised model raised the
10,000-read estimate from ~16.9hrs to ~21.3hrs and the full-file estimate from
~4.2 to ~5.3 days versus the original 50-read-only fit - a reminder that
extrapolating from a single small data point understated the true cost.
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
    ("2,000 reads",          "35.1M",  "12.42 hrs\n(44,716s)", "MEASURED\n(S0, done)"),
    ("10,000 reads",         "60.2M",  "~21.3 hrs", "ESTIMATED\n(not run)"),
    ("104,832 reads\n(full file)", "357.6M", "~5.3 days", "ESTIMATED\n(not run)"),
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
        color = "#7fd97f" if status.startswith("MEASURED") else WARN
        cell.set_text_props(fontfamily="monospace", color=color)

fig.text(0.02, 0.035,
          "10/50/2,000-read rows are measured (S0, no cache, Luna, 50MB DB). 10,000-read and the\n"
          "full file are extrapolated from a fixed+variable cost model refit on BOTH real points\n"
          "(50 reads and 2,000 reads): fixed ~71.8s DB load + ~1.272ms/base - not actually run,\n"
          "treat as rough estimates, not measurements, until confirmed.",
          fontsize=7.3, color="#999999", fontfamily="monospace")

for ext in ("png", "pdf"):
    path = os.path.join(OUT_DIR, f"fig8_readcount_time_estimate.{ext}")
    fig.savefig(path, dpi=300, facecolor=BG)
    print(f"wrote {path}")
