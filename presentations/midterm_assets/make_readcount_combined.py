import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Same real data as the 4-panel grid (no --memory-mapping), combined onto one
# chart. A single red line style threads through each group's 4 bars, one
# point per bar (its own real LLC cache-miss rate, not an average) - drawn as
# 4 separate short segments (one per read-count group) rather than one line
# spanning the whole chart, so it doesn't dive across empty space between
# groups and cut through unrelated bars.
read_labels = ["10", "1,000", "104,918", "1,872,777"]
db_labels = ["50 MB", "8 GB", "16 GB", "103 GB"]
walltime = {
    "50 MB":  [0.084, 0.298, 1.244, 13.881],
    "8 GB":   [4.396, 4.337, 5.313, 18.535],
    "16 GB":  [9.086, 7.956, 8.937, 22.304],
    "103 GB": [51.347, 51.187, 53.950, 79.463],
}
llc = {
    "50 MB":  [70.77, 19.10, 11.84, 11.47],
    "8 GB":   [92.19, 92.85, 79.16, 56.84],
    "16 GB":  [90.48, 94.47, 82.21, 58.02],
    "103 GB": [97.70, 97.49, 84.09, 71.93],
}
RED_LINE = "#c81e2e"

DB_COLOR = {
    "50 MB":  "#d92b3a",  # red
    "8 GB":   "#2f6fed",  # blue
    "16 GB":  "#1f9e6d",  # green
    "103 GB": "#e8c520",  # yellow
}
# text labels use a slightly darker tone per color so they stay readable on
# white - pure yellow text especially would be nearly invisible
LABEL_COLOR = {
    "50 MB":  "#d92b3a",
    "8 GB":   "#2f6fed",
    "16 GB":  "#1f9e6d",
    "103 GB": "#9c8000",  # darkened yellow, readable
}

INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#9aa1ac"
LINE = "#e6e8ed"

Y_LO, Y_HI = 0.03, 250   # left axis (log) bounds
R_LO, R_HI = 0, 108      # right axis (linear) bounds


def frac_log(v):
    return (np.log10(v) - np.log10(Y_LO)) / (np.log10(Y_HI) - np.log10(Y_LO))


fig, ax1 = plt.subplots(figsize=(11.5, 7.0), dpi=270)
fig.patch.set_facecolor("white")
ax1.set_facecolor("white")

x = np.arange(4)
bar_w = 0.19
ax1.set_yscale("log")
ax1.grid(axis="y", which="major", color=LINE, linewidth=0.8, zorder=0)

# bar x-offset per db, per group - built once so the line-plotting section
# can reuse the exact same coordinates the bars were drawn at
offsets = {db: x + (di - 1.5) * bar_w for di, db in enumerate(db_labels)}

for db in db_labels:
    vals = walltime[db]
    ax1.bar(offsets[db], vals, width=bar_w * 0.92, color=DB_COLOR[db], zorder=3,
              edgecolor=INK, linewidth=1.1, label=db)
    for xi, v in zip(offsets[db], vals):
        lbl = f"{v:.2f}" if v < 10 else f"{v:.1f}"
        ax1.text(xi, v * 1.18, lbl, ha="center", fontsize=8, fontweight="bold",
                  color=LABEL_COLOR[db], rotation=90 if v < 1 else 0, zorder=5)

ax1.set_ylim(Y_LO, Y_HI)
ax1.set_ylabel("wall time (s, log scale)", fontsize=12.5, color=INK, fontweight="bold")
ax1.tick_params(axis="y", labelsize=10.5, colors=INK)
ax1.set_xticks(x)
ax1.set_xticklabels(read_labels, fontsize=12, fontweight="bold", color=INK)
ax1.set_xlabel("reads classified (log-order)", fontsize=12, color=INK, fontweight="bold")
for s in ["top", "right"]:
    ax1.spines[s].set_visible(False)
ax1.spines["left"].set_color(INK)
ax1.spines["bottom"].set_color(INK)

ax2 = ax1.twinx()
ax2.set_ylim(R_LO, R_HI)

for i in range(4):  # one segment per read-count group, not connected to neighbours
    xs = [offsets[db][i] for db in db_labels]
    ys = [llc[db][i] for db in db_labels]
    ax2.plot(xs, ys, color=RED_LINE, linewidth=2.2, linestyle="--", marker="o",
              markersize=6.5, markerfacecolor="white", markeredgecolor=RED_LINE,
              markeredgewidth=1.8, zorder=6)

    # this group's 4 wall-time label positions, in shared "fraction of panel
    # height" units, so each cache-miss label can be checked against all of
    # them (not just its own bar) and pushed to whichever side - above or
    # below its marker - sits clearest of every label in the group
    bar_fracs = [frac_log(walltime[db][i] * 1.18) for db in db_labels]
    for db, xi, v in zip(db_labels, xs, ys):
        line_frac = v / R_HI
        # last group's 103GB point is the line's right end and the dashed
        # segment arrives from the lower left, grazing a centered label -
        # put that one label to the right of its marker instead
        if i == 3 and db == "103 GB":
            ax2.text(xi + 0.105, v, f"{v:.0f}%", ha="left", va="center",
                      fontsize=10, fontweight="bold", color=INK, zorder=7)
            continue
        # the 8GB point in the last group has a steep incoming segment from
        # the 50MB point right below it (11% -> 57%) - the bar-label dodge
        # picks the side away from bar text, but that side runs straight
        # into that incoming line, so force it above the marker instead
        if i == 3 and db == "8 GB":
            dy, va = 0.05, "bottom"
        else:
            best = max(
                ((min(abs((line_frac + dy) - bf) for bf in bar_fracs), dy, va)
                 for dy, va in [(0.05, "bottom"), (-0.05, "top")]),
                key=lambda t: t[0],
            )
            _, dy, va = best
        ax2.text(xi, (line_frac + dy) * R_HI, f"{v:.0f}%", ha="center", va=va,
                  fontsize=10, fontweight="bold", color=INK, zorder=7)

ax2.set_ylabel("LLC cache-miss rate (%), per bar", fontsize=12.5, color=RED_LINE, fontweight="bold")
ax2.tick_params(axis="y", labelsize=10.5, colors=RED_LINE)
for s in ["top", "left"]:
    ax2.spines[s].set_visible(False)
ax2.spines["right"].set_color(RED_LINE)

bar_handles = [plt.Rectangle((0, 0), 1, 1, facecolor=DB_COLOR[db], edgecolor=INK, linewidth=1.1)
               for db in db_labels]
line_handle = [plt.Line2D([0], [0], color=RED_LINE, linestyle="--", marker="o",
                            markerfacecolor="white", markeredgecolor=RED_LINE, linewidth=2.2,
                            markersize=6.5)]
ax1.legend(bar_handles + line_handle, db_labels + ["LLC cache-miss (%)"],
            loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=5, fontsize=11,
            frameon=False, handlelength=1.6, columnspacing=1.5)

fig.suptitle("Kraken2 wall time & LLC cache-miss rate, all 4 database sizes combined",
             fontsize=15.5, fontweight="bold", color=INK, y=1.03)
fig.text(0.5, 0.005,
          "no --memory-mapping · 32T · Luna, numactl node0 · kraken2-fresh-bin-s0 (v2.17.1) · measured 2026-09-23",
          ha="center", va="bottom", fontsize=9, color=INK_FAINT, style="italic")

fig.tight_layout(pad=1.1, rect=[0, 0.02, 1, 0.92])
fig.savefig("k2_readcount_combined.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_readcount_combined.png")
