import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

# Same data as before, chart only - no title/subtitle/table.
cells = ["32-bit", "24-bit", "20-bit", "16-bit"]
db_size_label = ["48.8 MB", "36.6 MB", "36.6 MB", "24.4 MB"]
runtime = [23.611, 22.783, 22.820, 20.203]
cache_miss = [59.43, 53.41, 53.23, 41.20]
classified = [84.26, 84.27, 85.00, 91.29]

BLUE = "#2f6fed"
BLUE_DARK = "#173f8f"
BLUE_SHADOW = "#c7d5fb"
ORANGE = "#df7f42"
INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#9aa1ac"
LINE = "#e6e8ed"

fig, ax = plt.subplots(figsize=(9.2, 5.3), dpi=280)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

x = np.arange(4)
bar_w = 0.56
ax.grid(axis="y", color=LINE, linewidth=0.8, zorder=0)

# clean rounded-top bars, solid vivid blue
for xi, r in zip(x, runtime):
    bar = FancyBboxPatch((xi - bar_w / 2, 0), bar_w, r,
                           boxstyle="round,pad=0,rounding_size=0.09",
                           linewidth=1.4, edgecolor=BLUE_DARK, facecolor=BLUE, zorder=3)
    ax.add_patch(bar)

ax.set_xlim(-0.6, 3.6)
ax.set_ylim(0, 31.5)
ax.set_yticks(range(0, 31, 5))
ax.tick_params(axis="y", labelsize=10.5, colors=INK_SOFT)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(INK_SOFT)
ax.spines["left"].set_linewidth(0.9)
ax.spines["bottom"].set_color(INK)
ax.spines["bottom"].set_linewidth(1.1)

ax2 = ax.twinx()
ax2.plot(x, cache_miss, color=ORANGE, linewidth=2.4, linestyle="-", marker="o",
          markersize=9, markerfacecolor=ORANGE, markeredgecolor="white",
          markeredgewidth=2.2, zorder=5)
ax2.set_ylim(0, 100)
ax2.set_yticks(range(0, 101, 20))
ax2.tick_params(axis="y", labelsize=10.5, colors=ORANGE)
ax2.set_ylabel("cache-miss rate (%)", fontsize=11, color=ORANGE, fontweight="bold", rotation=270, labelpad=18)
for s in ["top", "left"]:
    ax2.spines[s].set_visible(False)
ax2.spines["right"].set_color(ORANGE)
ax2.spines["right"].set_linewidth(0.9)

# classified % + caption, above each bar
for xi, r, c in zip(x, runtime, classified):
    ax.text(xi, r + 2.7, f"{c:.2f}%", ha="center", fontsize=13.5, fontweight="bold", color=INK, zorder=6)
    ax.text(xi, r + 1.55, "classified", ha="center", fontsize=8.8, color=INK_FAINT, zorder=6)

# runtime value, white bold, inside the bar near its base
for xi, r in zip(x, runtime):
    ax.text(xi, 1.35, f"{r:.2f}s", ha="center", fontsize=12, fontweight="bold", color="white", zorder=6)

# cache-miss pill label, on the marker
for xi, cm in zip(x, cache_miss):
    ax2.annotate(f"{cm:.1f}%", (xi, cm), ha="center", va="center", fontsize=9.8,
                  fontweight="bold", color="white", zorder=7,
                  bbox=dict(boxstyle="round,pad=0.34", fc=ORANGE, ec="white", lw=1.8))

# x tick labels: cell name (bold) + db size (grey) underneath
ax.set_xticks(x)
ax.set_xticklabels([])
for xi, cell, sz in zip(x, cells, db_size_label):
    ax.text(xi, -2.1, cell, ha="center", fontsize=13, fontweight="bold", color=INK)
    ax.text(xi, -3.6, sz, ha="center", fontsize=9.8, color=INK_FAINT)

legend_handles = [
    FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.08",
                     facecolor=BLUE, edgecolor=BLUE_DARK, linewidth=1.1),
    plt.Line2D([0], [0], color=ORANGE, marker="o", markerfacecolor=ORANGE,
                markeredgecolor="white", linewidth=2.4, markersize=8),
]
ax.legend(legend_handles, ["runtime (s)", "cache-miss (%)"], loc="upper center",
           bbox_to_anchor=(0.5, 1.13), ncol=2, fontsize=10, frameon=False,
           handlelength=1.6, columnspacing=1.8)

fig.tight_layout(pad=1.0)
fig.savefig("k2_cellwidth_chart_only.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_cellwidth_chart_only.png")
