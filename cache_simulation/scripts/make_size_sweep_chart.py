"""
Figure for the SOFTWARE CACHE SIZE sweep (RESEARCH_PROMPT_optimal_cache_size.md).

IMPORTANT DISTINCTION (this project has repeatedly had to correct chart captions
for exactly this confusion - don't repeat it): this chart is about SOFTWARE
CACHE CAPACITY, i.e. the number of entries (sets) the S2 lookup cache is sized
to hold, at a FIXED associativity (4-way) throughout. It is NOT the hardware
LLC associativity sweep (fig12/fig13) and NOT the software cache WIDTH
(associativity) sweep (fig1/fig2/fig9/fig10/fig11). Those varied "how many ways"
a cache line's set is searched; this varies "how many sets" the whole software
cache has, i.e. its total capacity, holding 4-way fixed.

Data source (ground truth, read directly - not transcribed by hand from a
summary):
  cache_simulation/measurements/size_sweep_50mb_2026-09-15.csv
  cache_simulation/measurements/size_sweep_8gb_peer_2026-09-15.csv   (columns: db,size,... - normalized below)
  cache_simulation/measurements/size_sweep_103gb_2026-09-15.csv

Metric discipline: cycles_M only, never wallclock_s/elapsed_s (see
command_log.md step 60 - wallclock/elapsed track simulator run time, not
real-hardware-equivalent execution time; cycles/frequency is the correct
metric).

Finding this chart exists to show: cycles are flat across nearly every size
tested, with a sharp, isolated spike at exactly 65536 sets on ALL THREE DBs
(50MB, 8GB, 103GB) - independent of database size - that fully reverts by
262144. Every other size sits within ~1% of its own DB's median cycle count.
"""

import csv
import os

import matplotlib.pyplot as plt
import numpy as np

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
MEAS_DIR = os.path.join(os.path.dirname(__file__), "..", "measurements")
os.makedirs(OUT_DIR, exist_ok=True)

# ---- publication style (matches make_hw_assoc_full_table.py / make_slide_charts.py) ----
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 8.5,
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

DOUBLE_COL = 7.2
LINE_COLOR = "#2a78d6"
SPIKE_COLOR = "#b3312f"
S0_COLOR = "#0a7d0a"

SIZES = [2048, 4096, 16384, 65536, 262144, 1048576]
SPIKE_SIZE = 65536

FILES = {
    "50MB": ("size_sweep_50mb_2026-09-15.csv", "50mb"),
    "8GB":  ("size_sweep_8gb_peer_2026-09-15.csv", "8gb"),
    "103GB": ("size_sweep_103gb_2026-09-15.csv", "103gb"),
}

# True S0 (no software cache at all), 50MB DB, 10 reads, matched exactly to the
# size sweep's own config (command_log.md, Iteration 2 correction): 14.1M cycles.
TRUE_S0_50MB = 14.1


def load(fname, db_key):
    path = os.path.join(MEAS_DIR, fname)
    rows = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # normalize column order: size_sweep_8gb_peer has db,size,... instead of size,db,...
            size = int(r["size"])
            db = r["db"]
            assert db == db_key, f"unexpected db {db} in {fname}"
            rows[size] = float(r["cycles_M"])
    return [rows[s] for s in SIZES]


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


def fig_size_sweep():
    data = {label: load(fname, db_key) for label, (fname, db_key) in FILES.items()}

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL, 4.6), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.40, wspace=0.32)

    spike_idx = SIZES.index(SPIKE_SIZE)

    for ax, label in zip(axes, FILES.keys()):
        vals = data[label]
        median = float(np.median(vals))
        ax.plot(SIZES, vals, marker="o", markersize=5, color=LINE_COLOR,
                 linewidth=1.4, zorder=3)
        # highlight the spike point distinctly
        spike_val = vals[spike_idx]
        pct = (spike_val - median) / median * 100
        ax.scatter([SIZES[spike_idx]], [spike_val], s=90, facecolor="none",
                    edgecolor=SPIKE_COLOR, linewidth=2.0, zorder=4)
        ax.annotate(f"+{pct:.1f}%", (SIZES[spike_idx], spike_val),
                     textcoords="offset points", xytext=(6, 8),
                     fontsize=8, color=SPIKE_COLOR, fontweight="bold")
        if label == "50MB":
            ax.axhline(TRUE_S0_50MB, color=S0_COLOR, linewidth=1.0,
                        linestyle="--", zorder=2)
            ax.text(SIZES[0], TRUE_S0_50MB, "true S0 (no cache)\n14.1M",
                     fontsize=6.5, color=S0_COLOR, va="top", ha="left")

        ax.set_xscale("log", base=2)
        ax.set_xticks(SIZES)
        ax.set_xticklabels([f"{s:,}" for s in SIZES], rotation=40, ha="right",
                             fontsize=7.2)
        ax.set_title(label, fontsize=10)
        # zoom y-range around the median so the spike reads clearly but the
        # flat region isn't crushed
        yrange = max(median * 0.06, (max(vals) - median) * 1.6)
        ax.set_ylim(median - yrange * 0.55, median + yrange)
        style_ax(ax)

    axes[0].set_ylabel("Simulated cycles (M)")
    fig.text(0.525, 0.245,
              "Software S2 cache capacity (entries/sets), FIXED at 4-way associativity - log-x axis",
              ha="center", fontsize=8.5)
    fig.suptitle(
        "Software cache SIZE sweep: flat baseline, isolated spike at 65,536 sets,\n"
        "full revert by 262,144 - holds across all three DB sizes",
        fontsize=11, y=0.965)
    fig.text(
        0.02, 0.155,
        "SOFTWARE CACHE CAPACITY (set count), not associativity - fixed at 4-way throughout. This is a\n"
        "different axis from the hardware LLC associativity null result (fig12/fig13) and from the software\n"
        "cache WIDTH sweep (fig1/fig2/fig9-11); do not conflate them. Metric is Sniper cycles_M, never\n"
        "wallclock/elapsed (see command_log.md step 60). Every size except 65,536 sits within ~1% of its own\n"
        "DB's median; 65,536 sets spikes +6.3% (50MB), +2.5% (8GB), +6.0% (103GB), then fully reverts by\n"
        "262,144 - a fixed absolute set count, not a DB-size-scaled effect. On 50MB, every size tested\n"
        "(including the anomaly) still exceeds true no-cache S0 (14.1M cycles, green dashed line, left panel).",
        fontsize=6.8, color="#222222", va="top")

    savefig(fig, "fig14_size_sweep_all_db")


if __name__ == "__main__":
    fig_size_sweep()
