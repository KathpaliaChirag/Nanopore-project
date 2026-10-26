import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK = "#15181f"
INK_SOFT = "#5c6572"
TEAL = "#1f5c52"
RED = "#a13a2c"

# Real data: Luna, kraken2-fresh-bin-s0 (v2.17.1, latest), standard_8gb DB,
# 32T pinned (numactl node0), no -M flag, perf stat, 2026-09-23.
reads = [10, 1000, 104918, 1872777]
read_labels = ["10", "1,000", "104,918", "1,872,777\n(merged, 12 GB)"]
walltime = [4.396, 4.337, 5.313, 18.535]
ipc = [0.92, 1.21, 2.08, 2.46]
llc_miss = [92.19, 92.85, 79.16, 56.84]
throughput = [r / t for r, t in zip(reads, walltime)]

plt.rcParams["font.weight"] = "bold"


def style_ax(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(INK_SOFT)
    ax.spines["bottom"].set_color(INK)


fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6), dpi=270)
fig.patch.set_facecolor("white")

# Panel 1: wall time vs read count
ax = axes[0]
ax.set_facecolor("white")
ax.grid(color="#e6e8ed", linewidth=0.6, zorder=0)
x = np.arange(len(reads))
ax.plot(x, walltime, color=TEAL, linewidth=2.2, marker="o", markersize=7,
        markerfacecolor="white", markeredgecolor=TEAL, markeredgewidth=1.8, zorder=3)
for xi, v in zip(x, walltime):
    ax.text(xi, v + 0.9, f"{v:.2f}s", ha="center", fontsize=8, fontweight="bold", color=TEAL)
ax.axhspan(0, 4.45, color=RED, alpha=0.07, zorder=0)
ax.text(0.5, 2.1, "fixed DB-load cost\ndominates (no -M)", fontsize=7, color=RED,
         ha="center", fontweight="bold", style="italic")
ax.set_xticks(x)
ax.set_xticklabels(read_labels, fontsize=7.3, color=INK)
ax.set_ylabel("wall time (s)", fontsize=8.5, color=INK, fontweight="bold")
ax.set_xlabel("reads classified", fontsize=8.5, color=INK, fontweight="bold")
ax.set_ylim(0, 22)
style_ax(ax)
ax.tick_params(axis="y", labelsize=7, colors=INK_SOFT)
ax.set_title("Wall time is flat, then scales", fontsize=9.5, color=INK, pad=8)

# Panel 2: throughput vs read count (log y)
ax = axes[1]
ax.set_facecolor("white")
ax.grid(color="#e6e8ed", linewidth=0.6, zorder=0, which="both")
ax.plot(x, throughput, color=RED, linewidth=2.2, marker="o", markersize=7,
        markerfacecolor="white", markeredgecolor=RED, markeredgewidth=1.8, zorder=3)
ax.set_yscale("log")
for xi, v in zip(x, throughput):
    label = f"{v:.1f}/s" if v < 1000 else f"{v/1000:.1f}k/s"
    ax.text(xi, v * 1.7, label, ha="center", fontsize=8, fontweight="bold", color=RED)
ax.set_xticks(x)
ax.set_xticklabels(read_labels, fontsize=7.3, color=INK)
ax.set_ylabel("throughput (reads/s, log)", fontsize=8.5, color=INK, fontweight="bold")
ax.set_xlabel("reads classified", fontsize=8.5, color=INK, fontweight="bold")
ax.set_ylim(1, 500000)
style_ax(ax)
ax.tick_params(axis="y", labelsize=7, colors=INK_SOFT)
ax.set_title("Throughput improves 44,500x as fixed cost amortizes", fontsize=9.5, color=INK, pad=8)

fig.suptitle("Kraken2 read-count scaling, standard_8gb, 32T, latest binary (v2.17.1)",
             fontsize=10.5, color=INK, fontweight="bold", y=1.05)
fig.tight_layout(pad=0.9)
fig.savefig("k2_readcount_scaling.png", facecolor="white", bbox_inches="tight", pad_inches=0.1)
plt.close(fig)

print("throughput values:", throughput)
print("saved k2_readcount_scaling.png")
