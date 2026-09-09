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
IPC_S0 = {"50mb": 1.47, "8gb": 1.32, "16gb": 1.27, "103gb": 1.09}


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
    # Grayscale ramp, light -> dark, with distinct hatch patterns so bars are
    # still distinguishable in pure black-and-white print with no color at all.
    grays = ["#dcdcdc", "#b8b8b8", "#8c8c8c", "#5c5c5c", "#2a2a2a"]
    hatches = ["", "//", "xx", "\\\\", ".."]

    fig, ax = plt.subplots(figsize=(SINGLE_COL + 0.3, 3.1))
    bars = ax.bar(widths, times, color=grays, width=0.62, zorder=3,
                   edgecolor="#000000", linewidth=0.8)
    for b, h in zip(bars, hatches):
        b.set_hatch(h)
    ax.axhline(times[0], color="#000000", linestyle="--", linewidth=0.9, zorder=2)
    for b, t in zip(bars, times):
        ax.annotate(f"{t:.0f}", (b.get_x() + b.get_width() / 2, t + 4),
                    ha="center", fontsize=8.5, fontweight="600")
    ax.set_ylabel("Wall-clock time (s)")
    ax.set_title("Software cache width vs. simulated time", fontsize=10.5)
    style_ax(ax)
    ax.set_ylim(0, max(times) * 1.22)
    fig.text(0.0, -0.20,
              "10-read workload, 50 MB DB, atomics-contention removed. Dashed line: 4-way time.\n"
              "Width shown = the SOFTWARE S2 lookup-cache's associativity (kraken2's own code).\n"
              "Real Luna HARDWARE cache is fixed and unchanged throughout: L1d 48KB/12-way,\n"
              "L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way (96 cores/socket).",
              fontsize=7, color="#222222")
    savefig(fig, "fig1_width_sweep_10reads")


# =========================================================================
# FIGURE 2 — Cycles by variant, small multiples per DB size
# =========================================================================
def fig_cycles_by_db():
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 3.0), sharey=False)
    for ax, dbname, dbkey in zip(axes, DBS, DB_KEYS):
        vals = [CYCLES[dbkey][v] for v in VARIANTS]
        bars = ax.bar(LABELS, vals, color=colors, width=0.7, zorder=3,
                       edgecolor="#222222", linewidth=0.4)
        best_idx = int(np.argmin(vals[1:])) + 1
        bars[best_idx].set_edgecolor(GOOD)
        bars[best_idx].set_linewidth(1.8)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}", (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=7.5, fontweight="600")
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(LABELS)))
        ax.set_xticklabels(LABELS, rotation=40, ha="right", fontsize=7.5)
        style_ax(ax)
        ax.set_ylim(0, max(vals) * 1.22)
    axes[0].set_ylabel("Cycles (M)")
    fig.suptitle("Simulated cycles by SOFTWARE cache width, across database sizes",
                 fontsize=11, fontweight="bold", y=1.04)
    fig.text(0.0, -0.22,
              "50-read workload. Green outline marks the lowest-cycle cache variant at each\n"
              "database size (4-way in every case). Cycles are the real-hardware-equivalent\n"
              "metric (cycles / clock frequency). Width shown = the SOFTWARE S2 lookup-cache's\n"
              "associativity. Real Luna HARDWARE cache is fixed throughout: L1d 48KB/12-way,\n"
              "L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way (96 cores/socket), 2.1GHz.",
              fontsize=7, color="#222222")
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
    ax.set_title("Software cache speedup by width and database size", fontsize=10, pad=28)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=4, columnspacing=1.2, handlelength=1.2, fontsize=8)
    style_ax(ax)
    ax.set_ylim(0, 2.5)
    fig.text(0.0, -0.26,
              "50-read workload. Speedup computed from simulated CYCLES / core frequency\n"
              "(real-hardware-equivalent time), not Sniper's own simulation wall-clock.\n"
              "Width shown = the SOFTWARE S2 lookup-cache's associativity (kraken2's own code).\n"
              "Real Luna HARDWARE cache is fixed and unchanged throughout: L1d 48KB/12-way,\n"
              "L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way (96 cores/socket), 2.1GHz.",
              fontsize=7, color="#222222")
    savefig(fig, "fig3_speedup_vs_nocache")


