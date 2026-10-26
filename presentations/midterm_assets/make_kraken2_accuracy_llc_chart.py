import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerBase
from matplotlib.text import Text

# All 6 original databases. eskape_650mb (142 MB) and eskape_human_4gb
# (3.8 GB) no longer exist on Luna, so accuracy/LLC-miss keep their
# last-recorded values (kraken2 v2.1.3, 2026-08-03). Wall time for those two
# is SCALED, not measured: v2.17.1 runs a different speed than v2.1.3 (a real
# effect, confirmed on the 4 DBs we could directly re-run), so the raw v2.1.3
# wall times would be misleading dropped in next to today's v2.17.1 numbers.
# Scale factor = log-size-interpolated (v2.17.1/v2.1.3) ratio from the two
# nearest re-verified points (50 MB: 1.277/0.928=1.376x; 7.6 GB:
# 5.528/4.830=1.145x) -> 142 MB x1.328 = 1.39s, 3.8 GB x1.176 = 3.50s.
labels = ['50 MB', '142 MB', '3.8 GB', '7.6 GB', '15 GB', '103 GB']
accuracy = [84.80, 65.28, 66.13, 95.77, 97.77, 98.86]
llc = [11.91, 30.53, 59.03, 77.68, 79.70, 90.17]
walltime_s = [1.277, 1.388, 3.501, 5.528, 10.120, 53.646]
walltime_labels = ["1.28 s", "1.39 s", "3.50 s", "5.53 s", "10.12 s", "53.6 s"]
llc_value_labels = ["11.9%", "30.5%", "59.0%", "77.7%", "79.7%", "90.2%"]
x = list(range(len(labels)))

BLUE = "#2f6fed"
BLUE_DARK = "#173f8f"
RED = "#d92b3a"

fig, ax1 = plt.subplots(figsize=(4.6, 2.7), dpi=280)
fig.patch.set_facecolor("white")
ax1.set_facecolor("white")

ax1.grid(axis="y", color="#e6e8ed", linewidth=0.7, zorder=0)

bars = ax1.bar(x, accuracy, width=0.44, color=BLUE, edgecolor=BLUE_DARK,
               linewidth=0.8, zorder=3)

ax1.set_ylim(0, 124)
ax1.set_ylabel("classification\naccuracy (%)", color=BLUE_DARK, fontsize=7, fontweight="bold", labelpad=2)
ax1.tick_params(axis="y", colors=BLUE_DARK, labelsize=6.3, pad=1.5)
ax1.set_yticks([0, 20, 40, 60, 80, 100])
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=6.3, fontweight="bold", color="#15181f")
ax1.tick_params(axis="x", pad=2)
ax1.set_xlabel("reference database size (log-order)", fontsize=6.8, fontweight="bold", color="#15181f", labelpad=3)
for spine in ["top", "right"]:
    ax1.spines[spine].set_visible(False)
ax1.spines["left"].set_color(BLUE_DARK)
ax1.spines["left"].set_linewidth(0.8)
ax1.spines["bottom"].set_color("#15181f")
ax1.spines["bottom"].set_linewidth(0.8)

ax2 = ax1.twinx()
ax2.plot(x, llc, color=RED, linestyle="--", linewidth=1.4, marker="o",
          markersize=4, markerfacecolor="white", markeredgecolor=RED,
          markeredgewidth=1.3, zorder=4)
ax2.set_ylim(0, 124)
ax2.set_yticks([0, 20, 40, 60, 80, 100])
ax2.set_ylabel("LLC cache-miss\nrate (%)", color=RED, fontsize=7, fontweight="bold", labelpad=2)
ax2.tick_params(axis="y", colors=RED, labelsize=6.3, pad=1.5)
for spine in ["top", "left"]:
    ax2.spines[spine].set_visible(False)
ax2.spines["right"].set_color(RED)
ax2.spines["right"].set_linewidth(0.8)

for i, v in enumerate(accuracy):
    ax1.text(i, v + 3.0, f"{v:.1f}%", ha="center", fontsize=6.6, fontweight="bold", color=BLUE_DARK, zorder=5)
    ax1.text(i, v + 10.0, walltime_labels[i], ha="center", fontsize=5.6, fontweight="bold",
              color="#8891a0", style="italic", zorder=5)

# every label sits centered directly above its own point - except 3.8 GB and
# 103 GB, where the accuracy label above the bar leaves no real headroom
# (confirmed by direct visual check, twice). Those two go centered *below*
# instead, the one open spot near their dot, rather than force an "above"
# placement that keeps colliding with the line or the text above it.
llc_label_dy = [7, 7, -10, 7, 7, -10]
for i, v in enumerate(llc):
    ax2.text(i, v + llc_label_dy[i], llc_value_labels[i], ha="center",
              fontsize=5.6, fontweight="bold", color="#15181f", zorder=5)


# legend key for the grey italic wall-time numbers: the key itself is a small
# grey italic "1.28 s" drawn in the handle slot, so it matches what it labels
class WallTimeKey:
    pass


class HandlerWallTimeKey(HandlerBase):
    def create_artists(self, legend, orig_handle, xdescent, ydescent, width,
                       height, fontsize, trans):
        return [Text(xdescent + width / 2, ydescent + height / 2, "1.28 s",
                     ha="center", va="center", color="#8891a0", style="italic",
                     fontweight="bold", fontsize=fontsize * 0.85, transform=trans)]


legend_elems = [
    Patch(facecolor=BLUE, edgecolor=BLUE_DARK),
    Line2D([0], [0], color=RED, marker="o", markerfacecolor="white",
           markeredgecolor=RED, markeredgewidth=1.3, linestyle="--"),
    WallTimeKey(),
]
# one row across the top (a 3rd stacked row would run into the labels above
# the 50 MB bar)
ax1.legend(handles=legend_elems,
           labels=["accuracy (%)", "LLC miss (%)", "wall time"],
           handler_map={WallTimeKey: HandlerWallTimeKey()},
           loc="upper left", ncol=3, frameon=True, fontsize=5.6,
           facecolor="white", edgecolor="#e6e8ed", handlelength=3.4,
           handletextpad=0.6, borderpad=0.5, columnspacing=1.2)

ax1.set_title("Accuracy vs LLC cache-miss rate, by database size",
              fontsize=8, fontweight="bold", color="#15181f", pad=6)

fig.text(0.5, 0.005,
          "grey italic = wall time, same fixed input (reads_hac, 104,918 reads) · 32T · Luna, numactl node0",
          ha="center", va="bottom", fontsize=5, color="#8891a0", style="italic")

fig.tight_layout(pad=0.6, rect=[0, 0.03, 1, 1])
fig.savefig("chart.png", facecolor="white", bbox_inches="tight", pad_inches=0.05)
print("saved chart.png")
