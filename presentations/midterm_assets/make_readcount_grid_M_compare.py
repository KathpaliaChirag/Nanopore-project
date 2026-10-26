import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Real data, both sides: Luna, kraken2-fresh-bin-s0 (v2.17.1), 32T pinned (numactl
# node0), perf stat wrapped, kraken2-fresh-bin-s0. noM side measured 2026-09-23
# (same run as kraken2_readcount_grid_noM.png). -M side measured 2026-09-23 in a
# fresh 16-cell perf-stat sweep (see M_sweep_results_raw.txt), same DBs/inputs:
# sample_targeted(50MB), standard_8gb, standard_16gb, pluspf_103gb; reads_10.fastq,
# reads_1000.fastq, reads_hac.fastq (104,918), all 16 pod5_N.fastq combined (1,872,777).
read_labels = ["10", "1,000", "104,918", "1,872,777"]
x = np.arange(4)

PANELS = [
    ("50 MB",  [0.084, 0.298, 1.244, 13.881],  [0.08, 0.27, 1.22, 15.58]),
    ("8 GB",   [4.396, 4.337, 5.313, 18.535],  [0.11, 0.47, 1.39, 15.50]),
    ("16 GB",  [9.086, 7.956, 8.937, 22.304],  [0.16, 0.63, 1.50, 15.92]),
    ("103 GB", [51.347, 51.187, 53.950, 79.463], [0.65, 2.99, 4.17, 31.29]),
]

# a warmer, less "corporate report" pairing than navy/sky blue - deep teal vs
# warm coral, complementary and easy to tell apart at a glance
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

for panel_i, (ax1, (db_label, noM, M)) in enumerate(zip(axes, PANELS)):
    ax1.set_facecolor("white")
    ax1.grid(axis="y", color="#e6e8ed", linewidth=0.8, zorder=0)
    ax1.set_yscale("log")

    off_noM = x - bar_w / 2
    off_M = x + bar_w / 2
    ax1.bar(off_noM, noM, width=bar_w * 0.72, color=TEAL, edgecolor=INK,
             linewidth=1, zorder=3, label="no -M" if panel_i == 0 else None)
    ax1.bar(off_M, M, width=bar_w * 0.72, color=CORAL, edgecolor=INK,
             linewidth=1, zorder=3, label="-M (--memory-mapping)" if panel_i == 0 else None)

    ymin, ymax = 0.02, max(noM) * 6.2
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

    for xi, v in zip(off_noM, noM):
        lbl = f"{v:.2f}s" if v < 10 else f"{v:.1f}s"
        ax1.text(xi, v * 1.20, lbl, ha="center", fontsize=12, fontweight="bold", color=INK, zorder=5)
    for xi, v in zip(off_M, M):
        lbl = f"{v:.2f}s" if v < 10 else f"{v:.1f}s"
        ax1.text(xi, v * 1.20, lbl, ha="center", fontsize=12, fontweight="bold", color=INK, zorder=5)

    # one fixed header row near the top of the panel for every Nx-faster
    # label, clear of the tallest bar in every group - simple now that
    # there's no LLC line to dodge as well
    fixed_top = 10 ** (0.91 * (np.log10(ymax) - np.log10(ymin)) + np.log10(ymin))
    for xi, a, b in zip(x, noM, M):
        speedup = a / b
        if speedup >= 1:
            txt, col = f"{speedup:.1f}x faster", GREEN
        else:
            txt, col = f"{1/speedup:.1f}x slower", AMBER
        ax1.text(xi, fixed_top, txt, ha="center", fontsize=12.5, fontweight="bold", color=col, zorder=6)

    ax1.set_title(db_label, fontsize=13, fontweight="bold", color=INK, pad=10)

fig.suptitle("Kraken2 wall time: with vs. without --memory-mapping, by database size",
             fontsize=16.5, fontweight="bold", color=INK, y=1.0)

h1 = [plt.Rectangle((0, 0), 1, 1, color=TEAL, ec=INK), plt.Rectangle((0, 0), 1, 1, color=CORAL, ec=INK)]
fig.legend(h1, ["no -M", "-M (--memory-mapping)"],
            loc="upper center", bbox_to_anchor=(0.5, 0.965), ncol=2, fontsize=10.5, frameon=False)

fig.text(0.5, -0.01,
          "32T, numactl node0 · Luna · kraken2-fresh-bin-s0 (v2.17.1) · perf stat · both sides measured 2026-09-23",
          ha="center", va="top", fontsize=9.5, color=INK_FAINT, style="italic")

fig.tight_layout(pad=1.4, rect=[0, 0.01, 1, 0.93])
fig.savefig("k2_readcount_grid_M_compare.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_readcount_grid_M_compare.png")
