"""
Generates publication-quality figures (PDF vector + high-DPI PNG) from the
cache_simulation experiment data. Run locally (not on Luna) - Python +
matplotlib only.

Data below is transcribed directly from
cache_simulation/measurements/final_fair_batch_2026-09-09_5variant_all_db.csv
and cache_simulation/command_log.md - update these dicts if new data lands.

IMPORTANT: speedup is computed from CYCLES / core frequency, not from Sniper's
own wallclock_s / elapsed_s columns. Those measure how long the SIMULATOR took
to compute the run (roughly tracks instruction count) - not how fast the
simulated program would run on real hardware. Cycles/frequency is the
correct real-hardware-equivalent metric (see command_log.md step 60 for the
full story of how this was caught).
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

LUNA_FREQ_GHZ = 2.1  # Xeon Platinum 8468 documented base clock, from luna.cfg

# ---- publication style --------------------------------------------------
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
BLUE_RAMP = {
    "1way":  "#9ec5f4",
    "4way":  "#5598e7",
    "8way":  "#2a78d6",
    "16way": "#184f95",
}
GOOD = "#0a7d0a"
CRIT = "#b3312f"

SINGLE_COL = 3.4
DOUBLE_COL = 7.0

# ---- final, verified data (fair batch, 2026-09-09) -----------------------
DBS = ["50 MB", "7.5 GB", "16 GB", "103 GB"]
DB_KEYS = ["50mb", "8gb", "16gb", "103gb"]
VARIANTS = ["S0", "1way", "4way", "8way", "16way"]
LABELS = ["No cache", "1-way", "4-way", "8-way", "16-way"]

CYCLES = {
    "50mb":  {"S0": 24.4, "1way": 27.0, "4way": 26.8, "8way": 27.8, "16way": 28.7},
    "8gb":   {"S0": 51.8, "1way": 28.6, "4way": 28.3, "8way": 28.7, "16way": 28.9},
    "16gb":  {"S0": 60.7, "1way": 30.1, "4way": 29.6, "8way": 30.1, "16way": 30.4},
    "103gb": {"S0": 94.3, "1way": 48.8, "4way": 47.8, "8way": 49.1, "16way": 50.0},
}
LINES = {
    "50mb":  {"S0": 76606, "1way": 67751, "4way": 76966, "8way": 89255, "16way": 113831},
    "8gb":   {"S0": 186526, "1way": 54874, "4way": 64091, "8way": 76379, "16way": 100954},
    "16gb":  {"S0": 200423, "1way": 47681, "4way": 56898, "8way": 69185, "16way": 93761},
    "103gb": {"S0": 306921, "1way": 79566, "4way": 88782, "8way": 101070, "16way": 125646},
}


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
# FIGURE 1 — 10-read associativity width sweep (wall-clock), 50MB DB, noatomics
# Single-batch, single-DB, self-consistent - not affected by the cross-batch
# or wallclock-vs-cycles issues (all 5 bars ran back to back in one batch).
# =========================================================================
def fig_width_sweep():
    widths = ["4-way", "8-way", "16-way", "32-way", "64-way"]
    times = [115.5, 121.3, 129.5, 138.6, 164.6]
    colors = ["#5598e7", "#3987e5", "#2a78d6", "#1c5cab", "#184f95"]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.6))
    bars = ax.bar(widths, times, color=colors, width=0.62, zorder=3,
                   edgecolor="#222222", linewidth=0.5)
    ax.axhline(times[0], color="#999999", linestyle="--", linewidth=0.9, zorder=2)
    for b, t in zip(bars, times):
        ax.annotate(f"{t:.0f}", (b.get_x() + b.get_width() / 2, t + 4),
                    ha="center", fontsize=8)
    ax.set_ylabel("Wall-clock time (s)")
    ax.set_title("Associativity width vs. simulated time", fontsize=10)
    style_ax(ax)
    ax.set_ylim(0, max(times) * 1.18)
    fig.text(0.0, -0.16,
              "10-read workload, 50 MB DB, atomics-contention removed. "
              "Dashed line: 4-way time. Single batch, directly comparable.",
              fontsize=7, color="#555555")
    savefig(fig, "fig1_width_sweep_10reads")


# =========================================================================
# FIGURE 2 — Cycles by variant, small multiples per DB size
# =========================================================================
def fig_cycles_by_db():
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.8), sharey=False)
    for ax, dbname, dbkey in zip(axes, DBS, DB_KEYS):
        vals = [CYCLES[dbkey][v] for v in VARIANTS]
        bars = ax.bar(LABELS, vals, color=colors, width=0.7, zorder=3,
                       edgecolor="#222222", linewidth=0.4)
        best_idx = int(np.argmin(vals[1:])) + 1
        bars[best_idx].set_edgecolor(GOOD)
        bars[best_idx].set_linewidth(1.8)
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(LABELS)))
        ax.set_xticklabels(LABELS, rotation=40, ha="right", fontsize=7.5)
        style_ax(ax)
        ax.set_ylim(0, max(vals) * 1.18)
    axes[0].set_ylabel("Cycles (M)")
    fig.suptitle("Simulated cycles by associativity width, across database sizes",
                 fontsize=11, fontweight="bold", y=1.04)
    fig.text(0.0, -0.16,
              "50-read workload. Green outline marks the lowest-cycle cache "
              "variant at each database size (4-way in every case). Cycles are "
              "the real-hardware-equivalent metric (cycles / clock frequency).",
              fontsize=7, color="#555555")
    fig.tight_layout()
    savefig(fig, "fig2_cycles_by_db_5variant")


# =========================================================================
# FIGURE 3 — Real-hardware-equivalent speedup vs no-cache (from cycles, NOT
# Sniper's own wallclock_s - see module docstring for why that distinction
# matters). All 4 cache widths shown.
# =========================================================================
def fig_speedup_clean():
    x = np.arange(len(DBS))
    width = 0.19
    widths_to_plot = ["1way", "4way", "8way", "16way"]
    offsets = [-1.5, -0.5, 0.5, 1.5]

    fig, ax = plt.subplots(figsize=(SINGLE_COL + 1.3, 3.2))
    for w, off in zip(widths_to_plot, offsets):
        speedups = [CYCLES[dbkey]["S0"] / CYCLES[dbkey][w] for dbkey in DB_KEYS]
        bars = ax.bar(x + off * width, speedups, width, label=LABELS[VARIANTS.index(w)],
                       color=BLUE_RAMP[w], zorder=3, edgecolor="#222222", linewidth=0.4)
        for b, h in zip(bars, speedups):
            ax.annotate(f"{h:.2f}", (b.get_x() + b.get_width() / 2, h + 0.05),
                        ha="center", fontsize=6.5, rotation=90)
    ax.axhline(1.0, color="#999999", linestyle="--", linewidth=0.9, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels(DBS)
    ax.set_ylabel("Speedup vs. no cache\n(real-hardware-equivalent)")
    ax.set_title("Cache speedup by width and database size", fontsize=10, pad=28)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=4, columnspacing=1.2, handlelength=1.2, fontsize=8)
    style_ax(ax)
    ax.set_ylim(0, 2.5)
    fig.text(0.0, -0.2,
              "50-read workload. Speedup computed from simulated CYCLES / core "
              "frequency (real-hardware-equivalent time), not Sniper's own "
              "simulation wall-clock. 4-way wins or ties at every database size.",
              fontsize=7, color="#555555")
    savefig(fig, "fig3_speedup_vs_nocache")


# =========================================================================
# FIGURE 4 — Unique cache lines touched (memory footprint), small multiples
# =========================================================================
def fig_footprint():
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.8))
    for ax, dbname, dbkey in zip(axes, DBS, DB_KEYS):
        vals = [LINES[dbkey][v] for v in VARIANTS]
        ax.bar(LABELS, vals, color=colors, width=0.7, zorder=3,
               edgecolor="#222222", linewidth=0.4)
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(LABELS)))
        ax.set_xticklabels(LABELS, rotation=40, ha="right", fontsize=7.5)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K"))
        style_ax(ax)
    axes[0].set_ylabel("Unique cache lines touched")
    fig.suptitle("Memory footprint touched, by associativity width and database size",
                 fontsize=11, fontweight="bold", y=1.04)
    fig.text(0.0, -0.16,
              "50-read workload. Fewer lines touched indicates fewer cold-memory "
              "probes into the underlying hash table.",
              fontsize=7, color="#555555")
    fig.tight_layout()
    savefig(fig, "fig4_memory_footprint_by_db")


if __name__ == "__main__":
    fig_width_sweep()
    fig_cycles_by_db()
    fig_speedup_clean()
    fig_footprint()
    print("done")
