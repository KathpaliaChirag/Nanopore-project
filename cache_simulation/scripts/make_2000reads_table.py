"""
Dark-terminal-style table of the 2000-reads job results (same 50MB DB -
sample_targeted - as the fair batch). Companion to fig9/fig10's bar charts,
in table form for slides.

CORRECT FRAMING: this DB was already known to be worse-with-cache at just 50
reads (fair batch, 2026-09-09) - this job confirms that holds at 40x more
reads. It does NOT test whether the real ~2x speedup on the 8GB+ DBs survives
at large read counts (untested, open). 16-way still running as of writing.
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
CRIT = "#e06060"
GOOD = "#7fd97f"

# variant, cycles_M, ratio vs S0, wallclock, status
rows = [
    ("S0 (no cache)", "6,354.0",  "1.00x",  "12.42 hrs", "BASELINE"),
    ("1-way",         "8,336.3",  "1.31x",  "12.36 hrs", "SLOWER"),
    ("4-way",         "8,159.1",  "1.28x",  "12.67 hrs", "SLOWER"),
    ("8-way",         "8,508.1",  "1.34x",  "13.63 hrs", "SLOWER"),
    ("16-way",        "...",      "...",    "running",   "PENDING"),
]

fig, ax = plt.subplots(figsize=(9.6, 4.0))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.axis("off")
ax.set_position([0.02, 0.20, 0.96, 0.76])

col_labels = ["Variant", "Cycles (M)", "vs. no cache", "Wallclock", "Status"]
cell_text = [list(r) for r in rows]
col_widths = [0.24, 0.19, 0.19, 0.18, 0.20]

tbl = ax.table(cellText=cell_text, colLabels=col_labels, loc="center",
               cellLoc="left", colWidths=col_widths)
tbl.auto_set_font_size(False)
tbl.set_fontsize(11)
tbl.scale(1, 2.5)

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
    if c == 4 and r > 0:
        status = rows[r - 1][4]
        color = {"BASELINE": FG, "SLOWER": CRIT, "PENDING": WARN}[status]
        cell.set_text_props(fontfamily="monospace", color=color, fontweight="bold" if status == "SLOWER" else "normal")

fig.text(0.02, 0.035,
          "2000-read workload, sample_targeted (50MB) DB - the SAME DB the fair batch used at 50\n"
          "reads, where cache already lost to no-cache. This job confirms that holds (and slightly\n"
          "worsens) at 40x more reads. Says nothing about the 8GB+ DBs, where cache DOES help\n"
          "(~2x) at 50 reads - untested at large read counts, remains open. 16-way still running.",
          fontsize=7.3, color="#999999", fontfamily="monospace")

for ext in ("png", "pdf"):
    path = os.path.join(OUT_DIR, f"fig11_2000reads_results_table.{ext}")
    fig.savefig(path, dpi=300, facecolor=BG)
    print(f"wrote {path}")
