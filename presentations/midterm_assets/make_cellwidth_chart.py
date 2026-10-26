import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Data exactly as given (pod5_2.fastq, 151,591 reads, 499.98 Mbp, 1 thread,
# stock kraken2 2.17.1, no prefetch, mean of 3 runs).
cells = ["32-bit", "24-bit", "20-bit", "16-bit"]
key_bits = [26, 18, 14, 10]
db_size_mb = [48.8, 36.6, 36.6, 24.4]
db_size_label = ["48.8 MB", "36.6 MB", "36.6 MB", "24.4 MB"]
runtime = [23.611, 22.783, 22.820, 20.203]
vs_32bit = [None, -3.5, -3.3, -14.4]
speedup = ["1.00x", "1.00x", "1.00x", "1.00x"]
cache_miss = [59.43, 53.41, 53.23, 41.20]
llc_miss = [54.53, 49.27, 48.85, 38.53]
ipc = [1.38, 1.49, 1.49, 1.65]
classified = [84.26, 84.27, 85.00, 91.29]

BLUE = "#3f6a91"
BLUE_DARK = "#2c4d6b"
ORANGE = "#df7f42"
INK = "#1a1d21"
INK_SOFT = "#5c6572"
INK_FAINT = "#9aa1ac"
LINE = "#e6e8ed"

fig = plt.figure(figsize=(9.6, 9.6), dpi=250)
fig.patch.set_facecolor("white")
gs = fig.add_gridspec(2, 1, height_ratios=[3.3, 1.4], hspace=0.42,
                       top=0.88, bottom=0.06, left=0.09, right=0.93)
ax = fig.add_subplot(gs[0])
ax_tbl = fig.add_subplot(gs[1])
ax_tbl.axis("off")

# ---------------- main chart ----------------
ax.set_facecolor("white")
x = np.arange(4)
ax.grid(axis="y", color=LINE, linewidth=0.8, zorder=0)

bars = ax.bar(x, runtime, width=0.56, color=BLUE, edgecolor=BLUE_DARK, linewidth=1, zorder=3)
ax.set_ylim(0, 30)
ax.set_yticks(range(0, 31, 5))
ax.tick_params(axis="y", labelsize=10, colors=INK_SOFT)
ax.set_ylabel("runtime (seconds)", fontsize=11, color=INK, fontweight="bold")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(INK_SOFT)
ax.spines["bottom"].set_color(INK)

ax2 = ax.twinx()
ax2.plot(x, cache_miss, color=ORANGE, linewidth=2.2, linestyle="-", marker="o",
          markersize=9, markerfacecolor=ORANGE, markeredgecolor="white",
          markeredgewidth=2, zorder=4)
ax2.set_ylim(0, 100)
ax2.set_yticks(range(0, 101, 20))
ax2.tick_params(axis="y", labelsize=10, colors=ORANGE)
ax2.set_ylabel("cache-miss rate (%)", fontsize=11, color=ORANGE, fontweight="bold")
for s in ["top", "left"]:
    ax2.spines[s].set_visible(False)
ax2.spines["right"].set_color(ORANGE)

# classified % + caption, above each bar
for xi, r, c in zip(x, runtime, classified):
    ax.text(xi, r + 2.6, f"{c:.2f}%", ha="center", fontsize=13, fontweight="bold", color=INK, zorder=5)
    ax.text(xi, r + 1.55, "classified", ha="center", fontsize=8.5, color=INK_FAINT, zorder=5)

# runtime value, white bold, inside the bar near its base
for xi, r in zip(x, runtime):
    ax.text(xi, 1.3, f"{r:.2f}s", ha="center", fontsize=11.5, fontweight="bold", color="white", zorder=5)

# cache-miss pill label, on the marker
for xi, cm in zip(x, cache_miss):
    ax2.annotate(f"{cm:.1f}%", (xi, cm), ha="center", va="center", fontsize=9.5,
                  fontweight="bold", color="white", zorder=6,
                  bbox=dict(boxstyle="round,pad=0.32", fc=ORANGE, ec="white", lw=1.6))

# x tick labels: cell name (bold) + db size (grey) underneath
ax.set_xticks(x)
ax.set_xticklabels([])
for xi, cell, sz in zip(x, cells, db_size_label):
    ax.text(xi, -2.2, cell, ha="center", fontsize=12.5, fontweight="bold", color=INK)
    ax.text(xi, -3.7, sz, ha="center", fontsize=9.5, color=INK_FAINT)
ax.set_xlabel("compact-hash cell width", fontsize=10.5, color=INK_SOFT, labelpad=34)

legend_handles = [
    mpatches.Patch(facecolor=BLUE, edgecolor=BLUE_DARK, label="runtime (s)"),
    plt.Line2D([0], [0], color=ORANGE, marker="o", markerfacecolor=ORANGE,
                markeredgecolor="white", linewidth=2.2, label="cache-miss (%)"),
]
ax.legend(handles=legend_handles, loc="upper right", fontsize=9.5, frameon=False)

fig.text(0.09, 0.975, "Runtime vs cache-miss rate, by cell width",
          fontsize=17, fontweight="bold", color=INK, ha="left", va="top")
fig.text(0.09, 0.945,
          "1 thread · pod5_2.fastq (151,591 reads, 499.98 Mbp) · stock kraken2 2.17.1, no prefetch · mean of 3 runs",
          fontsize=9, color=INK_FAINT, style="italic", ha="left", va="top")

# ---------------- data table ----------------
col_labels = ["CELL", "KEY_BITS", "DB SIZE", "RUNTIME", "VS 32-BIT", "SPEED-UP",
              "CACHE-MISS", "LLC-MISS", "IPC", "CLASSIFIED"]
rows = []
for i in range(4):
    vs = "baseline" if vs_32bit[i] is None else f"{vs_32bit[i]:.1f}%"
    rows.append([
        cells[i], str(key_bits[i]), db_size_label[i], f"{runtime[i]:.3f} s", vs,
        speedup[i], f"{cache_miss[i]:.2f}%", f"{llc_miss[i]:.2f}%", f"{ipc[i]:.2f}",
        f"{classified[i]:.2f}%",
    ])

tbl = ax_tbl.table(cellText=rows, colLabels=col_labels, loc="upper center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.9)
for (r, c), cell in tbl.get_celld().items():
    cell.set_edgecolor(LINE)
    cell.set_linewidth(0.8)
    if r == 0:
        cell.set_text_props(color=INK_FAINT, fontweight="bold")
        cell.set_facecolor("white")
        cell.get_text().set_fontsize(7.6)
    else:
        cell.set_facecolor("white")
        if c == 0:
            cell.set_text_props(fontweight="bold", color=INK)
        elif c == 9:
            color = ORANGE if r == 4 else INK
            weight = "bold" if r == 4 else "normal"
            cell.set_text_props(color=color, fontweight=weight)
        else:
            cell.set_text_props(color=INK_SOFT)

fig.text(0.125, 0.015,
          "The figure above each bar is the classification rate, identical at every thread count. "
          "Speed-up is against the same database at 1 thread. Cache-miss and LLC-miss are the share "
          "of cache references and of LL-cache accesses respectively.",
          fontsize=7.6, color=INK_FAINT, wrap=True)

fig.savefig("k2_cellwidth_chart.png", facecolor="white", bbox_inches="tight", pad_inches=0.25)
plt.close(fig)
print("saved k2_cellwidth_chart.png")