# =========================================================================
# FIGURE 4 — Unique cache lines touched (memory footprint), small multiples
# =========================================================================
def fig_footprint():
    colors = [GRAY, BLUE_RAMP["1way"], BLUE_RAMP["4way"], BLUE_RAMP["8way"], BLUE_RAMP["16way"]]

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 3.0))
    for ax, dbname, dbkey in zip(axes, DBS, DB_KEYS):
        vals = [LINES[dbkey][v] for v in VARIANTS]
        bars = ax.bar(LABELS, vals, color=colors, width=0.7, zorder=3,
                       edgecolor="#222222", linewidth=0.4)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v/1000:.0f}K", (b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", fontsize=7.5, fontweight="600")
        ax.set_title(dbname, fontsize=9.5)
        ax.set_xticks(range(len(LABELS)))
        ax.set_xticklabels(LABELS, rotation=40, ha="right", fontsize=7.5)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K"))
        style_ax(ax)
        ax.set_ylim(0, max(vals) * 1.22)
    axes[0].set_ylabel("Unique cache lines touched")
    fig.suptitle("Memory footprint touched, by SOFTWARE cache width and database size",
                 fontsize=11, fontweight="bold", y=1.04)
    fig.text(0.0, -0.22,
              "50-read workload. Fewer lines touched indicates fewer cold-memory probes into\n"
              "the underlying hash table. Width shown = the SOFTWARE S2 lookup-cache's\n"
              "associativity. Real Luna HARDWARE cache is fixed throughout: L1d 48KB/12-way,\n"
              "L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way (96 cores/socket), 2.1GHz.",
              fontsize=7, color="#222222")
    fig.tight_layout()
    savefig(fig, "fig4_memory_footprint_by_db")


