import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Same real data as k2_cache_readcount_compare.png, collapsed to a single
# combined speedup-ratio view (S0 / S1) instead of 4 separate wall-time
# panels. Luna, 32T, kraken2-fresh-bin-s0 vs kraken2-fresh-bin-s1 (commit
# fbf993d), perf stat, measured 2026-09-23.
read_labels = ["10", "1,000", "104,918", "1,872,777"]
db_labels = ["50 MB", "8 GB", "16 GB", "103 GB"]

S0 = {
    "50 MB":  [0.12, 0.30, 1.27, 15.70],
    "8 GB":   [4.53, 4.63, 5.57, 19.74],
    "16 GB":  [8.46, 8.56, 9.51, 24.27],
    "103 GB": [61.73, 60.57, 62.61, 85.71],
}
S1 = {
    "50 MB":  [0.11, 0.29, 1.05, 13.16],
    "8 GB":   [4.57, 4.66, 5.40, 15.93],
    "16 GB":  [8.59, 8.59, 9.40, 20.76],
    "103 GB": [61.31, 60.71, 62.48, 87.93],
}
speedup = {db: [a / b for a, b in zip(S0[db], S1[db])] for db in db_labels}

DB_COLOR = {
    "50 MB":  "#d92b3a",
    "8 GB":   "#2f6fed",
    "16 GB":  "#1f9e6d",
    "103 GB": "#e8c520",
}
LABEL_COLOR = {
    "50 MB":  "#d92b3a",
    "8 GB":   "#2f6fed",
    "16 GB":  "#1f9e6d",
    "103 GB": "#9c8000",
}
INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#9aa1ac"
LINE = "#e6e8ed"

x = np.arange(4)
bar_w = 0.19

fig, ax1 = plt.subplots(figsize=(12, 7.2), dpi=270)
fig.patch.set_facecolor("white")
ax1.set_facecolor("white")
ax1.grid(axis="y", color=LINE, linewidth=0.8, zorder=0)

ax1.axhline(1.0, color=INK_SOFT, linewidth=1.6, linestyle="--", zorder=2)
ax1.text(3.62, 1.0, "no change", va="center", fontsize=10, color=INK_SOFT, fontweight="bold",
          bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="none"), zorder=4)

for di, db in enumerate(db_labels):
    offsets = x + (di - 1.5) * bar_w
    vals = speedup[db]
    ax1.bar(offsets, vals, width=bar_w * 0.92, color=DB_COLOR[db], zorder=3,
              edgecolor=INK, linewidth=1.1, label=db)
    for xi, v in zip(offsets, vals):
        lbl = f"{v:.2f}x"
        lbl_col = "#1f9e6d" if v >= 1 else "#c9932f"
        va = "bottom" if v >= 1 else "top"
        dy = 0.018 if v >= 1 else -0.018
        ax1.text(xi, v + dy, lbl, ha="center", va=va, fontsize=8.5, fontweight="bold",
                  color=lbl_col, rotation=90, zorder=5)

ax1.set_ylim(0.9, 1.32)
ax1.set_ylabel("speedup (S0 elapsed / S1 elapsed)", fontsize=12.5, color=INK, fontweight="bold")
ax1.tick_params(axis="y", labelsize=10.5, colors=INK)
ax1.set_xticks(x)
ax1.set_xticklabels(read_labels, fontsize=12, fontweight="bold", color=INK)
ax1.set_xlabel("reads classified (log-order)", fontsize=12, color=INK, fontweight="bold")
ax1.set_xlim(-0.55, 3.95)
for s in ["top", "right"]:
    ax1.spines[s].set_visible(False)
ax1.spines["left"].set_color(INK)
ax1.spines["bottom"].set_color(INK)

bar_handles = [plt.Rectangle((0, 0), 1, 1, color=DB_COLOR[db]) for db in db_labels]
ax1.legend(bar_handles, db_labels, loc="upper center", bbox_to_anchor=(0.5, 1.13),
            ncol=4, fontsize=11.5, frameon=False, handlelength=1.6, columnspacing=1.6)

fig.suptitle("How much faster is the 1-minimizer cache than no cache at all?",
             fontsize=16, fontweight="bold", color=INK, y=1.02)
fig.text(0.5, 0.005,
          "32T · Luna · kraken2-fresh-bin-s0 vs kraken2-fresh-bin-s1 (commit fbf993d) · perf stat · measured 2026-09-23",
          ha="center", va="bottom", fontsize=9, color=INK_FAINT, style="italic")

fig.tight_layout(pad=1.1, rect=[0, 0.02, 1, 0.92])
fig.savefig("k2_cache_speedup_combined.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_cache_speedup_combined.png")
