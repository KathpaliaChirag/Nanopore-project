import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Data exactly as given (pod5_2.fastq, 151,591 reads, -T 0, stock kraken2 2.17.1)
species = ["P. aeruginosa", "E. coli", "K. pneumoniae", "E. cloacae", "E. faecium", "S. aureus"]
widths = ["32-bit", "24-bit", "20-bit", "16-bit"]
data = {
    "P. aeruginosa": [79402, 79408, 79615, 81151],
    "E. coli":        [33101, 33101, 33231, 34270],
    "K. pneumoniae":  [14427, 14430, 14695, 17425],
    "E. cloacae":     [628, 628, 780, 2441],
    "E. faecium":     [5, 10, 93, 802],
    "S. aureus":      [3, 3, 66, 552],
}

COLORS = ["#2f5fa8", "#8bb4e0", "#f2c896", "#d9722e"]
INK = "#15181f"
INK_SOFT = "#5c6572"
INK_FAINT = "#9aa1ac"
LINE = "#e6e8ed"

fig, ax = plt.subplots(figsize=(7.6, 10.8), dpi=280)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

n_species = len(species)
n_widths = len(widths)
bar_h = 0.16
group_gap = 1.0

y_base = np.arange(n_species)[::-1] * group_gap  # top-to-bottom order
ax.set_xscale("log")
ax.set_xlim(1, 200000)

for wi, (w, color) in enumerate(zip(widths, COLORS)):
    offsets = y_base + (n_widths / 2 - wi - 0.5) * bar_h
    values = [data[sp][wi] for sp in species]
    ax.barh(offsets, values, height=bar_h * 0.72, color=color, edgecolor="none",
             zorder=3, label=w)
    for yi, v in zip(offsets, values):
        bold = (wi == 3)
        ax.text(v * 1.18, yi, f"{v:,}", va="center", fontsize=9.8,
                 fontweight="bold" if bold else "normal",
                 color=INK, zorder=4)

ax.set_yticks(y_base)
ax.set_yticklabels(species, fontsize=13.5, fontstyle="italic", color=INK, fontweight="bold")
ax.tick_params(axis="y", length=0)
ax.set_xlabel("reads assigned (log scale)", fontsize=11.5, color=INK, fontweight="bold")
ax.tick_params(axis="x", labelsize=10.5, colors=INK)
ax.xaxis.set_major_formatter(plt.FuncFormatter(
    lambda v, _: {1: "1", 10: "10", 100: "100", 1000: "1k", 10000: "10k", 100000: "100k"}.get(int(v), "")
))

for s in ["top", "right", "left"]:
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(INK)
ax.grid(axis="x", which="major", color=LINE, linewidth=0.8, zorder=0)

for yi in y_base:
    ax.axhline(yi + group_gap / 2, color=LINE, linewidth=0.7, zorder=0)

leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.10), ncol=4, fontsize=11,
                  frameon=False, handlelength=1.4, columnspacing=1.4)
for text in leg.get_texts():
    text.set_color(INK)
    text.set_fontweight("bold")

ax.set_ylim(-group_gap * 0.6, y_base[0] + group_gap * 0.6)

fig.tight_layout(pad=1.0)
fig.savefig("k2_species_chart.png", facecolor="white", bbox_inches="tight", pad_inches=0.2)
plt.close(fig)
print("saved k2_species_chart.png")