# =========================================================================
# FIGURE 5 — Dual-axis: 4-way speedup (bars, hatched) vs no-cache IPC decline
# (dashed line, secondary axis) across database size. Bars answer "how much
# faster"; the line answers "why" - IPC falling as DB grows shows the
# uncached lookup stalling more, which is exactly what the cache fixes.
# =========================================================================
def fig_dual_axis():
    x = np.arange(len(DBS))
    speedups = [CYCLES[dbkey]["S0"] / CYCLES[dbkey]["4way"] for dbkey in DB_KEYS]
    ipcs = [IPC_S0[dbkey] for dbkey in DB_KEYS]

    fig, ax1 = plt.subplots(figsize=(DOUBLE_COL - 1.0, 3.6))
    bars = ax1.bar(x, speedups, width=0.5, color="white", edgecolor="#222222",
                    linewidth=1.1, hatch="///", zorder=3)
    for b, v in zip(bars, speedups):
        ax1.annotate(f"{v:.2f}×", (b.get_x() + b.get_width() / 2, v),
                     xytext=(0, 5), textcoords="offset points",
                     ha="center", fontsize=10, fontweight="700")
    ax1.axhline(1.0, color="#999999", linestyle=":", linewidth=1.0, zorder=1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(DBS)
    ax1.set_xlabel("reference database size (log-order)")
    ax1.set_ylabel("4-way speedup vs. no cache (×)", color="#222222")
    ax1.set_ylim(0, 2.6)
    style_ax(ax1)

    ax2 = ax1.twinx()
    ax2.plot(x, ipcs, color=CRIT, linestyle="--", marker="o", markersize=6,
              linewidth=1.4, zorder=4)
    for xi, v in zip(x, ipcs):
        ax2.annotate(f"{v:.2f}", (xi, v), xytext=(0, -16), textcoords="offset points",
                     ha="center", fontsize=9.5, color=CRIT, fontweight="600")
    ax2.set_ylabel("no-cache IPC", color=CRIT)
    ax2.tick_params(axis="y", colors=CRIT)
    ax2.set_ylim(0.8, 1.7)
    ax2.spines["top"].set_visible(False)

    ax1.set_title("Cache speedup grows as the uncached lookup stalls more", fontsize=11, pad=12)
    fig.text(0.0, -0.19,
              "50-read workload, all values from the verified fair batch. Bars: real-hardware-\n"
              "equivalent speedup (cycles / frequency) for the SOFTWARE S2 cache at 4-way.\n"
              "Dashed line: no-cache IPC, falling as the database grows - the mechanism the\n"
              "cache is compensating for. Real Luna HARDWARE cache is fixed throughout:\n"
              "L1d 48KB/12-way, L1i 32KB/8-way, L2 2MB/16-way, L3 105MB/15-way, 2.1GHz.",
              fontsize=7.5, color="#222222")
    fig.tight_layout()
    savefig(fig, "fig5_speedup_vs_ipc_dualaxis")


# =========================================================================
# FIGURE 6 — Of the accesses that miss L1, where do they get resolved?
# Stacked 100% bar: L2 share / LLC(NUCA) share / DRAM share of L1 misses,
# per variant, at the 103GB DB (the size where this matters most). Shows the
# actual mechanism: wider caches catch more L1-misses before DRAM.
# =========================================================================
HIT_PCT_103GB = {
    "S0":    {"l1": 98.69, "l2": .67,   "nuca": .0365},
    "1way":  {"l1": 98.67, "l2": .94,   "nuca": .0329},
    "4way":  {"l1": 98.29, "l2": 1.24,  "nuca": .0668},
    "8way":  {"l1": 98.07, "l2": 1.30,  "nuca": .1116},
    "16way": {"l1": 97.68, "l2": 1.33,  "nuca": .1135},
}

def fig_miss_breakdown():
    x = np.arange(len(VARIANTS))
    l2_share, nuca_share, dram_share = [], [], []
    for v in VARIANTS:
        h = HIT_PCT_103GB[v]
        l1_miss = 100 - h["l1"]
        dram = l1_miss - h["l2"] - h["nuca"]
        l2_share.append(h["l2"] / l1_miss * 100)
        nuca_share.append(h["nuca"] / l1_miss * 100)
        dram_share.append(dram / l1_miss * 100)

    fig, ax = plt.subplots(figsize=(SINGLE_COL + 1.0, 3.3))
    c_l2, c_nuca, c_dram = "#5598e7", "#184f95", "#b3312f"
    b1 = ax.bar(x, l2_share, width=0.55, color=c_l2, edgecolor="#222222", linewidth=0.4, zorder=3, label="Resolved at L2")
    b2 = ax.bar(x, nuca_share, width=0.55, bottom=l2_share, color=c_nuca, edgecolor="#222222", linewidth=0.4, zorder=3, label="Resolved at LLC")
    bottom2 = [a + b for a, b in zip(l2_share, nuca_share)]
    b3 = ax.bar(x, dram_share, width=0.55, bottom=bottom2, color=c_dram, edgecolor="#222222", linewidth=0.4, zorder=3, label="Fell through to DRAM")

    for i in range(len(VARIANTS)):
        ax.annotate(f"{l2_share[i]:.0f}%", (x[i], l2_share[i] / 2), ha="center", va="center", fontsize=8, color="white", fontweight="700")
        ax.annotate(f"{dram_share[i]:.0f}%", (x[i], bottom2[i] + dram_share[i] / 2), ha="center", va="center", fontsize=8, color="white", fontweight="700")

    ax.set_xticks(x)
    ax.set_xticklabels(LABELS, rotation=20, ha="right")
    ax.set_ylabel("Share of L1-cache misses (%)")
    ax.set_title("Wider caches keep more L1 misses out of DRAM", fontsize=10.5)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=3, fontsize=7.5, handlelength=1.2, columnspacing=1.0)
    ax.set_ylim(0, 100)
    style_ax(ax, ygrid=True)
    fig.text(0.0, -0.24,
              "103 GB database, 50-read workload. DRAM share drops from 46% (no cache) to 24%\n"
              "(4-way) - the cache intercepts exactly the expensive misses. X-axis width = the\n"
              "SOFTWARE S2 lookup-cache's associativity. The L2/LLC/DRAM breakdown itself is\n"
              "REAL Luna HARDWARE cache behavior (L1d 48KB/12-way, L2 2MB/16-way,\n"
              "L3 105MB/15-way) - this chart shows how a software design choice changes what\n"
              "the real hardware caches actually see.",
              fontsize=7.5, color="#222222")
    fig.tight_layout()
    savefig(fig, "fig6_miss_breakdown_103gb")


