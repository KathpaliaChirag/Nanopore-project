"""
Full detailed results table for the hardware-only LLC associativity sweep
(base kraken2, NO software cache - the "point 2" experiment CK asked to see
in full: cycles, IPC, wallclock per run). All 24 runs, from
cache_simulation/measurements/hw_assoc_sweep_2026-09-14.csv.
"""

import matplotlib.pyplot as plt
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

BG = "#0d0d0d"
FG = "#d6d6d6"
HEAD_BG = "#1a1a1a"
GROUP_BG = "#151515"
BORDER = "#3a3a3a"
REAL = "#7fd97f"

# reads, assoc, cycles_M, ipc, wallclock_s, l2_hit_pct, nuca_hit_pct
rows = [
    (10, 1,  13.6, 1.64, "115s",  "1.18%", "0.0003%"),
    (10, 4,  13.7, 1.64, "117s",  "1.18%", "0.0005%"),
    (10, 8,  13.6, 1.64, "117s",  "1.18%", "0.0004%"),
    (10, 15, 13.7, 1.64, "116s",  "1.18%", "0.0004%"),
    (10, 16, 13.7, 1.64, "114s",  "1.18%", "0.0003%"),
    (10, 30, 13.7, 1.64, "116s",  "1.18%", "0.0004%"),
    (50, 1,  24.4, 1.47, "193s",  "0.41%", "0.0147%"),
    (50, 4,  24.4, 1.47, "194s",  "0.40%", "0.0179%"),
    (50, 8,  24.4, 1.47, "193s",  "0.40%", "0.0180%"),
    (50, 15, 24.4, 1.47, "193s",  "0.41%", "0.0180%"),
    (50, 16, 24.4, 1.47, "193s",  "0.41%", "0.0189%"),
    (50, 30, 24.4, 1.47, "194s",  "0.41%", "0.0179%"),
    (100, 1,  870.0, 1.58, "1h 48m", "0.21%", "0.0332%"),
    (100, 4,  877.2, 1.57, "1h 48m", "0.21%", "0.0356%"),
    (100, 8,  869.9, 1.58, "1h 48m", "0.21%", "0.0361%"),
    (100, 15, 870.4, 1.58, "1h 48m", "0.21%", "0.0363%"),
    (100, 16, 869.8, 1.58, "1h 48m", "0.21%", "0.0364%"),
    (100, 30, 877.3, 1.57, "1h 47m", "0.21%", "0.0362%"),
    (500, 1,  4528.2, 1.59, "9h 06m", "0.20%", "0.0316%"),
    (500, 4,  4524.0, 1.59, "9h 13m", "0.20%", "0.0326%"),
    (500, 8,  4537.9, 1.59, "9h 11m", "0.20%", "0.0336%"),
    (500, 15, 4534.5, 1.59, "9h 05m", "0.20%", "0.0336%"),
    (500, 16, 4526.4, 1.59, "9h 01m", "0.20%", "0.0335%"),
    (500, 30, 4523.2, 1.59, "9h 09m", "0.20%", "0.0334%"),
]

col_labels = ["Reads", "Assoc.", "Cycles (M)", "IPC", "Wallclock", "L2 hit%", "NUCA hit%"]
col_widths = [0.10, 0.12, 0.16, 0.10, 0.16, 0.16, 0.20]

fig, ax = plt.subplots(figsize=(11.0, 9.2))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.axis("off")
ax.set_position([0.02, 0.07, 0.96, 0.81])

cell_text = [[str(r[0]), f"{r[1]}-way", f"{r[2]:,.1f}", f"{r[3]:.2f}", r[4], r[5], r[6]] for r in rows]

tbl = ax.table(cellText=cell_text, colLabels=col_labels, loc="center",
               cellLoc="left", colWidths=col_widths)
tbl.auto_set_font_size(False)
tbl.set_fontsize(9.5)
tbl.scale(1, 1.55)

group_starts = {0: True}
prev_reads = None
for i, r in enumerate(rows):
    group_starts[i] = (r[0] != prev_reads)
    prev_reads = r[0]

for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor(BORDER)
    cell.set_linewidth(0.6)
    cell.PAD = 0.02
    cell.set_text_props(fontfamily="monospace", color=FG)
    if r == 0:
        cell.set_facecolor(HEAD_BG)
        cell.set_text_props(fontfamily="monospace", color=FG, fontweight="bold")
        continue
    data_row = rows[r - 1]
    cell.set_facecolor(GROUP_BG if (data_row[0] // 100) % 2 == 0 else BG)
    if group_starts[r - 1]:
        cell.set_linewidth(1.4)
        cell.visible_edges = "T" + cell.visible_edges if hasattr(cell, "visible_edges") else "closed"
    if c == 1 and data_row[1] == 15:
        cell.set_text_props(fontfamily="monospace", color=REAL, fontweight="bold")

fig.suptitle("Hardware LLC associativity sweep - full results\n(base kraken2, NO software cache, 50MB DB)",
             fontsize=13, y=0.99, color=FG)
fig.text(0.02, 0.035,
          "24 runs: 6 real hardware LLC associativities (1/4/8/15/16/30-way) x 4 workload sizes\n"
          "(10/50/100/500 reads). Green = Luna's real 15-way. No software S2 cache in any row (base\n"
          "kraken2 binary throughout). Within each read-count group, cycles/IPC/hit-rates are flat -\n"
          "the null result: hardware associativity alone has no measurable effect here.",
          fontsize=8, color="#999999", fontfamily="monospace")

for ext in ("png", "pdf"):
    path = os.path.join(OUT_DIR, f"fig13_hw_assoc_full_table.{ext}")
    fig.savefig(path, dpi=300, facecolor=BG)
    print(f"wrote {path}")
