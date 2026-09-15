"""
Figure for the hardware LLC associativity sweep (base kraken2, S0, no software
cache) - the mirror-image experiment to every other chart in this project,
which varied the SOFTWARE S2 cache's width. This one holds software fixed at
none and varies Luna's real hardware LLC associativity (1/4/8/15[real]/16/30
-way) across 4 workload sizes (10/50/100/500 reads), all on the same 50MB DB.

Verdict: NULL RESULT. Cycles are flat (well under 1% spread) across every
associativity value at every workload size - see command_log.md's
"hw_assoc_sweep COMPLETE" section for the full mechanistic explanation (almost
nothing is ever resolved at the LLC layer on this DB, so its associativity
can't matter - the same underlying reason the software cache also fails to
help on this DB, see fig9/fig10/fig11).
"""

import matplotlib.pyplot as plt
import numpy as np
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

DOUBLE_COL = 7.0
REAL_COLOR = "#0a7d0a"
LINE_COLOR = "#2a78d6"

# reads -> {associativity: cycles_M}, from hw_assoc_sweep_2026-09-14.csv
DATA = {
    10:  {1: 13.6, 4: 13.7, 8: 13.6, 15: 13.7, 16: 13.7, 30: 13.7},
    50:  {1: 24.4, 4: 24.4, 8: 24.4, 15: 24.4, 16: 24.4, 30: 24.4},
    100: {1: 870.0, 4: 877.2, 8: 869.9, 15: 870.4, 16: 869.8, 30: 877.3},
    500: {1: 4528.2, 4: 4524.0, 8: 4537.9, 15: 4534.5, 16: 4526.4, 30: 4523.2},
}
ASSOC = [1, 4, 8, 15, 16, 30]


def style_ax(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, color="#d8d8d8", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=3, width=0.8, color="#333333")


def savefig(fig, name):
    for ext in ("pdf", "png"):
        path = os.path.join(OUT_DIR, f"{name}.{ext}")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"wrote {path}")
    plt.close(fig)


def fig_hw_assoc_sweep():
    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 4.2), sharex=True)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.72, bottom=0.30, wspace=0.45)
    for ax, reads in zip(axes, DATA.keys()):
        vals = [DATA[reads][a] for a in ASSOC]
        mean = np.mean(vals)
        spread_pct = (max(vals) - min(vals)) / mean * 100
        ax.plot(range(len(ASSOC)), vals, marker="o", markersize=5,
                 color=LINE_COLOR, linewidth=1.4, zorder=3)
        real_idx = ASSOC.index(15)
        ax.scatter([real_idx], [vals[real_idx]], s=70, facecolor="none",
                    edgecolor=REAL_COLOR, linewidth=1.8, zorder=4)
        ax.set_xticks(range(len(ASSOC)))
        ax.set_xticklabels([str(a) for a in ASSOC], fontsize=7.5)
        ax.set_title(f"{reads} reads\n(spread: {spread_pct:.2f}%)", fontsize=8.8)
        ymid = mean
        yrange = max(mean * 0.03, (max(vals) - min(vals)) * 3, mean * 0.01)
        ax.set_ylim(ymid - yrange, ymid + yrange)
        style_ax(ax)
    axes[0].set_ylabel("Simulated cycles (M)")
    fig.text(0.525, 0.235, "Real HARDWARE LLC associativity (green circle = Luna's real 15-way)",
              ha="center", fontsize=8.5)
    fig.suptitle("Hardware LLC associativity alone has no measurable effect\n"
                  "(base kraken2, NO software cache, 50MB DB)", fontsize=11, y=0.965)
    fig.text(0.02, 0.16,
              "Software S2 cache held fixed at NONE throughout (base kraken2 binary) - the inverse\n"
              "of every other experiment in this project, which varied the software cache instead.\n"
              "Y-axis is zoomed to each panel's own tiny range to show there is no trend - all four\n"
              "panels show <1% spread with no monotonic direction. NULL RESULT: at this 50MB DB,\n"
              "almost nothing is ever resolved at the LLC layer (l2/nuca hit rates all <2%), so its\n"
              "associativity has nothing to act on - the same underlying reason the software cache\n"
              "also fails to help on this DB (see fig9/fig10/fig11).",
              fontsize=7, color="#222222", va="top")
    savefig(fig, "fig12_hw_assoc_sweep_null")


if __name__ == "__main__":
    fig_hw_assoc_sweep()