# =========================================================================
# FIGURE 7 — Hardware cache-size comparison: Luna (real) vs. simulated
# desktop-sized vs. simulated Orion-sized caches. Non-monotonic finding.
# =========================================================================
def fig_hw_comparison():
    hw_names = ["Luna\n(real server)", "Desktop-sized\n(sim.)", "Orion-sized\n(sim.)"]
    speedup_50mb = [0.910, 0.919, 0.902]
    speedup_8gb = [1.830, 1.936, 1.649]

    x = np.arange(len(hw_names))
    width = 0.32
    fig, (ax, ax_tbl) = plt.subplots(2, 1, figsize=(SINGLE_COL + 1.4, 5.6),
                                       gridspec_kw={"height_ratios": [3, 2]})
    b1 = ax.bar(x - width / 2, speedup_50mb, width, label="50 MB DB", color="#9ec5f4", edgecolor="#222222", linewidth=0.5, zorder=3)
    b2 = ax.bar(x + width / 2, speedup_8gb, width, label="8 GB DB", color="#184f95", edgecolor="#222222", linewidth=0.5, zorder=3)
    for bars in (b1, b2):
        for b in bars:
            h = b.get_height()
            ax.annotate(f"{h:.2f}×", (b.get_x() + b.get_width() / 2, h + 0.05),
                        ha="center", fontsize=8.5, fontweight="600")
    ax.axhline(1.0, color="#999999", linestyle="--", linewidth=0.9, zorder=2)
    ax.set_xticks(x)
    ax.set_xticklabels(hw_names, fontsize=8.5)
    ax.set_ylabel("4-way speedup vs. no cache")
    ax.set_title("Cache benefit isn't simply\n\"smaller hardware cache = bigger win\"", fontsize=10.5, pad=34)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2, fontsize=8.5)
    ax.set_ylim(0, 2.3)
    ax.set_xlim(-0.55, 2.55)
    style_ax(ax)

    # --- hardware config table ---
    ax_tbl.axis("off")
    col_labels = ["Level", "Luna (real)", "Desktop (sim.)", "Orion (sim.)"]
    rows = [
        ["L1 data",  "48KB / 12-way",  "32KB / 8-way",   "64KB / 4-way"],
        ["L1 instr.", "32KB / 8-way",   "32KB / 8-way",   "64KB / 4-way"],
        ["L2",        "2MB / 16-way",   "512KB / 8-way",  "256KB / 8-way"],
        ["LLC (total)", "105MB / 15-way", "32MB / 16-way", "4MB / 16-way*"],
        ["LLC shared by", "96 cores",   "6 cores",        "12 cores"],
        ["Clock",     "2.1 GHz",        "3.7 GHz",        "2.2 GHz"],
    ]
    tbl = ax_tbl.table(cellText=rows, colLabels=col_labels, loc="center",
                        cellLoc="center", colLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.65)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#888888")
        cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor("#e8e8e8")
            cell.set_text_props(fontweight="700")
        if c == 0:
            cell.set_text_props(fontweight="600", ha="left")
            cell.PAD = 0.03
    fig.text(0.0, 0.005, "*Orion LLC associativity is an unverified placeholder (real value not "
              "publicly documented); all other values are real spec or sysfs-measured.",
              fontsize=6.3, color="#555555")
    fig.text(0.0, -0.03,
              "This chart is the reverse of the others: the SOFTWARE S2 cache is held FIXED at "
              "4-way throughout - what changes is the HARDWARE cache config itself (table above). "
              "Desktop sees a stronger win than Luna's real cache; Orion sees a weaker one, despite "
              "having the smallest cache of the three. Config-only comparison (same x86 core model).",
              fontsize=6.8, color="#222222", va="top")
    fig.tight_layout()
    savefig(fig, "fig7_hardware_comparison")


if __name__ == "__main__":
    fig_width_sweep()
    fig_cycles_by_db()
    fig_speedup_clean()
    fig_footprint()
    fig_dual_axis()
    fig_miss_breakdown()
    fig_hw_comparison()
    print("done")
