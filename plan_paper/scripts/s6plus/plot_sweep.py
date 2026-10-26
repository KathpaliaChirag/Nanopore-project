#!/usr/bin/env python3
"""
plot_sweep.py - the 103GB thread sweep (stock S0 vs S10), split into load, classify and exit time.

why three panels: the total wall time mixes three costs that respond to threads differently.
the loader never sees --threads (the table is built at classify.cc:260, omp_set_num_threads runs at
classify.cc:273), so load is flat for both binaries; only classify can scale; exit is the kernel
freeing 111GB of 4KB pages and does not scale either.

input is the tsv from split_sweep.sh:
  bash split_sweep.sh sweep103 > sweep103_split.tsv
run on luna (matplotlib is in the snn venv):
  ~/snn/venv/bin/python3 plot_sweep.py sweep103_split.tsv sweep103_split.png
"""

import sys
import matplotlib.pyplot as plt

tsv = sys.argv[1] if len(sys.argv) > 1 else "sweep103_split.tsv"
out = sys.argv[2] if len(sys.argv) > 2 else "sweep103_split.png"

NAMES = {"kraken2-fresh-bin-s0": "stock (S0)", "kraken2-fresh-bin-s10": "S10 (S8+S9+S10)"}
COLORS = {"kraken2-fresh-bin-s0": "#2a78d6", "kraken2-fresh-bin-s10": "#eb6834"}

rows = {}
with open(tsv) as f:
    next(f)
    for line in f:
        p = line.rstrip("\n").split("\t")
        if len(p) < 7:  # missing_err / incomplete rows are skipped, not plotted as zeros
            continue
        t, b = int(p[0]), p[1]
        rows.setdefault(b, []).append((t, float(p[2]), float(p[3]), float(p[4]), float(p[5])))

fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), dpi=150)
ax_wall, ax_cls, ax_fix = axes

for b, r in rows.items():
    r.sort()
    th = [x[0] for x in r]
    c, n = COLORS.get(b, "#52514e"), NAMES.get(b, b)
    ax_wall.plot(th, [x[1] for x in r], "-o", color=c, lw=2, ms=5, label=n)
    ax_cls.plot(th, [x[3] for x in r], "-o", color=c, lw=2, ms=5, label=n)
    # ideal scaling from this binary's own 8-thread point: 1 to 4 threads scaled superlinearly in the
    # first sweep (one rep, cause unknown), so a low reference would make everything look inefficient
    ref = [x for x in r if x[0] == 8] or r[:1]
    t0, c0 = ref[0][0], ref[0][3]
    ax_cls.plot(th, [c0 * t0 / t for t in th], "--", color=c, lw=1, alpha=0.6)
    ax_fix.plot(th, [x[2] for x in r], "-o", color=c, lw=2, ms=5, label=n + " load")
    ax_fix.plot(th, [x[4] for x in r], ":s", color=c, lw=2, ms=5, label=n + " exit")

for ax in axes:
    ax.set_xscale("log", base=2)
    ax.set_xlabel("--threads (log scale)")
    ax.axvline(96, color="#c3c2b7", lw=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linewidth=0.5, color="#e1e0d9")
    ax.set_axisbelow(True)
ax_wall.set_yscale("log")
ax_cls.set_yscale("log")
ax_wall.set_ylabel("seconds (log scale)")
ax_cls.set_ylabel("seconds (log scale)")
ax_fix.set_ylabel("seconds")
ax_fix.set_ylim(bottom=0)
ax_wall.set_title("total wall")
ax_cls.set_title("classify only (dashed = ideal from 8 threads)")
ax_fix.set_title("load (solid) and exit teardown (dotted)")
ax_cls.text(96, ax_cls.get_ylim()[1], " 96 cores,\n SMT beyond", va="top", fontsize=8, color="#898781")
ax_wall.legend(frameon=False, fontsize=9)
ax_fix.legend(frameon=False, fontsize=8, ncol=2)
fig.suptitle("kraken2 103GB, 1,872,777 reads, luna, one run per point, warm page cache")
fig.tight_layout()
fig.savefig(out)
print(f"wrote {out}")
