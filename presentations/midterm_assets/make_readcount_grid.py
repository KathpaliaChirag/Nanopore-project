import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Real data: Luna, kraken2-fresh-bin-s0 (v2.17.1, latest), no --memory-mapping,
# 32T pinned (numactl node0), perf stat, 2026-09-23. Tables 1 & 3 from chat.
read_labels = ["10", "1,000", "104,918", "1,872,777"]
x = np.arange(4)

PANELS = [
    ("50 MB",  [0.084, 0.298, 1.244, 13.881],  [70.77, 19.10, 11.84, 11.47]),
    ("8 GB",   [4.396, 4.337, 5.313, 18.535],  [92.19, 92.85, 79.16, 56.84]),
    ("16 GB",  [9.086, 7.956, 8.937, 22.304],  [90.48, 94.47, 82.21, 58.02]),
    ("103 GB", [51.347, 51.187, 53.950, 79.463], [97.70, 97.49, 84.09, 71.93]),
]

BLUE = "#2f6fed"
BLUE_DARK = "#173f8f"
RED = "#d92b3a"
INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#8891a0"

fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=250)
fig.patch.set_facecolor("white")
axes = axes.flatten()

for panel_i, (ax1, (db_label, walltime, llc)) in enumerate(zip(axes, PANELS)):
    ax1.set_facecolor("white")
    ax1.grid(axis="y", color="#e6e8ed", linewidth=0.8, zorder=0)

    ymax = max(walltime) * 1.32
    bars = ax1.bar(x, walltime, width=0.5, color=BLUE, edgecolor=BLUE_DARK,
                    linewidth=1, zorder=3)
    ax1.set_ylim(0, ymax)
    ax1.set_ylabel("wall time (s)", color=BLUE_DARK, fontsize=10, fontweight="bold")
    ax1.tick_params(axis="y", colors=BLUE_DARK, labelsize=8.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(read_labels, fontsize=9, fontweight="bold", color=INK)
    ax1.set_xlabel("reads classified (log-order)", fontsize=9.5, color=INK, fontweight="bold")
    for s in ["top", "right"]:
        ax1.spines[s].set_visible(False)
    ax1.spines["left"].set_color(BLUE_DARK)
    ax1.spines["bottom"].set_color(INK)

    ax2 = ax1.twinx()
    ax2.plot(x, llc, color=RED, linestyle="--", linewidth=2.0, marker="o",
              markersize=6, markerfacecolor="white", markeredgecolor=RED,
              markeredgewidth=1.6, zorder=4)
    ax2.set_ylim(0, 108)
    ax2.set_ylabel("LLC cache-miss rate (%)", color=RED, fontsize=10, fontweight="bold")
    ax2.tick_params(axis="y", colors=RED, labelsize=8.5)
    for s in ["top", "left"]:
        ax2.spines[s].set_visible(False)
    ax2.spines["right"].set_color(RED)

    # place both labels together, in shared "fraction of panel height" units,
    # so each one can be checked against where the OTHER actually ended up -
    # not just against the raw data point, which is what broke earlier passes
    for i, xi in enumerate(x):
        wt_v, llc_v = walltime[i], llc[i]
        line_frac = llc_v / 108  # where the red line itself sits, as a fraction

        # wall-time label: default just above its own bar, but dodge the line
        wt_frac = (wt_v + ymax * 0.03) / ymax
        if abs(wt_frac - line_frac) < 0.09:
            wt_frac = line_frac + 0.09
        ax1.text(xi, wt_frac * ymax, f"{wt_v:.2f}s" if wt_v < 10 else f"{wt_v:.1f}s",
                  ha="center", fontsize=9, fontweight="bold", color=BLUE_DARK, zorder=5)

        # LLC label: default above/below the line, then dodge wherever the
        # wall-time label actually landed (post-dodge, using wt_frac above)
        base_dy = 8 if i % 2 == 0 else -11
        llc_frac = (llc_v + base_dy) / 108
        if abs(llc_frac - wt_frac) < 0.13 or abs(llc_frac - line_frac) < 0.05:
            llc_frac = line_frac + 0.30 if wt_frac < 0.5 else max(line_frac - 0.18, 0.04)
        ax2.text(xi, llc_frac * 108, f"{llc_v:.1f}%", ha="center", fontsize=8.5,
                  fontweight="bold", color=RED, zorder=5)

    ax1.set_title(db_label, fontsize=13, fontweight="bold", color=INK, pad=10)

    if panel_i == 0:
        h1 = [plt.Rectangle((0, 0), 1, 1, color=BLUE, ec=BLUE_DARK)]
        h2 = [plt.Line2D([0], [0], color=RED, marker="o", markerfacecolor="white",
                          markeredgecolor=RED, linestyle="--", linewidth=2)]
        ax1.legend(h1 + h2, ["wall time (s)", "LLC miss (%)"], loc="upper left",
                    fontsize=9, frameon=True, edgecolor="#e6e8ed")

fig.suptitle("Kraken2 wall time & LLC cache-miss rate vs. read count, by database size",
             fontsize=16, fontweight="bold", color=INK, y=1.0)
fig.text(0.5, -0.01,
          "no --memory-mapping · 32T · Luna, numactl node0 · kraken2-fresh-bin-s0 (v2.17.1) · measured 2026-09-23",
          ha="center", va="top", fontsize=9.5, color=INK_FAINT, style="italic")

fig.tight_layout(pad=1.4, rect=[0, 0.01, 1, 0.98])
fig.savefig("k2_readcount_grid_noM.png", facecolor="white", bbox_inches="tight", pad_inches=0.15)
plt.close(fig)
print("saved k2_readcount_grid_noM.png")
