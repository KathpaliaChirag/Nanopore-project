import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Real data: Luna, 32T, kraken2-fresh-bin-s0 (no cache) vs kraken2-fresh-bin-s1
# (thread-local 1-minimizer cache, commit fbf993d). Same DBs/inputs as the
# --memory-mapping sweep: sample_targeted(50MB), standard_8gb, standard_16gb,
# pluspf_103gb; reads_10.fastq, reads_1000.fastq, reads_hac.fastq (104,918),
# all 16 pod5_N.fastq combined (1,872,777). perf-stat wrapped. Measured 2026-09-23.
read_labels = ["10", "1,000", "104,918", "1,872,777"]
x = np.arange(4)

PANELS = [
    ("50 MB",  [0.12, 0.30, 1.27, 15.70],  [0.11, 0.29, 1.05, 13.16]),
    ("8 GB",   [4.53, 4.63, 5.57, 19.74],  [4.57, 4.66, 5.40, 15.93]),
    ("16 GB",  [8.46, 8.56, 9.51, 24.27],  [8.59, 8.59, 9.40, 20.76]),
    ("103 GB", [61.73, 60.57, 62.61, 85.71], [61.31, 60.71, 62.48, 87.93]),
]

TEAL = "#0f766e"
CORAL = "#fb923c"
GREEN = "#1f9e6d"
AMBER = "#c9932f"
INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#8891a0"

fig, axes = plt.subplots(2, 2, figsize=(13, 9.5), dpi=250)
fig.patch.set_facecolor("white")
axes = axes.flatten()
bar_w = 0.40

for panel_i, (ax1, (db_label, s0, s1)) in enumerate(zip(axes, PANELS)):
    ax1.set_facecolor("white")
    ax1.grid(axis="y", color="#e6e8ed", linewidth=0.8, zorder=0)
    ax1.set_yscale("log")

    off_s0 = x - bar_w / 2
    off_s1 = x + bar_w / 2
    ax1.bar(off_s0, s0, width=bar_w * 0.72, color=TEAL, edgecolor=INK,
             linewidth=1, zorder=3, label="S0 - no cache" if panel_i == 0 else None)
    ax1.bar(off_s1, s1, width=bar_w * 0.72, color=CORAL, edgecolor=INK,
             linewidth=1, zorder=3, label="S1 - 1-minimizer cache" if panel_i == 0 else None)

    ymin, ymax = 0.02, max(s0) * 6.2
    ax1.set_ylim(ymin, ymax)
    ax1.set_ylabel("wall time (s, log scale)", color=INK, fontsize=10.5, fontweight="bold")
    ax1.tick_params(axis="y", colors=INK_SOFT, labelsize=8.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(read_labels, fontsize=9, fontweight="bold", color=INK)
    ax1.set_xlabel("reads classified (log-order)", fontsize=9.5, color=INK, fontweight="bold")
    for s in ["top", "right"]:
        ax1.spines[s].set_visible(False)
    ax1.spines["left"].set_color(INK_SOFT)
    ax1.spines["bottom"].set_color(INK)

    for xi, v in zip(off_s0, s0):
        lbl = f"{v:.2f}s" if v < 10 else f"{v:.1f}s"
        ax1.text(xi, v * 1.20, lbl, ha="center", fontsize=12, fontweight="bold", color=INK, zorder=5)
    for xi, v in zip(off_s1, s1):
        lbl = f"{v:.2f}s" if v < 10 else f"{v:.1f}s"
        ax1.text(xi, v * 1.20, lbl, ha="center", fontsize=12, fontweight="bold", color=INK, zorder=5)

    fixed_top = 10 ** (0.91 * (np.log10(ymax) - np.log10(ymin)) + np.log10(ymin))
    for xi, a, b in zip(x, s0, s1):
        speedup = a / b
        if speedup >= 1:
            txt, col = f"{speedup:.2f}x faster", GREEN
        else:
            txt, col = f"{1/speedup:.2f}x slower", AMBER
        ax1.text(xi, fixed_top, txt, ha="center", fontsize=12, fontweight="bold", color=col, zorder=6)

    ax1.set_title(db_label, fontsize=13, fontweight="bold", color=INK, pad=10)

fig.suptitle("Kraken2 wall time: S0 (no cache) vs S1 (1-minimizer thread-local cache)",
             fontsize=16, fontweight="bold", color=INK, y=1.0)

h1 = [plt.Rectangle((0, 0), 1, 1, color=TEAL, ec=INK), plt.Rectangle((0, 0), 1, 1, color=CORAL, ec=INK)]
fig.legend(h1, ["S0 - no cache", "S1 - 1-minimizer thread-local cache"],
            loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=2, fontsize=10.5, frameon=False)

fig.text(0.5, -0.01,
          "32T, numactl node0 · Luna · kraken2-fresh-bin-s0 vs kraken2-fresh-bin-s1 (commit fbf993d) · perf stat · measured 2026-09-23",
          ha="center", va="top", fontsize=9, color=INK_FAINT, style="italic")

fig.tight_layout(pad=1.4, rect=[0, 0.01, 1, 0.93])
fig.savefig("k2_cache_readcount_compare.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_cache_readcount_compare.png")
