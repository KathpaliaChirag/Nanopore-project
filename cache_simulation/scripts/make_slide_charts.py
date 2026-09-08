"""
Generates publication-quality figures (PDF vector + high-DPI PNG) from the
cache_simulation experiment data. Run locally (not on Luna) - Python +
matplotlib only.

Data below is transcribed directly from cache_simulation/measurements/*.csv
and cache_simulation/command_log.md - update these dicts if new data lands.
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

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
    "pdf.fonttype": 42,   # embed as real fonts, not paths (required by many venues)
    "ps.fonttype": 42,
})

GRAY = "#6b6b6b"           # S0 / no-cache reference
BLUE_RAMP = {               # sequential ramp, 1-way (light) -> 16-way (dark)
    "1way":  "#9ec5f4",
    "4way":  "#5598e7",
    "8way":  "#2a78d6",
    "16way": "#184f95",
}
GOOD = "#0a7d0a"
CRIT = "#b3312f"

SINGLE_COL = 3.4   # inches - standard single-column figure width (IEEE/ACM)
DOUBLE_COL = 7.0   # inches - full-width figure


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
              "Dashed line: 4-way time.",
              fontsize=7, color="#555555")
    savefig(fig, "fig1_width_sweep_10reads")


# =========================================================================
# FIGURE 2 — Cycles by variant, small multiples per DB size
# =========================================================================
def fig_cycles_by_db():
    dbs = ["50 MB", "7.5 GB", "16 GB", "103 GB"]
    labels = ["No cache", "1-way", "4-way", "8-way", "16-way"]
    cycles = {
        "50 MB":  [24.4, 27.0, 26.7, 27.8, 28.7],
        "7.5 GB": [51.7, 28.6, 28.3, 28.7, 28.9],
        "16 GB":  [60.7, 30.1, 29.6, 30.1, 30.3],
        "103 GB": [94.3, 48.8, 47.7, 49.0, 49.6],
    }
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.8), sharey=False)
    for ax, dbname in zip(axes, dbs):
        vals = cycles[dbname]
        bars = ax.bar(labels, vals, color=colors, width=0.7, zorder=3,
                       edgecolor="#222222", linewidth=0.4)
        best_idx = int(np.argmin(vals[1:])) + 1
        bars[best_idx].set_edgecolor(GOOD)
        bars[best_idx].set_linewidth(1.8)
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=7.5)
        style_ax(ax)
        ax.set_ylim(0, max(vals) * 1.18)
    axes[0].set_ylabel("Cycles (M)")
    fig.suptitle("Simulated cycles by associativity width, across database sizes",
                 fontsize=11, fontweight="bold", y=1.04)
    fig.text(0.0, -0.16,
              "50-read workload. Green outline marks the lowest-cycle cache "
              "variant at each database size (4-way in every case).",
              fontsize=7, color="#555555")
    fig.tight_layout()
    savefig(fig, "fig2_cycles_by_db_5variant")


# =========================================================================
# FIGURE 3 — Wall-clock speedup vs no-cache (S0), clean sequential data only
# =========================================================================
def fig_speedup_clean():
    dbs = ["50 MB", "7.5 GB", "16 GB", "103 GB"]
    s0 = [188.7, 748.3, 861.3, 1261.4]
    v4 = [204.4, 391.8, 390.1, 614.8]
    v16 = [360.3, 410.3, 430.5, 671.5]
    speedup4 = [s / w for s, w in zip(s0, v4)]
    speedup16 = [s / w for s, w in zip(s0, v16)]

    x = np.arange(len(dbs))
    width = 0.32
    fig, ax = plt.subplots(figsize=(SINGLE_COL, 2.7))
    b1 = ax.bar(x - width / 2, speedup4, width, label="4-way",
                color=BLUE_RAMP["4way"], zorder=3, edgecolor="#222222", linewidth=0.5)
    b2 = ax.bar(x + width / 2, speedup16, width, label="16-way",
                color=BLUE_RAMP["16way"], zorder=3, edgecolor="#222222", linewidth=0.5)
    ax.axhline(1.0, color="#999999", linestyle="--", linewidth=0.9, zorder=2)
    for bars in (b1, b2):
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.2f}×", (b.get_x() + b.get_width() / 2, h + 0.05),
                        ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(dbs)
    ax.set_ylabel("Speedup vs. no cache")
    ax.set_title("Wall-clock speedup vs. database size", fontsize=10)
    ax.legend(frameon=False, loc="upper left")
    style_ax(ax)
    fig.text(0.0, -0.16,
              "50-read workload. S0/4-way/16-way ran sequentially (uncontended). "
              "1-way/8-way timing excluded pending an isolated re-run.",
              fontsize=7, color="#555555")
    savefig(fig, "fig3_speedup_vs_nocache")


# =========================================================================
# FIGURE 4 — Unique cache lines touched (memory footprint), small multiples
# =========================================================================
def fig_footprint():
    dbs = ["50 MB", "7.5 GB", "16 GB", "103 GB"]
    labels = ["No cache", "1-way", "4-way", "8-way", "16-way"]
    lines = {
        "50 MB":  [76605, 67749, 76963, 89254, 113831],
        "7.5 GB": [186523, 54874, 64091, 76380, 100952],
        "16 GB":  [200423, 47680, 56897, 69187, 93761],
        "103 GB": [306921, 79560, 88782, 101066, 125646],
    }
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.8))
    for ax, dbname in zip(axes, dbs):
        vals = lines[dbname]
        ax.bar(labels, vals, color=colors, width=0.7, zorder=3,
               edgecolor="#222222", linewidth=0.4)
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=7.5)
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
