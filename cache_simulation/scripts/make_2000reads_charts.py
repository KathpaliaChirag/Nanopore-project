"""
Figures for the 2000-reads job (same 50MB DB - sample_targeted - as the fair
batch's "50mb" column, just a much larger, more realistic read count).

IMPORTANT correction baked into these captions: this job does NOT test whether
the ~2x speedup seen on the 8GB/16GB/103GB DBs survives at large read counts -
that comparison was never run. This job only shows that the SMALL (50MB) DB's
already-negative result (cache worse than no-cache, seen even at 50 reads in
the fair batch) continues to hold, and gets slightly worse, at 2000 reads.

16way is still running as of this data pull - only S0/1way/4way/8way included.

Speedup uses CYCLES / core frequency (real-hardware-equivalent), never
Sniper's own wallclock_s - see make_slide_charts.py's module docstring.
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

GRAY = "#6b6b6b"
BLUE_RAMP = {"1way": "#9ec5f4", "4way": "#5598e7", "8way": "#2a78d6", "16way": "#184f95"}
CRIT = "#b3312f"
GOOD = "#0a7d0a"
SINGLE_COL = 3.4
DOUBLE_COL = 7.0

# ---- 2000-reads data (50MB DB "sample_targeted"), from live_summary.csv ----
CYCLES_2000 = {"S0": 6354.0, "1way": 8336.3, "4way": 8159.1, "8way": 8508.1}
VARIANTS_2000 = ["S0", "1way", "4way", "8way"]
LABELS_2000 = ["No cache", "1-way", "4-way", "8-way"]

# ---- 50-read data on the SAME 50MB DB, from the fair batch (already-known
# negative result this job is reconfirming at scale) ------------------------
CYCLES_50 = {"S0": 24.4, "1way": 27.0, "4way": 26.8, "8way": 27.8, "16way": 28.7}


def style_ax(ax, ygrid=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ygrid:
        ax.yaxis.grid(True, color="#d8d8d8", linewidth=0.6, zorder=0)
        ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=3, width=0.8, color="#333333")


def savefig(fig, name):
    for ext in ("pdf", "png"):
        path = os.path.join(OUT_DIR, f"{name}.{ext}")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        print(f"wrote {path}")
    plt.close(fig)


# =========================================================================
# FIGURE 9 - cycles by SOFTWARE cache width at 2000-read scale, 50MB DB
# =========================================================================
def fig_2000reads_cycles():
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"]]
    vals = [CYCLES_2000[v] for v in VARIANTS_2000]

    fig, ax = plt.subplots(figsize=(SINGLE_COL + 0.4, 3.3))
    bars = ax.bar(LABELS_2000, vals, color=colors, width=0.6, zorder=3,
                   edgecolor="#000000", linewidth=0.8)
    bars[0].set_edgecolor(GOOD)
    bars[0].set_linewidth(2.0)
    ax.axhline(vals[0], color="#000000", linestyle="--", linewidth=0.9, zorder=2)
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:,.0f}", (b.get_x() + b.get_width() / 2, v + 60),
                    ha="center", fontsize=8.5, fontweight="600")
    ax.set_ylabel("Simulated cycles (M)")
    ax.set_title("2000-read workload, 50MB DB: cache is worse\nthan no cache at every width tested",
                  fontsize=10)
    style_ax(ax)
    ax.set_ylim(0, max(vals) * 1.20)
    fig.text(0.0, -0.24,
              "35.1M bases total (2000 reads), sample_targeted (50MB) DB. Dashed line: no-cache\n"
              "(S0) cycle count - every cache width sits above it. 16-way still running, not shown.\n"
              "Width shown = the SOFTWARE S2 lookup-cache's associativity. Real Luna HARDWARE cache\n"
              "is fixed throughout: L1d 48KB/12-way, L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way.",
              fontsize=7, color="#222222")
    savefig(fig, "fig9_2000reads_cycles_50mb")


# =========================================================================
# FIGURE 10 - does the small-DB negative result hold as read count scales up?
# 50 reads vs 2000 reads, SAME 50MB DB, cycles ratio vs no-cache.
# =========================================================================
def fig_readcount_scaling_same_db():
    widths = ["1way", "4way", "8way"]
    labels = ["1-way", "4-way", "8-way"]
    ratio_50 = [CYCLES_50[w] / CYCLES_50["S0"] for w in widths]
    ratio_2000 = [CYCLES_2000[w] / CYCLES_2000["S0"] for w in widths]

    x = np.arange(len(widths))
    bw = 0.32
    fig, ax = plt.subplots(figsize=(SINGLE_COL + 0.8, 3.3))
    b1 = ax.bar(x - bw / 2, ratio_50, bw, label="50 reads", color="#cfcfcf",
                edgecolor="#000000", linewidth=0.7, zorder=3, hatch="//")
    b2 = ax.bar(x + bw / 2, ratio_2000, bw, label="2000 reads", color="#5598e7",
                edgecolor="#000000", linewidth=0.7, zorder=3)
    for bars in (b1, b2):
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.2f}x", (b.get_x() + b.get_width() / 2, h + 0.015),
                        ha="center", fontsize=7.5)
    ax.axhline(1.0, color=CRIT, linestyle="--", linewidth=1.1, zorder=2)
    ax.text(x[-1] + 0.55, 1.0, "no cache", va="center", fontsize=7.5, color=CRIT)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Cycles vs. no cache\n(>1.0 = cache is SLOWER)")
    ax.set_title("Same 50MB DB, 50 reads vs 2000 reads:\nthe cache-hurts result already existed, and holds",
                  fontsize=9.8)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.10), ncol=2, fontsize=8.5)
    style_ax(ax)
    ax.set_ylim(0, max(max(ratio_50), max(ratio_2000)) * 1.35)
    fig.text(0.0, -0.22,
              "Both bars use the SAME 50MB DB (sample_targeted). The cache was already worse than\n"
              "no-cache at just 50 reads (fair batch, 2026-09-09) - this was NOT newly discovered by\n"
              "the 2000-read job. What the 2000-read job adds: ruling out \"needs more reads to warm\n"
              "up\" as an excuse - the negative result holds (and worsens slightly) at 40x more reads.\n"
              "This says nothing about the 8GB/16GB/103GB DBs, where cache DOES help (~2x) at 50 reads\n"
              "- that comparison has not been run at large read counts and remains open.",
              fontsize=6.8, color="#222222")
    savefig(fig, "fig10_readcount_scaling_same_db")


if __name__ == "__main__":
    fig_2000reads_cycles()
    fig_readcount_scaling_same_db()
